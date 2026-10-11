# Feature 049-B2: permiso de rol para encender/apagar el monitoreo. Aditivo, off por omisión.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0047_role_can_view_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_manage_activity",
            field=models.BooleanField(default=False),
        ),
    ]
