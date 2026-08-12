# Feature 030 · Fase 1: el motivo por el que un ciclo no trajo imagen.
#
# Campo nuevo y anulable: no toca ninguna fila existente (la tabla nace vacía en
# la 0064, que es de esta misma versión) y por lo tanto no necesita default en
# la base. Mismo patrón que el resto de los agregados de campo del proyecto.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0064_lostmodestate_lostmodeevidence"),
    ]

    operations = [
        migrations.AddField(
            model_name="lostmodeevidence",
            name="note",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
