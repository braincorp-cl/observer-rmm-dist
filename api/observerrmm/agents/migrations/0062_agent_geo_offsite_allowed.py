# Feature 026 (geocerca por sitio): marca de equipo autorizado a salir del sitio.
# Migración ADITIVA. Por defecto False — el caso mayoritario de un RMM corporativo es
# el equipo fijo; los móviles se marcan uno por uno desde la consola.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0061_alter_agent_time_zone"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="geo_offsite_allowed",
            field=models.BooleanField(default=False),
        ),
    ]
