from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0040_role_can_use_registry"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="language",
            field=models.CharField(
                blank=True,
                choices=[("en", "English"), ("es", "Español")],
                default="",
                max_length=5,
            ),
        ),
    ]
