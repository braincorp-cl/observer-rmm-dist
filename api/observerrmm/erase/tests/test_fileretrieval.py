"""Tests de fileretrieval (feature 042) — recuperar archivos antes de borrar.

fileretrieval NO es destructivo: gobernanza liviana (`can_retrieve_files`, sin
doble confirmación ni ventana), anclado a un caso perdido abierto (RF-G06), con
auditoría en la cadena inmutable y despacho por NATS no atado al gate ADR-029.
"""

import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from model_bakery import baker
from rest_framework.authtoken.models import Token

from accounts.models import Role, User
from agents.models import LostModeState
from erase import services
from erase.models import (
    EraseAuditRecord,
    FileRetrievalOrder,
    FileRetrievalStatus,
    RetrievedFile,
)
from observerrmm.helpers import make_random_password
from observerrmm.test import ObserverTestCase


async def _fake_nats_ok(*a, **k):
    return "ok"


async def _fake_nats_down(*a, **k):
    return "natsdown"


class FileRetrievalApiTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()  # john/alice superuser
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-FR", agent_id="aid-fr"
        )

    def _abrir_caso(self):
        LostModeState.objects.create(agent=self.agent, active=True, reason="robado")

    def _crear(self, **body):
        payload = {"paths": ["C:/Users/x/informe.docx"]}
        payload.update(body)
        return self.client.post(
            f"/erase/agents/{self.agent.agent_id}/fileretrieval/",
            payload,
            format="json",
        )

    def test_no_autenticado(self):
        self.check_not_authenticated("get", "/erase/fileretrieval/")

    def test_permiso_liviano_dedicado(self):
        """Un rol con can_manage_lost_mode pero sin can_retrieve_files NO puede."""
        role = Role.objects.create(name="solo-perdido", can_manage_lost_mode=True)
        u = User.objects.create_user(username="operador", password="x")
        u.role = role
        u.save()
        self.client.force_authenticate(user=u)
        self._abrir_caso()
        r = self._crear()
        self.assertEqual(r.status_code, 403)

    def test_solo_desde_caso_perdido_abierto(self):
        """RF-G06: sin caso perdido abierto, no se puede ordenar."""
        r = self._crear()
        self.assertEqual(r.status_code, 409)

    @patch("agents.models.Agent.nats_cmd", _fake_nats_down)
    def test_crea_anclada_al_caso(self):
        self._abrir_caso()
        r = self._crear(dry_run=True)
        self.assertEqual(r.status_code, 201)
        data = r.json()
        # Equipo "offline" en el test (nats down) ⇒ queda en cola.
        self.assertEqual(data["status"], FileRetrievalStatus.PENDING)
        self.assertTrue(data["dry_run"])
        self.assertIsNotNone(data["expires_at"])
        # Auditoría en la cadena inmutable (RF-G04/RF-07).
        self.assertTrue(
            EraseAuditRecord.objects.filter(event="retrieval_created").exists()
        )

    @patch("agents.models.Agent.nats_cmd", _fake_nats_ok)
    def test_despacha_cuando_el_equipo_responde(self):
        self._abrir_caso()
        r = self._crear()
        self.assertEqual(r.json()["status"], FileRetrievalStatus.DISPATCHED)

    def test_rutas_vacias_rechazadas(self):
        self._abrir_caso()
        r = self._crear(paths=[])
        self.assertEqual(r.status_code, 400)

    @patch("agents.models.Agent.nats_cmd", _fake_nats_down)
    def test_cancelar(self):
        self._abrir_caso()
        pk = self._crear().json()["id"]
        r = self.client.post(f"/erase/fileretrieval/{pk}/cancel/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], FileRetrievalStatus.CANCELLED)


class FileRetrievalServiceTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-SVC", agent_id="aid-svc"
        )

    @patch("agents.models.Agent.nats_cmd", _fake_nats_down)
    def _orden(self, **kw):
        return services.create_retrieval_order(
            agent=self.agent,
            client=self.client_obj,
            site=self.site,
            paths=kw.get("paths", ["/home/y/doc.txt"]),
            requested_by="john",
            dry_run=kw.get("dry_run", False),
            lost_mode_cycle=kw.get("lost_mode_cycle", 3),
        )

    def test_expira_orden_zombie(self):
        order = self._orden()
        # Simula que la ventana venció sin que el equipo reconectara.
        FileRetrievalOrder.objects.filter(pk=order.pk).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        n = services.expire_stale_retrieval_orders()
        self.assertEqual(n, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, FileRetrievalStatus.EXPIRED)

    def test_paths_vacio_error(self):
        with self.assertRaises(services.OrderStateError):
            self._orden(paths=[])


class FileRetrievalUploadTests(ObserverTestCase):
    def setUp(self):
        self.setup_client()  # self.client = APIClient (para .credentials del token)
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-UP", agent_id="aid-up"
        )
        # Token DEL AGENTE, igual que lo deja NewAgent al enrolar.
        user = User.objects.create_user(
            username=self.agent.agent_id,
            password=make_random_password(len=60),
            agent=self.agent,
        )
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.tmp = tempfile.mkdtemp(prefix="fileretrieval-")
        self.order = FileRetrievalOrder.objects.create(
            agent=self.agent,
            client=self.client_obj,
            site=self.site,
            agent_id_snapshot=self.agent.agent_id,
            agent_hostname=self.agent.hostname,
            paths=["/home/y/doc.txt"],
            status=FileRetrievalStatus.DISPATCHED,
            requested_by="john",
            size_limit_bytes=1024,
        )
        self.url = (
            f"/api/v3/{self.agent.agent_id}/fileretrieval/{self.order.pk}/upload/"
        )

    def _post(self, datos):
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            return self.client.post(self.url, datos, format="multipart")

    def test_sube_archivo_y_completa(self):
        f = SimpleUploadedFile("doc.txt", b"contenido", content_type="text/plain")
        r = self._post({"file": f, "source_path": "/home/y/doc.txt"})
        self.assertEqual(r.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, FileRetrievalStatus.UPLOADING)
        self.assertEqual(RetrievedFile.objects.filter(order=self.order).count(), 1)

        # Cierre.
        r2 = self._post({"done": "1"})
        self.assertEqual(r2.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, FileRetrievalStatus.DONE)

    def test_idempotente_misma_ruta(self):
        for _ in range(2):
            f = SimpleUploadedFile("doc.txt", b"abc", content_type="text/plain")
            self._post({"file": f, "source_path": "/home/y/doc.txt"})
        self.assertEqual(RetrievedFile.objects.filter(order=self.order).count(), 1)

    def test_tope_por_orden(self):
        big = SimpleUploadedFile(
            "big.bin", b"x" * 2048, content_type="application/octet-stream"
        )
        r = self._post({"file": big, "source_path": "/home/y/big.bin"})
        self.assertEqual(r.status_code, 413)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, FileRetrievalStatus.FAILED)

    def test_dry_run_reporta_plan_sin_subir(self):
        self.order.dry_run = True
        self.order.save(update_fields=["dry_run"])
        r = self._post({"done": "1", "plan": "recuperaria 3 archivos"})
        self.assertEqual(r.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, FileRetrievalStatus.DONE)
        self.assertIn("plan", self.order.result)
        self.assertEqual(RetrievedFile.objects.filter(order=self.order).count(), 0)

    def test_token_de_otro_equipo_no_escribe(self):
        otro = baker.make(
            "agents.Agent", site=self.site, hostname="OTRO", agent_id="aid-otro"
        )
        # Autenticado como self.agent, pero la URL apunta a otro agent_id.
        url_otro = f"/api/v3/{otro.agent_id}/fileretrieval/{self.order.pk}/upload/"
        f = SimpleUploadedFile("doc.txt", b"x", content_type="text/plain")
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            r = self.client.post(
                url_otro, {"file": f, "source_path": "/x"}, format="multipart"
            )
        self.assertNotEqual(r.status_code, 200)
