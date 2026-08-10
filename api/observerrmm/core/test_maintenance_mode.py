"""Tests de visibilidad y trazabilidad del modo mantenimiento (feature 036).

El modo mantenimiento es un interruptor de silencio: suprime alertas en seis puntos
de `alerts/models.py` y corta el rollup del dashboard. El origen de esta feature fue
encontrar 8 de 10 equipos de staging con cuatro días de alertas suprimidas, sin que
nada en el producto lo dijera y sin poder saber quién lo había hecho.

Lo que se cubre acá es justamente lo que falla en silencio:

1. Que el sellado de `since`/`by` ocurra en los CUATRO caminos de escritura y no sólo
   en el que pasa por `save()`.
2. Que el bulk deje auditoría — con control positivo: el test tiene que fallar si
   alguien vuelve al `.update()` ciego.
3. Que el `break` de `_get_failing_data` no vuelva. Ese `break` hacía que un equipo
   en mantenimiento pintara sano al sitio ENTERO, vecinos fallando incluidos.
4. El contrato del `since=None`: cuenta en el banner, no aporta al "más antiguo", y
   sí dispara el correo.
"""

import datetime as dt
from unittest.mock import patch

from django.utils import timezone as djangotime
from model_bakery import baker

from agents.models import Agent
from core.management.commands.server_maint_mode import Command as MaintModeCommand
from core.tasks import _get_failing_data, maintenance_mode_reminder_task
from logs.models import AuditLog
from observerrmm.constants import AGENT_STATUS_OVERDUE, AuditObjType
from observerrmm.test import ObserverTestCase


class TestMaintenanceSealing(ObserverTestCase):
    """Los cuatro caminos de escritura del flag."""

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.site = baker.make("clients.Site")
        self.agent = baker.make_recipe("agents.online_agent", site=self.site)

    def test_maintenance_since_sealed_on_enable(self):
        """Camino 1 de 4: el detalle del agente, que sí pasa por Agent.save()."""
        url = f"/agents/{self.agent.agent_id}/"

        r = self.client.put(url, {"maintenance_mode": True}, format="json")
        self.assertEqual(r.status_code, 200)

        self.agent.refresh_from_db()
        self.assertTrue(self.agent.maintenance_mode)
        self.assertIsNotNone(self.agent.maintenance_mode_since)
        # El autor sale del middleware, no de un parámetro: por eso importa que sea
        # el usuario real de la sesión y no "system".
        self.assertEqual(self.agent.maintenance_mode_by, "john")

        r = self.client.put(url, {"maintenance_mode": False}, format="json")
        self.assertEqual(r.status_code, 200)

        self.agent.refresh_from_db()
        self.assertFalse(self.agent.maintenance_mode)
        self.assertIsNone(self.agent.maintenance_mode_since)
        self.assertIsNone(self.agent.maintenance_mode_by)

    def test_save_does_not_reset_since_on_unrelated_edit(self):
        """Un save() cualquiera no debe mover la fecha de una ventana abierta."""
        self.agent.maintenance_mode = True
        self.agent.save()
        original = Agent.objects.get(pk=self.agent.pk).maintenance_mode_since

        self.client.put(
            f"/agents/{self.agent.agent_id}/",
            {"description": "otra cosa", "maintenance_mode": True},
            format="json",
        )

        self.agent.refresh_from_db()
        self.assertEqual(self.agent.maintenance_mode_since, original)

    def test_bulk_maintenance_seals_since(self):
        """Camino 2 de 4: el bulk por Site, que usa .update() y NO pasa por save()."""
        otro = baker.make_recipe("agents.online_agent", site=self.site)

        r = self.client.post(
            "/agents/maintenance/bulk/",
            {"type": "Site", "id": self.site.pk, "action": True},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

        for agent in (self.agent, otro):
            agent.refresh_from_db()
            self.assertTrue(agent.maintenance_mode)
            self.assertIsNotNone(agent.maintenance_mode_since)
            self.assertEqual(agent.maintenance_mode_by, "john")

    def test_server_maint_mode_command_seals_since(self):
        """Camino 3 de 4: el comando del playbook, con autor 'system'."""
        MaintModeCommand().handle(
            enable=False, disable=False, force_enable=True, force_disable=False
        )

        self.agent.refresh_from_db()
        self.assertTrue(self.agent.maintenance_mode)
        self.assertIsNotNone(self.agent.maintenance_mode_since)
        self.assertEqual(self.agent.maintenance_mode_by, "system")

        MaintModeCommand().handle(
            enable=False, disable=False, force_enable=False, force_disable=True
        )

        self.agent.refresh_from_db()
        self.assertFalse(self.agent.maintenance_mode)
        self.assertIsNone(self.agent.maintenance_mode_since)

    def test_server_maint_mode_preserves_existing_window(self):
        """El enable masivo no debe pisar la fecha de quien ya estaba marcado.

        Si lo hiciera, un despliegue cualquiera haría parecer que TODAS las ventanas
        empezaron ese día — y el correo del umbral nunca se dispararía.
        """
        self.agent.maintenance_mode = True
        self.agent.save()
        original = Agent.objects.get(pk=self.agent.pk).maintenance_mode_since

        MaintModeCommand().handle(
            enable=False, disable=False, force_enable=True, force_disable=False
        )

        self.agent.refresh_from_db()
        self.assertEqual(self.agent.maintenance_mode_since, original)


class TestMaintenanceAudit(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.site = baker.make("clients.Site")
        self.agents = [
            baker.make_recipe("agents.online_agent", site=self.site) for _ in range(3)
        ]

    def test_bulk_maintenance_writes_audit_log(self):
        """Control positivo: si alguien revierte al `.update()` ciego, esto falla.

        Es el agujero original — nadie podía saber quién había silenciado 8 equipos.
        """
        r = self.client.post(
            "/agents/maintenance/bulk/",
            {"type": "Site", "id": self.site.pk, "action": True},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

        logs = AuditLog.objects.filter(object_type=AuditObjType.BULK)
        self.assertEqual(logs.count(), 1)

        log = logs.first()
        self.assertEqual(log.username, "john")
        self.assertIn("maintenance mode enabled", log.message)
        self.assertEqual(log.after_value["target"], "site")
        self.assertEqual(log.after_value["site"], self.site.pk)
        self.assertEqual(log.after_value["count"], 3)
        self.assertCountEqual(
            log.after_value["agent_ids"], [a.agent_id for a in self.agents]
        )

    def test_bulk_maintenance_no_audit_when_nothing_changes(self):
        """Un POST que no toca a nadie no debe inventar una entrada de auditoría."""
        vacio = baker.make("clients.Site")

        self.client.post(
            "/agents/maintenance/bulk/",
            {"type": "Site", "id": vacio.pk, "action": True},
            format="json",
        )

        self.assertEqual(
            AuditLog.objects.filter(object_type=AuditObjType.BULK).count(), 0
        )


class TestFailingDataMaintenance(ObserverTestCase):
    """Regresión del `break` de `_get_failing_data` (core/tasks.py).

    Este test DEBE fallar contra el código anterior al arreglo. Si pasa en verde con
    el `break` puesto, está mal escrito.
    """

    def setUp(self):
        self.setup_coresettings()
        self.site = baker.make("clients.Site")

    def test_failing_data_skips_only_maintenance_agent(self):
        # El de mantenimiento va PRIMERO a propósito: con `break`, el bucle moría acá
        # y el sitio entero se reportaba sano.
        baker.make_recipe(
            "agents.overdue_agent",
            site=self.site,
            maintenance_mode=True,
            overdue_dashboard_alert=True,
        )
        fallando = baker.make_recipe(
            "agents.overdue_agent",
            site=self.site,
            maintenance_mode=False,
            overdue_dashboard_alert=True,
        )
        self.assertEqual(fallando.status, AGENT_STATUS_OVERDUE)

        agents = Agent.objects.filter(site=self.site).order_by("pk")
        self.assertTrue(_get_failing_data(agents)["error"])

    def test_failing_data_ignores_agent_in_maintenance(self):
        """La contraparte: el equipo en mantenimiento sigue sin contar.

        Eso NO cambia con el arreglo — el flag sigue suprimiendo, y el nodo se sigue
        pintando verde. Lo único que cambia es que deje de tapar a sus vecinos.
        """
        baker.make_recipe(
            "agents.overdue_agent",
            site=self.site,
            maintenance_mode=True,
            overdue_dashboard_alert=True,
        )

        agents = Agent.objects.filter(site=self.site)
        self.assertFalse(_get_failing_data(agents)["error"])


class TestDashboardInfoMaintenance(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_dashboard_info_maintenance_count_respects_role(self):
        """Un usuario sin permiso sobre el cliente no debe ver ni su conteo.

        Si el conteo se calculara sin filter_by_role, el banner avisaría de equipos
        que el usuario no puede ni listar.
        """
        from accounts.models import Role, User

        site = baker.make("clients.Site")
        baker.make_recipe(
            "agents.online_agent",
            site=site,
            maintenance_mode=True,
            maintenance_mode_since=djangotime.now(),
        )

        r = self.client.get("/core/dashinfo/", format="json")
        self.assertEqual(r.data["maintenance_count"], 1)
        self.assertIsNotNone(r.data["maintenance_oldest_since"])

        # Usuario con rol que no alcanza ese cliente.
        role = baker.make("accounts.Role")
        role.can_view_clients.set([baker.make("clients.Client")])
        ciego = User.objects.create_user(username="ciego", password="hunter2")
        ciego.role = role
        ciego.save()
        self.client.force_authenticate(user=ciego)

        r = self.client.get("/core/dashinfo/", format="json")
        self.assertEqual(r.data["maintenance_count"], 0)
        self.assertIsNone(r.data["maintenance_oldest_since"])

        self.assertTrue(isinstance(role, Role))

    def test_maintenance_since_null_contract(self):
        """`since=None` cuenta en N pero no aporta al "más antiguo".

        Es el caso de la migración sobre flota viva: no se inventa fecha. Si todos
        son nulos, `maintenance_oldest_since` es None y el banner omite la frase de
        antigüedad en vez de decir "0 días".
        """
        site = baker.make("clients.Site")
        for _ in range(2):
            baker.make_recipe("agents.online_agent", site=site)
        # `.update()` a propósito: así es EXACTAMENTE como nace este estado en
        # producción — la migración sobre flota viva, que no inventa fecha. Pasar
        # since=None por el constructor no sirve, porque save() lo rellenaría.
        Agent.objects.filter(site=site).update(
            maintenance_mode=True, maintenance_mode_since=None
        )

        r = self.client.get("/core/dashinfo/", format="json")
        self.assertEqual(r.data["maintenance_count"], 2)
        self.assertIsNone(r.data["maintenance_oldest_since"])

        # Con uno fechado, el conteo sigue en 2 y el "más antiguo" es el que sí tiene
        # fecha — el nulo no lo desplaza ni lo anula.
        fechado = baker.make_recipe(
            "agents.online_agent",
            site=site,
            maintenance_mode=True,
            maintenance_mode_since=djangotime.now() - dt.timedelta(days=9),
        )

        r = self.client.get("/core/dashinfo/", format="json")
        self.assertEqual(r.data["maintenance_count"], 3)
        self.assertEqual(
            r.data["maintenance_oldest_since"], fechado.maintenance_mode_since
        )


class TestMaintenanceReminderTask(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.coresettings.maintenance_alert_enabled = True
        self.coresettings.maintenance_alert_days = 3
        self.coresettings.save()
        self.site = baker.make("clients.Site")

    def _agent(self, days=None):
        agent = baker.make_recipe("agents.online_agent", site=self.site)
        since = (
            None
            if days is None
            else djangotime.now() - dt.timedelta(days=days, hours=1)
        )
        # `.update()` y no save(): el sellado rellenaría el `since=None` del caso de
        # la migración, y para el resto evita depender de cómo se construye el objeto.
        Agent.objects.filter(pk=agent.pk).update(
            maintenance_mode=True, maintenance_mode_since=since
        )
        agent.refresh_from_db()
        return agent

    @patch("core.models.CoreSettings.send_mail")
    def test_maintenance_reminder_respects_threshold(self, send_mail):
        send_mail.return_value = ("ok", True)
        joven = self._agent(days=2)
        viejo = self._agent(days=4)

        self.assertEqual(maintenance_mode_reminder_task(), "reported 1 agents")

        viejo.refresh_from_db()
        joven.refresh_from_db()
        self.assertIsNotNone(viejo.maintenance_alert_sent_at)
        self.assertIsNone(joven.maintenance_alert_sent_at)

        # Al día siguiente no vuelve a disparar: la marca es lo que evita que esto
        # se convierta en un correo diario que la gente aprende a filtrar.
        self.assertEqual(maintenance_mode_reminder_task(), "no agents past threshold")
        self.assertEqual(send_mail.call_count, 1)

    @patch("core.models.CoreSettings.send_mail")
    def test_reminder_includes_agents_without_since(self, send_mail):
        """Contrato del nulo: sin fecha se trata como si YA hubiera cruzado."""
        send_mail.return_value = ("ok", True)
        sin_fecha = self._agent(days=None)

        self.assertEqual(maintenance_mode_reminder_task(), "reported 1 agents")

        sin_fecha.refresh_from_db()
        self.assertIsNotNone(sin_fecha.maintenance_alert_sent_at)
        self.assertIn("desconocido", send_mail.call_args[0][1])

    @patch("core.models.CoreSettings.send_mail")
    def test_reminder_does_not_mark_when_send_fails(self, send_mail):
        """🪤 `send_mail` se traga las fallas SMTP y devuelve (msg, bool).

        Si se marcara igual, una caída del SMTP se comería el aviso para siempre.
        """
        send_mail.return_value = ("SMTP messaging not configured.", False)
        agente = self._agent(days=5)

        self.assertIn("send failed", maintenance_mode_reminder_task())

        agente.refresh_from_db()
        self.assertIsNone(agente.maintenance_alert_sent_at)

    @patch("core.models.CoreSettings.send_mail")
    def test_reminder_disabled(self, send_mail):
        self.coresettings.maintenance_alert_enabled = False
        self.coresettings.save()
        self._agent(days=10)

        self.assertEqual(maintenance_mode_reminder_task(), "disabled")
        send_mail.assert_not_called()

    @patch("core.models.CoreSettings.send_mail")
    def test_reminder_marker_cleared_on_new_window(self, send_mail):
        """Bajar y volver a subir el flag es una ventana NUEVA: vuelve a avisar."""
        send_mail.return_value = ("ok", True)
        agente = self._agent(days=4)
        maintenance_mode_reminder_task()

        agente.refresh_from_db()
        agente.maintenance_mode = False
        agente.save()
        agente.refresh_from_db()
        self.assertIsNone(agente.maintenance_alert_sent_at)
