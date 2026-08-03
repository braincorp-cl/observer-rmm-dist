import asyncio
import json

import websockets

# websockets 13.1 no expone el submódulo `exceptions` como atributo del paquete top-level
# por acceso perezoso: `websockets.exceptions.X` lanza AttributeError. Import explícito
# (observado vivo en el bring-up mesh 2026-06-27, GAP-049).
from websockets.exceptions import ConnectionClosedError

from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils import get_core_settings, get_mesh_ws_url
from observerrmm.constants import ORMM_WS_MAX_SIZE


class Command(BaseCommand):
    help = "Sets up initial mesh central configuration"

    async def websocket_call(self, uri) -> bool:
        # Devuelve True si creó el device group, False si ya existía (para que el
        # caller distinga "changed" de no-op — idempotencia del deploy Ansible).
        async with websockets.connect(uri, max_size=ORMM_WS_MAX_SIZE) as websocket:
            # Get Device groups to see if it exists
            await websocket.send(json.dumps({"action": "meshes"}))

            async for message in websocket:
                response = json.loads(message)
                if response["action"] == "meshes":
                    # If no meshes are present
                    if not response["meshes"]:
                        await websocket.send(
                            json.dumps(
                                {
                                    "action": "createmesh",
                                    "meshname": "ObserverRMM",
                                    "meshtype": 2,
                                    "responseid": "python",
                                }
                            )
                        )
                        return True
                    else:
                        return False
        return False

    def handle(self, *args, **kwargs):
        mesh_settings = get_core_settings()

        try:
            # Check for Mesh Username
            if (
                not mesh_settings.mesh_username
                or settings.MESH_USERNAME.lower() != mesh_settings.mesh_username
            ):
                mesh_settings.mesh_username = settings.MESH_USERNAME.lower()

            # Check for Mesh Site
            if (
                not mesh_settings.mesh_site
                or settings.MESH_SITE != mesh_settings.mesh_site
            ):
                mesh_settings.mesh_site = settings.MESH_SITE

            # Check for Mesh Token
            if (
                not mesh_settings.mesh_token
                or settings.MESH_TOKEN_KEY != mesh_settings.mesh_token
            ):
                mesh_settings.mesh_token = settings.MESH_TOKEN_KEY

            mesh_settings.save()

        except AttributeError:
            self.stdout.write(
                "Mesh Setup was skipped because the configuration wasn't available. Needs to be setup manually."
            )
            return

        try:
            uri = get_mesh_ws_url()
            created = asyncio.run(self.websocket_call(uri))
            if created:
                self.stdout.write("Created device group ObserverRMM")
            else:
                self.stdout.write("Device group ObserverRMM already present")
            self.stdout.write("Initial Mesh Central setup complete")
        except ConnectionClosedError:
            self.stdout.write(
                "Unable to connect to MeshCentral. Please verify it is online and the configuration is correct in the settings."
            )
