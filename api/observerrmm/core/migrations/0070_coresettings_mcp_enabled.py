from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0069_alter_coresettings_default_time_zone"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresettings",
            name="mcp_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
