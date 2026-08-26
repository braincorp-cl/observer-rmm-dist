from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0044_role_can_manage_asset_intake_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_retrieve_files",
            field=models.BooleanField(default=False),
        ),
    ]
