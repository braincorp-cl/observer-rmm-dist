from unittest.mock import ANY, call, patch

from django.core.management import call_command
from model_bakery import baker

from observerrmm.constants import AgentMonType, AgentPlat
from observerrmm.test import ObserverTestCase


class TestBulkRestartAgents(ObserverTestCase):
    def setUp(self) -> None:
        self.authenticate()
        self.setup_coresettings()
        self.setup_base_instance()

    @patch("core.management.commands.bulk_restart_agents.sleep")
    @patch("agents.models.Agent.recover")
    @patch("core.management.commands.bulk_restart_agents.get_mesh_ws_url")
    def test_bulk_restart_agents_mgmt_cmd(
        self, get_mesh_ws_url, recover, mock_sleep
    ) -> None:
        get_mesh_ws_url.return_value = "https://mesh.example.com/test"

        baker.make_recipe(
            "agents.online_agent",
            site=self.site1,
            monitoring_type=AgentMonType.SERVER,
            plat=AgentPlat.WINDOWS,
        )

        baker.make_recipe(
            "agents.online_agent",
            site=self.site3,
            monitoring_type=AgentMonType.SERVER,
            plat=AgentPlat.LINUX,
        )

        # El backport v1.5.1 (Tier B/C/D) agregó `agent_url` a la llamada
        # "tacagent": la URL concreta depende de LATEST_AGENT_VER y del CDN
        # (configuración), así que acá se exige que el kwarg VENGA — ANY no
        # empareja si falta — y el contenido se verifica abajo.
        calls = [
            call(
                "tacagent",
                "https://mesh.example.com/test",
                wait=False,
                agent_url=ANY,
            ),
            call("mesh", "", wait=False),
        ]

        call_command("bulk_restart_agents")

        recover.assert_has_calls(calls)
        mock_sleep.assert_called_with(10)

        tacagent_urls = [
            c.kwargs["agent_url"]
            for c in recover.call_args_list
            if c.args and c.args[0] == "tacagent"
        ]
        self.assertEqual(len(tacagent_urls), 2)  # un agente Windows + uno Linux
        self.assertTrue(all(tacagent_urls), "agent_url no puede venir vacío")
