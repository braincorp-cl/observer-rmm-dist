# Feature 049-B: permiso de rol para ver el monitoreo de actividad. Aditivo, off por omisión.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0046_role_can_use_mcp"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_view_activity",
            field=models.BooleanField(default=False),
        ),
    ]
