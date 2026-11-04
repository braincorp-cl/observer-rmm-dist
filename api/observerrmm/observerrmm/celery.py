from __future__ import absolute_import, unicode_literals

import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "observerrmm.settings")

redis_host = f"redis://{settings.REDIS_HOST}"
app = Celery("observerrmm", backend=redis_host, broker=redis_host)
# estos tres van en app.conf: asignarlos sobre app deja un atributo muerto
app.conf.accept_content = ["application/json"]
app.conf.result_serializer = "json"
app.conf.task_serializer = "json"
app.conf.task_track_started = True
app.conf.worker_proc_alive_timeout = 30
# reciclar el proceso hijo por memoria y no cada N tareas: con flota grande,
# recrearlo cada dos tareas es un fork() + import de Django casi continuo
app.conf.worker_max_memory_per_child = 250_000  # KB
app.conf.broker_connection_retry_on_startup = True
# sin estos limites, un corte con Redis deja al worker esperando sin tope
app.conf.broker_transport_options = {
    "socket_timeout": 30,
    "socket_connect_timeout": 10,
    "socket_keepalive": True,
    "retry_on_timeout": True,
}
app.conf.redis_socket_timeout = 30
app.conf.redis_socket_connect_timeout = 10
app.conf.redis_socket_keepalive = True
app.conf.redis_retry_on_timeout = True
app.conf.redis_backend_health_check_interval = 30
app.conf.result_expires = 3600
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # el latido vale justamente por correr seguido: si se enfria, el monitoreo
    # se entera de que las tareas de fondo dejaron de procesarse
    "celery-heartbeat": {
        "task": "core.tasks.celery_heartbeat_task",
        "schedule": crontab(minute="*"),
    },
    "auto-approve-win-updates": {
        "task": "winupdate.tasks.auto_approve_updates_task",
        "schedule": crontab(minute=2, hour="*/8"),
    },
    "install-scheduled-win-updates": {
        "task": "winupdate.tasks.check_agent_update_schedule_task",
        "schedule": crontab(minute=5, hour="*"),
    },
    "agent-auto-update": {
        "task": "agents.tasks.auto_self_agent_update_task",
        "schedule": crontab(minute=35, hour="*"),
    },
    "remove-orphaned-tasks": {
        "task": "autotasks.tasks.remove_orphaned_win_tasks",
        "schedule": crontab(minute=50, hour="*/2"),
    },
    "agent-outages-task": {
        "task": "agents.tasks.agent_outages_task",
        "schedule": timedelta(seconds=150.0),
    },
    "unsnooze-alerts": {
        "task": "alerts.tasks.unsnooze_alerts",
        "schedule": crontab(minute=10, hour="*"),
    },
    "core-maintenance-tasks": {
        "task": "core.tasks.core_maintenance_tasks",
        "schedule": crontab(minute=15, hour="*"),
    },
    "cache-db-fields-task": {
        "task": "core.tasks.cache_db_fields_task",
        "schedule": crontab(minute="*/3", hour="*"),
    },
    "sync-scheduled-tasks": {
        "task": "core.tasks.sync_scheduled_tasks",
        "schedule": crontab(minute="*/2", hour="*"),
    },
    "sync-mesh-perms-task": {
        "task": "core.tasks.sync_mesh_perms_task",
        "schedule": crontab(minute="*/4", hour="*"),
    },
    "resolve-pending-actions": {
        "task": "core.tasks.resolve_pending_actions",
        "schedule": timedelta(seconds=100.0),
    },
    "resolve-alerts-task": {
        "task": "core.tasks.resolve_alerts_task",
        "schedule": timedelta(seconds=80.0),
    },
    "ormm-scheduler": {
        "task": "core.tasks.scheduled_task_runner",
        "schedule": crontab(),
    },
    # Geocerca por sitio (feature 026). Cada 5 min: la ubicación se reporta en el
    # check-in del agente (300 s por defecto), así que una pasada más frecuente no
    # tendría datos nuevos que evaluar.
    "geofence-check-task": {
        "task": "agents.tasks.geofence_check_task",
        "schedule": crontab(minute="*/5"),
    },
    "ormm-reports-scheduler": {
        "task": "ee.reporting.tasks.scheduled_reports_runner",
        "schedule": crontab(),
    },
    # Censo de nodos Mesh huérfanos: sólo LEE y reporta, no borra (el borrado va
    # por el runbook SQL; la API removedevices no persiste a escala). Una vez al
    # día y de madrugada porque un huérfano es deriva de inventario, no un
    # incidente: nace de un enrolamiento fallido y se queda quieto. Más seguido
    # sería una lectura del websocket de control —el mismo puerto que atienden
    # los agentes en vivo— sin nada nuevo que mirar.
    "mesh-orphan-nodes-census": {
        "task": "core.tasks.mesh_orphan_nodes_census_task",
        "schedule": crontab(minute=40, hour=4),
    },
    # Recordatorio de mantenimiento prolongado (feature 036). Una vez al día y en
    # horario laboral, por el mismo criterio del censo de huérfanos: un mantenimiento
    # olvidado es deriva, no un incidente. De madrugada tampoco serviría — el correo
    # existe para que alguien lo lea y decida bajar el flag, así que llega cuando esa
    # persona está frente al computador.
    "maintenance-mode-reminder": {
        "task": "core.tasks.maintenance_mode_reminder_task",
        "schedule": crontab(minute=0, hour=9),
    },
}


@app.task(bind=True)
def debug_task(self):
    print("Request: {0!r}".format(self.request))
