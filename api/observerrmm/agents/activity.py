"""Monitoreo de actividad: cascada de encendido (feature 049-B2).

Regla única, usada por el polling de config del agente, por el push NATS y por
la consola, para que los tres digan siempre lo mismo:

1. `CoreSettings.activity_monitoring_enabled` apagado (default) => nadie muestrea.
2. Encendido => manda el valor explícito más específico: equipo > sitio > cliente.
3. Sin ningún valor explícito => NO. El monitoreo es opt-in por cliente: sólo se
   enciende donde alguien lo pidió.

`activity_feature_available()` es el punto único para condicionar el módulo a una
licencia EE más adelante: hoy siempre disponible.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from django.db.models import Q

if TYPE_CHECKING:
    from agents.models import Agent
    from core.models import CoreSettings

# Rango que el agente acepta (clampActInterval); se valida igual en la consola.
ACTIVITY_INTERVAL_MIN = 15
ACTIVITY_INTERVAL_MAX = 600


@dataclass(frozen=True)
class ActivityResolution:
    active: bool
    # "global" (interruptor global apagado), "agent", "site", "client" o
    # "default" (nadie decidió => apagado).
    source: str
    interval_seg: int
    idle_seg: int
    window_titles: bool
    # 049-C: capturas cada N minutos (0 = apagadas) y red por aplicación.
    screenshots_min: int = 0
    network: bool = False

    def nats_payload(self) -> dict:
        # Mismo contrato que el RPC `actividad_monitor` del agente (strings).
        return {
            "active": "1" if self.active else "0",
            "interval_seg": str(self.interval_seg),
            "inactivo_seg": str(self.idle_seg),
            "con_titulo": "1" if self.window_titles else "0",
            "capturas_min": str(self.screenshots_min if self.active else 0),
            "red": "1" if (self.network and self.active) else "0",
        }


def activity_feature_available() -> bool:
    """Gancho EE: el día que el módulo sea de pago, la licencia se mira acá."""
    return True


def resolve_activity(
    agent: "Agent", core: Optional["CoreSettings"] = None
) -> ActivityResolution:
    if core is None:
        from core.utils import get_core_settings

        core = get_core_settings()

    interval = min(
        max(int(core.activity_interval_seg), ACTIVITY_INTERVAL_MIN),
        ACTIVITY_INTERVAL_MAX,
    )
    common = dict(
        interval_seg=interval,
        idle_seg=int(core.activity_idle_seg),
        window_titles=bool(core.activity_window_titles),
        screenshots_min=int(core.activity_screenshots_min),
        network=bool(core.activity_network),
    )

    if not (activity_feature_available() and core.activity_monitoring_enabled):
        return ActivityResolution(active=False, source="global", **common)

    site = agent.site
    for source, value in (
        ("agent", agent.activity_monitoring),
        ("site", site.activity_monitoring),
        ("client", site.client.activity_monitoring),
    ):
        if value is not None:
            return ActivityResolution(active=bool(value), source=source, **common)

    return ActivityResolution(active=False, source="default", **common)


def agents_possibly_on():
    """Equipos con algún "sí" explícito en su cascada.

    Son los únicos cuyo estado efectivo cambia al tocar el interruptor global o
    la cadencia: el resto está apagado igual. Evita empujar a toda la flota.
    """
    from agents.models import Agent

    return Agent.objects.filter(
        Q(activity_monitoring=True)
        | Q(site__activity_monitoring=True)
        | Q(site__client__activity_monitoring=True)
    )
