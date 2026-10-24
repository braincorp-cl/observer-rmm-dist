# Feature 052: lista de perfiles que puede otorgar quien porta un rol.
#
# Aditiva y vacía: crea solo la tabla intermedia, no toca ninguna columna de
# accounts_role ni ninguna fila existente. Una tabla vacía ya significa lo
# correcto —ningún rol otorga ningún otro—, que es el comportamiento de la
# plataforma hoy, así que no hace falta migración de datos (RN-08).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0048_role_can_manage_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="assignable_roles",
            field=models.ManyToManyField(
                blank=True, related_name="assignable_by", to="accounts.role"
            ),
        ),
    ]
