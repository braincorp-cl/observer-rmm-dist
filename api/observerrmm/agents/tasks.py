import asyncio
import datetime as dt
from time import sleep
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone as djangotime

from agents.models import Agent
from core.utils import get_core_settings, get_mesh_ws_url, remove_mesh_agent
from logs.models import DebugLog
from scripts.models import Script
from observerrmm.celery import app
from observerrmm.constants import (
    AGENT_DEFER,
    AGENT_OUTAGES_LOCK,
    AGENT_STATUS_OVERDUE,
    CheckStatus,
    DebugLogType,
)
from observerrmm.helpers import rand_range
from observerrmm.nats_utils import abulk_nats_command
from observerrmm.utils import redis_lock

if TYPE_CHECKING:
    from django.db.models.query import QuerySet


# Pasadas espaciadas del borrado del nodo Mesh (ver remove_mesh_node_task).
MESH_NODE_REMOVE_PASSES = 3
MESH_NODE_REMOVE_INTERVAL = 30

# Segundos que tiene que superar `last_seen - aviso` para considerar que el
# agente "volvió" y cancelar el borrado (ver manual_uninstall_delete_task).
MANUAL_UNINSTALL_REVIVAL_MARGIN = 120


@app.task(rate_limit="20/s")
def remove_mesh_node_task(mesh_node_id: Optional[str], _pass: int = 0) -> str:
    """Borra el nodo del agente en MeshCentral tras eliminarse el Agent.

    Se dispara desde la señal post_delete de Agent (ver agents/signals.py),
    de modo que CUALQUIER ruta de borrado (UI/API, admin, queryset, command
    bulk_delete_agents) propaga el borrado al nodo Mesh y no deja huérfanos.

    Corre uno a uno por el worker Celery: el rate_limit + la concurrencia del
    worker evitan saturar el puerto de control 4430 (compartido con los
    agentes en vivo). Para limpieza masiva del backlog histórico se usa el
    runbook SQL vía bulk_delete_orphans_meshagents, no esta ruta.

    Reintento diferido (defensa contra el race del agente vivo): al borrar un
    agente ONLINE, la señal corre casi a la par del `uninstall` por NATS. El
    meshagent sigue conectado unos segundos y RE-AGREGA el nodo (keepalive)
    justo después de esta remoción, dejándolo huérfano. Como removedevices es
    idempotente, reprogramamos pasadas espaciadas: una pasada posterior corre
    cuando el agente ya se desconectó y deja el nodo borrado de forma estable.
    Para agentes muertos/offline (el caso principal) la 1ª pasada ya basta y
    las siguientes son no-ops baratos.
    """
    if not mesh_node_id:
        return "skipped: agent sin mesh_node_id"
    try:
        uri = get_mesh_ws_url()
        asyncio.run(remove_mesh_agent(uri, mesh_node_id))
    except Exception as e:
        DebugLog.error(
            message=f"No se pudo borrar el nodo {mesh_node_id} de MeshCentral: {e}",
            log_type=DebugLogType.AGENT_ISSUES,
        )
        return f"error: {e}"
    if _pass < MESH_NODE_REMOVE_PASSES - 1:
        remove_mesh_node_task.apply_async(
            (mesh_node_id, _pass + 1), countdown=MESH_NODE_REMOVE_INTERVAL
        )
    return f"nodo mesh borrado (pasada {_pass}): {mesh_node_id}"


@app.task
def manual_uninstall_delete_task(agent_id: str, notified_at: str) -> str:
    """Borra el agente que avisó su propia desinstalación, tras la gracia.

    La ventana existe por una sola razón: **reinstalar corre el mismo
    `uninstall`**. Si borráramos al recibir el aviso, cada reinstalación se
    llevaría el registro por delante. Y si la desinstalación se cae a la mitad
    —el script falla después de avisar— el agente sigue vivo y reportando; en
    ese caso hay que cancelar el borrado, no ejecutarlo.

    El criterio de cancelación es que el agente haya vuelto a dar señales
    DESPUÉS del aviso. Un agente realmente desinstalado no puede: el servicio ya
    no existe.

    El nodo de MeshCentral no se toca acá: lo propaga la señal `post_delete`
    (agents/signals.py → remove_mesh_node_task), igual que en toda otra ruta de
    borrado.
    """
    from core.tasks import sync_mesh_perms_task
    from observerrmm.utils import reload_nats

    agent = (
        Agent.objects.defer(*AGENT_DEFER).filter(agent_id=agent_id).first()  # type: ignore
    )
    if not agent:
        return f"skipped: el agente {agent_id} ya no existe"

    try:
        notified = dt.datetime.fromisoformat(notified_at)
    except (TypeError, ValueError):
        notified = None

    # Margen contra el propio check-in que el agente pueda tener en vuelo cuando
    # avisa. Sin él, un `last_seen` escrito medio segundo después del aviso se
    # leería como "volvió" y el agente huérfano quedaría para siempre.
    if notified and agent.last_seen:
        revived = agent.last_seen - notified > dt.timedelta(
            seconds=MANUAL_UNINSTALL_REVIVAL_MARGIN
        )
        if revived:
            DebugLog.info(
                message=(
                    f"Borrado por desinstalación manual CANCELADO para "
                    f"{agent.hostname}: el agente volvió a reportar "
                    f"({agent.last_seen.isoformat()}) después del aviso "
                    f"({notified.isoformat()})."
                ),
                agent=agent,
                log_type=DebugLogType.AGENT_ISSUES,
            )
            return f"cancelado: {agent.hostname} volvió a reportar"

    hostname = agent.hostname
    agent.delete()
    reload_nats()
    sync_mesh_perms_task.delay()
    return f"agente borrado tras desinstalación manual: {hostname}"


@app.task
def send_agent_update_task(*, agent_ids: list[str], token: str, force: bool) -> None:
    agents: "QuerySet[Agent]" = Agent.objects.defer(*AGENT_DEFER).filter(
        agent_id__in=agent_ids
    )
    for agent in agents:
        agent.do_update(token=token, force=force)


@app.task
def auto_self_agent_update_task() -> None:
    if getattr(settings, "ORMM_DISABLE_AGENT_AUTO_UPDATE_TASK", False):
        return

    call_command("update_agents")


@app.task
def agent_outage_email_task(pk: int, alert_interval: Optional[float] = None) -> str:
    from alerts.models import Alert

    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return "alert not found"

    if not alert.email_sent:
        sleep(rand_range(100, 1500))
        alert.agent.send_outage_email()
        alert.email_sent = djangotime.now()
        alert.save(update_fields=["email_sent"])
    else:
        if alert_interval:
            # send an email only if the last email sent is older than alert interval
            delta = djangotime.now() - dt.timedelta(days=alert_interval)
            if alert.email_sent < delta:
                sleep(rand_range(100, 1500))
                alert.agent.send_outage_email()
                alert.email_sent = djangotime.now()
                alert.save(update_fields=["email_sent"])

    return "ok"


@app.task
def agent_recovery_email_task(pk: int) -> str:
    from alerts.models import Alert

    sleep(rand_range(100, 1500))

    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return "alert not found"

    alert.agent.send_recovery_email()
    alert.resolved_email_sent = djangotime.now()
    alert.save(update_fields=["resolved_email_sent"])

    return "ok"


@app.task
def agent_outage_sms_task(pk: int, alert_interval: Optional[float] = None) -> str:
    from alerts.models import Alert

    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return "alert not found"

    if not alert.sms_sent:
        sleep(rand_range(100, 1500))
        alert.agent.send_outage_sms()
        alert.sms_sent = djangotime.now()
        alert.save(update_fields=["sms_sent"])
    else:
        if alert_interval:
            # send an sms only if the last sms sent is older than alert interval
            delta = djangotime.now() - dt.timedelta(days=alert_interval)
            if alert.sms_sent < delta:
                sleep(rand_range(100, 1500))
                alert.agent.send_outage_sms()
                alert.sms_sent = djangotime.now()
                alert.save(update_fields=["sms_sent"])

    return "ok"


@app.task
def agent_recovery_sms_task(pk: int) -> str:
    from alerts.models import Alert

    sleep(rand_range(100, 1500))
    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return "alert not found"

    alert.agent.send_recovery_sms()
    alert.resolved_sms_sent = djangotime.now()
    alert.save(update_fields=["resolved_sms_sent"])

    return "ok"


@app.task(bind=True)
def agent_outages_task(self) -> str:
    with redis_lock(AGENT_OUTAGES_LOCK, self.app.oid) as acquired:
        if not acquired:
            return f"{self.app.oid} still running"

        from alerts.models import Alert
        from core.tasks import _get_agent_qs

        for agent in _get_agent_qs():
            if agent.status == AGENT_STATUS_OVERDUE:
                Alert.handle_alert_failure(agent)

        return "completed"


@app.task
def run_script_email_results_task(
    agentpk: int,
    scriptpk: int,
    nats_timeout: int,
    emails: list[str],
    args: list[str] = [],
    history_pk: int = 0,
    run_as_user: bool = False,
    env_vars: list[str] = [],
):
    agent = Agent.objects.get(pk=agentpk)
    script = Script.objects.get(pk=scriptpk)
    r = agent.run_script(
        scriptpk=script.pk,
        args=args,
        full=True,
        timeout=nats_timeout,
        wait=True,
        history_pk=history_pk,
        run_as_user=run_as_user,
        env_vars=env_vars,
    )
    if r == "timeout":
        DebugLog.error(
            agent=agent,
            log_type=DebugLogType.SCRIPTING,
            message=f"{agent.hostname}({agent.pk}) timed out running script.",
        )
        return

    CORE = get_core_settings()
    subject = f"{agent.client.name}, {agent.site.name}, {agent.hostname} {script.name} Results"
    exec_time = "{:.4f}".format(r["execution_time"])
    body = (
        subject
        + f"\nReturn code: {r['retcode']}\nExecution time: {exec_time} seconds\nStdout: {r['stdout']}\nStderr: {r['stderr']}"
    )

    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = CORE.smtp_from_email

    if emails:
        msg["To"] = ", ".join(emails)
    else:
        msg["To"] = ", ".join(CORE.email_alert_recipients)

    msg.set_content(body)

    try:
        with smtplib.SMTP(CORE.smtp_host, CORE.smtp_port, timeout=20) as server:
            if CORE.smtp_requires_auth:
                server.ehlo()
                server.starttls()
                server.login(CORE.smtp_host_user, CORE.smtp_host_password)
                server.send_message(msg)
                server.quit()
            else:
                server.send_message(msg)
                server.quit()
    except Exception as e:
        DebugLog.error(message=str(e))


@app.task
def clear_faults_task(older_than_days: int) -> None:
    from alerts.models import Alert

    # (ref. de issue del proyecto de origen: 484)
    agents = Agent.objects.exclude(last_seen__isnull=True).filter(
        last_seen__lt=djangotime.now() - djangotime.timedelta(days=older_than_days)
    )
    for agent in agents:
        for check in agent.get_checks_with_policies():
            # reset check status
            if check.check_result:
                check.check_result.status = CheckStatus.PASSING
                check.check_result.save(update_fields=["status"])
            if check.alert.filter(agent=agent, resolved=False).exists():
                alert = Alert.create_or_return_check_alert(check, agent=agent)
                if alert:
                    alert.resolve()

        # reset overdue alerts
        agent.overdue_email_alert = False
        agent.overdue_text_alert = False
        agent.overdue_dashboard_alert = False
        agent.save(
            update_fields=[
                "overdue_email_alert",
                "overdue_text_alert",
                "overdue_dashboard_alert",
            ]
        )


@app.task
def prune_agent_history(older_than_days: int) -> str:
    from .models import AgentHistory

    AgentHistory.objects.filter(
        time__lt=djangotime.now() - djangotime.timedelta(days=older_than_days)
    ).delete()

    return "ok"


@app.task
def bulk_recover_agents_task() -> None:
    call_command("bulk_restart_agents")


# --- Geocerca por sitio (feature 026) -----------------------------------------
# Sólo se evalúan fixes MEDIDOS (native/wifi). Deliberadamente NO se evalúa "ip":
# su error típico contra un bloque de ISP registrado en la casa matriz es de
# cientos de km (238 km medidos en el bloque de Entel que usa el datacenter de
# Talca), así que evaluarlo generaría un falso positivo por cada equipo sin radio
# WiFi. Tampoco "site", que sería tautológico: esas coordenadas SON las del sitio.

# Un punto más viejo que esto no se evalúa: si el equipo dejó de reportar
# ubicación hace un día, lo que corresponde es la alerta de disponibilidad, no
# afirmar dónde está en base a un dato rancio.
GEOFENCE_MAX_FIX_AGE = dt.timedelta(hours=24)


def _format_distance(meters: float) -> str:
    return f"{meters / 1000:.1f} km" if meters >= 1000 else f"{round(meters)} m"


@app.task
def geofence_check_task() -> str:
    """Compara la última posición medida de cada agente contra su sitio.

    Corre desde celerybeat. Crea una alerta cuando el equipo se midió fuera del
    radio y la resuelve cuando vuelve a entrar (o cuando deja de ser evaluable,
    p. ej. si se le quitan las coordenadas al sitio o se lo marca como
    autorizado a salir) — así no quedan alertas colgadas para siempre.
    """
    from alerts.models import Alert
    from checks.models import CheckHistory
    from core.geo import haversine_m
    from observerrmm.constants import (
        GEO_CHECK_HISTORY_ID,
        GEO_MEASURED_SOURCES,
        AlertType,
    )

    core = get_core_settings()
    if not core.geo_tracking_enabled or not core.geo_geofence_enabled:
        return "geofence disabled"

    radius = core.geo_geofence_radius_m

    # Candidatos: equipos estacionarios cuyo sitio TIENE coordenadas. Un sitio sin
    # coordenadas no define ninguna cerca, así que sus equipos no se evalúan.
    agents = {
        a.agent_id: a
        for a in Agent.objects.select_related("site", "site__client")
        .filter(
            site__latitude__isnull=False,
            site__longitude__isnull=False,
            geo_offsite_allowed=False,
            maintenance_mode=False,
        )
        .only(
            "agent_id",
            "hostname",
            "alert_template",
            "site__name",
            "site__latitude",
            "site__longitude",
            "site__client__name",
        )
    }

    # Última fila geo por agente en UNA consulta (DISTINCT ON de Postgres) en vez
    # de una por equipo: esto corre cada pocos minutos sobre toda la flota.
    latest = (
        CheckHistory.objects.filter(
            check_id=GEO_CHECK_HISTORY_ID,
            agent_id__in=agents.keys(),
            x__gte=djangotime.now() - GEOFENCE_MAX_FIX_AGE,
        )
        .order_by("agent_id", "-x")
        .distinct("agent_id")
    )

    outside: dict[str, float] = {}
    inside: set[str] = set()

    for row in latest:
        results = row.results or {}
        if results.get("source") not in GEO_MEASURED_SOURCES:
            continue

        lat, long = results.get("lat"), results.get("long")
        if lat is None or long is None:
            continue

        site = agents[row.agent_id].site
        distance = haversine_m(lat, long, site.latitude, site.longitude)

        # El radio del fix se descuenta del margen: un equipo a 1.010 m con un
        # fix de ±20 m puede estar perfectamente dentro de la cerca. Se alerta
        # sólo cuando estar fuera es la única lectura posible del dato.
        if distance - (row.y or 0) > radius:
            outside[row.agent_id] = distance
        else:
            inside.add(row.agent_id)

    for agent_id, distance in outside.items():
        _open_geofence_alert(agents[agent_id], distance, radius)

    # Se resuelve sólo con evidencia POSITIVA de que la alerta ya no aplica:
    #   a) el equipo se volvió a medir dentro del radio, o
    #   b) dejó de ser evaluable por configuración (se le quitaron las coordenadas
    #      al sitio, se lo marcó como autorizado a salir, entró en mantención).
    # Deliberadamente NO se resuelve por falta de datos frescos: si un equipo se
    # fue del sitio y después dejó de reportar, cerrar la alerta sería justo lo
    # contrario de lo que el operador necesita ver.
    open_alerts = Alert.objects.filter(
        alert_type=AlertType.GEOFENCE, resolved=False
    ).select_related("agent", "agent__site", "agent__site__client")

    resolved = 0
    for alert in open_alerts:
        if not alert.agent:
            continue
        agent_id = alert.agent.agent_id
        if agent_id in inside:
            _resolve_geofence_alert(alert, back_inside=True)
            resolved += 1
        elif agent_id not in agents:
            _resolve_geofence_alert(alert, back_inside=False)
            resolved += 1

    return (
        f"geofence: {len(outside)} outside, {len(inside)} inside, {resolved} resolved"
    )


def _open_geofence_alert(agent: "Agent", distance: float, radius: int) -> None:
    from alerts.models import Alert
    from observerrmm.constants import AlertSeverity, AlertType

    # Ya hay una alerta abierta: no se duplica ni se re-notifica en cada pasada.
    # El operador la resuelve o la silencia con la maquinaria estándar de alertas.
    if Alert.objects.filter(
        agent=agent, alert_type=AlertType.GEOFENCE, resolved=False
    ).exists():
        return

    message = (
        f"{agent.hostname} se midió a {_format_distance(distance)} de "
        f"{agent.site.client.name} / {agent.site.name}, "
        f"fuera del radio autorizado de {_format_distance(radius)}."
    )

    Alert.objects.create(
        agent=agent,
        alert_type=AlertType.GEOFENCE,
        severity=AlertSeverity.WARNING,
        message=message,
        # hidden=False a propósito: la alerta debe aparecer en el widget de la
        # consola de inmediato (el listado filtra hidden=False).
        hidden=False,
    )

    DebugLog.warning(
        agent=agent,
        log_type=DebugLogType.AGENT_ISSUES,
        message=message,
    )

    _send_geofence_email(agent, subject_prefix="Geocerca", message=message)


def _resolve_geofence_alert(alert, *, back_inside: bool) -> None:
    """Cierra la alerta. `back_inside` distingue los dos motivos posibles para
    que el correo diga la verdad: el equipo volvió al sitio, o la geocerca dejó
    de aplicarle por un cambio de configuración."""
    agent = alert.agent
    alert.resolve()

    if not agent:
        return

    site = f"{agent.site.client.name} / {agent.site.name}"
    message = (
        f"{agent.hostname} volvió al radio autorizado de {site}."
        if back_inside
        else (
            f"{agent.hostname} ya no se evalúa contra la geocerca de {site} "
            f"(cambió su configuración: coordenadas del sitio, permiso de salida "
            f"o modo mantención)."
        )
    )
    _send_geofence_email(agent, subject_prefix="Geocerca resuelta", message=message)


def _send_geofence_email(agent: "Agent", subject_prefix: str, message: str) -> None:
    """Envía el correo con la maquinaria de email existente.

    Best-effort: si el SMTP no está configurado, send_mail devuelve False y la
    alerta igual queda en el widget. Un problema de correo nunca debe romper la
    pasada de la geocerca ni el resto de la flota.
    """
    core = get_core_settings()
    try:
        core.send_mail(
            f"{subject_prefix}: {agent.hostname}",
            message,
            alert_template=agent.alert_template,
        )
    except Exception as e:
        DebugLog.error(
            agent=agent,
            log_type=DebugLogType.AGENT_ISSUES,
            message=f"Geofence email failed: {e}",
        )


# Feature 028 · fan-out masivo de lock / alert / alarm.
@app.task
def bulk_endpoint_response_task(
    *, agent_pks: list[int], func: str, payload: Optional[dict] = None
) -> None:
    """Manda la misma acción de respuesta a varios agentes.

    A diferencia de las vistas por agente, acá NO se espera respuesta: el envío es
    "fire and forget" (`abulk_nats_command`). Es una decisión de escala, no de
    comodidad — un mensaje a toda la flota son cientos de peticiones NATS, y
    esperar 15 s por cada agente apagado convertiría la acción en un cuelgue de
    varios minutos ([[project_production_context]]: flotas grandes).

    El precio es que el operador no ve por qué falló equipo por equipo. Se asume a
    conciencia: para el diagnóstico individual está la acción por agente, que sí
    devuelve el código.
    """
    nats_data: dict = {"func": func}
    if payload:
        nats_data["payload"] = payload

    items = [
        (agent.agent_id, nats_data)
        for agent in Agent.objects.defer(*AGENT_DEFER).filter(pk__in=agent_pks)
    ]

    try:
        asyncio.run(abulk_nats_command(items=items))
    except Exception as e:
        DebugLog.error(
            log_type=DebugLogType.AGENT_ISSUES,
            message=f"bulk_endpoint_response_task ({func}) failed: {e}",
        )
