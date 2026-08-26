"""Tests de la API HTTP de Observer Erase: flujo de dos personas y emisión C7.

Complementa `test_core.py` (que prueba la lógica) verificando el camino de
producción por endpoints: quién ordena y quién confirma son personas distintas, y
la emisión del certificado de destrucción física de punta a punta.
"""

from model_bakery import baker

from erase.models import EraseCertificate, WipeOrderStatus
from observerrmm.test import ObserverTestCase


class WipeOrderApiTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()  # john y alice, ambos superuser (distinto username)
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-API", agent_id="aid-api"
        )

    def _crear_orden(self):
        return self.client.post(
            f"/erase/agents/{self.agent.agent_id}/orders/",
            {"action": "crypto_erase", "reason": "equipo robado"},
            format="json",
        )

    def test_no_autenticado(self):
        self.check_not_authenticated("get", "/erase/orders/")

    def test_flujo_dos_personas(self):
        r = self._crear_orden()
        self.assertEqual(r.status_code, 201)
        order_id = r.json()["id"]
        self.assertEqual(r.json()["status"], WipeOrderStatus.PENDING_CONFIRMATION)

        # john (quien ordenó) NO puede autoconfirmar → 409
        r_self = self.client.post(
            f"/erase/orders/{order_id}/confirm/",
            {"recovery_seconds": 60},
            format="json",
        )
        self.assertEqual(r_self.status_code, 409)

        # alice (segunda persona) sí confirma
        self.client.force_authenticate(user=self.alice)
        r_ok = self.client.post(
            f"/erase/orders/{order_id}/confirm/",
            {"recovery_seconds": 60},
            format="json",
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertEqual(r_ok.json()["status"], WipeOrderStatus.RECOVERY_WINDOW)

    def test_cancelar_en_ventana(self):
        order_id = self._crear_orden().json()["id"]
        self.client.force_authenticate(user=self.alice)
        self.client.post(
            f"/erase/orders/{order_id}/confirm/",
            {"recovery_seconds": 60},
            format="json",
        )
        r = self.client.post(
            f"/erase/orders/{order_id}/cancel/",
            {"reason": "falso positivo"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], WipeOrderStatus.CANCELLED)


class CertifyDestructionApiTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client", name="MINSAL")
        self.site = baker.make("clients.Site", client=self.client_obj)

    def test_intake_y_certificado_c7(self):
        # D1: ingreso del activo
        r_in = self.client.post(
            "/erase/intake/",
            {
                "client": self.client_obj.pk,
                "site": self.site.pk,
                "equipment_serial": "SN-123",
                "media_serial": "MED-999",
                "asset_tag": "ACT-7",
                "ticket_ref": "TCK-1",
                "state": "non_functional",
            },
            format="json",
        )
        self.assertEqual(r_in.status_code, 201)
        intake_id = r_in.json()["id"]
        self.assertTrue(r_in.json()["routes_to_physical_destruction"])

        # C7: certificado de destrucción física
        r_cert = self.client.post(
            f"/erase/intake/{intake_id}/certify-destruction/",
            {"method": "trituración", "operator": "op-terreno"},
            format="json",
        )
        self.assertEqual(r_cert.status_code, 201)
        cert_id = r_cert.json()["certificate_id"]
        self.assertTrue(cert_id.startswith("OE-"))

        cert = EraseCertificate.objects.get(certificate_id=cert_id)
        self.assertEqual(cert.kind, "physical_destruction")
        self.assertEqual(cert.tenant, "MINSAL")

        # descargas: JSON y PDF
        pk = cert.pk
        r_json = self.client.get(f"/erase/certificates/{pk}/json/")
        self.assertEqual(r_json.status_code, 200)
        self.assertIn("document", r_json.json())

        r_pdf = self.client.get(f"/erase/certificates/{pk}/pdf/")
        self.assertEqual(r_pdf.status_code, 200)
        self.assertEqual(r_pdf["Content-Type"], "application/pdf")

        # detalle trae la verificación
        r_det = self.client.get(f"/erase/certificates/{pk}/")
        self.assertEqual(r_det.status_code, 200)
        self.assertTrue(r_det.json()["verification"]["chain_intact"])
