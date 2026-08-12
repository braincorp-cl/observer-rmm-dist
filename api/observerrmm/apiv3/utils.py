import random

from django.conf import settings

from observerrmm.structs import AgentCheckInConfig


def _geo_tracking_enabled() -> bool:
    # Feature 023: interruptor GLOBAL. Se lee de CoreSettings; ante cualquier
    # problema se asume apagado (fail-safe: nunca activar geolocalización por error).
    try:
        from core.utils import get_core_settings

        return bool(get_core_settings().geo_tracking_enabled)
    except Exception:
        return False


def _geo_force_location_on() -> bool:
    # Gap 3: force-on del sensor de ubicación/radio WiFi en el endpoint. GLOBAL;
    # fail-safe apagado. Solo aplica si además geo_tracking_enabled=True (el agente
    # ya lo condiciona, pero aquí también degradamos a False si el track está off).
    try:
        from core.utils import get_core_settings

        cs = get_core_settings()
        return bool(cs.geo_tracking_enabled and cs.geo_force_location_on)
    except Exception:
        return False


def _lost_mode(agentid: str) -> tuple[bool, int]:
    """Feature 030: estado de modo perdido de ESTE agente.

    Fail-safe apagado, igual que los interruptores de geo: ante cualquier
    problema —agente inexistente, tabla no migrada, BD con hipo— se responde
    "no está perdido". Encender una recolección de evidencia por un error de
    lectura sería el peor fallo posible de esta feature.
    """
    try:
        from agents.models import LostModeState

        state = LostModeState.objects.filter(agent__agent_id=agentid).first()
        if not state or not state.active:
            return False, 0

        return True, state.interval_min
    except Exception:
        return False, 0


def get_agent_config(agentid: str = "") -> AgentCheckInConfig:
    lost_mode, lost_mode_interval_min = _lost_mode(agentid)

    return AgentCheckInConfig(
        # Fallbacks aligned to the anti-OOM production defaults in settings.py:
        # losing a CHECKIN_* line must never degrade to a more aggressive interval.
        checkin_hello=random.randint(*getattr(settings, "CHECKIN_HELLO", (200, 400))),
        checkin_agentinfo=random.randint(
            *getattr(settings, "CHECKIN_AGENTINFO", (24000, 40000))
        ),
        checkin_winsvc=random.randint(
            *getattr(settings, "CHECKIN_WINSVC", (24000, 30000))
        ),
        checkin_pubip=random.randint(*getattr(settings, "CHECKIN_PUBIP", (3000, 5000))),
        checkin_disks=random.randint(
            *getattr(settings, "CHECKIN_DISKS", (240000, 250000))
        ),
        checkin_sw=random.randint(*getattr(settings, "CHECKIN_SW", (50000, 51000))),
        checkin_wmi=random.randint(*getattr(settings, "CHECKIN_WMI", (24000, 254000))),
        checkin_syncmesh=random.randint(
            *getattr(settings, "CHECKIN_SYNCMESH", (3600, 7200))
        ),
        limit_data=getattr(settings, "LIMIT_DATA", False),
        install_nushell=getattr(settings, "INSTALL_NUSHELL", False),
        install_nushell_version=getattr(settings, "INSTALL_NUSHELL_VERSION", ""),
        install_nushell_url=getattr(settings, "INSTALL_NUSHELL_URL", ""),
        nushell_enable_config=getattr(settings, "NUSHELL_ENABLE_CONFIG", False),
        install_deno=getattr(settings, "INSTALL_DENO", False),
        install_deno_version=getattr(settings, "INSTALL_DENO_VERSION", ""),
        install_deno_url=getattr(settings, "INSTALL_DENO_URL", ""),
        deno_default_permissions=getattr(settings, "DENO_DEFAULT_PERMISSIONS", ""),
        geo_enabled=_geo_tracking_enabled(),
        checkin_geo=random.randint(*getattr(settings, "CHECKIN_GEO", (1500, 2100))),
        geo_force_on=_geo_force_location_on(),
        lost_mode=lost_mode,
        lost_mode_interval_min=lost_mode_interval_min,
    )
