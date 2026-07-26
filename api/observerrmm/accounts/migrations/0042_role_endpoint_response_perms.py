# Feature 028 · respuesta rápida de endpoint (lock / alert / alarm).
#
# Tres permisos separados. El default es False en los tres: encender una capacidad
# nueva para todos los roles existentes de golpe sería un cambio de postura de
# seguridad silencioso, y bloquear equipos ajenos no es algo que deba habilitarse
# por omisión al desplegar.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0041_user_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_send_alerts",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="role",
            name="can_lock_agents",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="role",
            name="can_sound_alarm",
            field=models.BooleanField(default=False),
        ),
    ]
