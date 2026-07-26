# Feature 026 (geocerca por sitio): ubicación física declarada del sitio.
# Migración ADITIVA. Ambas columnas son NULLABLE a propósito: crear un Site NO exige
# coordenadas, se editan después. Con null no hay fallback de posición ni geocerca —
# el comportamiento previo queda intacto para todo sitio existente.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0024_alter_deployment_goarch"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="latitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="site",
            name="longitude",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
