# Feature 030 · agrega AuditActionType.LOST_MODE al catálogo de acciones.
#
# Es un AlterField de sólo `choices`: Django no toca la columna en PostgreSQL
# (las choices se validan en Python, no con un CHECK), así que la migración es
# instantánea y no bloquea la tabla de auditoría por grande que sea.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logs', '0027_auditlog_agent_uninstall_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('login', 'User Login'), ('failed_login', 'Failed User Login'), ('delete', 'Delete Object'), ('modify', 'Modify Object'), ('add', 'Add Object'), ('view', 'View Object'), ('check_run', 'Check Run'), ('task_run', 'Task Run'), ('agent_install', 'Agent Install'), ('remote_session', 'Remote Session'), ('execute_script', 'Execute Script'), ('execute_command', 'Execute Command'), ('bulk_action', 'Bulk Action'), ('url_action', 'URL Action'), ('endpoint_response', 'Endpoint Response'), ('lost_mode', 'Lost Mode'), ('agent_uninstall', 'Agent Uninstall')], max_length=100),
        ),
    ]
