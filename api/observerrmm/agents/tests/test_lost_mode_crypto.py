"""Feature 030 · Fase 3 · T020 — cifrado en reposo de la evidencia (ADR-025 punto 5).

Lo que se prueba acá es lo que NO se ve desde la consola: que el archivo esté
ilegible EN EL DISCO. Un test que sólo comprobara que la descarga devuelve el
PNG pasaría igual con el cifrado apagado — sería el "ok falso" clásico de esta
feature. Por eso cada caso mira los bytes del fichero, no la respuesta HTTP.

También se prueba lo que pasa cuando la llave NO está: un ambiente sin llave
tiene que seguir guardando y sirviendo evidencia (un caso abierto no se puede
quedar sin capturas por un problema de despliegue), y una evidencia cifrada sin
su llave tiene que dar un error explícito, nunca una imagen rota.
"""

import os
import tempfile

from cryptography.fernet import Fernet
from django.core.files.base import ContentFile
from django.test import override_settings
from model_bakery import baker

from agents.lostmode_crypto import (
    EVIDENCE_MAGIC,
    EvidenceKeyMissing,
    decrypt_bytes,
    encrypt_bytes,
    encryption_enabled,
)
from agents.models import LostModeEvidence, LostModeState
from observerrmm.constants import LostModeEvidenceKind
from observerrmm.test import ObserverTestCase

base_url = "/agents"

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

LLAVE = Fernet.generate_key().decode()
OTRA_LLAVE = Fernet.generate_key().decode()


class TestCifradoEnReposo(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()

        self.agent = baker.make_recipe("agents.agent")
        LostModeState.objects.create(
            agent=self.agent, active=True, reason="robo, ticket #4821"
        )
        self.tmp = tempfile.mkdtemp(prefix="lostmode-crypto-")
        self.url = f"{base_url}/{self.agent.agent_id}/lostmode/evidence/"

    def guardar_captura(self, contenido=PNG_1x1):
        pieza = LostModeEvidence(
            agent=self.agent, cycle=1, kind=LostModeEvidenceKind.SCREEN
        )
        pieza.asset.save("pantalla-000001.png", ContentFile(contenido), save=False)
        pieza.save()
        return pieza

    def bytes_en_disco(self, pieza):
        with open(os.path.join(self.tmp, pieza.asset.name), "rb") as f:
            return f.read()

    # ------------------------------------------------- el archivo en disco

    def test_el_archivo_en_disco_queda_cifrado(self):
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=LLAVE
        ):
            pieza = self.guardar_captura()
            crudo = self.bytes_en_disco(pieza)

        self.assertTrue(crudo.startswith(EVIDENCE_MAGIC))
        # Lo que importa: el PNG no está ahí. Ni entero ni su firma.
        self.assertNotIn(PNG_1x1, crudo)
        self.assertNotIn(b"\x89PNG", crudo)

    def test_lo_guardado_cifrado_se_lee_igual(self):
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=LLAVE
        ):
            pieza = self.guardar_captura()
            with pieza.asset.open("rb") as f:
                self.assertEqual(f.read(), PNG_1x1)

    def test_sin_llave_se_guarda_en_claro_y_se_avisa(self):
        """Un ambiente sin llave NO se queda sin evidencia: la guarda sin cifrar.

        Negarse a guardar dejaría un caso ABIERTO sin las capturas de ese ciclo,
        que es irrecuperable. Lo que sí tiene que pasar es que el estado se
        declare: `encryption_enabled()` en False y el listado del caso diciéndolo.
        """
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=""
        ):
            self.assertFalse(encryption_enabled())
            pieza = self.guardar_captura()
            self.assertEqual(self.bytes_en_disco(pieza), PNG_1x1)
            with pieza.asset.open("rb") as f:
                self.assertEqual(f.read(), PNG_1x1)

    def test_evidencia_vieja_sin_cifrar_se_sigue_leyendo_con_la_llave_puesta(self):
        """Encender el cifrado no deja ilegible lo que ya estaba en disco.

        Es el caso real del despliegue: hay casos con capturas guardadas antes
        de que el ambiente tuviera llave. Se reconoce por cabecera, no por una
        columna de la tabla.
        """
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=""
        ):
            pieza = self.guardar_captura()

        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=LLAVE
        ):
            with pieza.asset.open("rb") as f:
                self.assertEqual(f.read(), PNG_1x1)

    # --------------------------------------------------- llave ausente/mala

    def test_cifrada_sin_llave_es_error_explicito(self):
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=LLAVE
        ):
            pieza = self.guardar_captura()

        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=""
        ):
            with self.assertRaises(EvidenceKeyMissing):
                pieza.asset.open("rb")

    def test_con_otra_llave_tampoco_se_finge_exito(self):
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=LLAVE
        ):
            pieza = self.guardar_captura()

        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=OTRA_LLAVE
        ):
            with self.assertRaises(EvidenceKeyMissing):
                pieza.asset.open("rb")

    def test_llave_mal_formada_no_pasa_por_apagado(self):
        """Una llave inválida es un error de despliegue, no "cifrado apagado"."""
        with override_settings(LOST_MODE_EVIDENCE_KEY="esto-no-es-una-llave"):
            with self.assertRaises(ValueError):
                encryption_enabled()

    # ------------------------------------------------------------ la API

    def test_la_descarga_devuelve_la_imagen_original(self):
        self.authenticate()
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=LLAVE
        ):
            pieza = self.guardar_captura()
            r = self.client.get(f"{self.url}{pieza.pk}/file/")

            self.assertEqual(r.status_code, 200)
            self.assertEqual(b"".join(r.streaming_content), PNG_1x1)

    def test_la_descarga_sin_llave_contesta_el_motivo_y_no_un_500(self):
        self.authenticate()
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=LLAVE
        ):
            pieza = self.guardar_captura()

        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=""
        ):
            r = self.client.get(f"{self.url}{pieza.pk}/file/")

        self.assertEqual(r.status_code, 400)
        self.assertIn("cifrada", str(r.data))

    def test_el_listado_declara_si_el_ambiente_cifra(self):
        self.authenticate()
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=LLAVE
        ):
            r = self.client.get(self.url, format="json")
            self.assertTrue(r.data["encryption"]["enabled"])

        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=""
        ):
            r = self.client.get(self.url, format="json")
            self.assertFalse(r.data["encryption"]["enabled"])

    def test_una_llave_rota_no_tumba_la_linea_de_tiempo(self):
        """Leer el caso es lo que se está haciendo mientras el equipo sigue perdido.

        Escribir y descifrar son estrictos; el rótulo del listado, no. `null` no
        es `false`: la consola distingue "el servidor no lo pudo decir" de "este
        ambiente no cifra".
        """
        self.authenticate()
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp,
            LOST_MODE_EVIDENCE_KEY="esto-no-es-una-llave",
        ):
            r = self.client.get(self.url, format="json")

        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["encryption"]["enabled"])

    def test_el_listado_declara_la_politica_de_retencion(self):
        self.authenticate()
        r = self.client.get(self.url, format="json")

        self.assertEqual(r.data["retention"]["prune_days"], 90)
        self.assertEqual(r.data["retention"]["closed_case_days"], 7)

    # ------------------------------------------------------ el módulo solo

    def test_ida_y_vuelta_del_modulo(self):
        with override_settings(LOST_MODE_EVIDENCE_KEY=LLAVE):
            cifrado = encrypt_bytes(PNG_1x1)
            self.assertNotEqual(cifrado, PNG_1x1)
            self.assertEqual(decrypt_bytes(cifrado), PNG_1x1)

    def test_sin_llave_el_modulo_es_la_identidad(self):
        with override_settings(LOST_MODE_EVIDENCE_KEY=""):
            self.assertEqual(encrypt_bytes(PNG_1x1), PNG_1x1)
            self.assertEqual(decrypt_bytes(PNG_1x1), PNG_1x1)
