"""Desinstalación manual del agente: aviso, alerta, auditoría y borrado.

Lo que estos tests protegen, en orden de importancia:

1. Que la alerta SOBREVIVA al borrado del agente. Es el punto entero de la
   feature y el más fácil de romper sin darse cuenta: `Alert.agent` es CASCADE,
   así que basta con "arreglar" la alerta ligándola al agente para que la alerta
   desaparezca junto con lo que denuncia.
2. Que el agente salga del TOKEN y no del cuerpo. Es un endpoint que borra
   máquinas.
3. Que la ventana de gracia CANCELE el borrado si el agente vuelve a reportar,
   porque reinstalar corre el mismo `uninstall`.
"""

import datetime as dt
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone as djangotime
from model_bakery import baker
from rest_framework.authtoken.models import Token

from accounts.models import User
from agents.models import Agent
from agents.tasks import manual_uninstall_delete_task
from alerts.models import Alert
from logs.models import AuditLog
from observerrmm.constants import AlertType, AuditActionType
from observerrmm.helpers import make_random_password
from observerrmm.test import ObserverTestCase

# El caso base usa la caché dummy de los tests, donde `get` siempre devuelve
# None: los guardas de deduplicación quedan inertes y eso es lo que queremos
# para no tener que limpiarlos entre casos. Los dos tests que SÍ ejercen esos
# guardas piden una caché de verdad con este override.
REAL_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-manual-uninstall",
    }
}

URL = "/api/v3/uninstalled/"


class TestManualUninstallEndpoint(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()
        self.agent = baker.make_recipe("agents.online_agent", hostname="PC-TALCA-07")
        self.agent_user = User.objects.create_user(  # type: ignore
            username=self.agent.agent_id,
            agent=self.agent,
            password=make_random_password(len=60),  # type: ignore
        )
        self.token = Token.objects.create(user=self.agent_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def payload(self, **over):
        data = {
            "agent_id": self.agent.agent_id,
            "actor": "juan.perez",
            "sudo_user": "juan.perez",
            "login_user": "juan.perez",
            "lan_ips": "10.20.0.77",
            "local_time": "2026-08-02T15:33:00-04:00",
            "source": "script-linux",
        }
        data.update(over)
        return data

    def test_sin_token_rechaza(self):
        self.client.credentials()
        r = self.client.post(URL, self.payload(), format="json")
        self.assertEqual(r.status_code, 401)

    @patch("agents.tasks.manual_uninstall_delete_task.apply_async")
    @patch("agents.uninstall.send_manual_uninstall_email")
    def test_crea_alerta_y_auditoria(self, mock_mail, mock_task):
        r = self.client.post(URL, self.payload(), format="json")
        self.assertEqual(r.status_code, 200)

        alert = Alert.objects.get(alert_type=AlertType.AGENT_UNINSTALL)
        # Lo crítico: la alerta NACE sin agente, para que el borrado que viene
        # después no se la lleve por CASCADE.
        self.assertIsNone(alert.agent)
        self.assertFalse(alert.hidden)
        self.assertIn("PC-TALCA-07", alert.message)
        self.assertIn("juan.perez", alert.message)
        self.assertIn("vía sudo", alert.message)
        self.assertIn("10.20.0.77", alert.message)

        audit = AuditLog.objects.get(action=AuditActionType.AGENT_UNINSTALL)
        self.assertEqual(audit.agent, "PC-TALCA-07")
        self.assertEqual(audit.agent_id, self.agent.agent_id)

        mock_mail.assert_called_once()
        mock_task.assert_called_once()

    @patch("agents.tasks.manual_uninstall_delete_task.apply_async")
    @patch("agents.uninstall.send_manual_uninstall_email")
    def test_la_alerta_sobrevive_al_borrado_del_agente(self, mock_mail, mock_task):
        """El corazón de la feature, verificado de punta a punta."""
        self.client.post(URL, self.payload(), format="json")
        alert_pk = Alert.objects.get(alert_type=AlertType.AGENT_UNINSTALL).pk

        self.agent.delete()

        self.assertTrue(Alert.objects.filter(pk=alert_pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(action=AuditActionType.AGENT_UNINSTALL).exists()
        )

    @patch("agents.tasks.manual_uninstall_delete_task.apply_async")
    @patch("agents.uninstall.send_manual_uninstall_email")
    def test_ignora_el_agent_id_del_cuerpo(self, mock_mail, mock_task):
        """El token manda. Un agent_id ajeno en el payload no debe tocarse."""
        otro = baker.make_recipe("agents.online_agent", hostname="PC-AJENA")

        self.client.post(URL, self.payload(agent_id=otro.agent_id), format="json")

        alert = Alert.objects.get(alert_type=AlertType.AGENT_UNINSTALL)
        self.assertIn("PC-TALCA-07", alert.message)
        self.assertNotIn("PC-AJENA", alert.message)
        # Y el borrado programado apunta al agente del token, no al del cuerpo.
        args, _ = mock_task.call_args
        self.assertEqual(args[0][0], self.agent.agent_id)

    @patch("agents.tasks.manual_uninstall_delete_task.apply_async")
    @patch("agents.uninstall.send_manual_uninstall_email")
    def test_sin_sudo_no_dice_via_sudo(self, mock_mail, mock_task):
        self.client.post(URL, self.payload(sudo_user="", actor="root"), format="json")
        alert = Alert.objects.get(alert_type=AlertType.AGENT_UNINSTALL)
        self.assertIn("root", alert.message)
        self.assertNotIn("vía sudo", alert.message)

    @patch("agents.tasks.manual_uninstall_delete_task.apply_async")
    @patch("agents.uninstall.send_manual_uninstall_email")
    def test_actor_desconocido_no_revienta(self, mock_mail, mock_task):
        r = self.client.post(URL, {}, format="json")
        self.assertEqual(r.status_code, 200)
        alert = Alert.objects.get(alert_type=AlertType.AGENT_UNINSTALL)
        self.assertIn("desconocido", alert.message)

    @override_settings(MANUAL_UNINSTALL_AUTO_DELETE=False)
    @patch("agents.tasks.manual_uninstall_delete_task.apply_async")
    @patch("agents.uninstall.send_manual_uninstall_email")
    def test_auto_delete_apagado_deja_la_alerta_pero_no_borra(
        self, mock_mail, mock_task
    ):
        r = self.client.post(URL, self.payload(), format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            Alert.objects.filter(alert_type=AlertType.AGENT_UNINSTALL).exists()
        )
        mock_task.assert_not_called()

    @override_settings(CACHES=REAL_CACHE)
    @patch("agents.tasks.manual_uninstall_delete_task.apply_async")
    @patch("agents.uninstall.send_manual_uninstall_email")
    def test_reintento_no_duplica_la_alerta(self, mock_mail, mock_task):
        cache.clear()
        self.client.post(URL, self.payload(), format="json")
        self.client.post(URL, self.payload(), format="json")
        self.assertEqual(
            Alert.objects.filter(alert_type=AlertType.AGENT_UNINSTALL).count(), 1
        )
        self.assertEqual(mock_task.call_count, 1)

    @override_settings(CACHES=REAL_CACHE)
    @patch("agents.tasks.manual_uninstall_delete_task.apply_async")
    @patch("agents.uninstall.send_manual_uninstall_email")
    def test_borrado_desde_la_consola_no_genera_alerta(self, mock_mail, mock_task):
        """La consola corre el MISMO script; su aviso no es manual."""
        from observerrmm.constants import AGENT_CONSOLE_UNINSTALL_CACHE_PREFIX

        cache.clear()
        cache.set(
            f"{AGENT_CONSOLE_UNINSTALL_CACHE_PREFIX}{self.agent.agent_id}", True, 60
        )

        r = self.client.post(URL, self.payload(), format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(
            Alert.objects.filter(alert_type=AlertType.AGENT_UNINSTALL).exists()
        )
        mock_task.assert_not_called()


class TestManualUninstallDeleteTask(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent", hostname="PC-BORRABLE")

    @patch("core.tasks.sync_mesh_perms_task.delay")
    @patch("observerrmm.utils.reload_nats")
    def test_borra_pasada_la_gracia(self, mock_nats, mock_perms):
        avisado = djangotime.now()
        Agent.objects.filter(pk=self.agent.pk).update(
            last_seen=avisado - dt.timedelta(seconds=30)
        )

        ret = manual_uninstall_delete_task(self.agent.agent_id, avisado.isoformat())

        self.assertIn("borrado", ret)
        self.assertFalse(Agent.objects.filter(pk=self.agent.pk).exists())

    @patch("core.tasks.sync_mesh_perms_task.delay")
    @patch("observerrmm.utils.reload_nats")
    def test_cancela_si_el_agente_volvio_a_reportar(self, mock_nats, mock_perms):
        """Reinstalar corre el mismo uninstall: no puede costar el registro."""
        avisado = djangotime.now()
        Agent.objects.filter(pk=self.agent.pk).update(
            last_seen=avisado + dt.timedelta(minutes=5)
        )

        ret = manual_uninstall_delete_task(self.agent.agent_id, avisado.isoformat())

        self.assertIn("cancelado", ret)
        self.assertTrue(Agent.objects.filter(pk=self.agent.pk).exists())

    @patch("core.tasks.sync_mesh_perms_task.delay")
    @patch("observerrmm.utils.reload_nats")
    def test_un_checkin_en_vuelo_no_cancela(self, mock_nats, mock_perms):
        """El check-in que iba en camino al avisar no debe leerse como revivir."""
        avisado = djangotime.now()
        Agent.objects.filter(pk=self.agent.pk).update(
            last_seen=avisado + dt.timedelta(seconds=5)
        )

        ret = manual_uninstall_delete_task(self.agent.agent_id, avisado.isoformat())

        self.assertIn("borrado", ret)
        self.assertFalse(Agent.objects.filter(pk=self.agent.pk).exists())

    def test_agente_inexistente_es_no_op(self):
        ret = manual_uninstall_delete_task("no-existe", djangotime.now().isoformat())
        self.assertIn("skipped", ret)
