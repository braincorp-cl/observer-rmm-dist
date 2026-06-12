"""DF-03: CheckConstraint de invariantes de schedule en autotasks_automatedtask.

ORDEN OBLIGATORIO en BDs con datos legacy (data-delta.md §4 de F008):
correr `python manage.py sanitize_task_schedule_invariants` ANTES de
`migrate` — una fila preexistente que viole un invariante (ej. task WEEKLY
con run_time_bit_weekdays NULL, caso EC-11 pre-fix) hace fallar el
AddConstraint. En instalación fresh el riesgo es nulo.

Reversible: el reverso de cada AddConstraint es RemoveConstraint.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("autotasks", "0041_automatedtask_task_supported_platforms_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="automatedtask",
            constraint=models.CheckConstraint(
                name="runonce_requires_run_time_date",
                check=~Q(task_type="runonce") | Q(run_time_date__isnull=False),
            ),
        ),
        migrations.AddConstraint(
            model_name="automatedtask",
            constraint=models.CheckConstraint(
                name="daily_requires_schedule_fields",
                check=~Q(task_type="daily")
                | (Q(run_time_date__isnull=False) & Q(daily_interval__isnull=False)),
            ),
        ),
        migrations.AddConstraint(
            model_name="automatedtask",
            constraint=models.CheckConstraint(
                name="weekly_requires_schedule_fields",
                check=~Q(task_type="weekly")
                | (
                    Q(run_time_date__isnull=False)
                    & Q(weekly_interval__isnull=False)
                    & Q(run_time_bit_weekdays__isnull=False)
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name="automatedtask",
            constraint=models.CheckConstraint(
                name="monthly_requires_schedule_fields",
                check=~Q(task_type="monthly")
                | (
                    Q(run_time_date__isnull=False)
                    & Q(monthly_months_of_year__isnull=False)
                    & Q(monthly_days_of_month__isnull=False)
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name="automatedtask",
            constraint=models.CheckConstraint(
                name="monthlydow_requires_schedule_fields",
                check=~Q(task_type="monthlydow")
                | (
                    Q(run_time_date__isnull=False)
                    & Q(monthly_months_of_year__isnull=False)
                    & Q(monthly_weeks_of_month__isnull=False)
                    & Q(run_time_bit_weekdays__isnull=False)
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name="automatedtask",
            constraint=models.CheckConstraint(
                name="checkfailure_requires_assigned_check",
                check=~Q(task_type="checkfailure")
                | Q(assigned_check__isnull=False),
            ),
        ),
    ]
