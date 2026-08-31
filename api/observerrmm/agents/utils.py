import asyncio
import copy
import dataclasses
import logging
import urllib.parse
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from packaging import version as pyver

from checks.models import CheckResult
from core.utils import get_core_settings, get_mesh_device_id, get_mesh_ws_url
from observerrmm.constants import (
    AGENT_DEFER,
    AlertSeverity,
    CheckStatus,
    CheckType,
    MeshAgentIdent,
)
from observerrmm.helpers import notify_error

logger = logging.getLogger("ormm")


# Feature 038: cascada de contramedidas que dispara marcar un equipo como
# perdido/robado. Los campos coinciden 1:1 con los overrides de LostModePolicy
# (por equipo) y con los cascade_* de LostModeState (por caso).
_CASCADE_FIELDS = (
    "auto_lock",
    "lock_delay_min",
    "no_hibernate",
    "webcam_override",
    "alarm",
)


@dataclasses.dataclass
class LostModeCascade:
    auto_lock: bool
    lock_delay_min: int
    no_hibernate: bool
    webcam_override: bool
    alarm: bool


def resolve_lost_mode_cascade(agent, state=None, core=None) -> LostModeCascade:
    """Resuelve la cascada del modo perdido con precedencia **incidente > equipo > global**.

    - Global: los `lost_mode_*` de `CoreSettings` (siempre presentes, son la base).
    - Equipo: `LostModePolicy` del agente; cada campo no-nulo pisa al global.
    - Caso: los `cascade_*` de `LostModeState`; cada campo no-nulo pisa a todo.

    Regla única y central: nadie más resuelve esta precedencia. Vive acá para que
    el endpoint de config (polling) y el push por NATS entreguen exactamente el
    mismo valor, y para que un cambio de política no haya que replicarlo en dos
    lugares (watch item W002 de la feature 038).
    """
    core = core or get_core_settings()

    resolved = {
        "auto_lock": bool(core.lost_mode_auto_lock_enabled),
        "lock_delay_min": int(core.lost_mode_lock_delay_min),
        "no_hibernate": bool(core.lost_mode_no_hibernate_enabled),
        "webcam_override": bool(core.lost_mode_webcam_override_default),
        "alarm": bool(core.lost_mode_alarm_enabled),
    }

    # Import perezoso: evita el ciclo agents.models <-> agents.utils.
    from agents.models import LostModePolicy, LostModeState

    policy = LostModePolicy.objects.filter(agent=agent).first()
    if policy is not None:
        for field in _CASCADE_FIELDS:
            value = getattr(policy, field)
            if value is not None:
                resolved[field] = value

    if state is None:
        state = LostModeState.objects.filter(agent=agent).first()
    if state is not None:
        for field in _CASCADE_FIELDS:
            value = getattr(state, f"cascade_{field}")
            if value is not None:
                resolved[field] = value

    return LostModeCascade(**resolved)


def get_agent_url(*, goarch: str, plat: str, token: str = "") -> str:
    ver = settings.LATEST_AGENT_VER
    if token:
        params = {
            "version": ver,
            "arch": goarch,
            "token": token,
            "plat": plat,
            "api": settings.ALLOWED_HOSTS[0],
        }
        return settings.AGENTS_URL + urllib.parse.urlencode(params)

    ext = ".exe" if plat == "windows" else ""
    # CDN propio agents.observer.cl (AGENT_BASE_URL): sirve los binarios desde
    # infra propia en vez de github.com/.../releases. Mismo path que el release
    # de observer-agent-dist, poblado por scripts/appserver/observer-agents-cdn-publish.sh.
    return f"{settings.AGENT_BASE_URL}/releases/download/v{ver}/observeragent-v{ver}-{plat}-{goarch}{ext}"


def generate_linux_install(
    client: str,
    site: str,
    agent_type: str,
    arch: str,
    token: str,
    api: str,
    download_url: str,
) -> FileResponse:
    match arch:
        case "amd64":
            arch_id = MeshAgentIdent.LINUX64
        case "386":
            arch_id = MeshAgentIdent.LINUX32
        case "arm64":
            arch_id = MeshAgentIdent.LINUX_ARM_64
        case "arm":
            arch_id = MeshAgentIdent.LINUX_ARM_HF
        case _:
            arch_id = "not_found"

    core = get_core_settings()

    uri = get_mesh_ws_url()
    mesh_id = asyncio.run(get_mesh_device_id(uri, core.mesh_device_group))
    mesh_dl = (
        f"{core.mesh_site}/meshagents?id={mesh_id}&installflags=2&meshinstall={arch_id}"
    )

    text = Path(settings.LINUX_AGENT_SCRIPT).read_text()

    replace = {
        "agentDLChange": download_url,
        "meshDLChange": mesh_dl,
        # Alimenta el guard de arquitectura del script (CheckArch). Sin esto el
        # script no tiene contra qué comparar `uname -m` y sólo puede avisar.
        "archChange": arch,
        "clientIDChange": client,
        "siteIDChange": site,
        "agentTypeChange": agent_type,
        "tokenChange": token,
        "apiURLChange": api,
    }

    for i, j in replace.items():
        text = text.replace(i, j)

    text += "\n"
    with StringIO(text) as fp:
        return FileResponse(
            fp.read(), as_attachment=True, filename="observer_linux_install.sh"
        )


def generate_macos_install(
    client: str,
    site: str,
    agent_type: str,
    arch: str,
    token: str,
    api: str,
    download_url: str,
) -> FileResponse:
    match arch:
        case "arm64":
            arch_id = MeshAgentIdent.DARWIN_UNIVERSAL
        case _:
            arch_id = MeshAgentIdent.DARWIN_UNIVERSAL

    core = get_core_settings()

    uri = get_mesh_ws_url()
    try:
        mesh_id = asyncio.run(
            asyncio.wait_for(
                get_mesh_device_id(uri, core.mesh_device_group), timeout=10
            )
        )
    except asyncio.TimeoutError:
        logger.error(
            "MeshCentral timeout in generate_macos_install for client=%s site=%s",
            client,
            site,
        )
        return JsonResponse(
            {"error": "MeshCentral unavailable, retry later"}, status=503
        )
    mesh_dl = (
        f"{core.mesh_site}/meshagents?id={mesh_id}&installflags=2&meshinstall={arch_id}"
    )

    text = Path(settings.MACOS_AGENT_SCRIPT).read_text()

    replace = {
        "agentDLChange": download_url,
        "meshDLChange": mesh_dl,
        # Alimenta el guard de arquitectura del script (CheckArch). Sin esto el
        # script no tiene contra qué comparar `uname -m` y sólo puede avisar.
        "archChange": arch,
        "clientIDChange": client,
        "siteIDChange": site,
        "agentTypeChange": agent_type,
        "tokenChange": token,
        "apiURLChange": api,
    }

    for i, j in replace.items():
        text = text.replace(i, j)

    text += "\n"
    with StringIO(text) as fp:
        return FileResponse(
            fp.read(), as_attachment=True, filename="observer_macos_install.sh"
        )


def get_validated_agent(agent_id, min_version="2.10.0"):
    from .models import Agent

    agent = get_object_or_404(Agent.objects.defer(*AGENT_DEFER), agent_id=agent_id)

    if pyver.parse(agent.version) < pyver.parse(min_version):
        return notify_error(
            f"This feature requires agent version {min_version} or higher."
        )

    return agent


def send_nats_command(agent, func: str, payload: dict, timeout: int = 60):
    try:
        data = {"func": func, "payload": payload}
        response = asyncio.run(agent.nats_cmd(data, timeout=timeout))
    except Exception as e:
        return notify_error(f"NATS communication failed: {str(e)}")

    if response == "timeout":
        return notify_error("Unable to contact the agent")

    if isinstance(response, dict) and "error" in response:
        return notify_error(
            f"{func.replace('_', ' ').title()} failed: {response['error']}"
        )

    return response


def strip_relation_caches_for_cache(instances: list, keep: tuple = ("script",)) -> list:
    # returns shallow copies of model instances safe to pickle into redis cache
    # found when an appserver used an enormous amount of RAM for the redis cache: adding many
    # agents to policy exclusions made cached checks/tasks carry their select_related/prefetch
    # graph (check -> policy -> excluded_agents -> full agent rows with wmi_detail etc.),
    # blowing cache keys up to ~25 MB each instead of a few KB.
    # only relations listed in "keep" (e.g. check.script for the check runner) are preserved,
    # because consumers of the cached values need them.
    cleaned = []
    for instance in instances:
        obj = copy.copy(instance)
        obj._state = copy.copy(instance._state)
        obj._state.fields_cache = {
            field: value
            for field, value in instance._state.fields_cache.items()
            if field in keep
        }
        obj._prefetched_objects_cache = {}
        # results are attached per agent at runtime, never valid to cache
        obj.__dict__.pop("check_result", None)
        obj.__dict__.pop("task_result", None)
        cleaned.append(obj)
    return cleaned


def calculate_agent_checks(agent) -> dict:
    total, passing, failing, warning, info = 0, 0, 0, 0, 0

    for check in agent.get_checks_with_policies(exclude_overridden=True):
        total += 1
        if (
            not hasattr(check.check_result, "status")
            or isinstance(check.check_result, CheckResult)
            and check.check_result.status == CheckStatus.PASSING
        ):
            passing += 1
        elif (
            isinstance(check.check_result, CheckResult)
            and check.check_result.status == CheckStatus.FAILING
        ):
            alert_severity = (
                check.check_result.alert_severity
                if check.check_type
                in (
                    CheckType.MEMORY,
                    CheckType.CPU_LOAD,
                    CheckType.DISK_SPACE,
                    CheckType.SCRIPT,
                )
                else check.alert_severity
            )
            if alert_severity == AlertSeverity.ERROR:
                failing += 1
            elif alert_severity == AlertSeverity.WARNING:
                warning += 1
            elif alert_severity == AlertSeverity.INFO:
                info += 1

    ret = {
        "total": total,
        "passing": passing,
        "failing": failing,
        "warning": warning,
        "info": info,
        "has_failing_checks": failing > 0 or warning > 0,
    }
    return ret
