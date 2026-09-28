"""Tools 🟡 de acción reversible (F1). Ninguna borra ni ejecuta código en el endpoint.

Las acciones de impacto (scripts, reboot, instalar updates) son F2 con confirmación
MRTR; erase, borrado de agentes, usuarios/keys, lost-mode y rawcmd no se exponen.
"""

# Sin `from __future__ import annotations`: el SDK evalúa las anotaciones y
# `max_agents` (tope de fan-out) es una variable local del registro.
from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from ..safety import FanOutError, check_fan_out
from . import Deps, call_rest

AgentId = Annotated[str, Field(min_length=1, max_length=128)]
AlertId = Annotated[int, Field(ge=1)]


def _action(idempotent: bool) -> ToolAnnotations:
    return ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=idempotent, openWorldHint=False)


def register(server: MCPServer, deps: Deps) -> None:
    max_agents = deps.settings.max_agents

    def agents_or_fail(agent_ids: list[str]) -> list[str]:
        try:
            return check_fan_out(agent_ids, max_agents)
        except FanOutError as exc:
            raise ToolError(str(exc)) from exc

    async def per_agent(ctx: Context, tool: str, agent_ids: list[str], method: str, path_fmt: str, body: Any = None):
        # Se valida el lote completo ANTES de la primera llamada: o todo o nada.
        results = []
        for agent_id in agents_or_fail(agent_ids):
            try:
                msg = await call_rest(deps, ctx, tool, method, path_fmt.format(agent_id=agent_id), json_body=body)
                results.append({"agent_id": agent_id, "ok": True, "message": msg})
            except ToolError as exc:
                results.append({"agent_id": agent_id, "ok": False, "error": str(exc)})
        return {"results": results, "ok": sum(r["ok"] for r in results), "failed": sum(not r["ok"] for r in results)}

    @server.tool(annotations=_action(False), description="Add a text note to an agent (visible in the dashboard).")
    async def add_note(
        ctx: Context, agent_id: AgentId, note: Annotated[str, Field(min_length=1, max_length=4000)]
    ) -> dict[str, Any]:
        msg = await call_rest(
            deps, ctx, "add_note", "POST", "/agents/notes/", json_body={"agent_id": agent_id, "note": note}
        )
        return {"agent_id": agent_id, "ok": True, "message": msg}

    @server.tool(
        annotations=_action(True),
        description=f"Ask agents to run all their health checks now. At most {max_agents} agents per call.",
    )
    async def run_checks(
        ctx: Context, agent_ids: Annotated[list[str], Field(min_length=1, max_length=max_agents)]
    ) -> dict[str, Any]:
        return await per_agent(ctx, "run_checks", agent_ids, "POST", "/checks/{agent_id}/run/")

    @server.tool(
        annotations=_action(True),
        description=(
            "Enable or disable maintenance mode (suppresses alerts) on agents. "
            f"At most {max_agents} agents per call."
        ),
    )
    async def set_maintenance_mode(
        ctx: Context,
        agent_ids: Annotated[list[str], Field(min_length=1, max_length=max_agents)],
        enabled: bool,
    ) -> dict[str, Any]:
        return await per_agent(
            ctx, "set_maintenance_mode", agent_ids, "PUT", "/agents/{agent_id}/", {"maintenance_mode": enabled}
        )

    @server.tool(annotations=_action(True), description="Snooze an alert for N days (it stops notifying until then).")
    async def snooze_alert(
        ctx: Context, alert_id: AlertId, days: Annotated[int, Field(ge=1, le=30)] = 1
    ) -> dict[str, Any]:
        msg = await call_rest(
            deps, ctx, "snooze_alert", "PUT", f"/alerts/{alert_id}/", json_body={"type": "snooze", "snooze_days": days}
        )
        return {"alert_id": alert_id, "ok": True, "message": msg}

    @server.tool(annotations=_action(True), description="Remove the snooze from an alert.")
    async def unsnooze_alert(ctx: Context, alert_id: AlertId) -> dict[str, Any]:
        msg = await call_rest(
            deps, ctx, "unsnooze_alert", "PUT", f"/alerts/{alert_id}/", json_body={"type": "unsnooze"}
        )
        return {"alert_id": alert_id, "ok": True, "message": msg}

    @server.tool(annotations=_action(True), description="Mark an alert as resolved.")
    async def resolve_alert(ctx: Context, alert_id: AlertId) -> dict[str, Any]:
        msg = await call_rest(deps, ctx, "resolve_alert", "PUT", f"/alerts/{alert_id}/", json_body={"type": "resolve"})
        return {"alert_id": alert_id, "ok": True, "message": msg}

    @server.tool(
        annotations=_action(False),
        description=(
            "Show a pop-up message to the user logged in on one agent's desktop. "
            "Use sparingly: it interrupts the user."
        ),
    )
    async def send_user_alert(
        ctx: Context,
        agent_id: AgentId,
        title: Annotated[str, Field(min_length=1, max_length=100)],
        message: Annotated[str, Field(min_length=1, max_length=1000)],
    ) -> dict[str, Any]:
        msg = await call_rest(
            deps,
            ctx,
            "send_user_alert",
            "POST",
            f"/agents/{agent_id}/alert/",
            json_body={"title": title, "message": message},
        )
        return {"agent_id": agent_id, "ok": True, "message": msg}
