"""Feature 030 · modo perdido/robado — endpoint de marcar y recuperar (ADR-025).

Homologación del `missing`/`report stolen` de Prey (backlog 024), con la
gobernanza que su cliente no tiene: motivo obligatorio, permiso dedicado y
auditoría propia.

Lo que se prueba acá es lo que puede romperse en silencio:

- que marcar un equipo **apagado o sin red** siga siendo un éxito. Es la
  diferencia de diseño con `lock`/`alert`/`alarm`: aquellas fallan si el agente
  no contesta, ésta no puede, porque el caso de uso central es justamente un
  equipo que ya no está;
- que la auditoría quede escrita SIEMPRE, incluso cuando el push por NATS se
  pierde — si no, un caso abierto podría no tener autor;
- que el motivo vacío se rechace con el código que la consola sabe traducir;
- que el intervalo se acote de verdad en los dos extremos;
- que el permiso nuevo no lo habiliten los de la 028, y que el listado —que no
  lleva `agent_id` en la ruta— no reviente ni filtre equipos ajenos.
"""

from unittest.mock import patch

from model_bakery import baker

from agents.models import LostModeState
from logs.models import AuditLog
from observerrmm.constants import (
    LOST_MODE_MAX_INTERVAL_MIN,
    LOST_MODE_MIN_INTERVAL_MIN,
    AuditActionType,
)
from observerrmm.test import ObserverTestCase

base_url = "/agents"


class TestLostMode(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()
        self.agent = baker.make_recipe("agents.agent")
        self.url = f"{base_url}/{self.agent.agent_id}/lostmode/"

    # ------------------------------------------------------------- marcar

    @patch("agents.models.Agent.nats_cmd")
    def test_marcar_perdido(self, nats_cmd):
        nats_cmd.return_value = "ok"

        r = self.client.post(self.url, {"reason": "robo, ticket #4821"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["nats_delivered"])

        estado = LostModeState.objects.get(agent=self.agent)
        self.assertTrue(estado.active)
        self.assertEqual(estado.reason, "robo, ticket #4821")
        self.assertIsNotNone(estado.marked_at)
        self.assertIsNone(estado.recovered_at)

        # El payload tiene que ser exactamente el que el agente espera: un typo
        # en `func` o en una clave no falla, el agente sólo ignora el mensaje.
        nats_cmd.assert_called_with(
            {
                "func": "lost_mode",
                "payload": {"active": "1", "interval_min": "5"},
            },
            timeout=15,
        )

        self.check_not_authenticated("post", self.url)

    @patch("agents.models.Agent.nats_cmd")
    def test_marcar_equipo_apagado_es_exito(self, nats_cmd):
        """El caso de uso central: el equipo ya no contesta cuando lo marcan.

        Con `_endpoint_response()` esto habría sido un 400 y el operador no
        habría podido abrir el caso justo en el escenario para el que existe la
        feature. La BD es la fuente de verdad; el push es best-effort.
        """
        nats_cmd.return_value = "timeout"

        r = self.client.post(self.url, {"reason": "no aparece"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["nats_delivered"])
        self.assertTrue(LostModeState.objects.get(agent=self.agent).active)

    @patch("agents.models.Agent.nats_cmd")
    def test_auditoria_incluso_sin_agente(self, nats_cmd):
        """Un caso abierto no puede quedar sin autor porque el equipo no contesta."""
        nats_cmd.side_effect = Exception("nats caido")

        r = self.client.post(self.url, {"reason": "hurto en terreno"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["nats_delivered"])

        log = AuditLog.objects.get(action=AuditActionType.LOST_MODE)
        self.assertEqual(log.agent_id, self.agent.agent_id)
        self.assertEqual(log.after_value, "hurto en terreno")
        # El bypass del interruptor global de geo queda escrito, no implícito.
        self.assertIn("overrides", log.message)

    @patch("agents.models.Agent.nats_cmd")
    def test_motivo_obligatorio(self, nats_cmd):
        nats_cmd.return_value = "ok"

        for cuerpo in ({}, {"reason": ""}, {"reason": "   "}):
            r = self.client.post(self.url, cuerpo, format="json")
            self.assertEqual(r.status_code, 400)
            # Con el prefijo que el interceptor de axios necesita para
            # traducirlo; sin él el operador ve el código crudo en pantalla.
            self.assertIn("endpoint_response:empty_reason", r.data)

        self.assertFalse(LostModeState.objects.filter(agent=self.agent).exists())
        nats_cmd.assert_not_called()

    @patch("agents.models.Agent.nats_cmd")
    def test_intervalo_acotado(self, nats_cmd):
        nats_cmd.return_value = "ok"

        # El fallback de un valor ilegible es el intervalo VIGENTE, no el default
        # del modelo: re-marcar sin especificar cadencia no debe pisar en
        # silencio la que el operador ya había elegido para ese caso.
        casos = [
            (0, LOST_MODE_MIN_INTERVAL_MIN),
            (-5, LOST_MODE_MIN_INTERVAL_MIN),
            (999, LOST_MODE_MAX_INTERVAL_MIN),
            (15, 15),
            ("no es un numero", 15),
            (None, 15),
        ]
        for pedido, esperado in casos:
            r = self.client.post(
                self.url,
                {"reason": "x", "interval_min": pedido},
                format="json",
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["interval_min"], esperado, f"pedido={pedido}")
            self.assertEqual(
                LostModeState.objects.get(agent=self.agent).interval_min, esperado
            )

    @patch("agents.models.Agent.nats_cmd")
    def test_remarcar_limpia_la_recuperacion_anterior(self, nats_cmd):
        """Un caso reabierto no arrastra la fecha de recuperación del anterior."""
        nats_cmd.return_value = "ok"

        self.client.post(self.url, {"reason": "primero"}, format="json")
        self.client.delete(self.url, format="json")
        self.assertIsNotNone(LostModeState.objects.get(agent=self.agent).recovered_at)

        self.client.post(self.url, {"reason": "segundo"}, format="json")
        estado = LostModeState.objects.get(agent=self.agent)
        self.assertTrue(estado.active)
        self.assertIsNone(estado.recovered_at)
        self.assertEqual(estado.reason, "segundo")

    # ---------------------------------------------------------- recuperar

    @patch("agents.models.Agent.nats_cmd")
    def test_recuperar(self, nats_cmd):
        nats_cmd.return_value = "ok"

        self.client.post(self.url, {"reason": "robo"}, format="json")
        r = self.client.delete(self.url, format="json")
        self.assertEqual(r.status_code, 200)

        estado = LostModeState.objects.get(agent=self.agent)
        self.assertFalse(estado.active)
        self.assertIsNotNone(estado.recovered_at)
        # El motivo del marcaje original se conserva.
        self.assertEqual(estado.reason, "robo")

        nats_cmd.assert_called_with(
            {
                "func": "lost_mode",
                "payload": {"active": "0", "interval_min": "5"},
            },
            timeout=15,
        )

        self.assertEqual(
            AuditLog.objects.filter(action=AuditActionType.LOST_MODE).count(), 2
        )
        self.check_not_authenticated("delete", self.url)

    @patch("agents.models.Agent.nats_cmd")
    def test_recuperar_equipo_nunca_marcado_no_revienta(self, nats_cmd):
        """Doble clic, o una consola con estado viejo. No debe dar 500."""
        nats_cmd.return_value = "ok"

        r = self.client.delete(self.url, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(LostModeState.objects.get(agent=self.agent).active)

    # -------------------------------------------------------------- listado

    @patch("agents.models.Agent.nats_cmd")
    def test_listado_solo_trae_los_activos(self, nats_cmd):
        nats_cmd.return_value = "ok"
        otro = baker.make_recipe("agents.agent")

        self.client.post(self.url, {"reason": "robo"}, format="json")
        url_otro = f"{base_url}/{otro.agent_id}/lostmode/"
        self.client.post(url_otro, {"reason": "extravio"}, format="json")
        self.client.delete(url_otro, format="json")

        url = f"{base_url}/lostmode/"
        r = self.client.get(url, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["agent_id"], self.agent.agent_id)
        self.assertEqual(r.data[0]["hostname"], self.agent.hostname)
        self.assertEqual(r.data[0]["reason"], "robo")

        self.check_not_authenticated("get", url)


class TestLostModePermissions(ObserverTestCase):
    def setUp(self):
        self.setup_client()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.agent")

    @patch("agents.models.Agent.nats_cmd")
    def test_permiso_dedicado(self, nats_cmd):
        """Los permisos de la 028 no habilitan el modo perdido, ni al revés."""
        nats_cmd.return_value = "ok"

        url = f"{base_url}/{self.agent.agent_id}/lostmode/"
        ajeno = baker.make_recipe("agents.agent")
        url_ajeno = f"{base_url}/{ajeno.agent_id}/lostmode/"
        cuerpo = {"reason": "robo"}

        user = self.create_user_with_roles([])
        self.client.force_authenticate(user=user)

        self.check_not_authorized("post", url, cuerpo)

        # los de la 028 no alcanzan
        for otro in ("can_send_alerts", "can_lock_agents", "can_sound_alarm"):
            setattr(user.role, otro, True)
        user.role.save()
        self.check_not_authorized("post", url, cuerpo)

        # ver evidencia tampoco habilita a operar: son capacidades distintas
        user.role.can_view_lost_evidence = True
        user.role.save()
        self.check_not_authorized("post", url, cuerpo)

        user.role.can_manage_lost_mode = True
        user.role.save()
        self.check_authorized("post", url, cuerpo)
        self.check_authorized("delete", url, cuerpo)

        # el permiso global no basta si el rol no alcanza a ese cliente
        user.role.can_view_clients.set([self.agent.client])
        self.check_authorized("post", url, cuerpo)
        self.check_not_authorized("post", url_ajeno, cuerpo)

    @patch("agents.models.Agent.nats_cmd")
    def test_listado_no_revienta_sin_agent_id_y_filtra_por_rol(self, nats_cmd):
        """El listado no lleva `agent_id`: leerlo a secas daría KeyError.

        Y además tiene que recortarse por alcance, o sería una fuga de qué
        equipos de otros clientes están marcados como perdidos.
        """
        nats_cmd.return_value = "ok"
        ajeno = baker.make_recipe("agents.agent")

        self.authenticate()
        for a in (self.agent, ajeno):
            self.client.post(
                f"{base_url}/{a.agent_id}/lostmode/", {"reason": "robo"}, format="json"
            )

        url = f"{base_url}/lostmode/"
        user = self.create_user_with_roles([])
        self.client.force_authenticate(user=user)
        self.check_not_authorized("get", url)

        user.role.can_manage_lost_mode = True
        user.role.save()
        r = self.check_authorized("get", url)
        # sin clientes asignados el rol ve todo lo que su alcance permite
        self.assertEqual(len(r.data), 2)

        user.role.can_view_clients.set([self.agent.client])
        r = self.client.get(url, format="json")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["agent_id"], self.agent.agent_id)
