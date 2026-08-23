import dataclasses
from typing import Any


class ORMMStruct:
    def _to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class AgentCheckInConfig(ORMMStruct):
    checkin_hello: int
    checkin_agentinfo: int
    checkin_winsvc: int
    checkin_pubip: int
    checkin_disks: int
    checkin_sw: int
    checkin_wmi: int
    checkin_syncmesh: int
    limit_data: bool
    install_nushell: bool
    install_nushell_version: str
    install_nushell_url: str
    nushell_enable_config: bool
    install_deno: bool
    install_deno_version: str
    install_deno_url: str
    deno_default_permissions: str
    # Feature 023: interruptor GLOBAL (mismo valor para toda la flota) + intervalo
    # de captura de baja frecuencia. Claves aditivas; un agente antiguo las ignora.
    geo_enabled: bool
    checkin_geo: int
    # Gap 3: force-on del sensor de ubicación/radio WiFi en el endpoint corporativo.
    geo_force_on: bool
    # Feature 030 (ADR-025): PRIMER campo per-agente de este endpoint — todos los
    # anteriores son globales. Es el canal de respaldo del push por NATS: un
    # equipo que estaba apagado cuando lo marcaron se entera acá al reconectar,
    # que es justamente el escenario para el que existe la feature.
    lost_mode: bool
    lost_mode_interval_min: int
    # Feature 030 · Fase 2: interruptor global de la foto de webcam (ADR-025).
    lost_mode_webcam: bool
    # Feature 038: cascada RESUELTA (incidente > equipo > global) que el agente
    # ejecuta al entrar en modo perdido. Sólo son significativos cuando
    # `lost_mode=True`; viajan siempre (aditivos: un agente viejo los ignora).
    # El bloqueo es silencioso-diferido: el agente espera `lost_mode_lock_delay_min`
    # minutos recolectando evidencia y recién ahí bloquea si `lost_mode_auto_lock`.
    lost_mode_auto_lock: bool
    lost_mode_lock_delay_min: int
    lost_mode_no_hibernate: bool
    # Fuerza la foto de webcam para el caso aunque `lost_mode_webcam` (global)
    # esté apagado (decisión "override total en perdido", 2026-08-20).
    lost_mode_webcam_override: bool
    lost_mode_alarm: bool
    # Feature 041: aditivos (RN-07). Llevan default para no romper el único
    # constructor (get_agent_config) hasta que T014 los cablee con los valores
    # reales de Agent.outside_geofence y CoreSettings. Un agente viejo los ignora
    # (copia el struct campo por campo). El config sigue siendo solo bool/int:
    # ni lat/long ni SSIDs (NFR §6).
    outside_geofence: bool = False
    outside_geofence_interval_min: int = 5
    keep_awake_baseline: bool = True
    # T034: toggle global de RF-05 (asociarse a WiFi abierta fuera de geocerca).
    # Default True (ON): parte del módulo de perdidos/robados; el toggle es opt-out.
    # Un agente viejo lo ignora. Sigue siendo solo bool (NFR §6).
    open_wifi: bool = True
