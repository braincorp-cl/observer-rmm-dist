"""Retención de adjuntos de borrado por cliente (feature 053 · ola 3, RNF-06/L-04).

Un solo campo nullable en `Client`. `null` significa "heredar el ajuste global del
servidor", no "cero días", y por eso NO hay backfill: cada cliente existente queda
correcto sin escribir una sola fila. Una migración de datos acá fijaría 366 en
todos y rompería justamente la herencia que el nulo existe para preservar.

El validador va LITERAL y no importando
`observerrmm.constants.ERASE_ATTACHMENT_RETENTION_FLOOR_DAYS`: una migración
aplicada es historia, y debe seguir significando lo mismo si mañana el piso legal
cambia en el código. Mismo criterio que `0003_wipe.py` y `0006_custodia.py` con
sus `choices`.

🔒 Esta migración NO toca `erase_erasecertificate` —ninguna columna, ningún
`RunPython`, ningún `UPDATE` sobre `data`—. Eso es lo que mantiene verificables
los certificados ya emitidos.
"""

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0026_client_site_activity_monitoring"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="erase_attachment_retention_days",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(366)],
            ),
        ),
    ]
