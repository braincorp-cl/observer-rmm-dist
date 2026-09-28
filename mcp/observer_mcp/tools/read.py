"""Tools 🟢 de solo lectura (F1)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from ..safety import pick, truncate_list
from . import UNTRUSTED, Deps, cached, call_rest, cred_fp, store

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

AgentId = Annotated[str, Field(min_length=1, max_length=128, description="Observer agent_id (from search_agents).")]
Days = Annotated[int, Field(ge=1, le=90)]

AGENT_FIELDS = (
    "hostname",
    "agent_id",
    "client",
    "site_name",
    "status",
    "description",
    "operating_system",
    "plat",
    "version",
    "last_seen",
    "boot_time",
    "logged_in_username",
    "last_logged_in_user",
    "public_ip",
    "local_ips",
    "cpu_model",
    "total_ram",
    "make_model",
    "serial_number",
    "physical_disks",
    "disks",
    "graphics",
    "needs_reboot",
    "maintenance_mode",
    "monitoring_type",
    "time_zone",
    "timezone",
    "patches_last_installed",
    "checks",
)
ALERT_FIELDS = (
    "id",
    "hostname",
    "agent_id",
    "client",
    "site",
    "alert_type",
    "severity",
    "message",
    "alert_time",
    "snoozed",
    "snooze_until",
    "resolved",
    "resolved_on",
)
CHECK_FIELDS = (
    "id",
    "name",
    "readable_desc",
    "check_type",
    "alert_severity",
    "check_result",
    "run_interval",
    "last_run",
    "managed_by_policy",
)
CHECK_RESULT_FIELDS = ("status", "alert_severity", "more_info", "last_run", "fail_count", "retcode", "stdout")
UPDATE_FIELDS = ("id", "kb", "title", "severity", "installed", "downloaded", "action", "result", "date_installed")
HISTORY_FIELDS = ("id", "time", "type", "command", "username", "status", "script_name", "results")
AUDIT_FIELDS = ("id", "entry_time", "username", "agent", "agent_id", "action", "object_type", "message", "ip_address")


def register(server: MCPServer, deps: Deps) -> None:
    s = deps.settings

    def listing(items: Any, fields: tuple[str, ...]) -> dict[str, Any]:
        rows = [pick(i, fields) for i in (items or []) if isinstance(i, dict)]
        return truncate_list(rows, s.max_response_chars)

    @server.tool(annotations=READ_ONLY, description="List the clients (organizations) visible to the caller.")
    async def list_clients(ctx: Context) -> dict[str, Any]:
        data = await call_rest(deps, ctx, "list_clients", "GET", "/clients/")
        return listing(data, ("id", "name", "agent_count", "maintenance_mode"))

    @server.tool(annotations=READ_ONLY, description="List the sites visible to the caller, optionally for one client.")
    async def list_sites(ctx: Context, client_id: int | None = None) -> dict[str, Any]:
        data = await call_rest(deps, ctx, "list_sites", "GET", "/clients/sites/")
        if client_id is not None:
            data = [d for d in data or [] if d.get("client") == client_id]
        return listing(data, ("id", "name", "client", "client_name", "agent_count", "maintenance_mode"))

    @server.tool(
        annotations=READ_ONLY,
        description="Find agents (managed endpoints) by hostname substring, optionally scoped to a client or site. "
        "Returns agent_id values used by the other tools." + UNTRUSTED,
    )
    async def search_agents(
        ctx: Context,
        query: Annotated[str, Field(max_length=100, description="Hostname substring; empty lists all.")] = "",
        client_id: int | None = None,
        site_id: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"detail": "false"}
        if site_id is not None:
            params["site"] = site_id
        elif client_id is not None:
            params["client"] = client_id
        key = ("agents", cred_fp(deps, ctx), params.get("site"), params.get("client"))
        data = cached(deps, key, 60)
        if data is None:
            data = await call_rest(deps, ctx, "search_agents", "GET", "/agents/", params=params)
            store(deps, key, 60, data)
        q = query.strip().lower()
        rows = [a for a in data or [] if not q or q in str(a.get("hostname", "")).lower()]
        rows.sort(key=lambda a: str(a.get("hostname", "")).lower())
        return listing(rows, ("hostname", "agent_id", "client", "site"))

    @server.tool(
        annotations=READ_ONLY, description="Get status, hardware, OS and health summary of one agent." + UNTRUSTED
    )
    async def get_agent(ctx: Context, agent_id: AgentId) -> dict[str, Any]:
        data = await call_rest(deps, ctx, "get_agent", "GET", f"/agents/{agent_id}/")
        return pick(data or {}, AGENT_FIELDS)

    @server.tool(
        annotations=READ_ONLY,
        description="List alerts from the last N days. By default only active ones (not resolved, not snoozed)."
        + UNTRUSTED,
    )
    async def list_alerts(
        ctx: Context,
        days: Days = 7,
        client_id: int | None = None,
        severity: list[Literal["info", "warning", "error"]] | None = None,
        include_resolved: bool = False,
        include_snoozed: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"timeFilter": days}
        if not include_resolved:
            body["resolvedFilter"] = False
        if not include_snoozed:
            body["snoozedFilter"] = False
        if client_id is not None:
            body["clientFilter"] = [client_id]
        if severity:
            body["severityFilter"] = severity
        data = await call_rest(deps, ctx, "list_alerts", "PATCH", "/alerts/", json_body=body)
        return listing(data, ALERT_FIELDS)

    @server.tool(
        annotations=READ_ONLY, description="List the health checks of one agent with their last result." + UNTRUSTED
    )
    async def get_checks(ctx: Context, agent_id: AgentId) -> dict[str, Any]:
        data = await call_rest(deps, ctx, "get_checks", "GET", f"/agents/{agent_id}/checks/")
        rows = []
        for c in data or []:
            row = pick(c, CHECK_FIELDS)
            if isinstance(row.get("check_result"), dict):
                row["check_result"] = pick(row["check_result"], CHECK_RESULT_FIELDS)
            rows.append(row)
        return truncate_list(rows, s.max_response_chars)

    @server.tool(
        annotations=READ_ONLY, description="List Windows updates known for one agent; pending ones by default."
    )
    async def get_pending_updates(ctx: Context, agent_id: AgentId, include_installed: bool = False) -> dict[str, Any]:
        data = await call_rest(deps, ctx, "get_pending_updates", "GET", f"/winupdate/{agent_id}/")
        rows = [u for u in data or [] if include_installed or not u.get("installed")]
        return listing(rows, UPDATE_FIELDS)

    @server.tool(
        annotations=READ_ONLY,
        description="List software installed on one agent, optionally filtered by name." + UNTRUSTED,
    )
    async def get_software(
        ctx: Context, agent_id: AgentId, name: Annotated[str, Field(max_length=100)] = ""
    ) -> dict[str, Any]:
        data = await call_rest(deps, ctx, "get_software", "GET", f"/software/{agent_id}/")
        items = data.get("software", []) if isinstance(data, dict) else (data or [])
        q = name.strip().lower()
        rows = [i for i in items if isinstance(i, dict) and (not q or q in str(i.get("name", "")).lower())]
        return listing(rows, ("name", "version", "publisher", "install_date", "size"))

    @server.tool(annotations=READ_ONLY, description="Recent command and script history of one agent." + UNTRUSTED)
    async def agent_history(ctx: Context, agent_id: AgentId) -> dict[str, Any]:
        data = await call_rest(deps, ctx, "agent_history", "GET", f"/agents/{agent_id}/history/")
        return listing(data, HISTORY_FIELDS)

    @server.tool(
        annotations=READ_ONLY,
        description="Query the audit log (who did what) for the last N days, optionally by agent, client or user.",
    )
    async def get_audit_log(
        ctx: Context,
        days: Days = 7,
        agent_id: str | None = None,
        client_id: int | None = None,
        username: str | None = None,
        page: Annotated[int, Field(ge=1)] = 1,
        page_size: Annotated[int, Field(ge=1, le=200)] = 50,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "timeFilter": days,
            "pagination": {"sortBy": "entry_time", "descending": True, "page": page, "rowsPerPage": page_size},
        }
        if agent_id:
            body["agentFilter"] = [agent_id]
        elif client_id is not None:
            body["clientFilter"] = [client_id]
        if username:
            body["userFilter"] = [username]
        data = await call_rest(deps, ctx, "get_audit_log", "PATCH", "/logs/audit/", json_body=body)
        data = data or {}
        out = listing(data.get("audit_logs", []), AUDIT_FIELDS)
        out["total"] = data.get("total", out["total"])
        out["page"] = page
        return out
