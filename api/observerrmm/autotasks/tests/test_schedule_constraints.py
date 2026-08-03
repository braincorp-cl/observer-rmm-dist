from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.utils import timezone as djangotime
from model_bakery import baker

from logs.models import DebugLog
from observerrmm.constants import TaskType
from observerrmm.test import ObserverTestCase

from autotasks.models import AutomatedTask


class TestScheduleInvariantConstraints(ObserverTestCase):
    """DF-03: los CheckConstraint de BD espejan TaskSerializer.SCHEDULE_INVARIANTS.

    Cubre el cierre total de EC-11/RN-026: el serializer ya rechaza el bypass
    (fix 8f887987 del hub); estos tests prueban que la BD rechaza escrituras
    ORM directas que salten el serializer.
    """

    def setUp(self):
        self.setup_coresettings()

    def _drop_constraint(self, name):
        # Simula una BD legacy pre-migración 0042: sin soltar el constraint es
        # imposible insertar la fila violatoria que el command debe sanear. El
        # DDL es transaccional en PG y se revierte al cerrar el test.
        constraint = next(c for c in AutomatedTask._meta.constraints if c.name == name)
        with connection.schema_editor() as editor:
            editor.remove_constraint(AutomatedTask, constraint)

    def _make_violating_weekly_task(self):
        # Caso EC-11 pre-fix: WEEKLY con run_time_bit_weekdays NULL
        return baker.make(
            "autotasks.AutomatedTask",
            task_type=TaskType.WEEKLY,
            run_time_date=djangotime.now(),
            weekly_interval=1,
            run_time_bit_weekdays=None,
            enabled=True,
        )

    def test_orm_write_violating_invariant_raises_integrity_error(self):
        # escenario Gherkin RF-08: bypass del serializer vía ORM directo
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._make_violating_weekly_task()

        # los 6 task_types con constraint, con todos sus campos invariantes NULL
        for task_type in (
            TaskType.RUN_ONCE,
            TaskType.DAILY,
            TaskType.WEEKLY,
            TaskType.MONTHLY,
            TaskType.MONTHLY_DOW,
            TaskType.CHECK_FAILURE,
        ):
            with self.subTest(task_type=task_type):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    baker.make("autotasks.AutomatedTask", task_type=task_type)

    def test_orm_write_valid_schedule_passes(self):
        # control: filas válidas por task_type no disparan los constraints
        agent = baker.make_recipe("agents.agent")
        check = baker.make_recipe("checks.diskspace_check", agent=agent)
        now = djangotime.now()
        valid_fields = {
            TaskType.RUN_ONCE: {"run_time_date": now},
            TaskType.DAILY: {"run_time_date": now, "daily_interval": 1},
            TaskType.WEEKLY: {
                "run_time_date": now,
                "weekly_interval": 1,
                "run_time_bit_weekdays": 62,
            },
            TaskType.MONTHLY: {
                "run_time_date": now,
                "monthly_months_of_year": 4095,
                "monthly_days_of_month": 1,
            },
            TaskType.MONTHLY_DOW: {
                "run_time_date": now,
                "monthly_months_of_year": 4095,
                "monthly_weeks_of_month": 1,
                "run_time_bit_weekdays": 62,
            },
            TaskType.CHECK_FAILURE: {"assigned_check": check},
            # sin constraint: schedule completamente NULL es válido
            TaskType.MANUAL: {},
            TaskType.ONBOARDING: {},
            TaskType.SCHEDULED: {},
        }
        for task_type, fields in valid_fields.items():
            with self.subTest(task_type=task_type):
                task = baker.make(
                    "autotasks.AutomatedTask", task_type=task_type, **fields
                )
                self.assertIsNotNone(task.pk)

    def test_sanitize_command_dry_run_reports_without_modifying(self):
        self._drop_constraint("weekly_requires_schedule_fields")
        task = self._make_violating_weekly_task()

        out = StringIO()
        call_command("sanitize_task_schedule_invariants", "--dry-run", stdout=out)
        output = out.getvalue()

        self.assertIn("viola invariante DF-03", output)
        self.assertIn(str(task.pk), output)
        self.assertIn("run_time_bit_weekdays", output)

        task.refresh_from_db()
        self.assertEqual(task.task_type, TaskType.WEEKLY)
        self.assertTrue(task.enabled)
        self.assertIsNone(task.run_time_bit_weekdays)
        self.assertFalse(
            DebugLog.objects.filter(
                message__icontains="sanitize_task_schedule_invariants"
            ).exists()
        )

    def test_sanitize_command_converts_to_manual_disabled_with_debuglog(self):
        self._drop_constraint("weekly_requires_schedule_fields")
        task = self._make_violating_weekly_task()

        out = StringIO()
        call_command("sanitize_task_schedule_invariants", stdout=out)
        output = out.getvalue()

        self.assertIn("viola invariante DF-03", output)
        self.assertIn("saneados", output)

        task.refresh_from_db()
        self.assertEqual(task.task_type, TaskType.MANUAL)
        self.assertFalse(task.enabled)
        # datos de schedule preservados
        self.assertIsNotNone(task.run_time_date)
        self.assertEqual(task.weekly_interval, 1)

        log = DebugLog.objects.filter(
            message__icontains="sanitize_task_schedule_invariants"
        )
        self.assertEqual(log.count(), 1)
        self.assertIn(str(task.pk), log.first().message)
        self.assertIn("weekly", log.first().message)

    def test_sanitize_command_clean_db_reports_nothing(self):
        out = StringIO()
        call_command("sanitize_task_schedule_invariants", "--dry-run", stdout=out)
        self.assertIn("Sin violaciones DF-03", out.getvalue())
