import json
import os
import secrets
import string
from itertools import cycle

from django.conf import settings
from django.utils import timezone as djangotime
from model_bakery.recipe import Recipe, foreign_key, seq

from observerrmm.constants import AgentMonType, AgentPlat


def generate_agent_id() -> str:
    return "".join(secrets.choice(string.ascii_letters) for i in range(39))


site = Recipe("clients.Site")


def get_wmi_data():
    with open(
        os.path.join(settings.BASE_DIR, "observerrmm/test_data/wmi_python_agent.json")
    ) as f:
        return json.load(f)


def get_win_svcs():
    svcs = settings.BASE_DIR.joinpath("observerrmm/test_data/winsvcs.json")
    with open(svcs) as f:
        return json.load(f)


agent = Recipe(
    "agents.Agent",
    site=foreign_key(site),
    hostname="DESKTOP-TEST123",
    version="1.3.0",
    monitoring_type=cycle(AgentMonType.values),
    agent_id=seq(generate_agent_id()),
    last_seen=djangotime.now() - djangotime.timedelta(days=5),
    plat=AgentPlat.WINDOWS,
)

server_agent = agent.extend(
    monitoring_type=AgentMonType.SERVER,
)

workstation_agent = agent.extend(
    monitoring_type=AgentMonType.WORKSTATION,
)

online_agent = agent.extend(
    last_seen=djangotime.now(), services=get_win_svcs(), wmi_detail=get_wmi_data()
)

offline_agent = agent.extend(
    last_seen=djangotime.now() - djangotime.timedelta(minutes=7)
)

overdue_agent = agent.extend(
    last_seen=djangotime.now() - djangotime.timedelta(minutes=35)
)

agent_with_services = agent.extend(
    services=[
        {
            "pid": 880,
            "name": "AeLookupSvc",
            "status": "stopped",
            "binpath": "C:\\Windows\\system32\\svchost.exe -k netsvcs",
            "username": "localSystem",
            "start_type": "manual",
            "description": "Processes application compatibility cache requests for applications as they are launched",
            "display_name": "Application Experience",
        },
        {
            "pid": 812,
            "name": "ALG",
            "status": "stopped",
            "binpath": "C:\\Windows\\System32\\alg.exe",
            "username": "NT AUTHORITY\\LocalService",
            "start_type": "manual",
            "description": "Provides support for 3rd party protocol plug-ins for Internet Connection Sharing",
            "display_name": "Application Layer Gateway Service",
        },
    ],
)

# Feature 037 · el bloque de cifrado, tal como lo manda el agente dentro de
# `agent-wmi`. Va acá y no en el JSON de `test_data/` a propósito: ese archivo es
# una captura real del inventario de un equipo anterior a la feature, y editarlo
# borraría la evidencia de qué mandaba un agente viejo — que es justo el caso
# «sin dato» que RN-A03 obliga a distinguir.
#
# 🔑 Las claves son las de WIRE, escritas a mano. Si alguien renombra una en el
# contrato, esta receta deja de reflejar la realidad y los tests que la usan lo
# muestran. Los nulos son deliberados: el volumen de datos trae la Fase 1b sin
# leer, y un `0` ahí significaría «cero protectores», que es otra cosa.
DISK_ENCRYPTION_WMI_BLOCK = {
    "soportado": True,
    "error": None,
    "volumenes": [
        {
            "device_id": "\\\\?\\Volume{11111111-2222-3333-4444-555555555555}\\",
            "drive_letter": "C:",
            "protection_status": 1,
            "conversion_status": 1,
            "encryption_method": 6,
            "persistent_volume_id": "pvid-c",
            "is_volume_initialized_for_protection": True,
            "encryption_percentage": 100,
            "volume_type": 0,
            "is_system_volume": True,
            "key_protector_count": 2,
            "key_protector_types": [3, 8],
        },
        {
            "device_id": "\\\\?\\Volume{99999999-8888-7777-6666-555555555555}\\",
            "drive_letter": None,
            "protection_status": 0,
            "conversion_status": 0,
            "encryption_method": 0,
            "persistent_volume_id": "",
            "is_volume_initialized_for_protection": False,
            "encryption_percentage": None,
            "volume_type": 1,
            "is_system_volume": False,
            "key_protector_count": None,
            "key_protector_types": None,
        },
    ],
}


def get_wmi_data_with_disk_encryption():
    """El inventario de siempre MÁS el bloque de cifrado (feature 037)."""
    datos = get_wmi_data()
    datos["disk_encryption"] = DISK_ENCRYPTION_WMI_BLOCK
    return datos


agent_with_wmi = agent.extend(wmi_detail=get_wmi_data())
# Un agente que ya reporta cifrado. Separado de `agent_with_wmi` para que los
# tests que dependen del inventario viejo —el del agente sin la feature— sigan
# probando ese caso, que no es hipotético: la flota tarda días en actualizarse.
agent_with_disk_encryption_wmi = agent.extend(
    wmi_detail=get_wmi_data_with_disk_encryption()
)
