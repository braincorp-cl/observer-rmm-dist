"""F009 (GAP-030 / RN-02): agent check-in intervals must stay anti-OOM safe.

get_agent_config() must never return an interval below the production floor —
neither from settings nor from the getattr fallback when a CHECKIN_* line is
missing. Floors = the min of each production (min, max) tuple in settings.py.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apiv3 import utils as apiv3_utils

# Min of each production anti-OOM interval (settings.py CHECKIN_* block).
ANTI_OOM_FLOORS = {
    "checkin_hello": 200,
    "checkin_agentinfo": 24000,
    "checkin_winsvc": 24000,
    "checkin_pubip": 3000,
    "checkin_disks": 240000,
    "checkin_sw": 50000,
    "checkin_wmi": 24000,
    "checkin_syncmesh": 3600,
}


class TestAgentConfigAntiOOM(SimpleTestCase):
    def test_configured_intervals_respect_floor(self):
        cfg = apiv3_utils.get_agent_config()
        for field, floor in ANTI_OOM_FLOORS.items():
            self.assertGreaterEqual(
                getattr(cfg, field), floor, msg=f"{field} below anti-OOM floor"
            )

    def test_fallbacks_safe_when_settings_missing(self):
        # Simulate every CHECKIN_* line removed from settings: the getattr
        # fallbacks in get_agent_config must still be anti-OOM safe.
        empty = SimpleNamespace()
        with patch.object(apiv3_utils, "settings", empty):
            cfg = apiv3_utils.get_agent_config()
        for field, floor in ANTI_OOM_FLOORS.items():
            self.assertGreaterEqual(
                getattr(cfg, field),
                floor,
                msg=f"{field} fallback below anti-OOM floor",
            )
