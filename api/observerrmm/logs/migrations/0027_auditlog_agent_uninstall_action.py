# Registro de auditoría de la desinstalación manual: nuevo valor en
# AuditActionType. Igual que la 0026, sólo cambia `choices`: no toca el esquema,
# pero tiene que existir para dejar limpio `makemigrations --check`.
#
# ⚠️ Va sobre la 0026 (`endpoint_response`, feature 028), que existe SÓLO en
# dist. En el hub esta misma alteración es la 0026: el número difiere entre
# repos a propósito (divergencia dist > hub, ADR-015).

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("logs", "0026_auditlog_endpoint_response_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("login", "User Login"),
                    ("failed_login", "Failed User Login"),
                    ("delete", "Delete Object"),
                    ("modify", "Modify Object"),
                    ("add", "Add Object"),
                    ("view", "View Object"),
                    ("check_run", "Check Run"),
                    ("task_run", "Task Run"),
                    ("agent_install", "Agent Install"),
                    ("remote_session", "Remote Session"),
                    ("execute_script", "Execute Script"),
                    ("execute_command", "Execute Command"),
                    ("bulk_action", "Bulk Action"),
                    ("url_action", "URL Action"),
                    ("endpoint_response", "Endpoint Response"),
                    ("agent_uninstall", "Agent Uninstall"),
                ],
                max_length=100,
            ),
        ),
    ]
