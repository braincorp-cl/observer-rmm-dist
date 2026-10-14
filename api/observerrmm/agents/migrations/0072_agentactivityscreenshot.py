# Feature 049-C: capturas de pantalla del monitoreo de actividad (cifradas en disco).

import django.db.models.deletion
from django.db import migrations, models

import agents.activity_storage
import agents.models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0071_agent_activity_sync_pending"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentActivityScreenshot",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("captured_at", models.DateTimeField()),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("username", models.CharField(blank=True, default="", max_length=255)),
                ("process", models.CharField(blank=True, default="", max_length=255)),
                ("title", models.CharField(blank=True, default="", max_length=512)),
                (
                    "image",
                    models.FileField(
                        storage=agents.activity_storage.get_activity_screenshots_fs,
                        upload_to=agents.models.activity_screenshot_path,
                    ),
                ),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_screenshots",
                        to="agents.agent",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["agent", "captured_at"],
                        name="agents_agen_agent_i_143550_idx",
                    )
                ],
            },
        ),
    ]
