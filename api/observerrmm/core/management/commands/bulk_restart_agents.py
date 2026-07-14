from time import sleep

from django.core.management.base import BaseCommand

from agents.models import Agent
from agents.utils import get_agent_url
from core.utils import get_mesh_ws_url, token_is_valid
from observerrmm.constants import AGENT_DEFER


class Command(BaseCommand):
    help = "Reinstalls the agent and meshagent services"

    def handle(self, *args, **kwargs) -> None:
        agents = Agent.objects.defer(*AGENT_DEFER)
        uri = get_mesh_ws_url()
        code_token, _ = token_is_valid()

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
            agent_url = get_agent_url(
                goarch=agent.goarch, plat=agent.plat, token=code_token
            )
            agent.recover("tacagent", uri, wait=False, agent_url=agent_url)

        self.stdout.write(self.style.WARNING("Waiting 10 seconds..."))
        sleep(10)

        for agent in agents:
            self.stdout.write(
                self.style.SUCCESS(f"Restarting MeshAgent Service on {agent.hostname}")
            )
            agent.recover("mesh", "", wait=False)
