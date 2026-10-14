# Feature 049-B2: interruptor global del monitoreo de actividad (APAGADO) + cadencia.
# AddField aditivos con default.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0071_coresettings_activity_prune_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresettings",
            name="activity_monitoring_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="coresettings",
            name="activity_interval_seg",
            field=models.PositiveIntegerField(default=60),
        ),
        migrations.AddField(
            model_name="coresettings",
            name="activity_idle_seg",
            field=models.PositiveIntegerField(default=300),
        ),
        migrations.AddField(
            model_name="coresettings",
            name="activity_window_titles",
            field=models.BooleanField(default=True),
        ),
    ]
