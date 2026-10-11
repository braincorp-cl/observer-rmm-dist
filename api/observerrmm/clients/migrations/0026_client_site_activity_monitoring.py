# Feature 049-B2: monitoreo de actividad por cliente y sitio (tri-estado, nulo = hereda).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0025_site_latitude_site_longitude"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="activity_monitoring",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="site",
            name="activity_monitoring",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
    ]
