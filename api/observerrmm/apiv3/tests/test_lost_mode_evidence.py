"""Feature 030 · Fase 1 · subida de evidencia del modo perdido (T010).

Este endpoint es el que convierte la feature en algo que se puede mirar: el
agente sube, por ciclo, el punto de ubicación del momento y la captura de la
pantalla. Lo que se prueba acá es lo que puede romperse **en silencio**:

- que el ciclo lo numere el SERVIDOR y sea monótono por agente. Si se reiniciara
  al reabrir un caso, la segunda captura del ciclo 1 pisaría el archivo de la
  primera en disco — evidencia perdida sin ningún error;
- que un agente no pueda escribir en el caso de otro equipo. Esta evidencia
  puede terminar en una denuncia; si un token robado pudiera fabricarla para
  cualquier equipo, no valdría nada;
- que un ciclo SIN imagen deje igual su fila con el motivo. Sin eso, la línea de
  tiempo no distingue "el equipo está apagado" de "este equipo nunca va a dar
  capturas porque su sesión es Wayland";
- que sólo entren imágenes de verdad, mirando el CONTENIDO y no la extensión;
- que una subida a un caso ya cerrado se rechace con 409, que es la señal con la
  que el agente se apaga sin esperar al próximo polling de config.
"""

import io

from django.test import override_settings
from model_bakery import baker
from rest_framework.authtoken.models import Token

from accounts.models import User
from agents.models import LostModeEvidence, LostModeState
from observerrmm.constants import LostModeEvidenceKind
from observerrmm.helpers import make_random_password
from observerrmm.test import ObserverTestCase

# PNG de 1×1 válido: 8 bytes de firma + el resto de un archivo real mínimo. Lo
# que importa para el endpoint es la firma; el resto lo hace legible por si algún
# día se mira.
PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def archivo_png(nombre="pantalla.png", contenido=PNG_1x1):
    f = io.BytesIO(contenido)
    f.name = nombre
    return f


class TestSubidaDeEvidencia(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()

        self.agent = baker.make_recipe("agents.agent")
        self.estado = LostModeState.objects.create(
            agent=self.agent, active=True, reason="robo, ticket #4821", interval_min=5
        )
        self.autenticar_como(self.agent)
        self.url = f"/api/v3/{self.agent.agent_id}/lostmode/evidence/"

    def autenticar_como(self, agent):
        """Autentica al cliente con el token DEL AGENTE, no con una sesión.

        Se puebla `User.agent`, que es como lo deja `NewAgent` al enrolar. El
        respaldo por username lo cubre `test_agente_historico_sin_vinculo`.
        """
        user = User.objects.create_user(  # type: ignore
            username=agent.agent_id,
            password=make_random_password(len=60),  # type: ignore
            agent=agent,
        )
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return user

    # ------------------------------------------------------------- el lote

    def test_sube_pantalla_y_geo_del_mismo_ciclo(self):
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.evidencia_tmp()):
            r = self.client.post(
                self.url,
                {
                    "captured_at": "1786000000",
                    "session_user": "ana",
                    "lat": "-33.4489",
                    "lng": "-70.6693",
                    "accuracy_m": "42",
                    "source": "wifi",
                    "screen": archivo_png(),
                },
                format="multipart",
            )

            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["cycle"], 1)
            self.assertEqual(r.data["saved"], 2)

            geo = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.GEO)
            pantalla = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.SCREEN)

            # Las dos piezas comparten ciclo: es lo que las junta en la línea de
            # tiempo como "esto pasó al mismo tiempo".
            self.assertEqual(geo.cycle, pantalla.cycle)
            self.assertEqual(geo.lat, -33.4489)
            self.assertEqual(geo.accuracy_m, 42)
            self.assertEqual(geo.source, "wifi")
            self.assertEqual(pantalla.session_user, "ana")
            self.assertTrue(pantalla.asset)

            # El reloj del EQUIPO se guarda aparte del `created` del servidor:
            # entre los dos puede haber horas si el equipo estuvo sin red.
            self.assertIsNotNone(pantalla.captured_at)
            self.assertNotEqual(pantalla.captured_at, pantalla.created)

    def test_el_ciclo_lo_numera_el_servidor_y_no_se_reinicia(self):
        """El número de ciclo es monótono por agente, aunque el caso se reabra.

        Si se reiniciara, el archivo del ciclo 1 del caso nuevo sobrescribiría el
        del caso viejo: la ruta en disco lleva el número de ciclo.
        """
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.evidencia_tmp()):
            for esperado in (1, 2, 3):
                r = self.client.post(
                    self.url, {"screen": archivo_png()}, format="multipart"
                )
                self.assertEqual(r.data["cycle"], esperado)

            # Se cierra el caso y se abre otro.
            self.estado.active = False
            self.estado.save()
            self.estado.active = True
            self.estado.save()

            r = self.client.post(
                self.url, {"screen": archivo_png()}, format="multipart"
            )
            self.assertEqual(r.data["cycle"], 4)

        rutas = {e.asset.name for e in LostModeEvidence.objects.exclude(asset="")}
        self.assertEqual(len(rutas), 4, "cada ciclo tiene que quedar en su propia ruta")

    def test_ciclo_sin_imagen_deja_su_motivo(self):
        r = self.client.post(
            self.url,
            {"screen_reason": "wayland_no_soportado", "lat": "-33.4", "lng": "-70.6"},
            format="multipart",
        )

        self.assertEqual(r.status_code, 200)
        pantalla = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.SCREEN)
        self.assertEqual(pantalla.note, "wayland_no_soportado")
        self.assertFalse(pantalla.asset)

    def test_ciclo_vacio_no_ensucia_la_linea_de_tiempo(self):
        r = self.client.post(self.url, {}, format="multipart")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "empty")
        self.assertEqual(LostModeEvidence.objects.count(), 0)

    # ------------------------------------------------- validación del punto

    def test_null_island_no_es_una_ubicacion(self):
        """(0,0) es el artefacto típico de "sin fix" que llega como coordenada."""
        r = self.client.post(
            self.url,
            {"lat": "0", "lng": "0", "screen_reason": "sin_sesion"},
            format="multipart",
        )

        self.assertEqual(r.status_code, 200)
        self.assertFalse(
            LostModeEvidence.objects.filter(kind=LostModeEvidenceKind.GEO).exists()
        )

    def test_coordenadas_fuera_de_rango_no_entran(self):
        r = self.client.post(
            self.url,
            {"lat": "91.5", "lng": "-70.6", "screen_reason": "sin_sesion"},
            format="multipart",
        )

        self.assertEqual(r.status_code, 200)
        self.assertFalse(
            LostModeEvidence.objects.filter(kind=LostModeEvidenceKind.GEO).exists()
        )

    def test_hora_ilegible_no_pierde_la_evidencia(self):
        """Perder la hora del equipo empobrece la fila; rechazarla la perdería."""
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.evidencia_tmp()):
            r = self.client.post(
                self.url,
                {"captured_at": "hace un rato", "screen": archivo_png()},
                format="multipart",
            )

            self.assertEqual(r.status_code, 200)
            pantalla = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.SCREEN)
            self.assertIsNone(pantalla.captured_at)
            self.assertTrue(pantalla.asset)

    # ------------------------------------------------ validación del archivo

    def test_lo_que_no_es_imagen_no_entra_pero_queda_registrado(self):
        """Se mira el CONTENIDO, no la extensión ni el Content-Type.

        Los dos los elige quien sube, y esta carpeta la sirve después el servidor
        a un navegador.
        """
        r = self.client.post(
            self.url,
            {"screen": archivo_png(contenido=b"<html>no soy un png</html>")},
            format="multipart",
        )

        self.assertEqual(r.status_code, 200)
        pantalla = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.SCREEN)
        self.assertFalse(pantalla.asset)
        self.assertEqual(pantalla.note, "formato_no_soportado")

    def test_archivo_demasiado_grande_no_llena_el_disco(self):
        # El tope se lee del módulo al importar, así que se parchea donde vive.
        from apiv3 import views

        original = views.LOST_MODE_MAX_EVIDENCE_BYTES
        views.LOST_MODE_MAX_EVIDENCE_BYTES = 8
        try:
            r = self.client.post(
                self.url, {"screen": archivo_png()}, format="multipart"
            )
        finally:
            views.LOST_MODE_MAX_EVIDENCE_BYTES = original

        self.assertEqual(r.status_code, 200)
        pantalla = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.SCREEN)
        self.assertFalse(pantalla.asset)
        self.assertEqual(pantalla.note, "archivo_muy_grande")

    # --------------------------------------------------------- autorización

    def test_un_agente_no_puede_escribir_en_el_caso_de_otro(self):
        ajeno = baker.make_recipe("agents.agent")
        LostModeState.objects.create(agent=ajeno, active=True, reason="robo")

        r = self.client.post(
            f"/api/v3/{ajeno.agent_id}/lostmode/evidence/",
            {"screen_reason": "sin_sesion"},
            format="multipart",
        )

        self.assertEqual(r.status_code, 400)
        self.assertEqual(LostModeEvidence.objects.count(), 0)

    def test_agente_historico_sin_vinculo_user_agent(self):
        """`User.agent` lo puebla `NewAgent`; los agentes viejos pueden no tenerlo.

        El respaldo por username sigue saliendo del token, así que conserva la
        propiedad que importa.
        """
        otro = baker.make_recipe("agents.agent")
        LostModeState.objects.create(agent=otro, active=True, reason="robo")

        user = User.objects.create_user(  # type: ignore
            username=otro.agent_id,
            password=make_random_password(len=60),  # type: ignore
        )
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        r = self.client.post(
            f"/api/v3/{otro.agent_id}/lostmode/evidence/",
            {"screen_reason": "sin_sesion"},
            format="multipart",
        )

        self.assertEqual(r.status_code, 200)

    def test_sin_token_no_se_sube_nada(self):
        self.client.credentials()
        r = self.client.post(self.url, {"screen_reason": "sin_sesion"})
        self.assertEqual(r.status_code, 401)

    # --------------------------------------------------------- caso cerrado

    def test_caso_cerrado_responde_409(self):
        """La señal con la que el agente se apaga sin esperar al polling."""
        self.estado.active = False
        self.estado.save()

        r = self.client.post(
            self.url, {"screen_reason": "sin_sesion"}, format="multipart"
        )

        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["status"], "not_lost")
        self.assertEqual(LostModeEvidence.objects.count(), 0)

    def test_equipo_nunca_marcado_no_puede_subir_evidencia(self):
        """Sin caso abierto no hay régimen de ADR-025 que autorice la captura."""
        self.estado.delete()

        r = self.client.post(
            self.url, {"screen_reason": "sin_sesion"}, format="multipart"
        )

        self.assertEqual(r.status_code, 409)

    # ------------------------------------------------------------- utilidad

    def evidencia_tmp(self) -> str:
        """Directorio temporal para la evidencia de este test.

        La ruta por omisión es `/opt/observer/lostmode/evidence`: escribir ahí de
        verdad haría que el test dependiera del entorno —pasa en el runner de la
        CI, donde `/opt` es escribible, y falla en cualquier equipo de
        desarrollo—. El storage la resuelve en cada uso justamente para que este
        `override_settings` alcance (ver agents/lostmode_storage.py).
        """
        import tempfile

        if not hasattr(self, "_tmp_evidencia"):
            self._tmp_evidencia = tempfile.mkdtemp(prefix="lostmode-evidence-")
        return self._tmp_evidencia
