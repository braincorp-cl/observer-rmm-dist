# Feature 041 keep-awake-geocerca (T034): toggle global de la asociación a redes
# WiFi abiertas (RF-05). AddField aditivo; default False (OFF por omisión: conducta
# sensible que no puede quedar viva por desplegar el agente; se enciende sólo tras
# cerrar política de uso aceptable + visto legal, T022). Encadena sobre 0066 para
# no dejar dos hojas de migración en core.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0066_coresettings_keep_awake_baseline_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='coresettings',
            name='open_wifi_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
