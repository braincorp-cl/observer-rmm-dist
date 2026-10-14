# Feature 049-B2: reentrega del monitoreo a equipos que no recibieron el push.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0070_agent_activity_monitoring"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="activity_sync_pending",
            field=models.BooleanField(default=False),
        ),
    ]
