"""REST de Observer simulada con httpx.MockTransport (sin red ni BD)."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Callable

import httpx
import pytest

from observer_mcp.config import Settings
from observer_mcp.rest_client import ObserverREST

VALID_KEY = "K" * 32

AGENTS = [
    {"id": 1, "hostname": "PC-CONTA-01", "agent_id": "aaa", "client": "Demo", "site": "Central"},
    {"id": 2, "hostname": "PC-CONTA-02", "agent_id": "bbb", "client": "Demo", "site": "Central"},
    {"id": 3, "hostname": "SRV-FILES", "agent_id": "ccc", "client": "Demo", "site": "DC"},
]
AGENT_DETAIL = {
    "hostname": "PC-CONTA-01",
    "agent_id": "aaa",
    "status": "online",
    "operating_system": "Windows 11 Pro, 64 bit v24H2 (build 26100.4349)",
    "bitlocker_recovery_key": "123456-654321",
    "mesh_node_id": "ABC",
    "all_timezones": ["x"] * 400,
}


class FakeREST:
    """Enruta (método, path) a respuestas; registra cada request recibido."""

    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.routes: dict[tuple[str, str], Callable[[httpx.Request], httpx.Response]] = {}
        self.valid_keys = {VALID_KEY}
        self.on("GET", "/core/version/", lambda r: httpx.Response(200, json="1.4.19"))
        self.on("GET", "/agents/", lambda r: httpx.Response(200, json=AGENTS))
        self.on("GET", "/agents/aaa/", lambda r: httpx.Response(200, json=AGENT_DETAIL))

    def on(self, method: str, path: str, handler: Callable[[httpx.Request], httpx.Response] | Any) -> None:
        if not callable(handler):
            value = handler
            handler = lambda r: httpx.Response(200, json=value)  # noqa: E731
        self.routes[(method, path)] = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if request.headers.get("x-api-key") not in self.valid_keys:
            return httpx.Response(401, json={"detail": "Invalid token."})
        handler = self.routes.get((request.method, request.url.path))
        if handler is None:
            return httpx.Response(404, json={"detail": "Not found."})
        return handler(request)

    def calls_to(self, path: str) -> list[httpx.Request]:
        return [c for c in self.calls if c.url.path == path]

    @staticmethod
    def body(request: httpx.Request) -> Any:
        return json.loads(request.content or b"null")


@pytest.fixture
def fake_rest() -> FakeREST:
    return FakeREST()


@pytest.fixture
def base_settings() -> Settings:
    return Settings(observer_url="http://observer.test", transport="stdio", api_key=VALID_KEY)


@pytest.fixture
def make_server(fake_rest, base_settings):
    from observer_mcp.server import build_server

    def _make(**overrides):
        settings = replace(base_settings, **overrides)
        rest = ObserverREST(settings, transport=httpx.MockTransport(fake_rest))
        server, _ = build_server(settings, rest)
        return server

    return _make
