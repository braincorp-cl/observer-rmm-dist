"""Tools in-process (transporte en memoria, credencial de stdio)."""

from __future__ import annotations

import httpx
from mcp import Client

from observer_mcp import __version__

# Capacidades 🔴 (nunca) y 🟠 (F2): ninguna tool de F1 puede mencionarlas.
FORBIDDEN = (
    "erase",
    "wipe",
    "rawcmd",
    "command",
    "lost",
    "delete",
    "remove",
    "apikey",
    "api_key",
    "create_user",
    "role",
    "reboot",
    "shutdown",
    "script",
    "uninstall",
    "install_updates",
)


async def test_catalogo_17_tools_sin_prohibidas(make_server):
    async with Client(make_server()) as c:
        names = [t.name for t in (await c.list_tools()).tools]
    assert len(names) == 17
    assert not [n for n in names if any(f in n for f in FORBIDDEN)]


async def test_lecturas_son_read_only(make_server):
    async with Client(make_server()) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert tools["get_agent"].annotations.read_only_hint is True
    assert tools["add_note"].annotations.read_only_hint is False
    assert tools["add_note"].annotations.destructive_hint is False


async def test_tool_deshabilitada_no_aparece(make_server):
    async with Client(make_server(disabled_tools=frozenset({"send_user_alert"}))) as c:
        names = [t.name for t in (await c.list_tools()).tools]
    assert "send_user_alert" not in names and len(names) == 16


async def test_search_agents_filtra_y_manda_headers(make_server, fake_rest):
    async with Client(make_server()) as c:
        r = await c.call_tool("search_agents", {"query": "conta"})
    assert not r.is_error
    assert [a["hostname"] for a in r.structured_content["items"]] == ["PC-CONTA-01", "PC-CONTA-02"]
    req = fake_rest.calls_to("/agents/")[0]
    assert req.url.params["detail"] == "false"
    assert req.headers["x-observer-client"] == f"mcp/{__version__} tool=search_agents"


async def test_search_agents_cachea(make_server, fake_rest):
    async with Client(make_server()) as c:
        await c.call_tool("search_agents", {"query": "a"})
        await c.call_tool("search_agents", {"query": "b"})
    assert len(fake_rest.calls_to("/agents/")) == 1


async def test_get_agent_lista_blanca_y_redaccion(make_server):
    async with Client(make_server()) as c:
        r = await c.call_tool("get_agent", {"agent_id": "aaa"})
    data = r.structured_content
    assert data["status"] == "online"
    for leaked in ("bitlocker_recovery_key", "mesh_node_id", "all_timezones"):
        assert leaked not in data


async def test_403_de_la_rest_es_error_de_tool(make_server, fake_rest):
    fake_rest.on("GET", "/agents/zzz/", lambda r: httpx.Response(403, json={"detail": "nope"}))
    async with Client(make_server()) as c:
        r = await c.call_tool("get_agent", {"agent_id": "zzz"})
    assert r.is_error
    assert "permission denied" in r.content[0].text


async def test_fan_out_excedido_no_llama_a_la_rest(make_server, fake_rest):
    ids = [f"a{i}" for i in range(11)]
    async with Client(make_server()) as c:
        r = await c.call_tool("run_checks", {"agent_ids": ids})
    assert r.is_error
    assert not [c for c in fake_rest.calls if "/run/" in c.url.path]


async def test_run_checks_por_agente(make_server, fake_rest):
    fake_rest.on("POST", "/checks/aaa/run/", "Checks will now be run on PC-CONTA-01")
    fake_rest.on("POST", "/checks/bbb/run/", lambda r: httpx.Response(400, json="Unable to contact the agent"))
    async with Client(make_server()) as c:
        r = await c.call_tool("run_checks", {"agent_ids": ["aaa", "bbb", "aaa"]})
    out = r.structured_content
    assert out["ok"] == 1 and out["failed"] == 1
    assert len(fake_rest.calls_to("/checks/aaa/run/")) == 1  # duplicado eliminado


async def test_maintenance_usa_put_por_agente(make_server, fake_rest):
    fake_rest.on("PUT", "/agents/aaa/", "The agent was updated successfully")
    async with Client(make_server()) as c:
        await c.call_tool("set_maintenance_mode", {"agent_ids": ["aaa"], "enabled": True})
    req = fake_rest.calls_to("/agents/aaa/")[-1]
    assert req.method == "PUT" and fake_rest.body(req) == {"maintenance_mode": True}
    assert not fake_rest.calls_to("/agents/maintenance/bulk/")


async def test_snooze_manda_snooze_days(make_server, fake_rest):
    fake_rest.on("PUT", "/alerts/5/", "ok")
    async with Client(make_server()) as c:
        await c.call_tool("snooze_alert", {"alert_id": 5, "days": 3})
    assert fake_rest.body(fake_rest.calls_to("/alerts/5/")[0]) == {"type": "snooze", "snooze_days": 3}


async def test_list_alerts_filtros(make_server, fake_rest):
    fake_rest.on("PATCH", "/alerts/", [{"id": 1, "severity": "error", "message": "disk", "hidden": False}])
    async with Client(make_server()) as c:
        r = await c.call_tool("list_alerts", {"days": 2, "client_id": 7})
    body = fake_rest.body(fake_rest.calls_to("/alerts/")[0])
    assert body == {"timeFilter": 2, "resolvedFilter": False, "snoozedFilter": False, "clientFilter": [7]}
    assert r.structured_content["items"] == [{"id": 1, "severity": "error", "message": "disk"}]


async def test_truncado(make_server, fake_rest):
    many = [{"id": i, "hostname": f"H{i:05d}", "agent_id": f"id{i}", "client": "C", "site": "S"} for i in range(5000)]
    fake_rest.on("GET", "/agents/", many)
    async with Client(make_server(max_response_chars=2000)) as c:
        r = await c.call_tool("search_agents", {})
    out = r.structured_content
    assert out["truncated"] is True and out["total"] == 5000 and 0 < out["returned"] < 5000


async def test_resource_de_agente(make_server):
    async with Client(make_server()) as c:
        r = await c.read_resource("observer://agent/aaa")
    assert "PC-CONTA-01" in r.contents[0].text and "recovery" not in r.contents[0].text


async def test_canal_cerrado_a_mitad_de_sesion_explica_el_motivo(make_server, fake_rest):
    # El admin apaga el MCP con la caché de auth aún vigente: la tool igual lo dice.
    fake_rest.on(
        "GET", "/agents/zzz/", lambda r: httpx.Response(403, json={"detail": "x", "code": "mcp_disabled"})
    )
    async with Client(make_server()) as c:
        r = await c.call_tool("get_agent", {"agent_id": "zzz"})
    assert r.is_error
    assert "disabled on this Observer RMM platform" in r.content[0].text
