import json
import os

from django.core.management.base import BaseCommand

from agents.models import Agent
from logs.models import AuditLog

# Tercero de los cuatro caminos de escritura del modo mantenimiento (ver el
# invariante junto al campo en agents/models.py). Como los otros dos masivos, usa
# `.update()` y por lo tanto NO pasa por Agent.save(): el sellado de since/by y la
# entrada de auditoría se piden a mano. El autor es "system" y no una persona,
# porque este comando lo corre el playbook de despliegue, no la consola.
MAINT_SYSTEM_USER = "system"


def _audit(action: str, count: int) -> None:
    if not count:
        return

    AuditLog.audit_bulk_action(
        MAINT_SYSTEM_USER,
        f"maintenance mode {action}",
        {"target": "all", "count": count, "source": "server_maint_mode"},
    )


class Command(BaseCommand):
    help = "Toggle server maintenance mode, preserving existing state"

    def add_arguments(self, parser):
        parser.add_argument("--enable", action="store_true")
        parser.add_argument("--disable", action="store_true")
        parser.add_argument("--force-enable", action="store_true")
        parser.add_argument("--force-disable", action="store_true")

    def handle(self, *args, **kwargs):
        enable = kwargs["enable"]
        disable = kwargs["disable"]
        force_enable = kwargs["force_enable"]
        force_disable = kwargs["force_disable"]

        home_dir = os.path.expanduser("~")
        fp = os.path.join(home_dir, "agents_maint_mode.json")

        enable_updates = Agent.maintenance_field_updates(True, MAINT_SYSTEM_USER)
        disable_updates = Agent.maintenance_field_updates(False, MAINT_SYSTEM_USER)

        if enable:
            current = list(
                Agent.objects.filter(maintenance_mode=True).values_list("id", flat=True)
            )

            with open(fp, "w") as f:
                json.dump(current, f)

            # Sólo los que TRANSITAN. Escribir sobre los que ya estaban en
            # mantenimiento les borraría la fecha de inicio real y haría parecer
            # que su ventana empezó con este despliegue.
            count = Agent.objects.filter(maintenance_mode=False).update(
                **enable_updates
            )
            _audit("enabled", count)

        elif disable:
            with open(fp, "r") as f:
                state = json.load(f)

            count = (
                Agent.objects.exclude(pk__in=state)
                .filter(maintenance_mode=True)
                .update(**disable_updates)
            )
            _audit("disabled", count)

        elif force_enable:
            count = Agent.objects.filter(maintenance_mode=False).update(
                **enable_updates
            )
            _audit("enabled", count)

        elif force_disable:
            if os.path.exists(fp):
                os.remove(fp)

            count = Agent.objects.filter(maintenance_mode=True).update(
                **disable_updates
            )
            _audit("disabled", count)
