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


# Feature 038: cascada apagada. Se despacha cuando el equipo NO está perdido
# (el agente no la usa igual, pero mandar ceros evita cualquier disparo por un
# valor heredado) o ante cualquier fallo de lectura (mismo fail-safe que la geo).
_CASCADE_OFF: dict = {
    "auto_lock": False,
    "lock_delay_min": 0,
    "no_hibernate": False,
    "webcam_override": False,
    "alarm": False,
}


def _lost_mode(agentid: str) -> tuple[bool, int, dict]:
    """Feature 030 + 038: estado de modo perdido de ESTE agente y su cascada resuelta.

    Fail-safe apagado, igual que los interruptores de geo: ante cualquier
    problema —agente inexistente, tabla no migrada, BD con hipo— se responde
    "no está perdido" y cascada en cero. Encender una recolección de evidencia
    —o peor, una contramedida— por un error de lectura sería el peor fallo
    posible de esta feature.
    """
    try:
        from agents.models import LostModeState
        from agents.utils import resolve_lost_mode_cascade

        state = (
            LostModeState.objects.filter(agent__agent_id=agentid)
            .select_related("agent")
            .first()
        )
        if not state or not state.active:
            return False, 0, dict(_CASCADE_OFF)

        cascade = resolve_lost_mode_cascade(state.agent, state=state)
        return (
            True,
            state.interval_min,
            {
                "auto_lock": cascade.auto_lock,
                "lock_delay_min": cascade.lock_delay_min,
                "no_hibernate": cascade.no_hibernate,
                "webcam_override": cascade.webcam_override,
                "alarm": cascade.alarm,
            },
        )
    except Exception:
        return False, 0, dict(_CASCADE_OFF)


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


def _outside_geofence(agentid: str) -> bool:
    """Feature 041: bandera de salida de geocerca de ESTE agente.

    Lee directo de `Agent.outside_geofence` (la escribe `geofence_check_task` en
    la misma transacción que abre/resuelve la alerta), SIN join a la tabla de
    alertas: el booleano ya es el estado resuelto. Fail-safe apagado, igual que
    el resto de los interruptores de geo: ante agente inexistente, tabla no
    migrada o BD con hipo se responde "dentro del radio" (no apretar cadencia ni
    forzar la radio por un error de lectura).
    """
    try:
        from agents.models import Agent

        return bool(
            Agent.objects.filter(agent_id=agentid)
            .values_list("outside_geofence", flat=True)
            .first()
        )
    except Exception:
        return False


def _geofence_interval_min() -> int:
    """Feature 041: cadencia apretada mientras el equipo está fuera de la geocerca.

    GLOBAL, de `CoreSettings.geo_geofence_interval_min`. Ante fallo espeja el
    default del modelo/dataclass (5 min): perder la lectura no puede volver la
    cadencia ni más agresiva ni más lenta que el default declarado.
    """
    try:
        from core.utils import get_core_settings

        return int(get_core_settings().geo_geofence_interval_min)
    except Exception:
        return 5


def _keep_awake_baseline() -> bool:
    """Feature 041 · D-12: baseline keep-awake global (prerrequisito Must).

    De `CoreSettings.keep_awake_baseline_enabled`. A diferencia de los
    interruptores reactivos —donde el fail-safe es APAGAR porque encender es el
    daño—, acá el estado deseado por defecto es ENCENDIDO (equipo dormido nunca
    se puede medir fuera). El daño real de un error de lectura sería el flapeo:
    revertir el baseline por un hipo de BD y reaplicarlo al siguiente poll. Por
    eso el fail-safe espeja el default del modelo (True) y no fuerza revert.
    """
    try:
        from core.utils import get_core_settings

        return bool(get_core_settings().keep_awake_baseline_enabled)
    except Exception:
        return True


def _open_wifi_enabled() -> bool:
    """Feature 041 · T034: toggle global de RF-05 (asociarse a WiFi abierta).

    De `CoreSettings.open_wifi_enabled`. ON por omisión: es parte del módulo de
    perdidos/robados y el uso corporativo del equipo está cubierto por el acta de
    entrega; el toggle es un opt-out para el cliente que desestima el módulo. El
    fail-safe espeja ese default (True): ante un error de lectura, un equipo
    posiblemente robado no debe dejar de intentar reportarse por un hipo de BD.
    Igual que `_keep_awake_baseline`. (El intento igual está acotado en runtime a
    fuera-de-geocerca + sin conectividad; el flag sólo lo habilita.)
    """
    try:
        from core.utils import get_core_settings

        return bool(get_core_settings().open_wifi_enabled)
    except Exception:
        return True


def get_agent_config(agentid: str = "") -> AgentCheckInConfig:
    lost_mode, lost_mode_interval_min, lost_mode_cascade = _lost_mode(agentid)

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
        lost_mode_auto_lock=lost_mode_cascade["auto_lock"],
        lost_mode_lock_delay_min=lost_mode_cascade["lock_delay_min"],
        lost_mode_no_hibernate=lost_mode_cascade["no_hibernate"],
        lost_mode_webcam_override=lost_mode_cascade["webcam_override"],
        lost_mode_alarm=lost_mode_cascade["alarm"],
        # Feature 041: la bandera es por-agente (Agent.outside_geofence); la
        # cadencia y el toggle del baseline son globales (CoreSettings). Viajan
        # siempre, esté el equipo fuera o no: el agente los guarda y recompone
        # cadencia/no-dormir/baseline al armar cada ciclo.
        outside_geofence=_outside_geofence(agentid),
        outside_geofence_interval_min=_geofence_interval_min(),
        keep_awake_baseline=_keep_awake_baseline(),
        # T034: RF-05 viaja siempre (global), pero OFF por omisión; el agente no
        # intenta asociarse a WiFi abierta hasta que este flag esté en True.
        open_wifi=_open_wifi_enabled(),
    )
