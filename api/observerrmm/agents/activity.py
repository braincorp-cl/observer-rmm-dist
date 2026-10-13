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

import re
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
    # 049-D: patrones "siempre activo" (reuniones).
    always_active: tuple = ()

    def nats_payload(self) -> dict:
        # Mismo contrato que el RPC `actividad_monitor` del agente (strings).
        return {
            "active": "1" if self.active else "0",
            "interval_seg": str(self.interval_seg),
            "inactivo_seg": str(self.idle_seg),
            "con_titulo": "1" if self.window_titles else "0",
            "capturas_min": str(self.screenshots_min if self.active else 0),
            "red": "1" if (self.network and self.active) else "0",
            # NATS lleva strings: un patrón por línea.
            "siempre_activo": "\n".join(self.always_active) if self.active else "",
        }


# Mismos topes que el agente (compilarSiempreActivo).
ALWAYS_ACTIVE_MAX_PATTERNS = 30
ALWAYS_ACTIVE_MAX_LEN = 200
# Construcciones que RE2 (Go) no acepta: el agente descartaría el patrón.
_RE2_INCOMPATIBLE = re.compile(r"\(\?(?:[=!]|<[=!])|\\[1-9]")


def always_active_patterns(text) -> list[str]:
    """Patrones limpios (uno por línea) en el orden en que se escribieron."""
    out = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if line and line not in out:
            out.append(line)
    return out[:ALWAYS_ACTIVE_MAX_PATTERNS]


def validate_always_active(text) -> list[str]:
    """Errores legibles por patrón; lista vacía si todo sirve."""
    errores = []
    lineas = [x.strip() for x in str(text or "").splitlines() if x.strip()]
    if len(lineas) > ALWAYS_ACTIVE_MAX_PATTERNS:
        errores.append(f"Máximo {ALWAYS_ACTIVE_MAX_PATTERNS} patrones")
    for p in lineas:
        if len(p) > ALWAYS_ACTIVE_MAX_LEN:
            errores.append(f"«{p[:30]}…»: más de {ALWAYS_ACTIVE_MAX_LEN} caracteres")
            continue
        if _RE2_INCOMPATIBLE.search(p):
            errores.append(f"«{p}»: lookaround y referencias no están soportados")
            continue
        try:
            re.compile(p)
        except re.error as e:
            errores.append(f"«{p}»: {e}")
    return errores


# 049-D: nombre canónico de un proceso, igual en los 3 SO: minúsculas, sin ruta
# ni ".exe", y con alias para los que cambian de nombre según el SO o el paquete.
PROCESS_ALIASES = {
    "msedge": "edge",
    "microsoft edge": "edge",
    "google chrome": "chrome",
    "google-chrome": "chrome",
    "google-chrome-stable": "chrome",
    "chromium-browser": "chromium",
    "firefox-esr": "firefox",
    "brave-browser": "brave",
    "ms-teams": "teams",
    "msteams": "teams",
    "microsoft teams": "teams",
    "zoom.us": "zoom",
    "soffice.bin": "libreoffice",
    "soffice": "libreoffice",
    "code - oss": "code",
    "winword": "word",
    "microsoft word": "word",
    "microsoft excel": "excel",
    "powerpnt": "powerpoint",
    "microsoft powerpoint": "powerpoint",
    "microsoft outlook": "outlook",
}


def canon_process(name) -> str:
    # Agente macOS 2.17.8 en macOS 27 mandaba el bloque entero de `lsappinfo`
    # ('finder"\n !cgsconnection ...'): el nombre real es lo previo a '"'/salto.
    n = re.split(r'["\r\n]', str(name or ""), maxsplit=1)[0]
    n = n.strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
    if n.endswith(".exe"):
        n = n[:-4]
    elif n.endswith(".app"):
        n = n[:-4]
    return PROCESS_ALIASES.get(n, n)


def _merge_canon(d) -> dict:
    out = {}
    for k, v in (d or {}).items():
        c = canon_process(k)
        if isinstance(v, (int, float)):
            out[c] = out.get(c, 0) + v
        elif isinstance(v, dict) and isinstance(out.get(c), dict):
            # red por app: minutos se suman, picos se toman al máximo
            prev = out[c]
            out[c] = {
                kk: (prev.get(kk, 0) + vv if kk == "min" else max(prev.get(kk, 0), vv))
                for kk, vv in v.items()
                if isinstance(vv, (int, float))
            }
        else:
            out[c] = v
    return out


PAUSA_MIN = 10


def _hhmm(v) -> Optional[int]:
    try:
        h, m = str(v).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def recortar_pausas(pausas, huecos) -> list:
    """Quita de las pausas los lapsos con el equipo apagado o suspendido.

    Una pausa es tiempo sin teclado ni mouse CON el equipo encendido; el agente
    la mide entre entradas y no sabe que en medio el equipo estuvo apagado. Lo
    que queda de cada pausa se conserva sólo si sigue durando >= PAUSA_MIN.
    """
    cortes = []
    for h in huecos or []:
        if isinstance(h, dict):
            a, b = _hhmm(h.get("desde")), _hhmm(h.get("hasta"))
            if a is not None and b is not None and b > a:
                cortes.append((a, b))
    if not cortes:
        return pausas
    out = []
    for p in pausas or []:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            continue
        a, b = _hhmm(p[0]), _hhmm(p[1])
        if a is None or b is None or b <= a:
            continue
        trozos = [(a, b)]
        for ca, cb in cortes:
            trozos = [
                t
                for x, y in trozos
                for t in ((x, min(y, ca)), (max(x, cb), y))
                if t[1] > t[0]
            ]
        out.extend(
            [f"{x // 60:02d}:{x % 60:02d}", f"{y // 60:02d}:{y % 60:02d}"]
            for x, y in trozos
            if y - x >= PAUSA_MIN
        )
    return out


def canon_activity_day(dia: dict) -> dict:
    """Unifica los nombres de proceso de un día subido por el agente y recorta
    de las pausas los lapsos con el equipo apagado o suspendido."""
    for u in dia.get("usuarios") or []:
        if not isinstance(u, dict):
            continue
        if u.get("pausas") and dia.get("huecos"):
            u["pausas"] = recortar_pausas(u["pausas"], dia["huecos"])
        for k in ("procs", "red"):
            if isinstance(u.get(k), dict):
                u[k] = _merge_canon(u[k])
        for h in (u.get("horas") or {}).values():
            if isinstance(h, dict) and isinstance(h.get("p"), dict):
                h["p"] = _merge_canon(h["p"])
    return dia


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
        always_active=tuple(
            always_active_patterns(core.activity_always_active_patterns)
        ),
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
