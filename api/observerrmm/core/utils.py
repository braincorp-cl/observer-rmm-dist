import asyncio
import binascii
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
from base64 import b64decode, b64encode
from contextlib import suppress
from typing import TYPE_CHECKING, Optional, cast

import requests
import websockets
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponse
from meshctrl.utils import get_auth_token
from requests.utils import requote_uri

from observerrmm.constants import (
    AGENT_CHECKS_CACHE_PREFIX,
    AGENT_TBL_PEND_ACTION_CNT_CACHE_PREFIX,
    CORESETTINGS_CACHE_KEY,
    ROLE_CACHE_PREFIX,
    TRMM_WS_MAX_SIZE,
    AgentPlat,
    GoArch,
    MeshAgentIdent,
)
from observerrmm.logger import logger

if TYPE_CHECKING:
    from core.models import CoreSettings


class CoreSettingsNotFound(Exception):
    pass


def clear_entire_cache() -> None:
    cache.delete_many_pattern(f"{ROLE_CACHE_PREFIX}*")
    cache.delete_many_pattern(f"{AGENT_TBL_PEND_ACTION_CNT_CACHE_PREFIX}*")
    cache.delete_many_pattern(f"{AGENT_CHECKS_CACHE_PREFIX}*")
    cache.delete(CORESETTINGS_CACHE_KEY)
    cache.delete_many_pattern("site_*")
    cache.delete_many_pattern("agent_*")
    cache.delete_many_pattern("throttle_*")


def token_is_valid() -> tuple[str, bool]:
    """
    Return type: token: str, is_valid: bool. Token wil be an empty string is not valid.
    """
    from core.models import CodeSignToken

    t: "Optional[CodeSignToken]" = CodeSignToken.objects.first()
    if not t:
        return "", False

    if not t.token:
        return "", False

    if t.is_valid:
        return t.token, True

    return "", False


def token_is_expired() -> bool:
    from core.models import CodeSignToken

    t: Optional["CodeSignToken"] = CodeSignToken.objects.first()
    if not t or not t.token:
        return False

    return t.is_expired


def get_core_settings() -> "CoreSettings":
    from core.models import CORESETTINGS_CACHE_KEY, CoreSettings

    coresettings = cache.get(CORESETTINGS_CACHE_KEY)

    if coresettings and isinstance(coresettings, CoreSettings):
        return coresettings
    else:
        coresettings = CoreSettings.objects.first()
        if not coresettings:
            raise CoreSettingsNotFound("CoreSettings not found.")

        cache.set(CORESETTINGS_CACHE_KEY, coresettings, 600)
        return cast(CoreSettings, coresettings)


def get_mesh_ws_url() -> str:
    core = get_core_settings()
    token = get_auth_token(core.mesh_api_superuser, core.mesh_token)

    if settings.DOCKER_BUILD:
        uri = f"{settings.MESH_WS_URL}/control.ashx?auth={token}"
    else:
        if getattr(settings, "USE_EXTERNAL_MESH", False):
            site = core.mesh_site.replace("https", "wss")
            uri = f"{site}/control.ashx?auth={token}"
        else:
            mesh_port = getattr(settings, "MESH_PORT", 4430)
            uri = f"ws://127.0.0.1:{mesh_port}/control.ashx?auth={token}"

    return uri


async def get_mesh_device_id(uri: str, device_group: str) -> None:
    async with websockets.connect(uri, max_size=TRMM_WS_MAX_SIZE) as ws:
        payload = {"action": "meshes", "responseid": "meshctrl"}
        await ws.send(json.dumps(payload))

        async for message in ws:
            r = json.loads(message)
            logger.error(f"get_mesh_device_id: received action={r.get('action')} keys={list(r.keys())}")
            if r["action"] == "meshes":
                meshes_names = [x["name"] for x in r.get("meshes", [])]
                logger.error(f"get_mesh_device_id: looking for '{device_group}' in {meshes_names}")
                filtered = list(filter(lambda x: x["name"] == device_group, r.get("meshes", [])))
                if not filtered:
                    logger.error(f"get_mesh_device_id: device_group '{device_group}' NOT FOUND")
                    return ""
                return filtered[0]["_id"].split("mesh//")[1]


def download_mesh_agent(dl_url: str) -> HttpResponse:
    r = requests.get(dl_url, timeout=15, verify=False)
    r.raise_for_status()
    response = HttpResponse(r.content, content_type="application/octet-stream")
    response["Content-Disposition"] = 'attachment; filename="meshagent"'
    return response


def get_mesh_installer(goarch: GoArch, dl_url: str, plat: AgentPlat):
    if plat not in AgentPlat.values or goarch not in GoArch.values:
        raise SuspiciousOperation("invalid args")

    mesh_installer = os.path.join(settings.EXE_DIR, f"mesh-{plat}-{goarch}")
    hasher = hashlib.sha256()
    chunks = []
    with requests.get(dl_url, stream=True, timeout=15, verify=False) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=64 * 1024):
            if chunk:
                hasher.update(chunk)
                chunks.append(chunk)

    new_digest = hasher.digest()

    if os.path.exists(mesh_installer):
        existing_hasher = hashlib.sha256()

        with open(mesh_installer, "rb") as f:
            for block in iter(lambda: f.read(64 * 1024), b""):
                existing_hasher.update(block)
        if existing_hasher.digest() == new_digest:
            return mesh_installer

    fp = tempfile.NamedTemporaryFile(
        prefix="mesh", dir=settings.EXE_DIR, delete=False, mode="wb"
    )
    try:
        for chunk in chunks:
            fp.write(chunk)
        fp.close()
        os.replace(fp.name, mesh_installer)
    except Exception:
        fp.close()
        if os.path.exists(fp.name):
            os.unlink(fp.name)
        raise

    return mesh_installer


def _b64_to_hex(h: str) -> str:
    return b64encode(bytes.fromhex(h)).decode().replace(r"/", "$").replace(r"+", "@")


def _mesh_id_to_hex(mesh_id: str) -> Optional[str]:
    """Normaliza un mesh node id a hex mayúscula, o devuelve None si no lo es.

    Acepta las dos formas en que llega el id: ya en hex, o en el base64 de
    MeshCentral (con `/`→`$` y `+`→`@`, que es como viaja por URL).

    **Devuelve None en vez de lanzar.** Antes esto era un `b64decode` pelado y
    un nodeid con basura reventaba con `binascii.Error` ⇒ HTTP 500 en un
    endpoint que cada agente golpea cada ~13-20 min. Que el 500 impidiera
    guardar el valor malo era un accidente afortunado, no una defensa: el
    descarte ahora es deliberado y queda registrado.

    `validate=True` es parte del descarte. Con el default (`False`) los
    caracteres fuera del alfabeto base64 se ignoran en silencio, así que una
    cadena arbitraria no lanza: produce un hex más corto, plausible y falso.
    Preferimos None a un id inventado.
    """
    try:
        bytes.fromhex(mesh_id)
        return mesh_id.upper()
    except ValueError:
        pass

    b64 = mesh_id.replace("@", "+").replace("$", "/")
    padding = 4 - len(b64) % 4
    if padding != 4:
        b64 += "=" * padding

    try:
        return b64decode(b64, validate=True).hex().upper()
    except (binascii.Error, ValueError):
        # `error` y no `warning`: el logger `trmm` corre en nivel ERROR
        # (`settings.TRMM_LOG_LEVEL`), así que un `warning` no se escribe en
        # ninguna parte y el descarte sería silencioso — medido en staging el
        # 2026-08-03. Y silencioso es justo lo que no queremos: un agente que
        # manda un nodeid inválido se queda sin «Tomar control» sin avisar,
        # que es el daño que persigue toda la feature 031.
        logger.error(f"_mesh_id_to_hex: nodeid descartado, no convertible: {mesh_id!r}")
        return None


async def send_command_with_mesh(
    cmd: str, uri: str, mesh_node_id: str, shell: int, run_as_user: int
) -> None:
    node_id = _b64_to_hex(mesh_node_id)
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "action": "runcommands",
                    "cmds": cmd,
                    "nodeids": [f"node//{node_id}"],
                    "runAsUser": run_as_user,
                    "type": shell,
                    "responseid": "trmm",
                }
            )
        )


async def wake_on_lan(*, uri: str, mesh_node_id: str) -> None:
    node_id = _b64_to_hex(mesh_node_id)
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "action": "wakedevices",
                    "nodeids": [f"node//{node_id}"],
                    "responseid": "trmm",
                }
            )
        )


async def remove_mesh_agent(uri: str, mesh_node_id: str) -> None:
    node_id = _b64_to_hex(mesh_node_id)
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "action": "removedevices",
                    "nodeids": [f"node//{node_id}"],
                    "responseid": "trmm",
                }
            )
        )
        # MeshCentral responde 'ok' de inmediato pero ejecuta el db.Remove del
        # nodo en un callback asíncrono POSTERIOR (ver meshuser.js, acción
        # 'removedevices'). Si cerramos el websocket apenas hacemos el send,
        # el borrado puede quedar sin ejecutarse y el nodo queda huérfano.
        # OJO: al abrir control.ashx el server empuja frames NO solicitados
        # (serverinfo/userinfo/...) ANTES de responder nuestro request, así que
        # un recv() único atrapa el serverinfo del handshake y cierra el socket
        # sin haber esperado el borrado. Por eso DRENAMOS los frames hasta ver
        # el evento 'removenode' (que MeshCentral emite recién cuando el callback
        # db.Remove ya corrió), manteniendo el socket abierto mientras tanto.
        # Best-effort con tope de 10s. Confiable a 1 nodo; para volumen se usa el
        # runbook SQL (bulk_delete_orphans_meshagents).
        async def _wait_removenode() -> None:
            async for message in ws:
                r = json.loads(message)
                if (r.get("event") or {}).get("action") == "removenode":
                    return

        try:
            await asyncio.wait_for(_wait_removenode(), timeout=10)
        except Exception:
            pass


def sysd_svc_is_running(svc: str) -> bool:
    cmd = ["systemctl", "is-active", "--quiet", svc]
    r = subprocess.run(cmd, capture_output=True)
    return not r.returncode


def get_meshagent_url(
    *, ident: "MeshAgentIdent", plat: str, mesh_site: str, mesh_device_id: str
) -> str:
    if settings.DOCKER_BUILD:
        base = settings.MESH_WS_URL.replace("ws://", "http://")
    elif getattr(settings, "USE_EXTERNAL_MESH", False):
        base = mesh_site
    else:
        mesh_port = getattr(settings, "MESH_PORT", 4430)
        base = f"http://127.0.0.1:{mesh_port}"

    if plat == AgentPlat.WINDOWS:
        params = {
            "id": ident,
            "meshid": mesh_device_id,
            "installflags": 0,
        }
    else:
        params = {
            "id": mesh_device_id,
            "installflags": 2,
            "meshinstall": ident,
        }

    return base + "/meshagents?" + urllib.parse.urlencode(params)


def make_alpha_numeric(s: str):
    return "".join(filter(str.isalnum, s))


def find_and_replace_db_values_str(*, text: str, instance):
    from observerrmm.utils import RE_DB_VALUE, get_db_value

    if not instance:
        return text

    return_string = text

    for string, model, prop in RE_DB_VALUE.findall(text):
        value = get_db_value(string=f"{model}.{prop}", instance=instance)
        return_string = return_string.replace(string, str(value))
    return return_string


# usually for stderr fields that contain windows file paths, like {{alert.get_result.stderr}}
# but preserves newlines or tabs
# removes all control chars
def _sanitize_webhook(s: str) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", s)
    s = re.sub(r"(?<!\\)(\\)(?![\\nrt])", r"\\\\", s)
    return s


def _run_url_rest_action(*, url: str, method, body: str, headers: str, instance=None):
    # replace url
    new_url = find_and_replace_db_values_str(text=url, instance=instance)
    new_body = find_and_replace_db_values_str(text=body, instance=instance)
    new_headers = find_and_replace_db_values_str(text=headers, instance=instance)
    new_url = requote_uri(new_url)

    new_body = _sanitize_webhook(new_body)
    try:
        new_body = json.loads(new_body, strict=False)
    except Exception as e:
        logger.error(f"{e=} {body=}")
        logger.error(f"{new_body=}")

    try:
        new_headers = json.loads(new_headers, strict=False)
    except Exception as e:
        logger.error(f"{e=} {headers=}")
        logger.error(f"{new_headers=}")

    if method in ("get", "delete"):
        return getattr(requests, method)(new_url, headers=new_headers)

    return getattr(requests, method)(
        new_url,
        data=json.dumps(new_body),
        headers=new_headers,
        timeout=8,
    )


def run_url_rest_action(*, action_id: int, instance=None) -> tuple[str, int]:
    if getattr(settings, "DEMO", False):
        return ("Not available in demo", 200)

    from core.models import URLAction

    action = URLAction.objects.get(pk=action_id)
    method = action.rest_method
    url = action.pattern
    body = action.rest_body
    headers = action.rest_headers

    try:
        response = _run_url_rest_action(
            url=url, method=method, body=body, headers=headers, instance=instance
        )
    except Exception as e:
        logger.error(str(e))
        return (str(e), 500)

    return (response.text, response.status_code)


lookup_apps = {
    "client": ("clients", "Client"),
    "site": ("clients", "Site"),
    "agent": ("agents", "Agent"),
}


def run_test_url_rest_action(
    *,
    url: str,
    method,
    body: str,
    headers: str,
    instance_type: Optional[str],
    instance_id: Optional[int],
) -> tuple[str, str, str]:
    if getattr(settings, "DEMO", False):
        return ("Not available in demo", "n/a", "n/a")

    lookup_instance = None
    if instance_type and instance_type in lookup_apps and instance_id:
        app, model = lookup_apps[instance_type]
        Model = apps.get_model(app, model)
        if instance_type == "agent":
            lookup_instance = Model.objects.get(agent_id=instance_id)
        else:
            lookup_instance = Model.objects.get(pk=instance_id)

    try:
        response = _run_url_rest_action(
            url=url, method=method, body=body, headers=headers, instance=lookup_instance
        )
    except requests.exceptions.ConnectionError as error:
        return (str(error), str(error.request.url), str(error.request.body))
    except Exception as e:
        return (str(e), str(e), str(e))

    return (response.text, response.request.url, response.request.body)


def run_server_script(
    *, body: str, args: list[str], env_vars: list[str], shell: str, timeout: int
) -> tuple[str, str, float, int]:
    disabled_ret = ("", "Error: this feature is disabled", 0.00, 1)
    if getattr(settings, "DEMO", False):
        return disabled_ret

    from core.models import CoreSettings
    from scripts.models import Script

    core = CoreSettings.objects.only("enable_server_scripts").first()
    if not core.server_scripts_enabled:  # type: ignore
        return disabled_ret

    body = Script.replace_with_snippets(body)

    parsed_args = Script.parse_script_args(None, shell, args)

    parsed_env_vars = Script.parse_script_env_vars(None, shell=shell, env_vars=env_vars)

    custom_env = os.environ.copy()
    for var in parsed_env_vars:
        var_split = var.split("=")
        custom_env[var_split[0]] = var_split[1]

    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, prefix="trmm-"
    ) as tmp_script:
        tmp_script.write(body.replace("\r\n", "\n"))
        tmp_script_path = tmp_script.name

    os.chmod(tmp_script_path, 0o550)

    stdout, stderr = "", ""
    retcode = 0

    start_time = time.time()
    try:
        ret = subprocess.run(
            [tmp_script_path] + parsed_args,
            capture_output=True,
            text=True,
            env=custom_env,
            timeout=timeout,
        )
        stdout, stderr, retcode = ret.stdout, ret.stderr, ret.returncode
    except subprocess.TimeoutExpired:
        stderr = f"Error: Timed out after {timeout} seconds."
        retcode = 98
    except Exception as e:
        stderr = f"Error: {e}"
        retcode = 99
    finally:
        execution_time = time.time() - start_time

        with suppress(Exception):
            os.remove(tmp_script_path)

    return stdout, stderr, execution_time, retcode
