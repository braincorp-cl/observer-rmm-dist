# Feature 028 · nuevo valor en AuditActionType: `endpoint_response`.
#
# Sólo cambia la lista de `choices` del campo, no su tipo ni su contenido: a nivel
# de base de datos es un no-op. Existe porque Django compara el estado del modelo
# con el de las migraciones, y sin esta el gate `makemigrations --check` quedaría
# rojo en cada despliegue.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logs", "0025_alter_auditlog_id_alter_debuglog_id_and_more"),
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
                ],
                max_length=100,
            ),
        ),
    ]
