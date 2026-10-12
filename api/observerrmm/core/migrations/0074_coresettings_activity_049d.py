# Feature 049-D: patrones "siempre activo" (reuniones) y jornada esperada.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0073_coresettings_activity_screenshots_network"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresettings",
            name="activity_always_active_patterns",
            field=models.TextField(
                blank=True, default="teams\nzoom\nwebex\n\\bmeet\\b"
            ),
        ),
        migrations.AddField(
            model_name="coresettings",
            name="activity_expected_min",
            field=models.PositiveIntegerField(default=480),
        ),
    ]
