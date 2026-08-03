# Renombre del campo `sync_mesh_with_trmm` -> `sync_mesh_with_ormm`.
#
# El prefijo `trmm` venia del upstream y nombra al producto legacy; el nuestro es
# Observer RMM, asi que la columna pasa a `ormm`. Es un RenameField: preserva los
# datos y es reversible, a diferencia de add+copy+drop.
#
# Las migraciones 0043 (que creo la columna) y 0044 (que la referencia como
# dependencia) NO se tocan: son historia congelada y editarlas dejaria el estado
# declarado fuera de sincronia con las bases ya migradas.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0059_coresettings_open_ai_temperature"),
    ]

    operations = [
        migrations.RenameField(
            model_name="coresettings",
            old_name="sync_mesh_with_trmm",
            new_name="sync_mesh_with_ormm",
        ),
    ]
