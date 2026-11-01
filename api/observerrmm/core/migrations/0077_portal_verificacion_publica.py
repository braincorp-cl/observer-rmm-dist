"""Interruptor del portal público de verificación (feature 053 · ola 4).

Un solo booleano, apagado por omisión. Gobierna si esta instalación expone
`GET /erase/verify/<certificate_id>/`, la única ruta de consulta sin
autenticación del producto.

**Sin backfill, y es deliberado**: el `default=False` deja apagadas todas las
instalaciones ya desplegadas. Encender una ruta pública en el dominio de un
cliente es una decisión por tenant, con el cliente avisado.

🔒 No toca ninguna tabla de `erase`. El portal sólo lee.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0076_purga_adjuntos_erase"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresettings",
            name="erase_public_verify_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
