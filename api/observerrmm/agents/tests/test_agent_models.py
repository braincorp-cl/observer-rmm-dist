"""Tests for Agent model — origin: F002 T007 (dist scaffold), ported in F008 (D-02 rescue).

Covers: Agent.status calculation (online/offline/overdue), get_agent_policies()
4-level inheritance, hex_mesh_node_id base64url->hex conversion.
"""

from datetime import timedelta

from django.utils import timezone as djangotime
from model_bakery import baker

from observerrmm.constants import (
    AGENT_STATUS_OFFLINE,
    AGENT_STATUS_ONLINE,
    AGENT_STATUS_OVERDUE,
)
from observerrmm.test import ObserverTestCase


class TestAgentStatus(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _make_agent(self, **kwargs):
        site = baker.make("clients.Site")
        return baker.make("agents.Agent", site=site, **kwargs)

    def test_online_when_last_seen_is_recent(self):
        agent = self._make_agent(
            last_seen=djangotime.now() - timedelta(minutes=1),
            offline_time=4,
            overdue_time=30,
        )
        self.assertEqual(agent.status, AGENT_STATUS_ONLINE)

    def test_offline_when_last_seen_exceeds_offline_time(self):
        agent = self._make_agent(
            last_seen=djangotime.now() - timedelta(minutes=10),
            offline_time=4,
            overdue_time=30,
        )
        self.assertEqual(agent.status, AGENT_STATUS_OFFLINE)

    def test_overdue_when_last_seen_exceeds_overdue_time(self):
        agent = self._make_agent(
            last_seen=djangotime.now() - timedelta(minutes=60),
            offline_time=4,
            overdue_time=30,
        )
        self.assertEqual(agent.status, AGENT_STATUS_OVERDUE)

    def test_offline_when_last_seen_is_none(self):
        agent = self._make_agent(last_seen=None, offline_time=4, overdue_time=30)
        self.assertEqual(agent.status, AGENT_STATUS_OFFLINE)


class TestGetAgentPolicies(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_returns_four_policy_levels(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        policies = agent.get_agent_policies()
        # Must contain all 4 keys regardless of values
        self.assertIn("agent_policy", policies)
        self.assertIn("site_policy", policies)
        self.assertIn("client_policy", policies)
        self.assertIn("default_policy", policies)

    def test_agent_policy_overrides_site_policy(self):
        agent_policy = baker.make("automation.Policy", active=True)
        site_policy = baker.make("automation.Policy", active=True)
        site = baker.make("clients.Site", server_policy=site_policy)
        agent = baker.make(
            "agents.Agent", site=site, policy=agent_policy, monitoring_type="server"
        )
        policies = agent.get_agent_policies()
        self.assertEqual(policies.get("agent_policy"), agent_policy)
        self.assertEqual(policies.get("site_policy"), site_policy)

    def test_no_policies_returns_none_values(self):
        site = baker.make("clients.Site", server_policy=None)
        agent = baker.make(
            "agents.Agent", site=site, policy=None, monitoring_type="server"
        )
        policies = agent.get_agent_policies()
        self.assertIsNone(policies.get("agent_policy"))
        self.assertIsNone(policies.get("site_policy"))


class TestHexMeshNodeId(ObserverTestCase):
    # Real contract (ADR-009): mesh_node_id is stored as HEX; the property
    # converts it to the MeshCentral URL format (base64 with / -> $ and
    # + -> @ substitutions) via core.utils._b64_to_hex. The original F002
    # test assumed the inverse direction (b64url stored -> hex out) and
    # never ran against real code.

    def test_valid_hex_converts_to_mesh_b64(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site, mesh_node_id="0a1b2c3d4e5f")
        self.assertEqual(agent.hex_mesh_node_id, "ChssPU5f")

    def test_invalid_mesh_node_id_returns_error(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site, mesh_node_id="not_valid_@@")
        result = agent.hex_mesh_node_id
        self.assertEqual(result, "error")

    def test_real_meshcentral_id_format(self):
        # the mesh URL substitutions ($ and @) appear with this value
        site = baker.make("clients.Site")
        agent = baker.make(
            "agents.Agent",
            site=site,
            mesh_node_id="deadbeefcafe1234567890abcdef1234",
        )
        self.assertEqual(agent.hex_mesh_node_id, "3q2@78r@EjRWeJCrze8SNA==")


class TestWrongArchInstall(ObserverTestCase):
    """El agente de 32 bits sobre un Windows de 64 bits.

    El modo de falla que esto detecta es MUDO: el equipo se ve en línea y sano,
    pero su actualización nunca surte efecto —re-descarga el instalador cada
    hora, para siempre— y su inventario de software queda incompleto. Y no se
    corrige solo: `do_update` elige el instalador con el `goarch` que el propio
    agente reporta, así que un 386 pide 386 indefinidamente.
    """

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _make_agent(self, **kwargs):
        site = baker.make("clients.Site")
        return baker.make("agents.Agent", site=site, **kwargs)

    def test_386_sobre_windows_de_64_bits_se_marca(self):
        agent = self._make_agent(
            plat="windows",
            goarch="386",
            operating_system="Microsoft Windows 7 Professional, 64 bit v6.1.7601",
        )
        self.assertTrue(agent.wrong_arch_install)

    def test_386_sobre_windows_de_32_bits_no_se_marca(self):
        # El caso legítimo, y el que el banco de pruebas quería ejercitar.
        agent = self._make_agent(
            plat="windows",
            goarch="386",
            operating_system="Microsoft Windows 7 Professional, 32 bit v6.1.7601",
        )
        self.assertFalse(agent.wrong_arch_install)

    def test_amd64_sobre_windows_de_64_bits_no_se_marca(self):
        agent = self._make_agent(
            plat="windows",
            goarch="amd64",
            operating_system="Microsoft Windows 10 Pro, 64 bit v22H2",
        )
        self.assertFalse(agent.wrong_arch_install)

    def test_sin_operating_system_no_se_marca(self):
        # `arch` devuelve None y no hay nada que afirmar. Ante la duda NO se
        # acusa: una marca falsa manda a alguien a reinstalar un equipo sano.
        agent = self._make_agent(plat="windows", goarch="386", operating_system=None)
        self.assertFalse(agent.wrong_arch_install)

    def test_posix_nunca_se_marca(self):
        # En Linux y macOS `arch` devuelve el propio goarch, así que sin la guarda
        # de plataforma un agente 386 sobre Linux se marcaría solo.
        for plat in ("linux", "darwin"):
            with self.subTest(plat=plat):
                agent = self._make_agent(
                    plat=plat, goarch="386", operating_system="Debian 12, 64 bit"
                )
                self.assertFalse(agent.wrong_arch_install)
