from django.conf import settings
from django.core.management.base import BaseCommand
from packaging import version as pyver

from agents.models import Agent
from agents.tasks import send_agent_update_task
from core.utils import get_core_settings, token_is_valid
from observerrmm.constants import AGENT_DEFER


class Command(BaseCommand):
    help = "Triggers an agent update task to run"

    def handle(self, *args, **kwargs):
        core = get_core_settings()
        if not core.agent_auto_update:
            return

        # order_by explicito por el mismo motivo que en agents.views.update_agents:
        # sin el, PostgreSQL puede devolver las filas en cualquier orden y la lista
        # que sale hacia Celery cambia entre corridas. Se ordena por PK, no por
        # agent_id, para no depender de la collation de la BD.
        q = (
            Agent.objects.defer(*AGENT_DEFER)
            .exclude(version=settings.LATEST_AGENT_VER)
            .order_by("id")
        )
        agent_ids: list[str] = [
            i.agent_id
            for i in q
            if pyver.parse(i.version) < pyver.parse(settings.LATEST_AGENT_VER)
        ]
        token, _ = token_is_valid()
        send_agent_update_task.delay(agent_ids=agent_ids, token=token, force=False)
