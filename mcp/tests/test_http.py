"""Puerta HTTP + transporte Streamable HTTP stateless, en memoria (ASGI)."""

from __future__ import annotations

from dataclasses import replace

import httpx
import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from observer_mcp.rest_client import ObserverREST
from observer_mcp.server import build_http_app

from .conftest import VALID_KEY

HOST = "api.observer.test"


@pytest.fixture
def http_app(fake_rest, base_settings):
    settings = replace(
        base_settings, transport="http", api_key=None, allowed_hosts=("127.0.0.1:*", HOST), rate_per_min=5
    )
    rest = ObserverREST(settings, transport=httpx.MockTransport(fake_rest))
    app, server, _ = build_http_app(settings, rest)
    return app, server


def _raw(app):
    return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=f"https://{HOST}")


async def test_health_sin_auth(http_app):
    app, _ = http_app
    async with _raw(app) as c:
        r = await c.get("/mcp/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


async def test_sin_bearer_401(http_app):
    app, _ = http_app
    async with _raw(app) as c:
        r = await c.post("/mcp", json={})
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Bearer")


async def test_key_invalida_401(http_app, fake_rest):
    app, _ = http_app
    async with _raw(app) as c:
        r = await c.post("/mcp", json={}, headers={"Authorization": "Bearer malo"})
    assert r.status_code == 401 and 'error="invalid_token"' in r.headers["www-authenticate"]
    assert fake_rest.calls_to("/core/version/")


async def test_token_en_query_400(http_app):
    app, _ = http_app
    async with _raw(app) as c:
        r = await c.post("/mcp?access_token=x", json={}, headers={"Authorization": f"Bearer {VALID_KEY}"})
    assert r.status_code == 400


async def test_get_405(http_app):
    app, _ = http_app
    async with _raw(app) as c:
        r = await c.get("/mcp", headers={"Authorization": f"Bearer {VALID_KEY}"})
    assert r.status_code == 405


async def test_rate_limit_429(http_app):
    app, server = http_app
    async with server.session_manager.run(), _raw(app) as c:
        codes = [
            (await c.post("/mcp?x=1", json={}, headers={"Authorization": f"Bearer {VALID_KEY}"})).status_code
            for _ in range(7)
        ]
    assert codes[-1] == 429


async def test_llamada_mcp_real_por_http(http_app, fake_rest):
    app, server = http_app
    headers = {"Authorization": f"Bearer {VALID_KEY}", "X-Forwarded-For": "203.0.113.9, 10.0.0.1"}
    async with server.session_manager.run():
        http = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), headers=headers)
        async with Client(streamable_http_client(f"https://{HOST}/mcp", http_client=http)) as c:
            tools = await c.list_tools()
            r = await c.call_tool("get_agent", {"agent_id": "aaa"})
    assert len(tools.tools) == 17
    assert r.structured_content["hostname"] == "PC-CONTA-01"
    req = fake_rest.calls_to("/agents/aaa/")[-1]
    assert req.headers["x-api-key"] == VALID_KEY
    assert req.headers["x-forwarded-for"] == "203.0.113.9"


async def test_host_no_permitido_rechazado(http_app):
    app, server = http_app
    async with server.session_manager.run():
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="https://evil.test") as c:
            r = await c.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                headers={"Authorization": f"Bearer {VALID_KEY}", "Accept": "application/json, text/event-stream"},
            )
    assert r.status_code in (400, 421)


@pytest.mark.parametrize(
    "code,texto",
    [("mcp_disabled", "disabled on this Observer RMM platform"), ("mcp_not_permitted", "role is not allowed")],
)
async def test_canal_cerrado_403_con_motivo(http_app, fake_rest, code, texto):
    fake_rest.on(
        "GET", "/core/version/", lambda r: httpx.Response(403, json={"detail": "x", "code": code})
    )
    app, _ = http_app
    async with _raw(app) as c:
        r = await c.post("/mcp", json={}, headers={"Authorization": f"Bearer {VALID_KEY}"})
    assert r.status_code == 403
    assert texto in r.json()["error"]
