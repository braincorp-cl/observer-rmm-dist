from time import sleep

from django.core.management.base import BaseCommand

from agents.models import Agent
from core.utils import get_mesh_ws_url
from observerrmm.constants import AGENT_DEFER


class Command(BaseCommand):
    help = "Restarts the agent and meshagent services"

    def handle(self, *args, **kwargs) -> None:
        agents = Agent.objects.defer(*AGENT_DEFER)
        uri = get_mesh_ws_url()

        for agent in agents:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Restarting Observer Agent Service on {agent.hostname}"
                )
            )
            # DEUDA (revisar en repo observer-agent): el comando "tacagent" y el
            # nombre del servicio del agente (hardcodeado en web checks.js) son
            # contrato con el binario del agente. Rebrand pendiente allá; cambiarlo
            # solo aquí rompería el control de agentes ya instalados.
            agent.recover("tacagent", uri, wait=False)

        self.stdout.write(self.style.WARNING("Waiting 10 seconds..."))
        sleep(10)

        for agent in agents:
            self.stdout.write(
                self.style.SUCCESS(f"Restarting MeshAgent Service on {agent.hostname}")
            )
            agent.recover("mesh", "", wait=False)
