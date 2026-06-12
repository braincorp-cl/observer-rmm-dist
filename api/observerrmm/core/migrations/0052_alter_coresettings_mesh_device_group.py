# Alinea el estado de migraciones con el rebrand F006:
# default 'TacticalRMM' -> 'ObserverRMM' en CoreSettings.mesh_device_group
# (core/models.py:82). El modelo cambió en F006 sin migración acompañante;
# detectado por el gate smoke de F008 (makemigrations --check).
# AlterField de solo-default no produce SQL: Django no persiste defaults en BD.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_alter_coresettings_default_time_zone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coresettings',
            name='mesh_device_group',
            field=models.CharField(blank=True, default='ObserverRMM', max_length=255, null=True),
        ),
    ]
