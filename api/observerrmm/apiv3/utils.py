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


def _lost_mode_webcam() -> bool:
    """Feature 030 · Fase 2: interruptor global de la foto de webcam.

    Fail-safe APAGADO, igual que el resto de los interruptores de captura y con
    más razón: encender una cámara por un error de lectura de la configuración
    fotografiaría la cara de una persona sin que nadie lo haya autorizado.
    """
    try:
        from core.utils import get_core_settings

        return bool(get_core_settings().lost_mode_webcam_enabled)
    except Exception:
        return False


def get_agent_config(agentid: str = "") -> AgentCheckInConfig:
    lost_mode, lost_mode_interval_min = _lost_mode(agentid)

    return AgentCheckInConfig(
        # Cada fallback espeja el default que settings.py despacha: perder una línea
        # de CHECKIN_* no puede volver el intervalo ni más agresivo ni más lento.
        # GAP-052 (2026-06-27) recalibró el bloque en settings.py y estos fallbacks
        # quedaron atrás con los valores viejos —disks 250000 s = 69 h, sw 14 h,
        # agentinfo 11 h—, así que un servidor al que se le cayera ese renglón
        # degradaba en silencio al inventario que GAP-052 declaró inaceptable.
        # Alineados el 2026-08-15 (feature 037); el WMI ya lo estaba.
        checkin_hello=random.randint(*getattr(settings, "CHECKIN_HELLO", (30, 60))),
        checkin_agentinfo=random.randint(
            *getattr(settings, "CHECKIN_AGENTINFO", (200, 400))
        ),
        checkin_winsvc=random.randint(
            *getattr(settings, "CHECKIN_WINSVC", (2400, 3000))
        ),
        checkin_pubip=random.randint(*getattr(settings, "CHECKIN_PUBIP", (300, 500))),
        checkin_disks=random.randint(*getattr(settings, "CHECKIN_DISKS", (1000, 2000))),
        checkin_sw=random.randint(*getattr(settings, "CHECKIN_SW", (2800, 3500))),
        checkin_wmi=random.randint(*getattr(settings, "CHECKIN_WMI", (3000, 4000))),
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
        # El interruptor viaja SIEMPRE, esté el equipo marcado o no: el agente
        # lo guarda en memoria y lo consulta al armar cada ciclo. Mandarlo sólo
        # con el equipo perdido dejaría al agente sin el dato justo cuando lo
        # necesita, porque el marcaje puede llegar por NATS entre dos consultas
        # de configuración.
        lost_mode_webcam=_lost_mode_webcam(),
    )
