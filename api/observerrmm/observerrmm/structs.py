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
