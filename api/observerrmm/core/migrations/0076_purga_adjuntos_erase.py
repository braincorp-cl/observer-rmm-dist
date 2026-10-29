"""Interruptor de la purga de adjuntos de borrado (feature 053 · ola 3).

Un solo booleano, apagado por omisión. NO gobierna si la tarea corre —eso lo
hace `core_maintenance_tasks` y es incondicional—, sino si **borra** o sólo
cuenta lo que borraría.

🔒 No toca ninguna tabla de `erase`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0075_activity_049e"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresettings",
            name="erase_attachment_prune_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
