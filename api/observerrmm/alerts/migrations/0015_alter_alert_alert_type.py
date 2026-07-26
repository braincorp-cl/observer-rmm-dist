# Feature 026 (geocerca por sitio): nuevo valor "geofence" en AlertType.
# Solo cambian los `choices` — es metadata de Django, no altera el tipo de la columna
# ni los datos existentes.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0014_alerttemplate_action_rest_alerttemplate_action_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alert",
            name="alert_type",
            field=models.CharField(
                choices=[
                    ("availability", "Availability"),
                    ("check", "Check"),
                    ("task", "Task"),
                    ("custom", "Custom"),
                    ("geofence", "Geofence"),
                ],
                default="availability",
                max_length=20,
            ),
        ),
    ]
