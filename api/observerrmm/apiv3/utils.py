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


def get_agent_config() -> AgentCheckInConfig:
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
    )
