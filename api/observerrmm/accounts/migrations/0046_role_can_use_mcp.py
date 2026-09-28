from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0045_role_can_retrieve_files"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_use_mcp",
            field=models.BooleanField(default=True),
        ),
    ]
