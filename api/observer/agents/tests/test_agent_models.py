"""Tests for Agent model — T007 (Feature 002).

Covers: Agent.status calculation (online/offline/overdue), get_agent_policies()
4-level inheritance, hex_mesh_node_id base64url→hex conversion.
Written for TDD: targets renamed observer.* module (after T010).
"""
import base64
import binascii
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.utils import timezone as djangotime
from model_bakery import baker

from agents.models import Agent
from observer.constants import AGENT_STATUS_OFFLINE, AGENT_STATUS_ONLINE, AGENT_STATUS_OVERDUE
from observer.test import TacticalTestCase


class TestAgentStatus(TacticalTestCase):
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


class TestGetAgentPolicies(TacticalTestCase):
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


class TestHexMeshNodeId(TacticalTestCase):
    def _b64url_to_hex(self, b64url: str) -> str:
        padded = b64url + "=" * (4 - len(b64url) % 4)
        raw = base64.urlsafe_b64decode(padded)
        return binascii.hexlify(raw).decode()

    def test_valid_base64url_converts_to_hex(self):
        raw_bytes = bytes.fromhex("0a1b2c3d4e5f")
        b64url = base64.urlsafe_b64encode(raw_bytes).decode().rstrip("=")
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site, mesh_node_id=b64url)
        self.assertEqual(agent.hex_mesh_node_id, "0a1b2c3d4e5f")

    def test_invalid_mesh_node_id_returns_error(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site, mesh_node_id="not_valid_@@")
        result = agent.hex_mesh_node_id
        self.assertEqual(result, "error")

    def test_real_meshcentral_id_format(self):
        raw_bytes = bytes.fromhex("deadbeefcafe1234567890abcdef1234")
        b64url = base64.urlsafe_b64encode(raw_bytes).decode().rstrip("=")
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site, mesh_node_id=b64url)
        self.assertEqual(agent.hex_mesh_node_id, "deadbeefcafe1234567890abcdef1234")
