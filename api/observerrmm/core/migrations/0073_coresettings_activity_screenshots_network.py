# Feature 049-C: capturas periódicas (0 = apagadas) y red por aplicación (apagada).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0072_coresettings_activity_monitoring"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresettings",
            name="activity_screenshots_min",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="coresettings",
            name="activity_network",
            field=models.BooleanField(default=False),
        ),
    ]
