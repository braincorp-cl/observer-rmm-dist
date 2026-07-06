# Limpieza de nodos huérfanos de MeshCentral — enfoque HÍBRIDO.
#
# Un nodo "huérfano" es un registro de dispositivo que sigue en MeshCentral
# (tabla `main`) pero cuyo agente ya no existe en el RMM (p. ej. desinstalaciones
# incompletas). Acumulados degradan MeshCentral (tráfico websocket inútil).
#
# ── Por qué este comando NO borra vía la API `removedevices` ──────────────────
# La primera versión de este comando borraba por la acción `removedevices` del
# control websocket de MeshCentral (misma ruta que `remove_mesh_agent`). La prueba
# en producción (MINSAL, ~28.500 agentes / ~29.400 nodos, informe 2026-07-06)
# demostró que ese camino NO es confiable ni seguro a esa escala:
#   * MeshCentral responde `result:"ok"` de forma INCONDICIONAL — su propio código
#     lo comenta: "in this case we always send ok which is not ideal"
#     (meshuser.js, acción removedevices). El "ok" significa "recibí el array",
#     no "borré los nodos".
#   * El borrado es fire-and-forget asíncrono (GetNodeWithRights + ~11 db.Remove
#     por nodo dentro de un callback); el "ok" se manda ANTES de que persista.
#   * El puerto de control (4430) es el MISMO puerto donde MeshCentral atiende a
#     los ~28.500 agentes en vivo. Un lote de cientos de `removedevices` satura el
#     event loop de Node (Recv-Q > backlog) y deja el canal inutilizable.
#   * Resultado empírico: de 626 nodos reportados "ok", solo 8 se persistieron.
#
# ── Qué hace en cambio (híbrido) ──────────────────────────────────────────────
# Reutiliza la parte SEGURA (descubrimiento) y delega el borrado al método SQL
# directo del runbook `meshcentral-limpieza-huerfanos`, que sí persiste y no toca
# el event loop:
#   1. DESCUBRE los huérfanos acotado al grupo del RMM (core.mesh_device_group):
#      lee los nodos del grupo por la acción read-only `nodes` (en la prueba la
#      lectura funcionó siempre) — o desde un dump SQL (`--node-ids-file`) para no
#      tocar MeshCentral en absoluto. Huérfano = nodo cuyo `_id` no está en
#      {node//_b64_to_hex(Agent.mesh_node_id)}.
#   2. EMITE el artefacto SQL probado del runbook (archivo de IDs con los 6
#      prefijos + script .sql con temp table + COPY + DELETE) para que el OPERADOR
#      lo ejecute con `psql` sobre la BD `meshcentral` (Django no tiene credenciales
#      a esa BD). El comando nunca borra por sí mismo.
#
# El nombre del grupo NO se hardcodea: se lee de CoreSettings.mesh_device_group
# (Observer = "ObserverRMM"; prod TacticalRMM = "TacticalRMM").
import asyncio
import json
import time
from pathlib import Path

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

MANIFEST_DIR = "/tmp"
WS_TIMEOUT = 30  # segundos de espera por la respuesta de la lectura antes de abortar
RETRIES = 2  # reintentos adicionales ante fallas transitorias de conexión
RETRY_BACKOFF = 3  # segundos entre reintentos

# Prefijos EXACTOS del runbook SQL probado (meshcentral-limpieza-huerfanos):
# por cada nodo huérfano se borran sus 6 variantes de registro en `main`.
#   node//        -> el nodo
#   alnode//      -> 'al' + node//  (error log last time)
#   ifnode//      -> 'if' + node//  (interfaces de red)
#   sinode//      -> 'si' + node//  (system information)
#   lcnode//      -> 'lc' + node//  (last connect time)
#   lastconnect// -> registro de última conexión
MESH_ID_PREFIXES = ["node//", "alnode//", "ifnode//", "sinode//", "lcnode//", "lastconnect//"]


def _err(e: Exception) -> str:
    """Mensaje legible incluso cuando str(e) viene vacío (p. ej. asyncio.TimeoutError)."""
    msg = str(e)
    return f"{type(e).__name__}: {msg}" if msg else f"{type(e).__name__} (sin mensaje propio)"


async def _list_mesh_nodes(uri: str, mesh_id: str) -> list:
    """Lista (read-only) los nodos del grupo de dispositivos del RMM en MeshCentral.

    Devuelve [{'_id': 'node//<b64>', 'name': <str>}, ...] SOLO del mesh cuyo id
    coincide con core.mesh_device_group, evitando considerar nodos de otros grupos.
    Es una lectura ligera (acción `nodes`), no toca el borrado.
    """

    async def _inner():
        async with websockets.connect(uri, max_size=TRMM_WS_MAX_SIZE, open_timeout=10) as ws:
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

    return await asyncio.wait_for(_inner(), timeout=WS_TIMEOUT)


class Command(BaseCommand):
    help = (
        "Descubre nodos huérfanos de MeshCentral (existen en el grupo del RMM pero "
        "ya no tienen agente en el RMM) y EMITE el SQL de borrado probado del runbook "
        "para que el operador lo ejecute con psql sobre la BD meshcentral. No borra por "
        "sí mismo ni usa la API removedevices (no confiable a escala; ver informe 2026-07-06)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--emit-sql",
            action="store_true",
            help="Genera el archivo de IDs + el script .sql de borrado y muestra las "
            "instrucciones para el operador. Sin este flag solo lista (dry-run).",
        )
        parser.add_argument(
            "--node-ids-file",
            type=str,
            default=None,
            help="Descubre desde un dump SQL de node ids (una id de `main` por línea, "
            "p. ej. `SELECT id FROM main WHERE TRIM(type)='node'`) en vez de la API de "
            "MeshCentral. Paridad con el runbook, sin tocar MeshCentral (NO acota por grupo).",
        )
        parser.add_argument(
            "--out-dir",
            type=str,
            default=MANIFEST_DIR,
            help=f"Directorio donde escribir los artefactos (default: {MANIFEST_DIR}). "
            "Debe ser legible por el usuario postgres para el COPY.",
        )
        parser.add_argument(
            "--print-limit",
            type=int,
            default=50,
            help="Máximo de huérfanos a listar en consola; el resto queda en el manifiesto "
            "(default: 50).",
        )

    # ── helpers ───────────────────────────────────────────────────────────────
    def _run_with_retries(self, label: str, coro_factory, retries: int):
        """Ejecuta coro_factory() vía asyncio.run reintentando ante fallas transitorias.
        Devuelve (resultado, None) si tuvo éxito, o (None, excepción) si agotó reintentos."""
        last_err = None
        for attempt in range(1, retries + 2):
            try:
                return asyncio.run(coro_factory()), None
            except Exception as e:
                last_err = e
                self.stdout.write(self.style.WARNING(f"{label}: intento {attempt} falló ({_err(e)})."))
                if attempt <= retries:
                    time.sleep(RETRY_BACKOFF)
        return None, last_err

    def _build_known_set(self):
        """Conjunto de node ids conocidos por el RMM. Agent.mesh_node_id está en hex;
        _b64_to_hex lo lleva a la forma b64 del mesh (node//<b64>)."""
        known = set()
        skipped = 0
        for a in Agent.objects.only("mesh_node_id"):
            if not a.mesh_node_id:
                continue
            try:
                known.add(f"node//{_b64_to_hex(a.mesh_node_id)}")
            except Exception:
                # mesh_node_id corrupto/no-hex: no tumbar el comando por un registro malo.
                skipped += 1
        return known, skipped

    def _write_manifest(self, entries: list, out_dir: str, ts: str) -> str:
        path = str(Path(out_dir) / f"mesh_orphans_preview_{ts}.json")
        with open(path, "w") as f:
            json.dump({"timestamp": ts, "count": len(entries), "orphans": entries}, f, indent=2)
        return path

    def _emit_sql_artifacts(self, orphans: list, out_dir: str, ts: str):
        """Reproduce el artefacto del runbook probado: archivo de IDs (6 prefijos por
        huérfano) + script .sql (temp table + COPY + DELETE). Devuelve (ids_path, sql_path, n_ids)."""
        bases = []
        for n in orphans:
            _id = n["_id"]
            base = _id[len("node//"):] if _id.startswith("node//") else _id
            bases.append(base)

        ids_path = str(Path(out_dir) / f"mesh_ids_completos_{ts}.txt")
        with open(ids_path, "w") as f:
            for base in bases:
                for prefijo in MESH_ID_PREFIXES:
                    f.write(f"{prefijo}{base}\n")

        sql_path = str(Path(out_dir) / f"limpiar_mesh_huerfanos_{ts}.sql")
        sql = (
            "\\timing on\n"
            "CREATE TEMP TABLE mesh_ids_eliminar (id TEXT PRIMARY KEY);\n"
            f"COPY mesh_ids_eliminar FROM '{ids_path}';\n"
            "SELECT COUNT(*) AS ids_cargados FROM mesh_ids_eliminar;\n"
            "SELECT COUNT(*) AS registros_a_eliminar\n"
            "  FROM main m WHERE m.id IN (SELECT id FROM mesh_ids_eliminar);\n"
            "SELECT COUNT(*) AS nodos_antes FROM main WHERE TRIM(type) = 'node';\n"
            "DELETE FROM main WHERE id IN (SELECT id FROM mesh_ids_eliminar);\n"
            "SELECT COUNT(*) AS nodos_despues FROM main WHERE TRIM(type) = 'node';\n"
            "SELECT COUNT(*) AS registros_totales FROM main;\n"
        )
        with open(sql_path, "w") as f:
            f.write(sql)

        return ids_path, sql_path, len(bases) * len(MESH_ID_PREFIXES)

    # ── discovery ───────────────────────────────────────────────────────────────
    def _discover_from_file(self, path: str, known: set):
        try:
            with open(path) as f:
                mesh_nodes = {line.strip() for line in f if line.strip()}
        except OSError as e:
            self.stdout.write(self.style.ERROR(f"No se pudo leer {path}: {_err(e)}"))
            return None, None
        orphan_ids = mesh_nodes - known
        # ya son solo huérfanos; el llamador no vuelve a filtrar
        nodes = [{"_id": i, "name": ""} for i in sorted(orphan_ids)]
        return nodes, len(mesh_nodes)

    def _discover_from_api(self, core, known: set):
        try:
            uri = get_mesh_ws_url()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"No se pudo obtener la URL del mesh: {_err(e)}"))
            return None, None

        mesh_id, err = self._run_with_retries(
            "get_mesh_device_id", lambda: get_mesh_device_id(uri, core.mesh_device_group), RETRIES
        )
        if err is not None:
            self.stdout.write(
                self.style.ERROR(f"Error obteniendo mesh device id tras reintentos: {_err(err)}")
            )
            return None, None
        if not mesh_id:
            self.stdout.write(
                self.style.ERROR(
                    f"No se encontró el grupo de dispositivos '{core.mesh_device_group}' en "
                    "MeshCentral. Abortando por seguridad."
                )
            )
            return None, None

        nodes, err = self._run_with_retries(
            "listado de nodos", lambda: _list_mesh_nodes(uri, mesh_id), RETRIES
        )
        if err is not None:
            self.stdout.write(
                self.style.ERROR(f"Error listando nodos del mesh tras reintentos: {_err(err)}")
            )
            return None, None

        orphans = [n for n in nodes if n["_id"] not in known]
        return orphans, len(nodes)

    # ── main ─────────────────────────────────────────────────────────────────────
    def handle(self, *args, **kwargs):
        emit_sql = kwargs["emit_sql"]
        node_ids_file = kwargs["node_ids_file"]
        out_dir = kwargs["out_dir"]
        print_limit = kwargs["print_limit"]

        core = get_core_settings()

        known, skipped = self._build_known_set()
        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"{skipped} agente(s) con mesh_node_id ilegible (ignorados, no cuentan como conocidos)."
                )
            )

        if node_ids_file:
            orphans, total_nodes = self._discover_from_file(node_ids_file, known)
            scope_note = "dump SQL (NO acotado a grupo)"
        else:
            orphans, total_nodes = self._discover_from_api(core, known)
            scope_note = f"grupo '{core.mesh_device_group}'"

        if orphans is None:
            return  # el helper ya reportó el error

        self.stdout.write(
            self.style.WARNING(
                f"{scope_note}: {total_nodes} nodos evaluados | {len(known)} agentes en RMM | "
                f"{len(orphans)} huérfanos"
            )
        )

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No hay nodos huérfanos. Mesh en paridad con el RMM."))
            return

        ts = time.strftime("%Y%m%d_%H%M%S")
        manifest_path = self._write_manifest(orphans, out_dir, ts)
        self.stdout.write(f"Detalle completo de huérfanos: {manifest_path}")

        for n in orphans[:print_limit]:
            self.stdout.write(self.style.WARNING(f"  huérfano: {n['name'] or '(sin nombre)'} [{n['_id']}]"))
        if len(orphans) > print_limit:
            self.stdout.write(self.style.WARNING(f"  ... y {len(orphans) - print_limit} más (ver manifiesto)."))

        if not emit_sql:
            self.stdout.write(
                self.style.SUCCESS(
                    "Dry-run. Para generar el SQL de borrado ejecuta de nuevo con --emit-sql."
                )
            )
            return

        ids_path, sql_path, n_ids = self._emit_sql_artifacts(orphans, out_dir, ts)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Artefactos SQL generados (el comando NO borró nada):"))
        self.stdout.write(
            f"  IDs ({n_ids} filas, {len(orphans)} nodos × {len(MESH_ID_PREFIXES)} prefijos): {ids_path}"
        )
        self.stdout.write(f"  Script SQL: {sql_path}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Pasos del operador (BD meshcentral, requiere sudo/postgres):"))
        self.stdout.write(
            "  1) BACKUP OBLIGATORIO:\n"
            "       sudo -u postgres pg_dump meshcentral | gzip > /tmp/meshcentral_backup_$(date +%Y%m%d_%H%M).sql.gz"
        )
        self.stdout.write("  2) (opcional) revisar el script antes de correrlo:\n" f"       cat {sql_path}")
        self.stdout.write(
            "  3) EJECUTAR el borrado (usar consola VMware / tmux si el COUNT tarda por volumen):\n"
            f"       sudo -u postgres psql -d meshcentral -f {sql_path}"
        )
        self.stdout.write(
            "  4) REINICIAR MeshCentral (necesario: el server cachea nodos en memoria):\n"
            "       sudo systemctl restart meshcentral && sleep 15 && systemctl status meshcentral | head -5"
        )
        self.stdout.write(
            "  5) VALIDAR:\n"
            "       python manage.py check_mesh\n"
            "       sudo -u postgres psql -d meshcentral -c \"SELECT COUNT(*) FROM main WHERE TRIM(type)='node';\""
        )
