# Feature 049-B: retención del monitoreo de actividad. AddField aditivo (default 90).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0070_coresettings_mcp_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresettings",
            name="activity_prune_days",
            field=models.PositiveIntegerField(default=90),
        ),
    ]
