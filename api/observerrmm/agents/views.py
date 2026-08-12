import asyncio
import datetime as dt
import random
import string
import time
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone as djangotime
from django.utils.dateparse import parse_datetime
from meshctrl.utils import get_login_token
from packaging import version as pyver
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from checks.models import CheckHistory
from core.tasks import sync_mesh_perms_task
from core.utils import (
    get_core_settings,
    get_mesh_ws_url,
    token_is_valid,
    wake_on_lan,
)
from logs.models import AuditLog, PendingAction
from scripts.models import Script
from scripts.tasks import bulk_command_task, bulk_script_task
from observerrmm.constants import (
    AGENT_CONSOLE_UNINSTALL_CACHE_PREFIX,
    AGENT_CONSOLE_UNINSTALL_CACHE_TIMEOUT,
    AGENT_DEFER,
    AGENT_STATUS_OFFLINE,
    AGENT_STATUS_ONLINE,
    ALARM_DEFAULT_SECONDS,
    ALARM_MAX_SECONDS,
    ALARM_MIN_SECONDS,
    ALERT_MAX_MESSAGE_LEN,
    ALERT_MAX_TITLE_LEN,
    ENDPOINT_RESPONSE_CODES,
    ENDPOINT_RESPONSE_PREFIX,
    GEO_CHECK_HISTORY_ID,
    LOST_MODE_MAX_INTERVAL_MIN,
    LOST_MODE_MIN_INTERVAL_MIN,
    NATS_UNREACHABLE,
    AgentHistoryType,
    AgentMonType,
    AgentPlat,
    CustomFieldModel,
    EndpointResponseAction,
    EvtLogNames,
    LostModeAction,
    PAAction,
    PAStatus,
)
from observerrmm.helpers import date_is_in_past, notify_error
from observerrmm.permissions import (
    _has_perm,
    _has_perm_on_agent,
    _has_perm_on_client,
    _has_perm_on_site,
)
from observerrmm.utils import get_default_timezone, reload_nats
from winupdate.models import WinUpdate, WinUpdatePolicy
from winupdate.serializers import WinUpdatePolicySerializer
from winupdate.tasks import bulk_check_for_updates_task, bulk_install_updates_task

from .models import Agent, AgentCustomField, AgentHistory, LostModeState, Note
from .permissions import (
    AgentHistoryPerms,
    AgentNotesPerms,
    AgentPerms,
    AgentRegistryPerms,
    AgentWOLPerms,
    EvtLogPerms,
    InstallAgentPerms,
    LockAgentPerms,
    ManageLostModePerms,
    ManageProcPerms,
    MeshPerms,
    RebootAgentPerms,
    RecoverAgentPerms,
    RunBulkPerms,
    RunScriptPerms,
    SendAlertPerms,
    SendCMDPerms,
    SoundAlarmPerms,
    UpdateAgentPerms,
)
from .serializers import (
    AgentCustomFieldSerializer,
    AgentHistorySerializer,
    AgentHostnameSerializer,
    AgentNoteSerializer,
    AgentSerializer,
    AgentTableSerializer,
    LostModeStateSerializer,
)
from .tasks import (
    bulk_endpoint_response_task,
    bulk_recover_agents_task,
    run_script_email_results_task,
    send_agent_update_task,
)
from .utils import get_validated_agent, send_nats_command


class GetAgents(APIView):
    permission_classes = [IsAuthenticated, AgentPerms]

    def get(self, request):
        monitoring_type_filter = Q()
        client_site_filter = Q()

        monitoring_type = request.query_params.get("monitoring_type", None)
        if monitoring_type:
            if monitoring_type in AgentMonType.values:
                monitoring_type_filter = Q(monitoring_type=monitoring_type)
            else:
                return notify_error("monitoring type does not exist")

        if "site" in request.query_params.keys():
            client_site_filter = Q(site_id=request.query_params["site"])
        elif "client" in request.query_params.keys():
            client_site_filter = Q(site__client_id=request.query_params["client"])

        # by default detail=true
        if (
            "detail" not in request.query_params.keys()
            or "detail" in request.query_params.keys()
            and request.query_params["detail"] == "true"
        ):
            agents = (
                Agent.objects.filter_by_role(request.user)  # type: ignore
                .filter(monitoring_type_filter)
                .filter(client_site_filter)
                .select_related(
                    "site__client",
                    "policy",
                    "alert_template",
                )
                .prefetch_related(
                    Prefetch(
                        "custom_fields",
                        queryset=AgentCustomField.objects.select_related("field"),
                    ),
                )
                .annotate(
                    has_patches_pending=Exists(
                        WinUpdate.objects.filter(
                            agent_id=OuterRef("pk"), action="approve", installed=False
                        )
                    ),
                    _pending_actions_count=Count(
                        "pendingactions",
                        filter=Q(pendingactions__status=PAStatus.PENDING),
                    ),
                )
                .defer(
                    "services",
                    "created_by",
                    "created_time",
                    "modified_by",
                    "modified_time",
                )
            )
            serializer = AgentTableSerializer(agents, many=True)

        # if detail=false
        else:
            agents = (
                Agent.objects.filter_by_role(request.user)  # type: ignore
                .defer(*AGENT_DEFER)
                .select_related("site__client")
                .filter(monitoring_type_filter)
                .filter(client_site_filter)
            )
            serializer = AgentHostnameSerializer(agents, many=True)

        return Response(serializer.data)


class GetUpdateDeleteAgent(APIView):
    permission_classes = [IsAuthenticated, AgentPerms]

    class InputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Agent
            fields = [
                "maintenance_mode",  # TODO separate this
                "policy",  # TODO separate this
                "block_policy_inheritance",  # TODO separate this
                "monitoring_type",
                "description",
                "overdue_email_alert",
                "overdue_text_alert",
                "overdue_dashboard_alert",
                "offline_time",
                "overdue_time",
                "check_interval",
                "time_zone",
                "site",
                "geo_offsite_allowed",  # feature 026: excluye de la geocerca
            ]

    # get agent details
    def get(self, request, agent_id):
        from checks.models import Check, CheckResult

        agent = get_object_or_404(
            Agent.objects.select_related(
                "site__server_policy",
                "site__workstation_policy",
                "site__client__server_policy",
                "site__client__workstation_policy",
                "policy",
                "alert_template",
            ).prefetch_related(
                Prefetch(
                    "agentchecks",
                    queryset=Check.objects.select_related("script"),
                ),
                Prefetch(
                    "checkresults",
                    queryset=CheckResult.objects.select_related("assigned_check"),
                ),
                Prefetch(
                    "custom_fields",
                    queryset=AgentCustomField.objects.select_related("field"),
                ),
                Prefetch(
                    "winupdatepolicy",
                    queryset=WinUpdatePolicy.objects.select_related("agent", "policy"),
                ),
            ),
            agent_id=agent_id,
        )
        return Response(AgentSerializer(agent).data)

    # edit agent
    def put(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        s = self.InputSerializer(instance=agent, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()

        if "winupdatepolicy" in request.data.keys():
            policy = agent.winupdatepolicy.get()  # type: ignore
            p_serializer = WinUpdatePolicySerializer(
                instance=policy, data=request.data["winupdatepolicy"][0]
            )
            p_serializer.is_valid(raise_exception=True)
            p_serializer.save()

        if "custom_fields" in request.data.keys():
            for field in request.data["custom_fields"]:
                custom_field = field
                custom_field["agent"] = agent.pk

                if AgentCustomField.objects.filter(
                    field=field["field"], agent=agent.pk
                ):
                    value = AgentCustomField.objects.get(
                        field=field["field"], agent=agent.pk
                    )
                    serializer = AgentCustomFieldSerializer(
                        instance=value, data=custom_field
                    )
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                else:
                    serializer = AgentCustomFieldSerializer(data=custom_field)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()

        sync_mesh_perms_task.delay()
        return Response("The agent was updated successfully")

    # uninstall agent
    def delete(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        code = "foo"  # stub for windows
        if agent.plat == AgentPlat.LINUX:
            code = Path(settings.LINUX_AGENT_SCRIPT).read_text()
        elif agent.plat == AgentPlat.DARWIN:
            code = Path(settings.MAC_UNINSTALL).read_text()

        # El script que estamos por disparar avisa al servidor antes de
        # destruirse (endpoint /api/v3/uninstalled/). Sin esta marca, ese aviso
        # se leería como una desinstalación MANUAL y levantaría una alerta falsa
        # por cada borrado hecho desde la consola. Va antes del nats_cmd: el
        # agente puede reaccionar en menos de lo que tarda el resto del request.
        cache.set(
            f"{AGENT_CONSOLE_UNINSTALL_CACHE_PREFIX}{agent.agent_id}",
            True,
            AGENT_CONSOLE_UNINSTALL_CACHE_TIMEOUT,
        )
        asyncio.run(agent.nats_cmd({"func": "uninstall", "code": code}, wait=False))
        name = agent.hostname
        # El borrado del nodo en MeshCentral lo propaga la señal post_delete de
        # Agent (agents/signals.py → remove_mesh_node_task), que cubre esta y
        # todas las demás rutas de borrado.
        agent.delete()
        reload_nats()
        sync_mesh_perms_task.delay()
        return Response(f"{name} will now be uninstalled.")


class AgentProcesses(APIView):
    permission_classes = [IsAuthenticated, ManageProcPerms]

    # list agent processes
    def get(self, request, agent_id):
        if getattr(settings, "DEMO", False):
            from observerrmm.demo_views import demo_get_procs

            return demo_get_procs()

        agent = get_object_or_404(Agent, agent_id=agent_id)
        r = asyncio.run(agent.nats_cmd(data={"func": "procs"}, timeout=5))
        if r in ("timeout", "natsdown"):
            return notify_error("Unable to contact the agent")
        return Response(r)

    # kill agent process
    def delete(self, request, agent_id, pid):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        r = asyncio.run(
            agent.nats_cmd({"func": "killproc", "procpid": int(pid)}, timeout=15)
        )

        if r in ("timeout", "natsdown"):
            return notify_error("Unable to contact the agent")
        elif r != "ok":
            return notify_error(r)

        return Response(f"Process with PID: {pid} was ended successfully")


class WebVNC(APIView):
    permission_classes = [IsAuthenticated, MeshPerms]

    def get(self, request, agent_id, port):
        from urllib.parse import urlparse

        from core.mesh_utils import MeshSync

        agent = get_object_or_404(
            Agent.objects.select_related("site__client").defer(*AGENT_DEFER),
            agent_id=agent_id,
        )
        if agent.hex_mesh_node_id == "error":
            return notify_error("Missing mesh node id")

        core = get_core_settings()

        uri = get_mesh_ws_url()
        ms = MeshSync(uri)

        payload = {
            "action": "getcookie",
            "name": None,
            "nodeid": f"node//{agent.hex_mesh_node_id}",
            "tag": "novnc",
            "tcpaddr": None,
            "tcpport": int(port),
        }
        cookie_ret = ms.mesh_action(payload=payload, wait=True)

        vnc_url = (
            core.mesh_site
            + "/novnc/vnc.html?ws=wss%3A%2F%2F"
            + urlparse(core.mesh_site).netloc
            + "%2F"
            + "meshrelay.ashx%3Fauth%3D"
            + cookie_ret["cookie"]  # type: ignore
            + f"&show_dot=1&l=en&resize=scale&name={agent.hostname}"
        )

        ret = {
            "hostname": agent.hostname,
            "vnc": vnc_url,
            "client": agent.client.name,
            "site": agent.site.name,
        }
        return Response(ret)


class AgentMeshCentral(APIView):
    permission_classes = [IsAuthenticated, MeshPerms]

    # get mesh urls
    def get(self, request, agent_id):
        agent = get_object_or_404(
            Agent.objects.select_related("site__client").defer(*AGENT_DEFER),
            agent_id=agent_id,
        )
        core = get_core_settings()

        user = (
            request.user.mesh_user_id
            if core.sync_mesh_with_ormm
            else f"user//{core.mesh_api_superuser}"
        )
        token = get_login_token(key=core.mesh_token, user=user)
        token_param = f"login={token}&"

        control = f"{core.mesh_site}/?{token_param}gotonode={agent.mesh_node_id}&viewmode=11&hide=31"
        terminal = f"{core.mesh_site}/?{token_param}gotonode={agent.mesh_node_id}&viewmode=12&hide=31"
        file = f"{core.mesh_site}/?{token_param}gotonode={agent.mesh_node_id}&viewmode=13&hide=31"

        AuditLog.audit_mesh_session(
            username=request.user.username,
            agent=agent,
            debug_info={"ip": request._client_ip},
        )

        ret = {
            "hostname": agent.hostname,
            "control": control,
            "terminal": terminal,
            "file": file,
            "status": agent.status,
            "client": agent.client.name,
            "site": agent.site.name,
        }
        return Response(ret)

    # start mesh recovery
    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        data = {"func": "recover", "payload": {"mode": "mesh"}}
        r = asyncio.run(agent.nats_cmd(data, timeout=90))
        if r != "ok":
            return notify_error("Unable to contact the agent")

        return Response(f"Repaired mesh agent on {agent.hostname}")


@api_view(["GET"])
@permission_classes([IsAuthenticated, AgentPerms])
def get_agent_versions(request):
    agents = (
        Agent.objects.defer(*AGENT_DEFER)
        .filter_by_role(request.user)  # type: ignore
        .select_related("site__client")
    )
    return Response(
        {
            "versions": [settings.LATEST_AGENT_VER],
            "agents": AgentHostnameSerializer(agents, many=True).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, UpdateAgentPerms])
def update_agents(request):
    # order_by explicito: sin el, PostgreSQL puede devolver las filas en
    # cualquier orden y la lista que sale hacia Celery cambia entre corridas.
    # Es lo que volvia intermitente a test_agent_update_permissions, que compara
    # los agent_ids contra el orden de entrada. Se ordena por PK (orden de
    # registro) y no por agent_id: la comparacion de texto en Postgres depende de
    # la collation de la BD y no coincide con sorted() de Python, asi que ordenar
    # por agent_id cambiaria el flake por una diferencia local-vs-CI.
    q = (
        Agent.objects.filter_by_role(request.user)  # type: ignore
        .filter(agent_id__in=request.data["agent_ids"])
        .only("agent_id", "version")
        .order_by("id")
    )
    agent_ids: list[str] = [
        i.agent_id
        for i in q
        if pyver.parse(i.version) < pyver.parse(settings.LATEST_AGENT_VER)
    ]

    token, _ = token_is_valid()
    send_agent_update_task.delay(agent_ids=agent_ids, token=token, force=False)
    return Response("ok")


@api_view(["GET"])
@permission_classes([IsAuthenticated, AgentPerms])
def ping(request, agent_id):
    agent = get_object_or_404(Agent, agent_id=agent_id)
    status = AGENT_STATUS_OFFLINE
    attempts = 0
    while 1:
        r = asyncio.run(agent.nats_cmd({"func": "ping"}, timeout=2))
        if r == "pong":
            status = AGENT_STATUS_ONLINE
            break
        else:
            attempts += 1
            time.sleep(0.5)

        if attempts >= 3:
            break

    return Response({"name": agent.hostname, "status": status})


@api_view(["GET"])
@permission_classes([IsAuthenticated, EvtLogPerms])
def get_event_log(request, agent_id, logtype, days):
    if getattr(settings, "DEMO", False):
        from observerrmm.demo_views import demo_get_eventlog

        return demo_get_eventlog()

    agent = get_object_or_404(Agent, agent_id=agent_id)
    timeout = 180 if logtype == EvtLogNames.SECURITY else 30

    data = {
        "func": "eventlog",
        "timeout": timeout,
        "payload": {
            "logname": logtype,
            "days": str(days),
        },
    }
    r = asyncio.run(agent.nats_cmd(data, timeout=timeout + 2))
    if r in ("timeout", "natsdown"):
        return notify_error("Unable to contact the agent")

    return Response(r)


@api_view(["POST"])
@permission_classes([IsAuthenticated, SendCMDPerms])
def send_raw_cmd(request, agent_id):
    agent = get_object_or_404(Agent, agent_id=agent_id)
    timeout = int(request.data["timeout"])
    if request.data["shell"] == "custom" and request.data["custom_shell"]:
        shell = request.data["custom_shell"]
    else:
        shell = request.data["shell"]

    data = {
        "func": "rawcmd",
        "timeout": timeout,
        "payload": {
            "command": request.data["cmd"],
            "shell": shell,
        },
        "run_as_user": request.data["run_as_user"],
    }

    hist = AgentHistory.objects.create(
        agent=agent,
        type=AgentHistoryType.CMD_RUN,
        command=request.data["cmd"],
        username=request.user.username[:50],
    )
    data["id"] = hist.pk

    r = asyncio.run(agent.nats_cmd(data, timeout=timeout + 2))

    if r == "timeout":
        return notify_error("Unable to contact the agent")

    AuditLog.audit_raw_command(
        username=request.user.username,
        agent=agent,
        cmd=request.data["cmd"],
        shell=shell,
        debug_info={"ip": request._client_ip},
    )

    return Response(r)


class Shutdown(APIView):
    permission_classes = [IsAuthenticated, RebootAgentPerms]

    # shutdown
    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        r = asyncio.run(agent.nats_cmd({"func": "shutdown"}, timeout=10))
        if r != "ok":
            return notify_error("Unable to contact the agent")

        return Response("ok")


class Reboot(APIView):
    permission_classes = [IsAuthenticated, RebootAgentPerms]

    # reboot now
    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        r = asyncio.run(agent.nats_cmd({"func": "rebootnow"}, timeout=10))
        if r != "ok":
            return notify_error("Unable to contact the agent")

        return Response("ok")

    # reboot later
    def patch(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        if agent.is_posix:
            return notify_error(f"Not currently implemented for {agent.plat}")

        try:
            obj = dt.datetime.strptime(request.data["datetime"], "%Y-%m-%dT%H:%M")
        except Exception:
            return notify_error("Invalid date")

        if date_is_in_past(datetime_obj=obj, agent_tz=agent.timezone):
            return notify_error("Date cannot be set in the past")

        task_name = "ObserverRMM_SchedReboot_" + "".join(
            random.choice(string.ascii_letters) for _ in range(10)
        )

        expire_date = obj + djangotime.timedelta(minutes=5)

        nats_data = {
            "func": "schedtask",
            "schedtaskpayload": {
                "type": "schedreboot",
                "enabled": True,
                "delete_expired_task_after": True,
                "start_when_available": False,
                "multiple_instances": 2,
                "trigger": "runonce",
                "name": task_name,
                "start_year": int(dt.datetime.strftime(obj, "%Y")),
                "start_month": int(dt.datetime.strftime(obj, "%-m")),
                "start_day": int(dt.datetime.strftime(obj, "%-d")),
                "start_hour": int(dt.datetime.strftime(obj, "%-H")),
                "start_min": int(dt.datetime.strftime(obj, "%-M")),
                "expire_year": int(expire_date.strftime("%Y")),
                "expire_month": int(expire_date.strftime("%-m")),
                "expire_day": int(expire_date.strftime("%-d")),
                "expire_hour": int(expire_date.strftime("%-H")),
                "expire_min": int(expire_date.strftime("%-M")),
            },
        }

        r = asyncio.run(agent.nats_cmd(nats_data, timeout=10))
        if r != "ok":
            return notify_error(r)

        details = {"taskname": task_name, "time": str(obj)}
        PendingAction.objects.create(
            agent=agent, action_type=PAAction.SCHED_REBOOT, details=details
        )
        nice_time = dt.datetime.strftime(obj, "%B %d, %Y at %I:%M %p")
        return Response(
            {"time": nice_time, "agent": agent.hostname, "task_name": task_name}
        )


# Feature 028 · respuesta rápida de endpoint (lock / alert / alarm).
#
# Homologación de las acciones `lock`, `alert` y `alarm` de Prey (backlog 024).
# `lock` acá es el bloqueo de sesión nativo del SO (Tier 1), NO el overlay
# antirrobo tipo kiosco de Prey, que quedó fuera de alcance por ser una app de UI
# nativa por plataforma.
#
# Las tres comparten la forma de responder, y esa forma es deliberada: se devuelve
# un CÓDIGO que la consola traduce, no una frase. El agente no sabe en qué idioma
# trabaja el operador y no debería inventárselo.


def _endpoint_response(agent: "Agent", nats_data: dict) -> Response:
    """Manda la acción al agente y traduce su respuesta a HTTP.

    Se distinguen tres desenlaces porque al operador le importan distinto:

    - `ok`: la acción se ejecutó.
    - agente incomunicado (`timeout`/`natsdown`): problema de conectividad; el
      equipo puede estar apagado o sin red.
    - código de error del agente: el equipo contestó y explicó por qué no pudo.
      El caso típico es `no_user_session` — nadie tiene sesión abierta, así que el
      mensaje NO se vio. Reportar "ok" ahí sería mentirle al operador.
    """
    r = asyncio.run(agent.nats_cmd(nats_data, timeout=15))

    if r == "ok":
        return Response("ok")

    if r in NATS_UNREACHABLE:
        return notify_error(f"{ENDPOINT_RESPONSE_PREFIX}agent_unreachable")

    # Un código desconocido (agente viejo que no entiende el comando y devuelve
    # otra cosa) se normaliza a "error" en vez de mostrarse crudo en pantalla.
    code = r if r in ENDPOINT_RESPONSE_CODES else "error"
    return notify_error(f"{ENDPOINT_RESPONSE_PREFIX}{code}")


class LockAgent(APIView):
    permission_classes = [IsAuthenticated, LockAgentPerms]

    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        AuditLog.audit_endpoint_response(
            username=request.user.username,
            agent=agent,
            action=EndpointResponseAction.LOCK,
            debug_info={"ip": request._client_ip},
        )

        return _endpoint_response(agent, {"func": "lock"})


class SendAlert(APIView):
    permission_classes = [IsAuthenticated, SendAlertPerms]

    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        title = str(request.data.get("title", "")).strip()
        message = str(request.data.get("message", "")).strip()

        # Se valida acá además de en el agente para no gastar un viaje por NATS en
        # algo que ya se sabe inválido, y para dar el error de inmediato en la UI.
        if not message:
            return notify_error(f"{ENDPOINT_RESPONSE_PREFIX}empty_message")

        title = title[:ALERT_MAX_TITLE_LEN]
        message = message[:ALERT_MAX_MESSAGE_LEN]

        AuditLog.audit_endpoint_response(
            username=request.user.username,
            agent=agent,
            action=EndpointResponseAction.ALERT,
            # El texto que el usuario vio queda registrado: es la respuesta a
            # "¿qué decía el mensaje que me apareció?".
            detail=message,
            debug_info={"ip": request._client_ip},
        )

        return _endpoint_response(
            agent,
            {"func": "alert", "payload": {"title": title, "message": message}},
        )


# Feature 028 Fase 2 · las dos banderas antirrobo de la alarma.
#
# Van en helpers de módulo porque las comparten la acción por agente y la masiva,
# y porque las tres decisiones que encierran —cómo se leen, cómo viajan y cómo se
# auditan— tienen que ser idénticas en los dos caminos. Duplicarlas era la forma
# más fácil de que la masiva quedara sin auditoría del "para siempre".


def _alarm_flag(value: object) -> bool:
    """Lee una bandera de la alarma fallando CERRADO.

    Son las dos opciones más peligrosas de la feature —sonar sin límite, y al
    máximo—, así que cualquier valor que no sea un verdadero reconocible se lee
    como falso. Acepta el bool nativo de JSON y también su forma en texto, que es
    como llega desde un formulario.
    """
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _alarm_payload(duration: int, forever: bool, max_volume: bool) -> dict[str, str]:
    """Arma el payload NATS.

    Todo va como texto porque del otro lado `NatsMsg.Data` es un
    `map[string]string` (`agent/rpc.go`), igual que la duración de siempre.

    ⚠️ La eterna NO se codifica como `duration=0`: `PlayAlarm` interpreta un
    `<= 0` como "usa el default de 30 s", así que reutilizar el cero daría una
    alarma de medio minuto sin ningún aviso. Por eso es un campo propio.
    """
    return {
        "duration": str(duration),
        "forever": "1" if forever else "0",
        "max_volume": "1" if max_volume else "0",
    }


def _alarm_audit_detail(duration: int, forever: bool, max_volume: bool) -> str:
    """Describe la alarma para el registro de auditoría.

    Antes de la Fase 2 esto era `f"{duration}s"` a secas, y con las dos banderas
    nuevas eso dejaría sin respuesta la pregunta "¿quién dejó este equipo sonando
    para siempre al máximo?" — que es justo lo que la auditoría de respuesta
    rápida existe para contestar.

    El caso de siempre conserva EXACTAMENTE el formato anterior (`"30s"`), para
    no romper a nadie que ya esté leyendo estos registros; las banderas sólo
    agregan texto cuando están encendidas.
    """
    detail = "forever" if forever else f"{duration}s"
    if max_volume:
        detail += "+max_volume"
    return detail


class SoundAlarm(APIView):
    permission_classes = [IsAuthenticated, SoundAlarmPerms]

    # hacer sonar la alarma
    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        forever = _alarm_flag(request.data.get("forever"))
        max_volume = _alarm_flag(request.data.get("max_volume"))

        try:
            duration = int(request.data.get("duration", ALARM_DEFAULT_SECONDS))
        except (TypeError, ValueError):
            duration = ALARM_DEFAULT_SECONDS

        # El clamp se conserva y se calcula SIEMPRE, incluso con `forever`: así el
        # valor que viaja en el payload sigue siendo válido si el agente que lo
        # recibe es uno viejo, que ignora la bandera y sonaría los segundos
        # pedidos en vez de interpretar un cero como "para siempre".
        duration = max(ALARM_MIN_SECONDS, min(duration, ALARM_MAX_SECONDS))

        AuditLog.audit_endpoint_response(
            username=request.user.username,
            agent=agent,
            action=EndpointResponseAction.ALARM,
            detail=_alarm_audit_detail(duration, forever, max_volume),
            debug_info={"ip": request._client_ip},
        )

        return _endpoint_response(
            agent,
            {
                "func": "alarm",
                "payload": _alarm_payload(duration, forever, max_volume),
            },
        )

    # detener la alarma
    def delete(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        AuditLog.audit_endpoint_response(
            username=request.user.username,
            agent=agent,
            action=EndpointResponseAction.STOP_ALARM,
            debug_info={"ip": request._client_ip},
        )

        return _endpoint_response(agent, {"func": "stopalarm"})


# Feature 030 · modo perdido/robado (ADR-025).
#
# DELIBERADAMENTE NO usa `_endpoint_response()`. Ese helper devuelve HTTP 400 si
# el agente no contesta por NATS, que es lo correcto para `lock`/`alert`/`alarm`:
# son acciones efímeras y si el equipo no las recibió, no pasaron. Acá es al
# revés — el caso de uso central del modo perdido es un equipo **apagado, sin red
# o ya en manos de otro** al momento de marcarlo. La BD es la fuente de verdad;
# el empujón por NATS es *best-effort* y no condiciona el éxito de la operación.
#
# El canal garantizado de reconciliación es el polling de config que la geo ya
# hace (`/api/v3/<agentid>/config/`, T005): un equipo que estaba apagado al
# marcarlo se entera al reconectar, sin depender de este push.


def _lost_mode_interval(value: object, fallback: int) -> int:
    """Lee el intervalo en MINUTOS y lo acota en los dos extremos.

    Un 0 sería captura continua —mata la batería y delata al agente frente a
    quien tiene el equipo— y un valor enorme vuelve la feature inútil. El agente
    vuelve a acotarlo de su lado: el piso no puede depender sólo del servidor,
    porque el mismo valor le llega también por el polling de config.
    """
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return fallback

    return max(LOST_MODE_MIN_INTERVAL_MIN, min(interval, LOST_MODE_MAX_INTERVAL_MIN))


def _push_lost_mode(agent: "Agent", state: LostModeState) -> bool:
    """Empuja el estado al agente. Devuelve si llegó, sin levantar nunca.

    Cualquier fallo se traga a propósito: la operación ya quedó firme en la BD y
    auditada, y un equipo incomunicado es el escenario esperado, no un error.
    """
    try:
        r = asyncio.run(
            agent.nats_cmd(
                {
                    "func": "lost_mode",
                    "payload": {
                        "active": "1" if state.active else "0",
                        "interval_min": str(state.interval_min),
                    },
                },
                timeout=15,
            )
        )
    except Exception:
        return False

    return r == "ok"


class LostMode(APIView):
    permission_classes = [IsAuthenticated, ManageLostModePerms]

    # marcar como perdido
    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        reason = str(request.data.get("reason", "")).strip()

        # El motivo es obligatorio por ADR-025, no por comodidad de la UI: es lo
        # que sostiene la proporcionalidad de encender una recolección de
        # evidencia sobre la persona que tiene el equipo.
        if not reason:
            return notify_error(f"{ENDPOINT_RESPONSE_PREFIX}empty_reason")

        previo = LostModeState.objects.filter(agent=agent).first()
        interval_min = _lost_mode_interval(
            request.data.get("interval_min"),
            (
                previo.interval_min
                if previo
                else LostModeState._meta.get_field("interval_min").default
            ),
        )

        state, _ = LostModeState.objects.update_or_create(
            agent=agent,
            defaults={
                "active": True,
                "reason": reason,
                "marked_by": request.user,
                "marked_at": djangotime.now(),
                # Se limpia al re-marcar: un caso reabierto no arrastra la fecha
                # de recuperación del anterior.
                "recovered_at": None,
                "interval_min": interval_min,
            },
        )

        # La auditoría va SIEMPRE y antes del push: si el agente no contesta, el
        # caso igual quedó abierto y tiene que quedar registrado quién lo abrió.
        AuditLog.audit_lost_mode(
            username=request.user.username,
            agent=agent,
            action=LostModeAction.MARK,
            reason=reason,
            debug_info={"ip": request._client_ip},
        )

        return Response(
            {
                "status": "ok",
                "nats_delivered": _push_lost_mode(agent, state),
                "interval_min": state.interval_min,
            }
        )

    # marcar como recuperado
    def delete(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        # Sin motivo: recuperar es apagar una capacidad, no encenderla. El motivo
        # del marcaje original se conserva en la fila.
        state, _ = LostModeState.objects.update_or_create(
            agent=agent,
            defaults={"active": False, "recovered_at": djangotime.now()},
        )

        AuditLog.audit_lost_mode(
            username=request.user.username,
            agent=agent,
            action=LostModeAction.RECOVER,
            debug_info={"ip": request._client_ip},
        )

        return Response(
            {"status": "ok", "nats_delivered": _push_lost_mode(agent, state)}
        )


class LostModeList(APIView):
    """Índice de equipos actualmente marcados como perdidos.

    Sin `agent_id` en la ruta: el alcance lo recorta `filter_by_role`, igual que
    en el resto de los listados de la consola.
    """

    permission_classes = [IsAuthenticated, ManageLostModePerms]

    def get(self, request):
        qs = (
            LostModeState.objects.filter_by_role(request.user)
            .filter(active=True)
            .select_related("agent__site__client", "marked_by")
            .order_by("-marked_at")
        )
        return Response(LostModeStateSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, InstallAgentPerms])
def install_agent(request):
    from knox.models import AuthToken

    from accounts.models import User
    from agents.utils import get_agent_url
    from core.utils import token_is_valid

    insecure = getattr(settings, "ORMM_INSECURE", False)

    if insecure and request.data["installMethod"] in {"exe", "powershell"}:
        return notify_error(
            "Not available in insecure mode. Please use the 'Manual' method."
        )

    # TODO rework this ghetto validation hack
    # (ref. de issue del proyecto de origen: 1461)
    try:
        int(request.data["expires"])
    except ValueError:
        return notify_error("Please enter a valid number of hours")

    client_id = request.data["client"]
    site_id = request.data["site"]
    version = settings.LATEST_AGENT_VER
    goarch = request.data["goarch"]
    plat = request.data["plat"]

    if not _has_perm_on_site(request.user, site_id):
        raise PermissionDenied()

    codesign_token, is_valid = token_is_valid()

    # Code signing check disabled in Observer RMM fork (BRAINCORP internal use)
    # if request.data["installMethod"] in {"bash", "mac"} and not is_valid:
    #     return notify_error(
    #         "Linux/Mac agents require code signing. (upstream docs reference)"
    #     )

    inno = f"observeragent-v{version}-{plat}-{goarch}"
    if plat == AgentPlat.WINDOWS:
        inno += ".exe"

    download_url = get_agent_url(goarch=goarch, plat=plat, token=codesign_token)

    installer_user = User.objects.filter(is_installer_user=True).first()

    _, token = AuthToken.objects.create(
        user=installer_user, expiry=dt.timedelta(hours=int(request.data["expires"]))
    )

    install_flags = [
        "-m",
        "install",
        "--api",
        request.data["api"],
        "--client-id",
        client_id,
        "--site-id",
        site_id,
        "--agent-type",
        request.data["agenttype"],
        "--auth",
        token,
    ]

    if request.data["installMethod"] == "exe":
        from observerrmm.utils import generate_winagent_exe

        return generate_winagent_exe(
            client=client_id,
            site=site_id,
            agent_type=request.data["agenttype"],
            rdp=request.data["rdp"],
            ping=request.data["ping"],
            power=request.data["power"],
            goarch=goarch,
            token=token,
            api=request.data["api"],
            file_name=request.data["fileName"],
        )

    elif request.data["installMethod"] == "bash":
        from agents.utils import generate_linux_install

        return generate_linux_install(
            client=str(client_id),
            site=str(site_id),
            agent_type=request.data["agenttype"],
            arch=goarch,
            token=token,
            api=request.data["api"],
            download_url=download_url,
        )

    elif request.data["installMethod"] == "manual":
        resp = {}
        # El release es un instalador InnoSetup (setup.iss). Es un ejecutable GUI,
        # así que en cmd.exe hay que lanzarlo con `start /wait` para BLOQUEAR hasta
        # que termine: sin `start`, cmd no espera a los programas GUI y el paso de
        # enrolamiento correría antes de que exista el binario recién instalado
        # ("El sistema no puede encontrar la ruta especificada"). El `ping` como
        # sleep era una carrera frágil (~4 s) que fallaba si la instalación se
        # demoraba. Corre silencioso (/VERYSILENT) para copiar el binario a
        # C:\Program Files\ObserverAgent, registrar el servicio y crear la entrada
        # de desinstalación (unins*.exe + "Agregar o quitar programas"); luego se
        # enrola corriendo el binario instalado con `-m install`. Flujo de 2 pasos
        # (full-A / GAP-055). Es un comando de cmd.exe (símbolo del sistema), NO de
        # PowerShell: `&&` y `start` no son válidos en Windows PowerShell 5.x.
        cmd = [
            "start",
            "/wait",
            '""',
            inno,
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "&&",
            r'"C:\Program Files\ObserverAgent\observeragent.exe"',
        ] + install_flags

        if int(request.data["rdp"]):
            cmd.append("--rdp")
        if int(request.data["ping"]):
            cmd.append("--ping")
        if int(request.data["power"]):
            cmd.append("--power")

        if insecure:
            cmd.append("--insecure")

        resp["cmd"] = " ".join(str(i) for i in cmd)
        resp["url"] = download_url

        return Response(resp)

    elif request.data["installMethod"] == "mac":
        from agents.utils import generate_macos_install

        return generate_macos_install(
            client=str(client_id),
            site=str(site_id),
            agent_type=request.data["agenttype"],
            arch=goarch,
            token=token,
            api=request.data["api"],
            download_url=download_url,
        )

    elif request.data["installMethod"] == "powershell":
        text = Path(settings.BASE_DIR / "core" / "installer.ps1").read_text()

        replace_dict = {
            "innosetupchange": inno,
            "clientchange": str(client_id),
            "sitechange": str(site_id),
            "apichange": request.data["api"],
            "atypechange": request.data["agenttype"],
            "powerchange": str(request.data["power"]),
            "rdpchange": str(request.data["rdp"]),
            "pingchange": str(request.data["ping"]),
            "downloadchange": download_url,
            "tokenchange": token,
        }

        for i, j in replace_dict.items():
            text = text.replace(i, j)

        with StringIO(text) as fp:
            response = HttpResponse(fp.read(), content_type="text/plain")
            response["Content-Disposition"] = (
                "attachment; filename=observer-installer.ps1"
            )
            return response


@api_view(["POST"])
@permission_classes([IsAuthenticated, RecoverAgentPerms])
def recover(request, agent_id: str) -> Response:
    agent: Agent = get_object_or_404(
        Agent.objects.defer(*AGENT_DEFER), agent_id=agent_id
    )
    mode = request.data["mode"]

    if mode == "tacagent":
        uri = get_mesh_ws_url()
        agent.recover(mode, uri, wait=False)
        return Response("Recovery will be attempted shortly")

    elif mode == "mesh":
        r, err = agent.recover(mode, "")
        if err:
            return notify_error(f"Unable to complete recovery: {r}")

    return Response("Successfully completed recovery")


@api_view(["POST"])
@permission_classes([IsAuthenticated, RunScriptPerms])
def run_script(request, agent_id):
    agent = get_object_or_404(Agent, agent_id=agent_id)
    script = get_object_or_404(Script, pk=request.data["script"])
    output = request.data["output"]
    args = request.data["args"]
    run_as_user: bool = request.data["run_as_user"]
    env_vars: list[str] = request.data["env_vars"]
    req_timeout = int(request.data["timeout"]) + 3
    run_on_server: bool | None = request.data.get("run_on_server")

    if run_on_server and not get_core_settings().server_scripts_enabled:
        return notify_error("This feature is disabled.")

    AuditLog.audit_script_run(
        username=request.user.username,
        agent=agent,
        script=script.name,
        debug_info={"ip": request._client_ip},
    )

    hist = AgentHistory.objects.create(
        agent=agent,
        type=AgentHistoryType.SCRIPT_RUN,
        script=script,
        username=request.user.username[:50],
    )
    history_pk = hist.pk

    if run_on_server:
        from core.utils import run_server_script

        r = run_server_script(
            body=script.script_body,
            args=script.parse_script_args(agent, script.shell, args),
            env_vars=script.parse_script_env_vars(agent, script.shell, env_vars),
            shell=script.shell,
            timeout=req_timeout,
        )

        ret = {
            "stdout": r[0],
            "stderr": r[1],
            "execution_time": "{:.4f}".format(r[2]),
            "retcode": r[3],
        }

        hist.script_results = {**ret, "id": history_pk}
        hist.save(update_fields=["script_results"])

        return Response(ret)

    if output == "wait":
        r = agent.run_script(
            scriptpk=script.pk,
            args=args,
            timeout=req_timeout,
            wait=True,
            history_pk=history_pk,
            run_as_user=run_as_user,
            env_vars=env_vars,
        )
        return Response(r)

    elif output == "email":
        emails = (
            [] if request.data["emailMode"] == "default" else request.data["emails"]
        )
        run_script_email_results_task.delay(
            agentpk=agent.pk,
            scriptpk=script.pk,
            nats_timeout=req_timeout,
            emails=emails,
            args=args,
            history_pk=history_pk,
            run_as_user=run_as_user,
            env_vars=env_vars,
        )
    elif output == "collector":
        from core.models import CustomField

        r = agent.run_script(
            scriptpk=script.pk,
            args=args,
            timeout=req_timeout,
            wait=True,
            history_pk=history_pk,
            run_as_user=run_as_user,
            env_vars=env_vars,
        )

        custom_field = CustomField.objects.get(pk=request.data["custom_field"])

        if custom_field.model == CustomFieldModel.AGENT:
            field = custom_field.get_or_create_field_value(agent)
        elif custom_field.model == CustomFieldModel.CLIENT:
            field = custom_field.get_or_create_field_value(agent.client)
        elif custom_field.model == CustomFieldModel.SITE:
            field = custom_field.get_or_create_field_value(agent.site)
        else:
            return notify_error("Custom Field was invalid")

        value = (
            r.strip()
            if request.data["save_all_output"]
            else r.strip().split("\n")[-1].strip()
        )

        field.save_to_field(value)
        return Response(r)
    elif output == "note":
        r = agent.run_script(
            scriptpk=script.pk,
            args=args,
            timeout=req_timeout,
            wait=True,
            history_pk=history_pk,
            run_as_user=run_as_user,
            env_vars=env_vars,
        )

        Note.objects.create(agent=agent, user=request.user, note=r)
        return Response(r)
    else:
        agent.run_script(
            scriptpk=script.pk,
            args=args,
            timeout=req_timeout,
            history_pk=history_pk,
            run_as_user=run_as_user,
            env_vars=env_vars,
        )

    return Response(f"{script.name} will now be run on {agent.hostname}")


class GetAddNotes(APIView):
    permission_classes = [IsAuthenticated, AgentNotesPerms]

    def get(self, request, agent_id=None):
        if agent_id:
            agent = get_object_or_404(Agent, agent_id=agent_id)
            notes = Note.objects.filter(agent=agent)
        else:
            notes = Note.objects.filter_by_role(request.user)  # type: ignore

        return Response(AgentNoteSerializer(notes, many=True).data)

    def post(self, request):
        agent = get_object_or_404(Agent, agent_id=request.data["agent_id"])
        if not _has_perm_on_agent(request.user, agent.agent_id):
            raise PermissionDenied()

        if "note" not in request.data.keys():
            return notify_error("Cannot add an empty note")

        data = {
            "note": request.data["note"],
            "agent": agent.pk,
            "user": request.user.pk,
        }

        serializer = AgentNoteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response("Note added!")


class GetEditDeleteNote(APIView):
    permission_classes = [IsAuthenticated, AgentNotesPerms]

    def get(self, request, pk):
        note = get_object_or_404(Note, pk=pk)

        if not _has_perm_on_agent(request.user, note.agent.agent_id):
            raise PermissionDenied()

        return Response(AgentNoteSerializer(note).data)

    def put(self, request, pk):
        note = get_object_or_404(Note, pk=pk)

        if not _has_perm_on_agent(request.user, note.agent.agent_id):
            raise PermissionDenied()

        serializer = AgentNoteSerializer(instance=note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response("Note edited!")

    def delete(self, request, pk):
        note = get_object_or_404(Note, pk=pk)

        if not _has_perm_on_agent(request.user, note.agent.agent_id):
            raise PermissionDenied()

        note.delete()
        return Response("Note was deleted!")


@api_view(["POST"])
@permission_classes([IsAuthenticated, RunBulkPerms])
def bulk(request):
    if request.data["target"] == "agents" and not request.data["agents"]:
        return notify_error("Must select at least 1 agent")

    if request.data["target"] == "client":
        if not _has_perm_on_client(request.user, request.data["client"]):
            raise PermissionDenied()
        q = Agent.objects.filter_by_role(request.user).filter(  # type: ignore
            site__client_id=request.data["client"]
        )

    elif request.data["target"] == "site":
        if not _has_perm_on_site(request.user, request.data["site"]):
            raise PermissionDenied()
        q = Agent.objects.filter_by_role(request.user).filter(  # type: ignore
            site_id=request.data["site"]
        )

    elif request.data["target"] == "agents":
        q = Agent.objects.filter_by_role(request.user).filter(  # type: ignore
            agent_id__in=request.data["agents"]
        )

    elif request.data["target"] == "all":
        q = Agent.objects.filter_by_role(request.user).only("pk", "monitoring_type")  # type: ignore

    else:
        return notify_error("Something went wrong")

    if request.data["monType"] == "servers":
        q = q.filter(monitoring_type=AgentMonType.SERVER)
    elif request.data["monType"] == "workstations":
        q = q.filter(monitoring_type=AgentMonType.WORKSTATION)

    if request.data["osType"] == AgentPlat.WINDOWS:
        q = q.filter(plat=AgentPlat.WINDOWS)
    elif request.data["osType"] == AgentPlat.LINUX:
        q = q.filter(plat=AgentPlat.LINUX)
    elif request.data["osType"] == AgentPlat.DARWIN:
        q = q.filter(plat=AgentPlat.DARWIN)

    agents: list[int] = [agent.pk for agent in q]

    if not agents:
        return notify_error("No agents were found meeting the selected criteria")

    # Feature 028: los modos de respuesta rápida exigen SU permiso además de
    # `can_run_bulk`. Sin esto, cualquiera con permiso de acciones masivas podría
    # bloquear la flota completa aunque no tenga `can_lock_agents` — la superficie
    # bulk se convertiría en una forma de saltarse los tres permisos nuevos.
    bulk_response_perms = {
        "lock": "can_lock_agents",
        "alert": "can_send_alerts",
        "alarm": "can_sound_alarm",
        "stopalarm": "can_sound_alarm",
    }
    required_perm = bulk_response_perms.get(request.data["mode"])
    if required_perm and not _has_perm(request, required_perm):
        raise PermissionDenied()

    AuditLog.audit_bulk_action(
        request.user,
        request.data["mode"],
        request.data,
        debug_info={"ip": request._client_ip},
    )

    ht = "Check the History tab on the agent to view the results."

    if request.data["mode"] == "command":
        if request.data["shell"] == "custom" and request.data["custom_shell"]:
            shell = request.data["custom_shell"]
        else:
            shell = request.data["shell"]

        bulk_command_task.delay(
            agent_pks=agents,
            cmd=request.data["cmd"],
            shell=shell,
            timeout=request.data["timeout"],
            username=request.user.username[:50],
            run_as_user=request.data["run_as_user"],
        )
        return Response(f"Command will now be run on {len(agents)} agents. {ht}")

    elif request.data["mode"] == "script":
        script = get_object_or_404(Script, pk=request.data["script"])

        # prevent API from breaking for those who haven't updated payload
        try:
            custom_field_pk = request.data["custom_field"]
            collector_all_output = request.data["collector_all_output"]
            save_to_agent_note = request.data["save_to_agent_note"]
        except KeyError:
            custom_field_pk = None
            collector_all_output = False
            save_to_agent_note = False

        bulk_script_task.delay(
            script_pk=script.pk,
            agent_pks=agents,
            args=request.data["args"],
            timeout=request.data["timeout"],
            username=request.user.username[:50],
            run_as_user=request.data["run_as_user"],
            env_vars=request.data["env_vars"],
            custom_field_pk=custom_field_pk,
            collector_all_output=collector_all_output,
            save_to_agent_note=save_to_agent_note,
        )

        return Response(f"{script.name} will now be run on {len(agents)} agents. {ht}")

    elif request.data["mode"] == "patch":
        if request.data["patchMode"] == "install":
            bulk_install_updates_task.delay(agents)
            return Response(
                f"Pending updates will now be installed on {len(agents)} agents"
            )
        elif request.data["patchMode"] == "scan":
            bulk_check_for_updates_task.delay(agents)
            return Response(f"Patch status scan will now run on {len(agents)} agents")

    # Feature 028 · respuesta rápida en masa.
    elif request.data["mode"] in ("lock", "alarm", "stopalarm"):
        payload = None
        if request.data["mode"] == "alarm":
            try:
                duration = int(request.data.get("duration", ALARM_DEFAULT_SECONDS))
            except (TypeError, ValueError):
                duration = ALARM_DEFAULT_SECONDS
            duration = max(ALARM_MIN_SECONDS, min(duration, ALARM_MAX_SECONDS))

            # Feature 028 Fase 2: las dos banderas también en masiva, por decisión
            # del usuario del 2026-07-27. La masiva es fire-and-forget y no
            # devuelve resultado por equipo, así que la salvaguarda no está acá
            # sino en la confirmación de la consola, que tiene que nombrar las dos
            # opciones activas y la cantidad de equipos alcanzados.
            #
            # La auditoría de este camino no necesita nada extra: `audit_bulk_action`
            # guarda `request.data` entera en `after_value`, o sea que `forever` y
            # `max_volume` quedan registradas tal como se pidieron.
            payload = _alarm_payload(
                duration,
                _alarm_flag(request.data.get("forever")),
                _alarm_flag(request.data.get("max_volume")),
            )

        bulk_endpoint_response_task.delay(
            agent_pks=agents, func=request.data["mode"], payload=payload
        )
        return Response({"mode": request.data["mode"], "count": len(agents)})

    elif request.data["mode"] == "alert":
        title = str(request.data.get("title", "")).strip()[:ALERT_MAX_TITLE_LEN]
        message = str(request.data.get("message", "")).strip()[:ALERT_MAX_MESSAGE_LEN]

        if not message:
            return notify_error(f"{ENDPOINT_RESPONSE_PREFIX}empty_message")

        bulk_endpoint_response_task.delay(
            agent_pks=agents,
            func="alert",
            payload={"title": title, "message": message},
        )
        return Response({"mode": "alert", "count": len(agents)})

    return notify_error("Something went wrong")


@api_view(["POST"])
@permission_classes([IsAuthenticated, AgentPerms])
def agent_maintenance(request):
    enabled = request.data["action"]

    if request.data["type"] == "Client":
        if not _has_perm_on_client(request.user, request.data["id"]):
            raise PermissionDenied()

        agents = Agent.objects.filter_by_role(request.user).filter(  # type: ignore
            site__client_id=request.data["id"]
        )
        affected = {"target": "client", "client": request.data["id"]}

    elif request.data["type"] == "Site":
        if not _has_perm_on_site(request.user, request.data["id"]):
            raise PermissionDenied()

        agents = Agent.objects.filter_by_role(request.user).filter(  # type: ignore
            site_id=request.data["id"]
        )
        affected = {"target": "site", "site": request.data["id"]}

    else:
        return notify_error("Invalid data")

    # Este es el segundo de los cuatro caminos de escritura del flag (ver el
    # invariante junto al campo en agents/models.py). El `.update()` masivo no
    # dispara señales, así que NO pasa por BaseAuditModel: sin las dos líneas de
    # abajo, un clic que silencia 300 equipos no deja rastro de quién fue —
    # que es justo el agujero que esta feature cierra.
    agent_ids = list(agents.values_list("agent_id", flat=True))
    count = agents.update(
        **Agent.maintenance_field_updates(enabled, request.user.username)
    )

    if count:
        action = "enabled" if enabled else "disabled"
        # Una entrada de ámbito, no una por equipo: 300 filas de auditoría por un
        # clic son ruido, y lo que se quiere poder reconstruir es "fulano silenció
        # el sitio X el día Y", con la lista de afectados dentro del after_value.
        affected["count"] = count
        affected["agent_ids"] = agent_ids
        AuditLog.audit_bulk_action(
            request.user.username,
            f"maintenance mode {action}",
            affected,
            debug_info={"ip": request._client_ip},
        )
        return Response(f"Maintenance mode has been {action} on {count} agents")

    return Response(
        "No agents have been put in maintenance mode. You might not have permissions to the resources."
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, RecoverAgentPerms])
def bulk_agent_recovery(request):
    bulk_recover_agents_task.delay()
    return Response("Agents will now be recovered")


class WMI(APIView):
    permission_classes = [IsAuthenticated, AgentPerms]

    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        r = asyncio.run(agent.nats_cmd({"func": "sysinfo"}, timeout=20))
        if r != "ok":
            return notify_error("Unable to contact the agent")
        return Response("Agent WMI data refreshed successfully")


class AgentHistoryView(APIView):
    permission_classes = [IsAuthenticated, AgentHistoryPerms]

    def get(self, request, agent_id=None):
        if agent_id:
            agent = get_object_or_404(Agent, agent_id=agent_id)
            history = AgentHistory.objects.filter(agent=agent)
        else:
            history = AgentHistory.objects.filter_by_role(request.user)  # type: ignore
        ctx = {"default_tz": get_default_timezone()}
        return Response(AgentHistorySerializer(history, many=True, context=ctx).data)


def _geo_visible(agent: "Agent") -> bool:
    """¿Se puede mostrar la ubicación de este equipo en la consola?

    Feature 030: el interruptor global de geo apagado ya NO basta para ocultarla
    si el equipo está marcado como perdido. Sin esta excepción, el bypass del
    agente (svc.go) publicaría puntos que la consola nunca mostraría — la feature
    sería un no-op visual en cualquier flota con la geo apagada por omisión, que
    es la instalación por defecto (ADR-024) y justo donde hace falta.

    Lo que sostiene la excepción es el mismo régimen de ADR-025 que sostiene el
    bypass del agente: motivo obligatorio, permiso dedicado y auditoría del
    marcaje. Y la consulta en sí ya queda auditada aparte (RF-09 / RN-02).
    """
    if get_core_settings().geo_tracking_enabled:
        return True

    return LostModeState.objects.filter(agent=agent, active=True).exists()


class AgentLocation(APIView):
    """Feature 023: última ubicación conocida del equipo.

    La posición "actual" se deriva de la última fila geo de CheckHistory (no se
    denormaliza en agents_agent). Si el interruptor global está apagado, responde
    {"enabled": false} — nunca 404 por estar apagado (eso se reserva para agente
    inexistente). Toda consulta queda auditada (RF-09 / RN-02).
    """

    permission_classes = [IsAuthenticated, AgentPerms]

    def get(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        AuditLog.audit_agent_location_viewed(
            username=request.user.username, agent=agent
        )

        if not _geo_visible(agent):
            return Response({"enabled": False})

        latest = (
            CheckHistory.objects.filter(
                agent_id=agent.agent_id, check_id=GEO_CHECK_HISTORY_ID
            )
            .order_by("-x")
            .first()
        )
        if not latest or not latest.results:
            return Response({"enabled": True, "lat": None, "long": None})

        r = latest.results
        return Response(
            {
                "enabled": True,
                "lat": r.get("lat"),
                "long": r.get("long"),
                "accuracy_m": latest.y,
                "source": r.get("source"),
                "captured_at": latest.x,
            }
        )


class AgentLocationHistory(APIView):
    """Feature 023: histórico de trayectoria (secuencia de puntos con timestamp).

    Lee de CheckHistory por rango de x. Respeta la retención existente
    (check_history_prune_days): no hay puntos más viejos que la ventana. Tope
    server-side con bandera `truncated` para no devolver series enormes.

    Feature 030: esta vista NO miraba el interruptor global, mientras que
    `AgentLocation` sí — o sea que con la geo apagada la posición actual quedaba
    oculta pero la trayectoria completa seguía saliendo por acá. Era una fuga, no
    una decisión: el test `test_latest_location_switch_off` dice explícitamente
    "aun habiendo puntos históricos, con el switch global apagado no se exponen".
    Ahora las dos vistas comparten la misma regla, `_geo_visible()`, incluida la
    excepción del modo perdido.

    La forma de la respuesta se mantiene (`points` vacío + `truncated`) y se le
    suma `enabled`, para no romper a un consumidor que sólo lee `points`.
    """

    permission_classes = [IsAuthenticated, AgentPerms]

    def get(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        AuditLog.audit_agent_location_viewed(
            username=request.user.username, agent=agent
        )

        if not _geo_visible(agent):
            return Response({"enabled": False, "points": [], "truncated": False})

        qs = CheckHistory.objects.filter(
            agent_id=agent.agent_id, check_id=GEO_CHECK_HISTORY_ID
        ).order_by("x")

        start = request.query_params.get("from")
        end = request.query_params.get("to")
        if start and parse_datetime(start):
            qs = qs.filter(x__gte=parse_datetime(start))
        if end and parse_datetime(end):
            qs = qs.filter(x__lte=parse_datetime(end))

        try:
            limit = int(request.query_params.get("limit", 500))
        except (TypeError, ValueError):
            limit = 500
        limit = max(1, min(limit, 5000))

        total = qs.count()
        points = [
            {
                "lat": row.results.get("lat"),
                "long": row.results.get("long"),
                "accuracy_m": row.y,
                "source": row.results.get("source"),
                "captured_at": row.x,
            }
            for row in qs[:limit]
            if row.results
        ]
        return Response({"enabled": True, "points": points, "truncated": total > limit})


class ScriptRunHistory(APIView):
    permission_classes = [IsAuthenticated, AgentHistoryPerms]

    class OutputSerializer(serializers.ModelSerializer):
        script_name = serializers.ReadOnlyField(source="script.name")
        agent_id = serializers.ReadOnlyField(source="agent.agent_id")

        class Meta:
            model = AgentHistory
            fields = (
                "id",
                "time",
                "username",
                "script",
                "script_results",
                "agent",
                "script_name",
                "agent_id",
            )
            read_only_fields = fields

    def get(self, request):
        date_range_filter = Q()
        script_name_filter = Q()

        start = request.query_params.get("start", None)
        end = request.query_params.get("end", None)
        limit = request.query_params.get("limit", None)
        script_name = request.query_params.get("scriptname", None)
        if start and end:
            start_dt = parse_datetime(start)
            end_dt = parse_datetime(end) + djangotime.timedelta(days=1)
            date_range_filter = Q(time__range=[start_dt, end_dt])

        if script_name:
            script_name_filter = Q(script__name=script_name)

        AGENT_R_DEFER = (
            "agent__wmi_detail",
            "agent__services",
            "agent__created_by",
            "agent__created_time",
            "agent__modified_by",
            "agent__modified_time",
            "agent__disks",
            "agent__operating_system",
            "agent__mesh_node_id",
            "agent__description",
            "agent__patches_last_installed",
            "agent__time_zone",
            "agent__alert_template_id",
            "agent__policy_id",
            "agent__site_id",
            "agent__version",
            "agent__plat",
            "agent__goarch",
            "agent__hostname",
            "agent__last_seen",
            "agent__public_ip",
            "agent__total_ram",
            "agent__boot_time",
            "agent__logged_in_username",
            "agent__last_logged_in_user",
            "agent__monitoring_type",
            "agent__overdue_email_alert",
            "agent__overdue_text_alert",
            "agent__overdue_dashboard_alert",
            "agent__offline_time",
            "agent__overdue_time",
            "agent__check_interval",
            "agent__needs_reboot",
            "agent__choco_installed",
            "agent__maintenance_mode",
            "agent__block_policy_inheritance",
        )
        hists = (
            AgentHistory.objects.filter(type=AgentHistoryType.SCRIPT_RUN)
            .select_related("agent")
            .select_related("script")
            .defer(*AGENT_R_DEFER)
            .filter(date_range_filter)
            .filter(script_name_filter)
            .order_by("-time")
        )
        if limit:
            try:
                lim = int(limit)
            except KeyError:
                return notify_error("Invalid limit")
            hists = hists[:lim]

        ret = self.OutputSerializer(hists, many=True).data
        return Response(ret)


@api_view(["POST"])
@permission_classes([IsAuthenticated, AgentWOLPerms])
def wol(request, agent_id):
    agent = get_object_or_404(
        Agent.objects.defer(*AGENT_DEFER),
        agent_id=agent_id,
    )
    try:
        uri = get_mesh_ws_url()
        asyncio.run(wake_on_lan(uri=uri, mesh_node_id=agent.mesh_node_id))
    except Exception as e:
        return notify_error(str(e))
    return Response(f"Wake-on-LAN sent to {agent.hostname}")


@api_view(["GET"])
@permission_classes([IsAuthenticated, AgentRegistryPerms])
def browse_registry(request, agent_id):
    agent = get_validated_agent(agent_id)
    if isinstance(agent, Response):
        return agent

    path = request.query_params.get("path", "Computer").strip()
    if path.lower() == "computer":
        path = "Computer"

    try:
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 200))
    except ValueError:
        return notify_error("page and page_size must be integers")

    payload = {"path": path, "page": str(page), "page_size": str(page_size)}
    r = send_nats_command(agent, "registry_browse", payload, timeout=30)

    if isinstance(r, Response):
        return r

    return Response(
        {
            "path": r.get("path", path),
            "subkeys": r.get("subkeys", []),
            "values": r.get("values", []),
            "has_more": r.get("has_more", False),
            "page": page,
            "page_size": page_size,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, AgentRegistryPerms])
def create_registry_key(request, agent_id):
    agent = get_validated_agent(agent_id)
    if isinstance(agent, Response):
        return agent

    path = (request.data.get("path") or "").strip()
    if not path:
        return notify_error("Registry path is required")

    payload = {"path": path}
    r = send_nats_command(agent, "registry_create_key", payload, timeout=30)

    if isinstance(r, Response):
        return r

    return Response({"status": "success", "path": path})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, AgentRegistryPerms])
def delete_registry_key(request, agent_id):
    agent = get_validated_agent(agent_id)
    if isinstance(agent, Response):
        return agent

    path = (request.query_params.get("path") or "").strip()
    if not path:
        return notify_error("Registry path is required")

    payload = {"path": path}
    r = send_nats_command(agent, "registry_delete_key", payload, timeout=30)

    if isinstance(r, Response):
        return r

    return Response({"status": "success", "deleted_path": path})


@api_view(["POST"])
@permission_classes([IsAuthenticated, AgentRegistryPerms])
def rename_registry_key(request, agent_id):
    agent = get_validated_agent(agent_id)
    if isinstance(agent, Response):
        return agent

    old_path = (request.data.get("old_path") or "").strip()
    new_path = (request.data.get("new_path") or "").strip()

    if not old_path or not new_path:
        return notify_error("Both 'old_path' and 'new_path' are required")
    if old_path == new_path:
        return notify_error("Old and new path cannot be the same")

    payload = {"old_path": old_path, "new_path": new_path}
    r = send_nats_command(agent, "registry_rename_key", payload, timeout=60)

    if isinstance(r, Response):
        return r

    return Response(
        {
            "status": "success",
            "old_path": old_path,
            "new_path": new_path,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, AgentRegistryPerms])
def create_registry_value(request, agent_id):
    agent = get_validated_agent(agent_id)
    if isinstance(agent, Response):
        return agent

    path = (request.data.get("path") or "").strip()
    val_name = request.data.get("name")
    val_type = (request.data.get("type") or "").strip().upper()
    val_data = request.data.get("data")

    if not path:
        return notify_error("Registry path is required")
    if not val_type:
        return notify_error("Registry value type is required")
    if not val_name:
        return notify_error("Registry value name is required")

    payload = {
        "path": path,
        "type": val_type,
        "name": val_name,
        "data": val_data,
    }

    r = send_nats_command(agent, "registry_create_value", payload, timeout=30)

    if isinstance(r, Response):
        return r

    return Response(
        {
            "status": "success",
            "data": {
                "name": r.get("name", val_name),
                "type": r.get("type", val_type),
                "data": r.get("data", val_data),
            },
        }
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, AgentRegistryPerms])
def delete_registry_value(request, agent_id):
    agent = get_validated_agent(agent_id)
    if isinstance(agent, Response):
        return agent

    path = (request.query_params.get("path") or "").strip()
    val_name = request.query_params.get("name")

    if not path:
        return notify_error("Registry path is required")
    if not val_name:
        return notify_error("Registry value name is required")

    payload = {"path": path, "name": val_name}
    r = send_nats_command(agent, "registry_delete_value", payload, timeout=30)

    if isinstance(r, Response):
        return r

    return Response({"status": "success", "name": val_name})


@api_view(["POST"])
@permission_classes([IsAuthenticated, AgentRegistryPerms])
def rename_registry_value(request, agent_id):
    agent = get_validated_agent(agent_id)
    if isinstance(agent, Response):
        return agent

    path = (request.data.get("path") or "").strip()
    old_name = request.data.get("old_name")
    new_name = request.data.get("new_name")

    if not path:
        return notify_error("Registry path is required")
    if not old_name:
        return notify_error("Old value name is required")
    if not new_name:
        return notify_error("New value name is required")
    if old_name == new_name:
        return notify_error("Old and new value names cannot be the same")

    payload = {
        "path": path,
        "old_name": old_name,
        "new_name": new_name,
    }

    r = send_nats_command(agent, "registry_rename_value", payload, timeout=30)

    if isinstance(r, Response):
        return r

    return Response(
        {
            "status": "success",
            "old_name": old_name,
            "new_name": r.get("new_name", new_name),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, AgentRegistryPerms])
def modify_registry_value(request, agent_id):
    agent = get_validated_agent(agent_id)
    if isinstance(agent, Response):
        return agent

    path = (request.data.get("path") or "").strip()
    val_name = request.data.get("name")
    val_type = (request.data.get("type") or "").strip().upper()
    val_data = request.data.get("data")

    if not path:
        return notify_error("Registry path is required")
    if not val_name:
        return notify_error("Registry value name is required")
    if not val_type:
        return notify_error("Registry value type is required")

    payload = {
        "path": path,
        "name": val_name,
        "type": val_type,
        "data": val_data,
    }

    r = send_nats_command(agent, "registry_modify_value", payload, timeout=30)

    if isinstance(r, Response):
        return r

    return Response(
        {
            "status": "success",
            "data": {
                "name": r.get("name", val_name),
                "type": r.get("type", val_type),
                "data": r.get("data", val_data),
            },
        }
    )
