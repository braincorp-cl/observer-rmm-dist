from __future__ import annotations

import pytest

from observer_mcp.config import ConfigError, load_settings
from observer_mcp.safety import REDACTED, FanOutError, RateLimiter, check_fan_out, redact


def test_redact_anidado():
    data = {"a": 1, "items": [{"mesh_password": "x", "ok": {"api_key": "y", "name": "n"}}]}
    assert redact(data) == {"a": 1, "items": [{"mesh_password": REDACTED, "ok": {"api_key": REDACTED, "name": "n"}}]}


def test_fan_out():
    assert check_fan_out(["a", "a", " b "], 2) == ["a", "b"]
    with pytest.raises(FanOutError):
        check_fan_out(["a", "b", "c"], 2)
    with pytest.raises(FanOutError):
        check_fan_out(["", " "], 2)


def test_rate_limiter():
    t = [0.0]
    rl = RateLimiter(2, clock=lambda: t[0])
    assert rl.acquire("k") == 0 and rl.acquire("k") == 0
    assert rl.acquire("k") > 0
    assert rl.acquire("otra") == 0
    t[0] += 30
    assert rl.acquire("k") == 0


def test_config_http_rechaza_key_de_entorno():
    with pytest.raises(ConfigError):
        load_settings({"OBSERVER_URL": "https://x", "OBSERVER_API_KEY": "k"}, transport="http")


def test_config_stdio_exige_key():
    with pytest.raises(ConfigError):
        load_settings({"OBSERVER_URL": "https://x"}, transport="stdio")


def test_config_defaults_y_listas():
    s = load_settings({"OBSERVER_URL": "https://x/", "MCP_DISABLED_TOOLS": "a, b", "MCP_ALLOWED_HOSTS": "api.x.cl"})
    assert s.observer_url == "https://x" and s.max_agents == 10
    assert s.disabled_tools == frozenset({"a", "b"}) and "api.x.cl" in s.allowed_hosts


def test_config_entero_invalido():
    with pytest.raises(ConfigError):
        load_settings({"OBSERVER_URL": "https://x", "MCP_MAX_AGENTS": "0"})
