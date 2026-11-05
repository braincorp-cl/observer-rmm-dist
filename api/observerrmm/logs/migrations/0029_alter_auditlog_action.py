# Feature 052: `AuditActionType` gana DELEGATION_DENIED.
#
# No cambia el esquema físico —`choices` no se materializa en Postgres— pero
# Django igual registra el AlterField para que el estado de las migraciones
# coincida con el modelo. Sin esta migración, `makemigrations --check` falla en
# CI aunque la base esté perfecta.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logs', '0028_alter_auditlog_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('login', 'User Login'), ('failed_login', 'Failed User Login'), ('delete', 'Delete Object'), ('modify', 'Modify Object'), ('add', 'Add Object'), ('view', 'View Object'), ('check_run', 'Check Run'), ('task_run', 'Task Run'), ('agent_install', 'Agent Install'), ('remote_session', 'Remote Session'), ('execute_script', 'Execute Script'), ('execute_command', 'Execute Command'), ('bulk_action', 'Bulk Action'), ('url_action', 'URL Action'), ('endpoint_response', 'Endpoint Response'), ('lost_mode', 'Lost Mode'), ('agent_uninstall', 'Agent Uninstall'), ('delegation_denied', 'Delegation Denied')], max_length=100),
        ),
    ]
