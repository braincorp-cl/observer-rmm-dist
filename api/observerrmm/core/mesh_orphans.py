"""Descubrimiento de nodos huérfanos de MeshCentral.

Un nodo es **huérfano** cuando existe en el grupo de dispositivos del RMM pero
ninguna fila de `Agent` lo apunta. Nadie lo va a borrar solo: el servidor tiene
UNA sola vía para borrar nodos —`post_delete` de Agent → `remove_mesh_node_task`
(agents/signals.py)— y esa vía necesita justamente la fila que al huérfano le
falta.

## De dónde salen los huérfanos

El instalador del agente instala el Mesh —que al conectarse ya registra el
nodo— y recién después hace `POST /api/v3/newagent/`. Un enrolamiento que falla
ahí deja el nodo registrado y ninguna fila creada. Medido: 4 nodos huérfanos el
2026-07-29 (2 `HP-ProOne-400`, 2 `FAZOCAR`), con `lastconnect` vacío.

## Lo que este módulo NO hace, y por qué

No borra. El borrado por la acción `removedevices` del websocket de control **no
es confiable a escala**: MeshCentral responde `ok` de forma incondicional (su
propio código lo comenta) y persiste de forma asíncrona; en la prueba de
producción del 2026-07-06, de 626 nodos reportados "ok" sólo se persistieron 8.
Además el puerto de control es el mismo que atienden los agentes en vivo. El
borrado sigue siendo el runbook SQL, vía
`bulk_delete_orphans_meshagents --emit-sql`.

Acá sólo se DESCUBRE y se reporta. La lectura (`action: nodes`) es liviana y en
esa misma prueba funcionó siempre.
"""

import asyncio
import json

import websockets

from agents.models import Agent
from core.utils import (
    _b64_to_hex,
    get_core_settings,
    get_mesh_device_id,
    get_mesh_ws_url,
)
from observerrmm.constants import ORMM_WS_MAX_SIZE

# Segundos de espera por la respuesta de la lectura antes de abortar.
WS_TIMEOUT = 30


async def list_group_nodes(uri: str, mesh_id: str) -> list[dict]:
    """Lista (read-only) los nodos del grupo de dispositivos del RMM.

    Devuelve `[{'_id': 'node//<b64>', 'name': <str>}, ...]` SÓLO del mesh cuyo id
    coincide con `core.mesh_device_group`: sin ese filtro se contarían como
    huérfanos los nodos de otros grupos, que no son nuestros para tocar.
    """

    async def _inner():
        async with websockets.connect(
            uri, max_size=ORMM_WS_MAX_SIZE, open_timeout=10
        ) as ws:
            await ws.send(json.dumps({"action": "nodes", "responseid": "ormm"}))

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

    return await asyncio.wait_for(_inner(), timeout=WS_TIMEOUT)


def known_node_ids() -> tuple[set[str], int]:
    """Node ids que el RMM conoce, en la forma en que los nombra MeshCentral.

    `Agent.mesh_node_id` está en hex; `_b64_to_hex` lo lleva a la forma b64 del
    mesh (`node//<b64>`). Devuelve `(conocidos, ilegibles)`: un `mesh_node_id`
    corrupto no puede tumbar el censo, pero tampoco puede contarse como conocido
    —eso escondería un huérfano de verdad— así que se cuenta aparte.
    """
    known = set()
    skipped = 0
    for a in Agent.objects.only("mesh_node_id"):
        if not a.mesh_node_id:
            continue
        try:
            known.add(f"node//{_b64_to_hex(a.mesh_node_id)}")
        except Exception:
            skipped += 1
    return known, skipped


def census() -> dict:
    """Cruza los nodos del grupo contra las filas del RMM.

    Devuelve `{"group", "total_nodes", "known", "skipped", "orphans"}`. Levanta
    excepción si MeshCentral no contesta o si el grupo no existe: sin la lista
    del mesh, «cero huérfanos» sería un cero mentiroso, y esa es exactamente la
    lectura que no se puede dar por buena.
    """
    core = get_core_settings()
    uri = get_mesh_ws_url()

    mesh_id = asyncio.run(get_mesh_device_id(uri, core.mesh_device_group))
    if not mesh_id:
        raise RuntimeError(
            f"No se encontró el grupo de dispositivos '{core.mesh_device_group}' "
            "en MeshCentral; sin él no se puede acotar el censo."
        )

    nodes = asyncio.run(list_group_nodes(uri, mesh_id))
    known, skipped = known_node_ids()
    orphans = [n for n in nodes if n["_id"] not in known]

    return {
        "group": core.mesh_device_group,
        "total_nodes": len(nodes),
        "known": len(known),
        "skipped": skipped,
        "orphans": orphans,
    }
