import asyncio
import json

import websockets
from django.core.management.base import BaseCommand

from agents.models import Agent
from observerrmm.constants import TRMM_WS_MAX_SIZE
from core.utils import (
    _b64_to_hex,
    get_core_settings,
    get_mesh_device_id,
    get_mesh_ws_url,
)


async def _list_mesh_nodes(uri: str, mesh_id: str) -> list:
    """Lista los nodos del grupo de dispositivos del RMM en MeshCentral.

    Devuelve [{'_id': 'node//<b64>', 'name': <str>}, ...] SOLO del mesh cuyo
    id coincide con el grupo de dispositivos del RMM (core.mesh_device_group),
    evitando tocar nodos de otros grupos que pudieran existir en MeshCentral.
    """
    async with websockets.connect(uri, max_size=TRMM_WS_MAX_SIZE) as ws:
        await ws.send(json.dumps({"action": "nodes", "responseid": "trmm"}))

        async for message in ws:
            r = json.loads(message)
            if r.get("action") != "nodes":
                continue

            nodes = []
            for mesh_key, group_nodes in r.get("nodes", {}).items():
                if mesh_key.split("mesh//")[-1] != mesh_id:
                    continue
                for n in group_nodes:
                    nodes.append({"_id": n["_id"], "name": n.get("name", "")})
            return nodes

    return []


async def _remove_devices(uri: str, nodeids: list) -> dict:
    """Borra nodos en MeshCentral por el mismo camino que remove_mesh_agent
    (acción 'removedevices' del control websocket)."""
    async with websockets.connect(uri, max_size=TRMM_WS_MAX_SIZE) as ws:
        await ws.send(
            json.dumps(
                {
                    "action": "removedevices",
                    "nodeids": nodeids,
                    "responseid": "trmm",
                }
            )
        )
        async for message in ws:
            r = json.loads(message)
            if r.get("action") == "removedevices":
                return r
    return {}


class Command(BaseCommand):
    help = (
        "Borra nodos huérfanos en MeshCentral: nodos que existen en el grupo de "
        "dispositivos del RMM pero que ya no tienen un agente asociado en el RMM "
        "(p. ej. desinstalaciones incompletas). Sin --delete solo los lista."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Borra realmente los nodos huérfanos (sin este flag solo los lista).",
        )

    def handle(self, *args, **kwargs):
        delete = kwargs["delete"]

        core = get_core_settings()

        try:
            uri = get_mesh_ws_url()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"No se pudo obtener la URL del mesh: {e}"))
            return

        # id del grupo de dispositivos del RMM en MeshCentral (acota el borrado a ese grupo)
        try:
            mesh_id = asyncio.run(get_mesh_device_id(uri, core.mesh_device_group))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error obteniendo mesh device id: {e}"))
            return

        if not mesh_id:
            self.stdout.write(
                self.style.ERROR(
                    f"No se encontró el grupo de dispositivos '{core.mesh_device_group}' en MeshCentral. Abortando por seguridad."
                )
            )
            return

        # nodos conocidos por el RMM (Agent.mesh_node_id está en hex → forma b64 del mesh)
        known = set()
        for a in Agent.objects.only("mesh_node_id"):
            if a.mesh_node_id:
                known.add(f"node//{_b64_to_hex(a.mesh_node_id)}")

        try:
            nodes = asyncio.run(_list_mesh_nodes(uri, mesh_id))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error listando nodos del mesh: {e}"))
            return

        orphans = [n for n in nodes if n["_id"] not in known]

        self.stdout.write(
            self.style.WARNING(
                f"Grupo '{core.mesh_device_group}': {len(nodes)} nodos en mesh | "
                f"{len(known)} agentes en RMM | {len(orphans)} huérfanos"
            )
        )

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No hay nodos huérfanos. Mesh en paridad con el RMM."))
            return

        for n in orphans:
            self.stdout.write(self.style.WARNING(f"  huérfano: {n['name'] or '(sin nombre)'} [{n['_id']}]"))

        if not delete:
            self.stdout.write(
                self.style.SUCCESS(
                    "Los nodos de arriba SE BORRARÍAN. Ejecuta de nuevo con --delete para borrarlos realmente."
                )
            )
            return

        nodeids = [n["_id"] for n in orphans]
        try:
            resp = asyncio.run(_remove_devices(uri, nodeids))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error borrando nodos: {e}"))
            return

        if resp.get("result") == "ok":
            self.stdout.write(self.style.SUCCESS(f"Borrados {len(nodeids)} nodos huérfanos (result: ok)."))
        else:
            self.stdout.write(self.style.ERROR(f"Respuesta inesperada de MeshCentral: {resp}"))
