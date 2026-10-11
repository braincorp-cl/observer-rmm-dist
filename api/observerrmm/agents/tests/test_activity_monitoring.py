"""Feature 049-B2 · encendido del monitoreo de actividad.

La regla que no puede romperse en silencio: con el interruptor global apagado
(default) NADIE muestrea; encendido, sólo muestrea quien tiene un "sí" explícito
en la cascada equipo > sitio > cliente. Y el polling de config entrega lo mismo
que resuelve la consola.
"""

from unittest.mock import patch

from model_bakery import baker

from agents.activity import agents_possibly_on, resolve_activity
from apiv3.utils import get_agent_config
from core.utils import get_core_settings
from observerrmm.test import ObserverTestCase


class TestResolucion(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")
        self.site = self.agent.site
        self.client_obj = self.site.client

    def _global(self, on: bool):
        cs = get_core_settings()
        cs.activity_monitoring_enabled = on
        cs.save()

    def test_apagado_de_fabrica(self):
        self.assertFalse(get_core_settings().activity_monitoring_enabled)
        res = resolve_activity(self.agent)
        self.assertFalse(res.active)
        self.assertEqual(res.source, "global")

    def test_global_apagado_gana_a_un_si_explicito(self):
        self.agent.activity_monitoring = True
        self.agent.save()
        self.assertFalse(resolve_activity(self.agent).active)

    def test_global_encendido_sin_valor_es_no(self):
        self._global(True)
        res = resolve_activity(self.agent)
        self.assertFalse(res.active)
        self.assertEqual(res.source, "default")

    def test_cascada_equipo_sitio_cliente(self):
        self._global(True)
        self.client_obj.activity_monitoring = True
        self.client_obj.save()
        res = resolve_activity(self.agent)
        self.assertEqual((res.active, res.source), (True, "client"))

        self.site.activity_monitoring = False
        self.site.save()
        self.agent.refresh_from_db()
        res = resolve_activity(self.agent)
        self.assertEqual((res.active, res.source), (False, "site"))

        self.agent.activity_monitoring = True
        self.agent.save()
        res = resolve_activity(self.agent)
        self.assertEqual((res.active, res.source), (True, "agent"))

    def test_cadencia_acotada_al_rango_del_agente(self):
        cs = get_core_settings()
        cs.activity_interval_seg = 1
        cs.save()
        self.assertEqual(resolve_activity(self.agent).interval_seg, 15)

    def test_config_de_checkin_entrega_lo_resuelto(self):
        self.assertFalse(get_agent_config(self.agent.agent_id).actividad_active)
        self._global(True)
        self.agent.activity_monitoring = True
        self.agent.save()
        conf = get_agent_config(self.agent.agent_id)
        self.assertTrue(conf.actividad_active)
        self.assertEqual(conf.actividad_interval_seg, 60)

    def test_agents_possibly_on(self):
        otro = baker.make_recipe("agents.online_agent")
        self.client_obj.activity_monitoring = True
        self.client_obj.save()
        pks = set(agents_possibly_on().values_list("pk", flat=True))
        self.assertIn(self.agent.pk, pks)
        self.assertNotIn(otro.pk, pks)


class TestEndpoint(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")
        self.url = "/agents/activity-monitoring/"

    @patch("agents.views.push_activity_monitoring_task.delay")
    def test_fijar_cliente_empuja_a_sus_equipos(self, push):
        client = self.agent.site.client
        r = self.client.put(
            self.url, {"level": "client", "id": client.pk, "value": True}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        client.refresh_from_db()
        self.assertTrue(client.activity_monitoring)
        push.assert_called_once_with(agent_pks=[self.agent.pk])

        # Volver a heredar (null) también empuja; repetir el mismo valor no.
        push.reset_mock()
        self.client.put(
            self.url, {"level": "client", "id": client.pk, "value": None}, format="json"
        )
        client.refresh_from_db()
        self.assertIsNone(client.activity_monitoring)
        push.assert_called_once()
        push.reset_mock()
        self.client.put(
            self.url, {"level": "client", "id": client.pk, "value": None}, format="json"
        )
        push.assert_not_called()

    @patch("agents.views.push_activity_monitoring_task.delay")
    def test_fijar_equipo(self, push):
        r = self.client.put(
            self.url,
            {"level": "agent", "id": self.agent.agent_id, "value": False},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.activity_monitoring)

    def test_estado_efectivo(self):
        r = self.client.get(f"/agents/{self.agent.agent_id}/activity/monitoring/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["active"])
        self.assertEqual(r.data["source"], "global")

    def test_nivel_invalido(self):
        r = self.client.put(
            self.url, {"level": "global", "id": "1", "value": True}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    @patch("agents.tasks.push_activity_monitoring_task.delay")
    def test_cambio_global_empuja_solo_a_los_posibles(self, push):
        self.agent.activity_monitoring = True
        self.agent.save()
        baker.make_recipe("agents.online_agent")
        data = self.client.get("/core/settings/").data
        data["activity_monitoring_enabled"] = True
        data.pop("all_timezones", None)
        r = self.client.put("/core/settings/", data, format="json")
        self.assertEqual(r.status_code, 200)
        push.assert_called_once_with(agent_pks=[self.agent.pk])

    def test_sin_permiso_no_fija(self):
        user = self.create_user_with_roles([])
        self.client.force_authenticate(user=user)
        r = self.client.put(
            self.url,
            {"level": "agent", "id": self.agent.agent_id, "value": True},
            format="json",
        )
        self.assertEqual(r.status_code, 403)


class TestReentrega(ObserverTestCase):
    """Pendiente 2 de la 049-B2: el equipo apagado durante el cambio se entera
    al volver, aunque su agente no tenga polling de `actividad_*`."""

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")

    @patch("agents.views.push_activity_monitoring_task.delay")
    def test_cambio_marca_pendiente(self, push):
        self.client.put(
            "/agents/activity-monitoring/",
            {"level": "site", "id": self.agent.site.pk, "value": True},
            format="json",
        )
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.activity_sync_pending)

    @patch("agents.tasks.push_activity_monitoring_task.delay")
    def test_config_reenvia_y_limpia(self, push):
        from apiv3.views import _reenviar_actividad_pendiente

        _reenviar_actividad_pendiente(self.agent.agent_id)
        push.assert_not_called()

        self.agent.activity_sync_pending = True
        self.agent.save()
        _reenviar_actividad_pendiente(self.agent.agent_id)
        push.assert_called_once_with(agent_pks=[self.agent.pk])
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.activity_sync_pending)

        push.reset_mock()
        _reenviar_actividad_pendiente(self.agent.agent_id)
        push.assert_not_called()
