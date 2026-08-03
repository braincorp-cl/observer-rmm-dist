from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from autotasks.models import AutomatedTask
from autotasks.serializers import TaskSerializer
from logs.models import DebugLog
from observerrmm.constants import DebugLogLevel, DebugLogType, TaskType


class Command(BaseCommand):
    # DF-03 / data-delta.md §4 — en BDs con datos legacy este command debe correr
    # ANTES de la migración que agrega los CheckConstraint de schedule: una fila
    # inválida preexistente hace fallar el AddConstraint. En instalación fresh no
    # encuentra nada. Usa TaskSerializer.SCHEDULE_INVARIANTS como única fuente de
    # verdad del mapeo task_type → campos requeridos.
    help = (
        "Detecta tasks cuyo schedule viola los invariantes DF-03 (campos NULL "
        "para su task_type) y los convierte a manual+disabled preservando datos. "
        "Con --dry-run solo reporta. Correr antes de migrate en BDs con datos legacy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo reporta las filas que violarían los constraints, sin modificar nada",
        )

    def handle(self, *args, **kwargs):
        dry_run = kwargs["dry_run"]
        violations_found = 0
        with transaction.atomic():
            for task_type, fields in TaskSerializer.SCHEDULE_INVARIANTS.items():
                # columna real por campo (FKs validan sobre <campo>_id sin fetch)
                attnames = {
                    field: AutomatedTask._meta.get_field(field).attname
                    for field in fields
                }
                null_q = Q()
                for field in fields:
                    null_q |= Q(**{f"{field}__isnull": True})

                for task in AutomatedTask.objects.filter(task_type=task_type).filter(
                    null_q
                ):
                    null_fields = [
                        field
                        for field in fields
                        if getattr(task, attnames[field]) is None
                    ]
                    violations_found += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Task {task.pk} '{task.name}' (task_type={task_type}) "
                            f"viola invariante DF-03: {', '.join(null_fields)} NULL"
                        )
                    )
                    if dry_run:
                        continue

                    original_type = task.task_type
                    task.task_type = TaskType.MANUAL
                    task.enabled = False
                    task.save(update_fields=["task_type", "enabled"])
                    DebugLog.objects.create(
                        log_level=DebugLogLevel.WARN,
                        log_type=DebugLogType.SYSTEM_ISSUES,
                        agent=task.agent,
                        message=(
                            f"sanitize_task_schedule_invariants: task {task.pk} "
                            f"'{task.name}' convertido de task_type="
                            f"'{original_type}' a manual+disabled por violar el "
                            f"invariante DF-03 ({', '.join(null_fields)} NULL). "
                            "Datos de schedule preservados."
                        ),
                    )
                    self.stdout.write(
                        f"  -> convertido a manual+disabled (era '{original_type}')"
                    )

        if violations_found == 0:
            self.stdout.write(
                self.style.SUCCESS("Sin violaciones DF-03. BD lista para migrate.")
            )
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"{violations_found} task(s) violarían los constraints DF-03. "
                    "Correr sin --dry-run antes de migrate."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{violations_found} task(s) saneados (manual+disabled, con DebugLog). "
                    "BD lista para migrate."
                )
            )
