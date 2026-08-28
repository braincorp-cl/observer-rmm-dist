import asyncio
import hashlib
import os
from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Max, Prefetch
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone as djangotime
from packaging import version as pyver
from rest_framework import status as rest_framework_status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from agents.models import (
    Agent,
    AgentHistory,
    LostModeEvidence,
    LostModeState,
    Note,
)
from agents.serializers import AgentHistorySerializer
from agents.tasks import manual_uninstall_delete_task
from agents.uninstall import grace_seconds, record_manual_uninstall
from alerts.tasks import cache_agents_alert_template
from apiv3.utils import get_agent_config
from autotasks.models import AutomatedTask, TaskResult
from autotasks.serializers import TaskGOGetSerializer, TaskResultSerializer
from checks.constants import CHECK_DEFER, CHECK_RESULT_DEFER
from checks.models import Check, CheckResult
from checks.serializers import CheckRunnerGetSerializer
from core.tasks import sync_mesh_perms_task
from core.utils import (
    _mesh_id_to_hex,
    download_mesh_agent,
    get_core_settings,
    get_mesh_device_id,
    get_mesh_installer,
    get_mesh_ws_url,
    get_meshagent_url,
)
from logs.models import DebugLog
from software.models import InstalledSoftware
from observerrmm.constants import (
    AGENT_CONSOLE_UNINSTALL_CACHE_PREFIX,
    AGENT_DEFER,
    AGENT_MANUAL_UNINSTALL_CACHE_PREFIX,
    AGENT_MANUAL_UNINSTALL_CACHE_TIMEOUT,
    ORMM_MAX_REQUEST_SIZE,
    AgentHistoryType,
    AgentMonType,
    AgentPlat,
    AuditActionType,
    AuditObjType,
    CheckStatus,
    CustomFieldModel,
    DebugLogType,
    LostModeEvidenceKind,
    GoArch,
    MeshAgentIdent,
    TaskRunStatus,
)
from observerrmm.helpers import make_random_password, notify_error
from observerrmm.utils import reload_nats
from winupdate.models import WinUpdate, WinUpdatePolicy


class CheckIn(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    # called once during agent windows service startup
    def post(self, request):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER), agent_id=request.data["agent_id"]
        )
        if not agent.choco_installed:
            asyncio.run(agent.nats_cmd({"func": "installchoco"}, wait=False))

        asyncio.run(agent.nats_cmd({"func": "getwinupdates"}, wait=False))
        return Response("ok")


class SyncMeshNodeID(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER), agent_id=request.data["agent_id"]
        )
        if agent.mesh_node_id != request.data["nodeid"]:
            # Un nodeid vacío o no convertible se DESCARTA y el id bueno queda
            # intacto: este endpoint sólo puede mejorar el valor guardado,
            # nunca degradarlo.
            #
            # Antes NO era así, y medirlo en staging desmintió lo que este
            # comentario decía en su primera versión. Sólo la basura que rompe
            # el padding reventaba con 500 (que al menos impedía guardar); la
            # basura que no lo rompe pasaba entera: `"no-es-un-nodeid"`
            # respondía 200 y guardaba `9E87ACBA79E875E89D`, y `"!!!!"`
            # guardaba cadena vacía, borrando el id bueno. O sea que este `if`
            # no es cosmético — es lo que impide que un nodeid inválido
            # destruya el que sirve.
            nodeid = (
                _mesh_id_to_hex(request.data["nodeid"])
                if request.data.get("nodeid")
                else None
            )
            if nodeid:
                agent.mesh_node_id = nodeid
                agent.save(update_fields=["mesh_node_id"])

        return Response("ok")


class AgentUninstalled(APIView):
    """El equipo avisa que lo están desinstalando ANTES de destruirse.

    Sin este aviso la desinstalación local es invisible para el servidor: el
    script sólo toca la máquina y la fila `Agent` queda para siempre como un
    equipo Offline que ya no existe. Ver `agents/uninstall.py` para el porqué de
    cada decisión (alerta sin agente, ventana de gracia, atribución del actor).
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # El agente sale del TOKEN, NUNCA del cuerpo. Este endpoint termina
        # borrando una máquina: aceptar un `agent_id` del payload convertiría el
        # token de cualquier agente en un borrado de cualquier otro.
        #
        # El respaldo por `username` sigue siendo derivado del token y no del
        # cuerpo, así que conserva esa propiedad. Existe porque el vínculo
        # `User.agent` lo puebla `NewAgent` al enrolar, y no hay garantía de que
        # todo agente histórico de la flota lo tenga; el `username` sí, porque
        # es la clave con la que se creó el usuario.
        agent = getattr(request.user, "agent", None)
        if agent is None:
            agent = (
                Agent.objects.defer(*AGENT_DEFER)
                .filter(agent_id=request.user.username)
                .first()
            )
        if agent is None:
            return notify_error("Este endpoint sólo lo puede llamar un agente")

        payload = request.data if isinstance(request.data, dict) else {}

        # Borrado disparado desde la consola: la consola corre este MISMO script
        # de desinstalación, así que el aviso llega igual. Ya hay auditoría de
        # esa acción y no es una desinstalación manual.
        console_key = f"{AGENT_CONSOLE_UNINSTALL_CACHE_PREFIX}{agent.agent_id}"
        if cache.get(console_key):
            return Response("ok (borrado iniciado desde la consola)")

        # El aviso se manda a pulso desde un script que puede reintentar. Una
        # sola alerta por episodio.
        dedupe_key = f"{AGENT_MANUAL_UNINSTALL_CACHE_PREFIX}{agent.agent_id}"
        if cache.get(dedupe_key):
            return Response("ok (aviso ya registrado)")
        cache.set(dedupe_key, True, AGENT_MANUAL_UNINSTALL_CACHE_TIMEOUT)

        notified_at = djangotime.now()
        record_manual_uninstall(
            agent, payload, client_ip=getattr(request, "_client_ip", None)
        )

        if not getattr(settings, "MANUAL_UNINSTALL_AUTO_DELETE", True):
            return Response("ok (alerta registrada; borrado automático apagado)")

        manual_uninstall_delete_task.apply_async(
            (agent.agent_id, notified_at.isoformat()), countdown=grace_seconds()
        )
        return Response("ok")


class Choco(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER), agent_id=request.data["agent_id"]
        )
        agent.choco_installed = request.data["installed"]
        agent.save(update_fields=["choco_installed"])
        return Response("ok")


class WinUpdates(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER), agent_id=request.data["agent_id"]
        )

        needs_reboot: bool = request.data["needs_reboot"]
        agent.needs_reboot = needs_reboot
        agent.save(update_fields=["needs_reboot"])

        reboot_policy: str = agent.get_patch_policy().reboot_after_install
        reboot = False

        if reboot_policy == "always":
            reboot = True
        elif needs_reboot and reboot_policy == "required":
            reboot = True

        if reboot:
            asyncio.run(agent.nats_cmd({"func": "rebootnow"}, wait=False))
            DebugLog.info(
                agent=agent,
                log_type=DebugLogType.WIN_UPDATES,
                message=f"{agent.hostname} is rebooting after updates were installed.",
            )

        agent.delete_superseded_updates()
        return Response("ok")

    def patch(self, request):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER), agent_id=request.data["agent_id"]
        )
        u = agent.winupdates.filter(guid=request.data["guid"]).last()  # type: ignore
        if not u:
            raise WinUpdate.DoesNotExist

        success: bool = request.data["success"]
        if success:
            u.result = "success"
            u.downloaded = True
            u.installed = True
            u.date_installed = djangotime.now()
            u.save(
                update_fields=[
                    "result",
                    "downloaded",
                    "installed",
                    "date_installed",
                ]
            )
        else:
            u.result = "failed"
            u.save(update_fields=["result"])

        agent.delete_superseded_updates()
        return Response("ok")

    def post(self, request):
        updates = request.data["wua_updates"]
        if not updates:
            return notify_error("Empty payload")

        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER), agent_id=request.data["agent_id"]
        )

        for update in updates:
            if agent.winupdates.filter(guid=update["guid"]).exists():  # type: ignore
                u = agent.winupdates.filter(guid=update["guid"]).last()  # type: ignore
                u.downloaded = update["downloaded"]
                u.installed = update["installed"]
                u.save(update_fields=["downloaded", "installed"])
            else:
                try:
                    kb = "KB" + update["kb_article_ids"][0]
                except:
                    continue

                WinUpdate(
                    agent=agent,
                    guid=update["guid"],
                    kb=kb,
                    title=update["title"],
                    installed=update["installed"],
                    downloaded=update["downloaded"],
                    description=update["description"],
                    severity=update["severity"],
                    categories=update["categories"],
                    category_ids=update["category_ids"],
                    kb_article_ids=update["kb_article_ids"],
                    more_info_urls=update["more_info_urls"],
                    support_url=update["support_url"],
                    revision_number=update["revision_number"],
                ).save()

        agent.delete_superseded_updates()
        return Response("ok")


class SupersededWinUpdate(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER), agent_id=request.data["agent_id"]
        )
        updates = agent.winupdates.filter(guid=request.data["guid"])  # type: ignore
        for u in updates:
            u.delete()

        return Response("ok")


class RunChecks(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, agentid):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER).prefetch_related(
                Prefetch("agentchecks", queryset=Check.objects.select_related("script"))
            ),
            agent_id=agentid,
        )
        checks = agent.get_checks_with_policies(exclude_overridden=True)
        ret = {
            "agent": agent.pk,
            "check_interval": agent.check_interval,
            "checks": CheckRunnerGetSerializer(
                checks, context={"agent": agent}, many=True
            ).data,
        }
        return Response(ret)


class CheckRunner(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, agentid):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER).prefetch_related(
                Prefetch("agentchecks", queryset=Check.objects.select_related("script"))
            ),
            agent_id=agentid,
        )
        checks = agent.get_checks_with_policies(exclude_overridden=True)

        run_list = [
            check
            for check in checks
            # always run if check hasn't run yet
            if not isinstance(check.check_result, CheckResult)
            or not check.check_result.last_run
            # see if the correct amount of seconds have passed
            or (
                check.check_result.last_run
                < djangotime.now()
                - djangotime.timedelta(
                    seconds=check.run_interval or agent.check_interval
                )
            )
        ]

        ret = {
            "agent": agent.pk,
            "check_interval": agent.check_run_interval(),
            "checks": CheckRunnerGetSerializer(
                run_list, context={"agent": agent}, many=True
            ).data,
        }
        return Response(ret)

    def patch(self, request):
        if "agent_id" not in request.data.keys():
            return notify_error("Agent upgrade required")

        check = get_object_or_404(
            Check.objects.defer(*CHECK_DEFER),
            pk=request.data["id"],
        )
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER), agent_id=request.data["agent_id"]
        )

        # get check result or create if doesn't exist
        check_result, created = CheckResult.objects.defer(
            *CHECK_RESULT_DEFER
        ).get_or_create(
            assigned_check=check,
            agent=agent,
        )

        if created:
            check_result.save()

        status = check_result.handle_check(request.data, check, agent)
        if status == CheckStatus.FAILING and check.assignedtasks.exists():
            for task in check.assignedtasks.all():
                if task.enabled:
                    if task.policy:
                        task.run_win_task(agent)
                    else:
                        task.run_win_task()

        return Response("ok")


class CheckRunnerInterval(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, agentid):
        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER).prefetch_related("agentchecks"),
            agent_id=agentid,
        )

        return Response(
            {"agent": agent.pk, "check_interval": agent.check_run_interval()}
        )


class TaskRunner(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, agentid):
        agent = get_object_or_404(
            Agent.objects.select_related("policy", "site").defer(*AGENT_DEFER),
            agent_id=agentid,
        )
        task = get_object_or_404(
            AutomatedTask.objects.select_related("agent", "policy"), pk=pk
        )

        if task.agent:
            if task.agent.agent_id != agent.agent_id:
                return notify_error("")
        elif task.policy:
            if pk not in [t.pk for t in agent.get_tasks_with_policies()]:
                return notify_error("")

        return Response(TaskGOGetSerializer(task, context={"agent": agent}).data)

    def patch(self, request, pk, agentid):
        from alerts.models import Alert

        agent = get_object_or_404(
            Agent.objects.defer(*AGENT_DEFER),
            agent_id=agentid,
        )
        task = get_object_or_404(
            AutomatedTask.objects.select_related("custom_field"), pk=pk
        )

        content_length = request.META.get("CONTENT_LENGTH")
        if content_length and int(content_length) > ORMM_MAX_REQUEST_SIZE:
            request.data["stdout"] = ""
            request.data["stderr"] = "Content truncated due to excessive request size."
            request.data["retcode"] = 1

        # get task result or create if doesn't exist
        try:
            task_result = (
                TaskResult.objects.select_related("agent")
                .defer("agent__services", "agent__wmi_detail")
                .get(task=task, agent=agent)
            )
            serializer = TaskResultSerializer(
                data=request.data, instance=task_result, partial=True
            )
        except TaskResult.DoesNotExist:
            serializer = TaskResultSerializer(data=request.data, partial=True)

        serializer.is_valid(raise_exception=True)
        task_result = serializer.save(
            last_run=djangotime.now(), run_status=TaskRunStatus.COMPLETED
        )

        AgentHistory.objects.create(
            agent=agent,
            type=AgentHistoryType.TASK_RUN,
            command=task.name,
            script_results=request.data,
        )

        # check if task is a collector and update the custom field
        if task.custom_field:
            if not task_result.stderr:
                task_result.save_collector_results()

                status = CheckStatus.PASSING
            else:
                status = CheckStatus.FAILING
        else:
            status = (
                CheckStatus.FAILING if task_result.retcode != 0 else CheckStatus.PASSING
            )

        task_result.status = status
        task_result.save(update_fields=["status"])

        if status == CheckStatus.PASSING:
            if Alert.create_or_return_task_alert(task, agent=agent, skip_create=True):
                Alert.handle_alert_resolve(task_result)
        else:
            Alert.handle_alert_failure(task_result)

        return Response("ok")


class MeshExe(APIView):
    """Sends the mesh exe to the installer"""

    def post(self, request):
        match request.data:
            case {"goarch": GoArch.AMD64, "plat": AgentPlat.WINDOWS}:
                ident = MeshAgentIdent.WIN64
            case {"goarch": GoArch.i386, "plat": AgentPlat.WINDOWS}:
                ident = MeshAgentIdent.WIN32
            case {"goarch": GoArch.AMD64, "plat": AgentPlat.DARWIN} | {
                "goarch": GoArch.ARM64,
                "plat": AgentPlat.DARWIN,
            }:
                ident = MeshAgentIdent.DARWIN_UNIVERSAL
            case _:
                return notify_error("Arch not supported")

        core = get_core_settings()

        try:
            uri = get_mesh_ws_url()
            mesh_device_id: str = asyncio.run(
                get_mesh_device_id(uri, core.mesh_device_group)
            )
        except:
            return notify_error("Unable to connect to mesh to get group id information")

        dl_url = get_meshagent_url(
            ident=ident,
            plat=request.data["plat"],
            mesh_site=core.mesh_site,
            mesh_device_id=mesh_device_id,
        )

        try:
            return download_mesh_agent(dl_url)
        except Exception as e:
            return notify_error(f"Unable to download mesh agent: {e}")


class MeshReinstall(APIView):
    """Sirve el instalador Mesh cacheado (SHA-256) para que el agente reinstale
    su servicio Mesh durante la auto-reparacion (backport v1.5.1 C1 + B1).

    Nota: consumido por el agente >= v1.5.1 (Observer 2.11.0). Con el agente
    actual (2.10.x, base v1.4.0) el endpoint queda inerte hasta subir el agente.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, agentid):
        agent = get_object_or_404(
            Agent.objects.only("plat", "goarch"), agent_id=agentid
        )
        core = get_core_settings()

        try:
            uri = get_mesh_ws_url()
            mesh_device_id: str = asyncio.run(
                get_mesh_device_id(uri, core.mesh_device_group)
            )
        except:
            return notify_error("Unable to connect to mesh to get group id information")

        # windows only for now
        ident = (
            MeshAgentIdent.WIN64
            if agent.goarch == GoArch.AMD64
            else MeshAgentIdent.WIN32
        )
        dl_url = get_meshagent_url(
            ident=ident,
            plat=agent.plat,
            mesh_site=core.mesh_site,  # type: ignore
            mesh_device_id=mesh_device_id,
        )

        try:
            mesh_installer = get_mesh_installer(agent.goarch, dl_url, agent.plat)
        except Exception as e:
            return notify_error(str(e))

        response = FileResponse(
            open(mesh_installer, "rb"),
            as_attachment=True,
            filename=os.path.basename(mesh_installer),
        )
        return response


class NewAgent(APIView):
    def post(self, request):
        from logs.models import AuditLog

        """ Creates the agent """

        if Agent.objects.filter(agent_id=request.data["agent_id"]).exists():
            return notify_error(
                "Agent already exists. Remove old agent first if trying to re-install"
            )

        # Mismo criterio que en SyncMeshNodeID, y acá importaba más: un
        # mesh_node_id con basura hacía reventar con 500 el ALTA del agente,
        # o sea que un id malformado no dejaba enrolar el equipo. Se descarta
        # y se registra el equipo sin mesh_node_id, que es el mismo estado que
        # cuando el campo no viene; el `SyncMeshNodeID` del propio agente lo
        # completa después.
        mesh_node_id = (
            _mesh_id_to_hex(request.data["mesh_node_id"])
            if request.data.get("mesh_node_id")
            else None
        )

        agent = Agent(
            agent_id=request.data["agent_id"],
            hostname=request.data["hostname"],
            site_id=int(request.data["site"]),
            monitoring_type=request.data["monitoring_type"],
            description=request.data["description"],
            mesh_node_id=mesh_node_id or "",
            goarch=request.data["goarch"],
            plat=request.data["plat"],
            last_seen=djangotime.now(),
        )
        agent.save()

        user = User.objects.create_user(  # type: ignore
            username=request.data["agent_id"],
            agent=agent,
            password=make_random_password(len=60),
        )

        token = Token.objects.create(user=user)

        if agent.monitoring_type == AgentMonType.WORKSTATION:
            WinUpdatePolicy(agent=agent, run_time_days=[5, 6]).save()
        else:
            WinUpdatePolicy(agent=agent).save()

        reload_nats()

        # create agent install audit record
        AuditLog.objects.create(
            username=request.user,
            agent=agent.hostname,
            object_type=AuditObjType.AGENT,
            action=AuditActionType.AGENT_INSTALL,
            message=f"{request.user} installed new agent {agent.hostname}",
            after_value=Agent.serialize(agent),
            debug_info={"ip": request._client_ip},
        )

        ret = {"pk": agent.pk, "token": token.key}
        sync_mesh_perms_task.delay()
        cache_agents_alert_template.delay()
        return Response(ret)


class Software(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        agent = get_object_or_404(Agent, agent_id=request.data["agent_id"])
        sw = request.data["software"]
        if not InstalledSoftware.objects.filter(agent=agent).exists():
            InstalledSoftware(agent=agent, software=sw).save()
        else:
            s = agent.installedsoftware_set.first()  # type: ignore
            s.software = sw
            s.save(update_fields=["software"])

        return Response("ok")


class Installer(APIView):
    def get(self, request):
        # used to check if token is valid. will return 401 if not
        return Response("ok")

    def post(self, request):
        if "version" not in request.data:
            return notify_error("Invalid data")

        ver = request.data["version"]
        if (
            pyver.parse(ver) < pyver.parse(settings.LATEST_AGENT_VER)
            and "-dev" not in settings.LATEST_AGENT_VER
        ):
            return notify_error(
                f"Old installer detected (version {ver} ). Latest version is {settings.LATEST_AGENT_VER} Please generate a new installer from the RMM"
            )

        return Response("ok")


class AgentHistoryResult(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, agentid, pk):
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length and int(content_length) > ORMM_MAX_REQUEST_SIZE:

            request.data["script_results"]["stdout"] = ""
            request.data["script_results"][
                "stderr"
            ] = "Content truncated due to excessive request size."
            request.data["script_results"]["retcode"] = 1

        hist = get_object_or_404(
            AgentHistory.objects.select_related("custom_field").filter(
                agent__agent_id=agentid
            ),
            pk=pk,
        )
        s = AgentHistorySerializer(instance=hist, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()

        if hist.custom_field:
            if hist.custom_field.model == CustomFieldModel.AGENT:
                field = hist.custom_field.get_or_create_field_value(hist.agent)
            elif hist.custom_field.model == CustomFieldModel.CLIENT:
                field = hist.custom_field.get_or_create_field_value(hist.agent.client)
            elif hist.custom_field.model == CustomFieldModel.SITE:
                field = hist.custom_field.get_or_create_field_value(hist.agent.site)

            r = request.data["script_results"]["stdout"]
            value = (
                r.strip()
                if hist.collector_all_output
                else r.strip().split("\n")[-1].strip()
            )

            field.save_to_field(value)

        if hist.save_to_agent_note:
            Note.objects.create(
                agent=hist.agent,
                user=request.user,
                note=request.data["script_results"]["stdout"],
            )

        return Response("ok")


class AgentConfig(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, agentid):
        # Feature 030: desde acá la config deja de ser 100 % global. El `agentid`
        # ya llegaba en la ruta y se ignoraba; ahora resuelve el modo perdido de
        # ESE equipo.
        ret = get_agent_config(agentid)
        return Response(ret._to_dict())


class Geolocate(APIView):
    """Feature 023 · F4: resolver WiFi→coordenadas (modelo Prey).

    El agente manda las antenas WiFi visibles ({considerIp, wifiAccessPoints})
    y el backend las resuelve contra Google Geolocation API usando una key que
    vive SOLO aquí (settings.GOOGLE_GEOLOCATION_API_KEY), nunca en la flota.
    Devuelve {location:{lat,lng},accuracy} (mismo formato que consume el agente)
    o {} cuando no hay key/fix → el agente degrada a IP. No persiste nada: el
    reporte de geolocalización sigue su flujo normal por NATS.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        key = getattr(settings, "GOOGLE_GEOLOCATION_API_KEY", "")
        if not key:
            # Resolución WiFi no configurada → el agente degrada a IP.
            return Response({})

        # Normaliza cada antena a los campos válidos de Google Geolocation API
        # (homologado con Prey: macAddress + signalStrength + channel; se aceptan
        # también age/signalToNoiseRatio si el agente los envía). Se descarta
        # cualquier otro campo (p.ej. ssid) y las antenas sin macAddress.
        raw_aps = request.data.get("wifiAccessPoints") or []
        google_fields = (
            "macAddress",
            "signalStrength",
            "channel",
            "age",
            "signalToNoiseRatio",
        )
        aps = [
            {k: ap[k] for k in google_fields if k in ap}
            for ap in raw_aps
            if isinstance(ap, dict) and ap.get("macAddress")
        ]
        # Google requiere al menos 2 antenas para un fix WiFi fiable; con menos,
        # dejamos que el agente caiga a IP en vez de gastar una consulta.
        if len(aps) < 2:
            return Response({})

        consider_ip = bool(request.data.get("considerIp", False))

        # Caché de flota (F4 · 4a): la misma constelación de antenas se resuelve UNA
        # vez y sirve a todos los equipos que la ven (una oficina con N máquinas = 1
        # consulta a Google, no N). Protege la cuota/costo. La clave es estable por el
        # conjunto ORDENADO de MACs + considerIp; señal y canal varían por equipo y no
        # deben fragmentar la caché.
        macs = sorted(ap["macAddress"].lower() for ap in aps)
        cache_key = (
            "geo:wifi:"
            + hashlib.sha1(
                (str(consider_ip) + "|" + "|".join(macs)).encode()
            ).hexdigest()
        )
        cached = cache.get(cache_key)
        if cached is not None:
            # "" = centinela de "Google no ubicó estas antenas" (miss cacheado).
            return Response({} if cached == "" else cached)

        payload = {
            "considerIp": consider_ip,
            "wifiAccessPoints": aps,
        }
        try:
            r = requests.post(
                settings.GOOGLE_GEOLOCATION_URL,
                params={"key": key},
                json=payload,
                timeout=10,
            )
        except requests.RequestException as e:
            DebugLog.error(
                message=f"geolocate: fallo consultando Google Geolocation: {e}"
            )
            return Response({})

        # 200 = fix; 404 = Google no ubicó las antenas; otros = error de cuota/key.
        # En todos los casos que no sean 200 el agente degrada a IP (no rompe el
        # check-in). Se devuelve el cuerpo de Google tal cual (mismo formato).
        if r.status_code != 200:
            if r.status_code == 404:
                # Antenas no ubicables: cachear el miss (TTL corto) para no
                # reconsultar Google por cada tick del mismo entorno WiFi.
                cache.set(cache_key, "", settings.GOOGLE_GEOLOCATION_CACHE_MISS_TTL)
            else:
                DebugLog.error(
                    message=f"geolocate: Google respondió {r.status_code}: {r.text[:200]}"
                )
            return Response({})

        data = r.json()
        cache.set(cache_key, data, settings.GOOGLE_GEOLOCATION_CACHE_TTL)
        return Response(data)


# ── Feature 030 · Fase 1 · subida de evidencia del modo perdido (T010) ────────


def _agente_del_token(request) -> "Agent | None":
    """Resuelve el agente a partir del TOKEN, nunca del cuerpo ni de la URL.

    Mismo criterio que `AgentUninstalled`: el vínculo `User.agent` lo puebla
    `NewAgent` al enrolar, y el respaldo por `username` cubre a los agentes
    históricos que no lo tengan. Los dos caminos salen del token, así que la
    propiedad que importa se conserva — un token no puede hablar por otro equipo.
    """
    agent = getattr(request.user, "agent", None)
    if agent is not None:
        return agent

    return (
        Agent.objects.defer(*AGENT_DEFER).filter(agent_id=request.user.username).first()
    )


def _fecha_de_captura(valor: object):
    """Convierte el reloj del equipo (epoch en segundos) a datetime con zona.

    Devuelve None ante cualquier valor ilegible: la fila se guarda igual y queda
    con `created` (el reloj del servidor), que siempre existe. Perder la hora del
    equipo empobrece la evidencia; rechazar la subida entera por eso la perdería
    completa.
    """
    try:
        epoch = int(valor)
    except (TypeError, ValueError):
        return None

    if epoch <= 0:
        return None

    try:
        return datetime.fromtimestamp(epoch, tz=dt_timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _numero(valor: object, tipo):
    try:
        return tipo(valor)
    except (TypeError, ValueError):
        return None


# Firmas de los formatos que se aceptan como evidencia. Se mira el CONTENIDO y
# no la extensión ni el Content-Type: los dos los elige quien sube, y esta
# carpeta la sirve después el servidor a un navegador. Un archivo que dice ser
# PNG y trae otra cosa no entra.
_FIRMAS_IMAGEN = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",  # JPEG
)

# 25 MiB: una captura PNG de una pantalla 4K anda por los 3–6 MiB, así que sobra
# con holgura, y el proxy admite 300M. El tope existe para que un agente con el
# token robado no pueda llenar el disco del servidor a punta de subidas.
LOST_MODE_MAX_EVIDENCE_BYTES = getattr(
    settings, "LOST_MODE_MAX_EVIDENCE_BYTES", 25 * 2**20
)


class LostModeEvidenceUpload(APIView):
    """Recibe el lote de un ciclo de captura: el punto de geo, la pantalla y la foto.

    POR QUÉ ES UN ENDPOINT PROPIO Y NO EL FLUJO DE GEO POR NATS: el punto de
    ubicación ya viaja por NATS y termina en `CheckHistory`, pero esa tabla la
    poda `check_history_prune_days` (30 días por omisión), que es una perilla de
    *monitoreo*. La evidencia de ADR-025 tiene su propio plazo de retención y no
    puede depender de ella, así que el ciclo guarda una COPIA acá. Y el binario
    no cabe en NATS: va por HTTP multipart, como los assets de reporting.

    EL CICLO LO NUMERA EL SERVIDOR. El agente no lleva la cuenta a propósito: se
    reinicia, se reinstala y puede estar semanas sin hablar, y dos ciclos con el
    mismo número se pisarían el archivo en disco (la ruta lleva el número). El
    contador es monótono por AGENTE y no se reinicia al reabrir un caso, por lo
    mismo.

    UNA FILA AUNQUE NO HAYA IMAGEN. Si la captura no se pudo hacer, el agente
    manda el motivo (`sin_sesion`, `wayland_no_soportado`, `permiso_denegado`,
    ...) y acá se guarda una fila de tipo `screen` con `note` y sin archivo. Sin
    eso, la línea de tiempo no distinguiría "el equipo está apagado" de "este
    equipo nunca va a dar capturas", que es la forma que toma el "ok falso" en
    una feature de evidencia.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, agentid):
        agent = _agente_del_token(request)
        if agent is None:
            return notify_error("Este endpoint sólo lo puede llamar un agente")

        # El `agentid` de la URL tiene que ser el del token. No es formalismo:
        # esta evidencia puede terminar en una denuncia, y un agente capaz de
        # escribir en el caso de otro equipo la volvería fabricable con un solo
        # token robado.
        if agent.agent_id != agentid:
            return notify_error("El agente del token no es el de la URL")

        state = (
            LostModeState.objects.filter(agent=agent, active=True)
            .only("id", "agent_id")
            .first()
        )
        if state is None:
            # 409 y no 400: no es una petición mal armada, es un estado que ya no
            # corresponde —el caso se cerró mientras el equipo estaba sin red—.
            # El agente lo trata como "deja de capturar" y se apaga sin esperar
            # al próximo polling de config.
            return Response(
                {"status": "not_lost"}, status=rest_framework_status.HTTP_409_CONFLICT
            )

        ciclo = (
            LostModeEvidence.objects.filter(agent=agent).aggregate(ultimo=Max("cycle"))[
                "ultimo"
            ]
            or 0
        ) + 1

        captured_at = _fecha_de_captura(request.data.get("captured_at"))
        session_user = (request.data.get("session_user") or "")[:255] or None
        lat = _numero(request.data.get("lat"), float)
        lng = _numero(request.data.get("lng"), float)
        accuracy_m = _numero(request.data.get("accuracy_m"), int)
        source = (request.data.get("source") or "")[:20] or None

        creadas = []

        # 1) El punto de ubicación del momento. Se guarda sólo con coordenadas
        #    válidas: una fila de geo sin fix no es evidencia de nada
        #    (CONTRACT-01 punto 3, la misma regla que aplica la ingesta por NATS).
        if lat is not None and lng is not None and _coordenadas_validas(lat, lng):
            creadas.append(
                LostModeEvidence.objects.create(
                    agent=agent,
                    cycle=ciclo,
                    kind=LostModeEvidenceKind.GEO,
                    lat=lat,
                    lng=lng,
                    accuracy_m=accuracy_m if accuracy_m and accuracy_m > 0 else None,
                    source=source,
                    session_user=session_user,
                    captured_at=captured_at,
                )
            )

        # 2) La captura de pantalla, o el motivo por el que no la hay.
        archivo = request.FILES.get("screen")
        motivo = (request.data.get("screen_reason") or "")[:50] or None

        if archivo is not None:
            error = _rechazo_de_imagen(archivo)
            if error:
                # Se registra en la propia línea de tiempo en vez de contestar un
                # 400 y perder el ciclo: que el servidor haya rechazado el archivo
                # es un hecho del caso, y el operador tiene que poder verlo.
                DebugLog.warning(
                    agent=agent,
                    log_type=DebugLogType.AGENT_ISSUES,
                    message=f"modo perdido: se rechazó la evidencia del ciclo {ciclo} ({error})",
                )
                archivo, motivo = None, error

        if archivo is not None:
            evidencia = LostModeEvidence(
                agent=agent,
                cycle=ciclo,
                kind=LostModeEvidenceKind.SCREEN,
                lat=lat,
                lng=lng,
                accuracy_m=accuracy_m if accuracy_m and accuracy_m > 0 else None,
                source=source,
                session_user=session_user,
                captured_at=captured_at,
            )
            # El nombre lo pone el servidor, no el agente: el que viene en el
            # multipart es texto de afuera y termina siendo una ruta en disco.
            evidencia.asset.save(f"pantalla-{ciclo:06d}.png", archivo, save=False)
            evidencia.save()
            creadas.append(evidencia)
        elif motivo:
            creadas.append(
                LostModeEvidence.objects.create(
                    agent=agent,
                    cycle=ciclo,
                    kind=LostModeEvidenceKind.SCREEN,
                    note=motivo,
                    lat=lat,
                    lng=lng,
                    accuracy_m=accuracy_m if accuracy_m and accuracy_m > 0 else None,
                    source=source,
                    session_user=session_user,
                    captured_at=captured_at,
                )
            )

        # 3) La foto de webcam, o el motivo por el que no la hay (Fase 2).
        #
        # SÓLO SI EL AGENTE MANDÓ ALGO. Con el interruptor global apagado, el
        # agente no manda ni archivo ni motivo, y acá no se crea ninguna fila:
        # una flota que nunca activó la webcam no tiene por qué ver, en cada
        # ciclo de cada caso, un renglón hablando de una cámara.
        #
        # El servidor NO comprueba el interruptor para decidir si acepta: si un
        # agente manda una foto es porque cuando armó el ciclo el interruptor
        # estaba encendido, y descartarla acá perdería evidencia de un caso real
        # por una carrera de milisegundos con la configuración.
        foto = request.FILES.get("webcam")
        motivo_webcam = (request.data.get("webcam_reason") or "")[:50] or None

        if foto is not None:
            error = _rechazo_de_imagen(foto)
            if error:
                DebugLog.warning(
                    agent=agent,
                    log_type=DebugLogType.AGENT_ISSUES,
                    message=f"modo perdido: se rechazó la foto del ciclo {ciclo} ({error})",
                )
                foto, motivo_webcam = None, error

        if foto is not None:
            pieza = LostModeEvidence(
                agent=agent,
                cycle=ciclo,
                kind=LostModeEvidenceKind.WEBCAM,
                lat=lat,
                lng=lng,
                accuracy_m=accuracy_m if accuracy_m and accuracy_m > 0 else None,
                source=source,
                session_user=session_user,
                captured_at=captured_at,
            )
            # El nombre lo pone el servidor, igual que en la pantalla: el del
            # multipart es texto de afuera y termina siendo una ruta en disco.
            pieza.asset.save(f"webcam-{ciclo:06d}.jpg", foto, save=False)
            pieza.save()
            creadas.append(pieza)
        elif motivo_webcam:
            creadas.append(
                LostModeEvidence.objects.create(
                    agent=agent,
                    cycle=ciclo,
                    kind=LostModeEvidenceKind.WEBCAM,
                    note=motivo_webcam,
                    lat=lat,
                    lng=lng,
                    accuracy_m=accuracy_m if accuracy_m and accuracy_m > 0 else None,
                    source=source,
                    session_user=session_user,
                    captured_at=captured_at,
                )
            )

        if not creadas:
            # Ni punto ni pantalla ni motivo: el ciclo no aporta nada y una fila
            # vacía sólo ensuciaría la línea de tiempo.
            return Response({"status": "empty", "cycle": ciclo})

        return Response({"status": "ok", "cycle": ciclo, "saved": len(creadas)})


def _coordenadas_validas(lat: float, lng: float) -> bool:
    """WGS84 dentro de rango y distinto de (0,0).

    (0,0) es Null Island: el artefacto típico de "sin fix" que llega como si
    fuera una coordenada. Misma validación que hace la ingesta por NATS y que el
    propio agente en `validCoords`; se repite acá a propósito, porque este es un
    camino de entrada distinto.
    """
    if lat < -90 or lat > 90 or lng < -180 or lng > 180:
        return False
    return not (lat == 0 and lng == 0)


def _rechazo_de_imagen(archivo) -> str:
    """Devuelve el código del rechazo, o "" si el archivo se acepta."""
    if archivo.size <= 0:
        return "archivo_vacio"

    if archivo.size > LOST_MODE_MAX_EVIDENCE_BYTES:
        return "archivo_muy_grande"

    cabecera = archivo.read(8)
    archivo.seek(0)
    if not any(cabecera.startswith(firma) for firma in _FIRMAS_IMAGEN):
        return "formato_no_soportado"

    return ""


class FileRetrievalUpload(APIView):
    """El agente sube los archivos recuperados de una orden de fileretrieval (042).

    Va en apiv3 y no en /erase/ porque quien llama es el AGENTE con su token, igual
    que la evidencia del modo perdido. Reusa el mismo almacén cifrado en reposo
    (`get_lost_mode_evidence_fs`, vía `RetrievedFile.asset`).

    Protocolo:
      - una petición por archivo: campo `file` + `source_path`;
      - una petición final `done=1` (para dry-run trae `plan` en vez de archivos);
      - o `error=<motivo>` si el agente falló.

    Idempotente: el `order_id` de la URL y la unicidad `(order, source_path)`
    garantizan que reenviar no duplica ni reejecuta al reconectar.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, agentid, order_id):
        from django.db.models import Sum

        from erase.models import FileRetrievalOrder, FileRetrievalStatus, RetrievedFile
        from erase.services import record_retrieval_event

        agent = _agente_del_token(request)
        if agent is None:
            return notify_error("Este endpoint sólo lo puede llamar un agente")
        if agent.agent_id != agentid:
            return notify_error("El agente del token no es el de la URL")

        order = FileRetrievalOrder.objects.filter(pk=order_id, agent=agent).first()
        if order is None:
            # 404 y no 400: el token es válido pero la orden no es de este equipo o
            # no existe. Un token robado no puede escribir en la orden de otro.
            return notify_error("orden inexistente para este equipo")

        # Estados terminales: el agente deja de intentar (cancelada/expirada mientras
        # estaba offline, o ya completada).
        if order.status in (
            FileRetrievalStatus.CANCELLED,
            FileRetrievalStatus.EXPIRED,
            FileRetrievalStatus.DONE,
            FileRetrievalStatus.FAILED,
        ):
            return Response(
                {"status": order.status},
                status=rest_framework_status.HTTP_409_CONFLICT,
            )

        # Falla reportada por el agente.
        error = request.data.get("error")
        if error:
            order.status = FileRetrievalStatus.FAILED
            order.failure_reason = str(error)[:255]
            order.save(update_fields=["status", "failure_reason"])
            record_retrieval_event(
                order=order,
                event="retrieval_failed",
                actor="agent",
                detail={"error": order.failure_reason},
            )
            return Response({"status": "failed"})

        # Cierre de la orden (dry-run trae el plan; real la marca completada).
        if request.data.get("done"):
            if order.dry_run:
                plan = request.data.get("plan") or ""
                order.result = {"plan": plan}
                record_retrieval_event(
                    order=order,
                    event="retrieval_plan",
                    actor="agent",
                    detail={"plan_bytes": len(str(plan))},
                )
            else:
                order.result = {"files": order.files.count()}
                record_retrieval_event(
                    order=order,
                    event="retrieval_completed",
                    actor="agent",
                    detail={"files": order.files.count()},
                )
            order.status = FileRetrievalStatus.DONE
            order.completed_at = djangotime.now()
            order.save(update_fields=["status", "completed_at", "result"])
            return Response({"status": "done"})

        # dry-run no sube archivos: sólo el cierre con `plan` de arriba.
        if order.dry_run:
            return Response({"status": "dry_run_no_upload"})

        # Subida de un archivo real.
        archivo = request.FILES.get("file")
        source_path = (request.data.get("source_path") or "")[:2000]
        if archivo is None or not source_path:
            return notify_error("falta el archivo o su ruta de origen")

        # Tope por orden (RF-08): tamaño acumulado no puede pasar el límite.
        limite = order.size_limit_bytes or 0
        if limite:
            ya = (
                RetrievedFile.objects.filter(order=order).aggregate(s=Sum("size"))["s"]
                or 0
            )
            if ya + archivo.size > limite:
                order.status = FileRetrievalStatus.FAILED
                order.failure_reason = "supera el tope de tamaño por orden (RF-08)"
                order.save(update_fields=["status", "failure_reason"])
                record_retrieval_event(
                    order=order,
                    event="retrieval_failed",
                    actor="agent",
                    detail={"error": order.failure_reason},
                )
                return Response(
                    {"status": "limit_exceeded"},
                    status=rest_framework_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )

        if order.status == FileRetrievalStatus.DISPATCHED:
            order.status = FileRetrievalStatus.UPLOADING
            order.save(update_fields=["status"])

        # Idempotente: la misma ruta de la misma orden no se re-crea.
        rf, creado = RetrievedFile.objects.get_or_create(
            order=order,
            source_path=source_path,
            defaults={"size": archivo.size},
        )
        if creado:
            # El nombre en disco lo pone el servidor, no el agente: el del multipart
            # es texto de afuera y termina siendo una ruta.
            safe_name = source_path.replace("/", "_").replace("\\", "_")[-120:]
            rf.asset.save(safe_name, archivo, save=False)
            rf.size = archivo.size
            rf.save()

        return Response({"status": "ok", "stored": bool(creado)})


class WipeReport(APIView):
    """El agente reporta el resultado de una orden de `wipe` (feature 043).

    Va en apiv3 (token de AGENTE, no sesión de operador), como el upload de
    fileretrieval. El agente no sube archivos: solo el resultado por-ruta, el
    veredicto de la verificación por relectura (`verified`, RN-08) y la técnica
    aplicada (`method_applied`). En dry-run trae `plan` en vez de resultado.

    Idempotente: la orden se toma por `(pk, agent)`; un reenvío en estado terminal
    responde 409 y el agente deja de intentar.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, agentid, order_id):
        from erase.models import WipeOrder, WipeOrderStatus
        from erase.services import apply_wipe_report

        agent = _agente_del_token(request)
        if agent is None:
            return notify_error("Este endpoint sólo lo puede llamar un agente")
        if agent.agent_id != agentid:
            return notify_error("El agente del token no es el de la URL")

        order = WipeOrder.objects.filter(pk=order_id, agent=agent).first()
        if order is None:
            return notify_error("orden inexistente para este equipo")

        if order.status in (
            WipeOrderStatus.EXECUTED,
            WipeOrderStatus.INCOMPLETE,
            WipeOrderStatus.FAILED,
            WipeOrderStatus.CANCELLED,
        ):
            return Response(
                {"status": order.status},
                status=rest_framework_status.HTTP_409_CONFLICT,
            )

        verified = request.data.get("verified")
        if verified is not None:
            verified = str(verified) in ("1", "true", "True")

        apply_wipe_report(
            order=order,
            result=request.data.get("result"),
            verified=verified,
            method_applied=request.data.get("method_applied", ""),
            plan=request.data.get("plan"),
            error=request.data.get("error", ""),
        )
        return Response({"status": order.status})
