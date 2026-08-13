"""Feature 030 · Fase 2 · ingesta de la foto de webcam (T017, ADR-025).

Lo que se prueba acá es la diferencia que decide si la línea de tiempo miente:
**"la webcam está apagada" no es "la webcam falló"**. Con el interruptor global
en off el agente no manda nada de cámara, y el servidor no puede inventar una
fila por ciclo hablando de un dispositivo que nadie pidió usar — en un caso
largo serían cientos de renglones diciendo que no hay foto.

Y el interruptor mismo: apagado de fábrica, sin excepción por agente. Va al
revés que la geolocalización (ADR-024, encendida de fábrica) porque fotografiar
la cara de una persona es cualitativamente más sensible que ubicar un activo.
"""

import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from accounts.models import User
from agents.models import LostModeEvidence, LostModeState
from apiv3.utils import get_agent_config
from core.utils import get_core_settings
from observerrmm.helpers import make_random_password
from rest_framework.authtoken.models import Token
from observerrmm.constants import LostModeEvidenceKind
from observerrmm.test import ObserverTestCase

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG_MINIMO = b"\xff\xd8\xff\xe0" + b"\x00" * 60


class TestInterruptorWebcam(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.agent")

    def test_apagado_de_fabrica(self):
        """Actualizar el producto NO puede empezar a fotografiar caras solo."""
        self.assertFalse(get_core_settings().lost_mode_webcam_enabled)
        self.assertFalse(get_agent_config(self.agent.agent_id).lost_mode_webcam)

    def test_el_agente_lo_recibe_encendido_cuando_se_enciende(self):
        core = get_core_settings()
        core.lost_mode_webcam_enabled = True
        core.save()

        self.assertTrue(get_agent_config(self.agent.agent_id).lost_mode_webcam)

    def test_viaja_aunque_el_equipo_no_este_marcado(self):
        """El marcaje puede llegar por NATS entre dos consultas de configuración.

        Si el interruptor viajara sólo con el equipo perdido, el agente se
        enteraría de que puede usar la cámara una consulta tarde — o sea, ciclos
        enteros de un caso real sin foto.
        """
        core = get_core_settings()
        core.lost_mode_webcam_enabled = True
        core.save()

        conf = get_agent_config(self.agent.agent_id)

        self.assertFalse(conf.lost_mode)
        self.assertTrue(conf.lost_mode_webcam)


class TestIngestaWebcam(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()
        self.agent = baker.make_recipe("agents.agent")
        LostModeState.objects.create(agent=self.agent, active=True, reason="robo")
        self.tmp = tempfile.mkdtemp(prefix="lostmode-webcam-")
        self.url = f"/api/v3/{self.agent.agent_id}/lostmode/evidence/"

    def _post(self, datos):
        # Token DEL AGENTE, no una sesión: es como lo deja `NewAgent` al enrolar.
        if not getattr(self, "_token", None):
            user = User.objects.create_user(  # type: ignore
                username=self.agent.agent_id,
                password=make_random_password(len=60),  # type: ignore
                agent=self.agent,
            )
            self._token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self._token.key}")
        return self.client.post(self.url, datos, format="multipart")

    def test_sin_webcam_no_se_crea_fila_de_webcam(self):
        """El caso normal de una flota que nunca activó la cámara."""
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            r = self._post(
                {
                    "screen": SimpleUploadedFile("p.png", PNG_1x1, "image/png"),
                    "lat": "-33.4489",
                    "lng": "-70.6693",
                }
            )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            LostModeEvidence.objects.filter(kind=LostModeEvidenceKind.WEBCAM).count(),
            0,
            "la webcam apagada no puede dejar filas en la línea de tiempo",
        )

    def test_la_foto_se_guarda_como_pieza_de_webcam(self):
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            r = self._post(
                {
                    "webcam": SimpleUploadedFile("w.jpg", JPEG_MINIMO, "image/jpeg"),
                    "lat": "-33.4489",
                    "lng": "-70.6693",
                }
            )

        self.assertEqual(r.status_code, 200)
        pieza = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.WEBCAM)
        self.assertTrue(pieza.asset)
        self.assertIsNone(pieza.note)

    def test_el_motivo_llega_sin_foto(self):
        """`permiso_denegado` en un Mac: la fila existe y explica por qué no hay cara."""
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            r = self._post({"webcam_reason": "permiso_denegado"})

        self.assertEqual(r.status_code, 200)
        pieza = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.WEBCAM)
        self.assertEqual(pieza.note, "permiso_denegado")
        self.assertFalse(pieza.asset)

    def test_la_foto_queda_cifrada_igual_que_la_pantalla(self):
        """La Fase 3 cubre la webcam sin tocar una línea: el cifrado vive en el storage."""
        from cryptography.fernet import Fernet

        from agents.lostmode_crypto import EVIDENCE_MAGIC

        llave = Fernet.generate_key().decode()
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=self.tmp, LOST_MODE_EVIDENCE_KEY=llave
        ):
            self._post(
                {"webcam": SimpleUploadedFile("w.jpg", JPEG_MINIMO, "image/jpeg")}
            )
            pieza = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.WEBCAM)

            import os

            with open(os.path.join(self.tmp, pieza.asset.name), "rb") as f:
                crudo = f.read()

        self.assertTrue(crudo.startswith(EVIDENCE_MAGIC))
        self.assertNotIn(JPEG_MINIMO, crudo)

    def test_una_foto_que_no_es_imagen_se_rechaza_y_se_dice(self):
        """Se registra en la línea de tiempo, no se contesta 400 perdiendo el ciclo."""
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            self._post(
                {
                    "webcam": SimpleUploadedFile(
                        "w.jpg", b"esto no es una imagen", "image/jpeg"
                    )
                }
            )

        pieza = LostModeEvidence.objects.get(kind=LostModeEvidenceKind.WEBCAM)
        self.assertEqual(pieza.note, "formato_no_soportado")
        self.assertFalse(pieza.asset)

    def test_la_foto_comparte_ciclo_con_la_pantalla_y_el_punto(self):
        """Las tres piezas del mismo momento tienen que agruparse en la línea de tiempo."""
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            self._post(
                {
                    "screen": SimpleUploadedFile("p.png", PNG_1x1, "image/png"),
                    "webcam": SimpleUploadedFile("w.jpg", JPEG_MINIMO, "image/jpeg"),
                    "lat": "-33.4489",
                    "lng": "-70.6693",
                }
            )

        ciclos = set(LostModeEvidence.objects.values_list("cycle", flat=True))
        self.assertEqual(len(ciclos), 1, "las tres piezas van en el mismo ciclo")
        self.assertEqual(LostModeEvidence.objects.count(), 3)
