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
