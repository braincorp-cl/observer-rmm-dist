# RT-AUT-09: marca de secreto por clave del almacen global.
#
# Todas las claves existentes nacen secretas (lo seguro por omision), salvo
# `actividad_categorias`, que es configuracion del monitoreo de actividad y se
# edita mirandola: ocultarla obligaria a reescribir el JSON a ciegas.
from django.db import migrations, models

CONFIGURACION_VISIBLE = ("actividad_categorias",)


def marcar_configuracion_visible(apps, schema_editor):
    GlobalKVStore = apps.get_model("core", "GlobalKVStore")
    GlobalKVStore.objects.filter(name__in=CONFIGURACION_VISIBLE).update(
        is_secret=False
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0077_portal_verificacion_publica"),
    ]

    operations = [
        migrations.AddField(
            model_name="globalkvstore",
            name="is_secret",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(marcar_configuracion_visible, migrations.RunPython.noop),
    ]
