"""Feature 051 · ubicación a demanda: POST /agents/<id>/location/refresh/.

Orden de los cortes (roadmap DT-04): geo global apagada y equipo fuera de línea
se rechazan SIN tocar NATS (no se encola nada); con el equipo en línea se manda
el RPC `geolocation` y un `timeout` (agente viejo sin el RPC, o desconectado
después del chequeo) es error, no 202. Los errores van como código con el
prefijo `endpoint_response:` (feature 028) para que la consola los traduzca.
"""

from unittest.mock import patch

from model_bakery import baker

from logs.models import AuditLog
from observerrmm.test import ObserverTestCase


class TestLocationRefresh(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.coresettings.geo_tracking_enabled = True
        self.coresettings.save(update_fields=["geo_tracking_enabled"])
        self.agent = baker.make_recipe("agents.online_agent")
        self.url = f"/agents/{self.agent.agent_id}/location/refresh/"

    def _audit(self):
        return AuditLog.objects.filter(
            agent_id=self.agent.agent_id, message__contains="location refresh"
        )

    @patch("agents.models.Agent.nats_cmd")
    def test_en_linea_manda_el_rpc_y_audita(self, nats_cmd):
        nats_cmd.return_value = "ok"
        r = self.client.post(self.url, format="json")
        self.assertEqual(r.status_code, 202)
        nats_cmd.assert_called_once_with({"func": "geolocation"}, timeout=5)
        self.assertEqual(self._audit().count(), 1)
        self.check_not_authenticated("post", self.url)

    @patch("agents.models.Agent.nats_cmd")
    def test_geo_apagada_no_toca_nats(self, nats_cmd):
        self.coresettings.geo_tracking_enabled = False
        self.coresettings.save(update_fields=["geo_tracking_enabled"])
        r = self.client.post(self.url, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "endpoint_response:geo_disabled")
        nats_cmd.assert_not_called()

    @patch("agents.models.Agent.nats_cmd")
    def test_fuera_de_linea_no_encola_nada(self, nats_cmd):
        agent = baker.make_recipe("agents.offline_agent")
        r = self.client.post(f"/agents/{agent.agent_id}/location/refresh/")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "endpoint_response:agent_offline")
        nats_cmd.assert_not_called()

    @patch("agents.models.Agent.nats_cmd")
    def test_timeout_es_error(self, nats_cmd):
        nats_cmd.return_value = "timeout"
        r = self.client.post(self.url, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "endpoint_response:agent_unreachable")

    def test_inexistente_404(self):
        inexistente = "x" * 40
        r = self.client.post(f"/agents/{inexistente}/location/refresh/")
        self.assertEqual(r.status_code, 404)

    @patch("agents.models.Agent.nats_cmd")
    def test_permiso_es_el_de_ver_la_ubicacion(self, nats_cmd):
        nats_cmd.return_value = "ok"
        self.setup_client()
        user = self.create_user_with_roles([])
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.post(self.url).status_code, 403)

        # Mismo permiso que GET /location/ (can_list_agents), no can_edit_agent.
        user.role.can_list_agents = True
        user.role.save()
        self.assertEqual(self.client.post(self.url).status_code, 202)

        # Y respeta el alcance del rol sobre el equipo.
        otro = baker.make("clients.Client")
        user.role.can_view_clients.set([otro])
        self.assertEqual(self.client.post(self.url).status_code, 403)
