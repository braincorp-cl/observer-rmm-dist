import zoneinfo
from enum import Enum

from django.conf import settings
from django.db import models


class MeshAgentIdent(Enum):
    WIN32 = 3
    WIN64 = 4
    LINUX32 = 5
    LINUX64 = 6
    LINUX_ARM_64 = 26
    LINUX_ARM_HF = 25
    DARWIN_UNIVERSAL = 10005

    def __str__(self):
        return str(self.value)


CORESETTINGS_CACHE_KEY = "core_settings"
ROLE_CACHE_PREFIX = "role_"
AGENT_TBL_PEND_ACTION_CNT_CACHE_PREFIX = "agent_tbl_pendingactions_"
AGENT_CHECKS_CACHE_PREFIX = "agent_checks_data_"
# Marca puesta por la consola JUSTO ANTES de borrar un agente. El script de
# desinstalación que la propia consola dispara avisa al servidor (endpoint
# /api/v3/uninstalled/), y sin esta marca ese aviso se leería como una
# desinstalación manual y levantaría una alerta falsa. TTL corto: sólo cubre la
# carrera entre el borrado y el aviso, que llega en segundos.
AGENT_CONSOLE_UNINSTALL_CACHE_PREFIX = "agent_console_uninstall_"
AGENT_CONSOLE_UNINSTALL_CACHE_TIMEOUT = 60 * 15
# Deduplicación del aviso de desinstalación manual: el script puede reintentar,
# y una alerta por episodio es suficiente.
AGENT_MANUAL_UNINSTALL_CACHE_PREFIX = "agent_manual_uninstall_"
AGENT_MANUAL_UNINSTALL_CACHE_TIMEOUT = 60 * 60

AGENT_STATUS_ONLINE = "online"
AGENT_STATUS_OFFLINE = "offline"
AGENT_STATUS_OVERDUE = "overdue"

REDIS_LOCK_EXPIRE = 60 * 60 * 2  # Lock expires in 2 hours
RESOLVE_ALERTS_LOCK = "resolve-alerts-lock-key"
SYNC_SCHED_TASK_LOCK = "sync-sched-tasks-lock-key"
AGENT_OUTAGES_LOCK = "agent-outages-task-lock-key"
ORPHANED_WIN_TASK_LOCK = "orphaned-win-task-lock-key"
SYNC_MESH_PERMS_TASK_LOCK = "sync-mesh-perms-lock-key"
CACHE_DB_FIELDS_TASK_LOCK = "cache-db-fields-task-lock-key"

ORMM_WS_MAX_SIZE = getattr(settings, "ORMM_WS_MAX_SIZE", 100 * 2**20)
ORMM_MAX_REQUEST_SIZE = getattr(settings, "ORMM_MAX_REQUEST_SIZE", 10 * 2**20)

# Piso de largo de un mesh node id ya normalizado a hex. Los reales son SHA-384,
# o sea 96 caracteres; el piso se deja en 64 para que coincida EXACTAMENTE con lo
# que ya exigen el agente (`esNodeIDValido`) y los instaladores
# (`ValidateMeshNodeID`, `^[0-9A-Fa-f]{64,}$`) — tres validaciones con el mismo
# criterio es una regla; tres con criterios distintos es por dónde se cuela el
# caso real. Existe porque el alfabeto no basta: el valor que dejó a un equipo
# sin «Tomar control» era hexadecimal legítimo (una MAC de 12 dígitos), y `"QQ"`
# es base64 válido que decodifica a un hex de 2.
MESH_NODE_ID_MIN_HEX = 64


class GoArch(models.TextChoices):
    AMD64 = "amd64", "amd64"
    i386 = "386", "386"
    ARM64 = "arm64", "arm64"
    ARM32 = "arm", "arm"


class CustomFieldModel(models.TextChoices):
    CLIENT = "client", "Client"
    SITE = "site", "Site"
    AGENT = "agent", "Agent"


class CustomFieldType(models.TextChoices):
    TEXT = "text", "Text"
    NUMBER = "number", "Number"
    SINGLE = "single", "Single"
    MULTIPLE = "multiple", "Multiple"
    CHECKBOX = "checkbox", "Checkbox"
    DATETIME = "datetime", "DateTime"


class TaskSyncStatus(models.TextChoices):
    SYNCED = "synced", "Synced With Agent"
    NOT_SYNCED = "notsynced", "Waiting On Agent Checkin"
    PENDING_DELETION = "pendingdeletion", "Pending Deletion on Agent"
    INITIAL = "initial", "Initial Task Sync"


class TaskStatus(models.TextChoices):
    PASSING = "passing", "Passing"
    FAILING = "failing", "Failing"
    PENDING = "pending", "Pending"


class TaskRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"


class TaskType(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    MONTHLY_DOW = "monthlydow", "Monthly Day of Week"
    CHECK_FAILURE = "checkfailure", "On Check Failure"
    MANUAL = "manual", "Manual"
    RUN_ONCE = "runonce", "Run Once"
    ONBOARDING = "onboarding", "Onboarding"
    SCHEDULED = "scheduled", "Scheduled"  # deprecated


class AlertSeverity(models.TextChoices):
    INFO = "info", "Informational"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"


class AlertType(models.TextChoices):
    AVAILABILITY = "availability", "Availability"
    CHECK = "check", "Check"
    TASK = "task", "Task"
    CUSTOM = "custom", "Custom"
    # Feature 026: el equipo se midió fuera del radio de su sitio.
    GEOFENCE = "geofence", "Geofence"
    # Desinstalación local del agente, avisada por el propio equipo antes de
    # destruirse. Nace y vive SIN agente asociado (agent=None) a propósito: el
    # agente se borra a continuación y Alert.agent es CASCADE, así que una
    # alerta ligada moriría junto con lo que está denunciando.
    AGENT_UNINSTALL = "agent_uninstall", "Agent Uninstall"


class AlertTemplateActionType(models.TextChoices):
    SCRIPT = "script", "Script"
    SERVER = "server", "Server"
    REST = "rest", "Rest"


class AgentHistoryType(models.TextChoices):
    TASK_RUN = "task_run", "Task Run"
    SCRIPT_RUN = "script_run", "Script Run"
    CMD_RUN = "cmd_run", "CMD Run"


class AgentMonType(models.TextChoices):
    SERVER = "server", "Server"
    WORKSTATION = "workstation", "Workstation"


class AgentPlat(models.TextChoices):
    WINDOWS = "windows", "Windows"
    LINUX = "linux", "Linux"
    DARWIN = "darwin", "macOS"


class ClientTreeSort(models.TextChoices):
    ALPHA_FAIL = "alphafail", "Move failing clients to the top"
    ALPHA = "alpha", "Sort alphabetically"


class AgentTableTabs(models.TextChoices):
    SERVER = "server", "Servers"
    WORKSTATION = "workstation", "Workstations"
    MIXED = "mixed", "Mixed"


class AgentDblClick(models.TextChoices):
    EDIT_AGENT = "editagent", "Edit Agent"
    TAKE_CONTROL = "takecontrol", "Take Control"
    REMOTE_BG = "remotebg", "Remote Background"
    URL_ACTION = "urlaction", "URL Action"


class ScriptShell(models.TextChoices):
    POWERSHELL = "powershell", "Powershell"
    CMD = "cmd", "Batch (CMD)"
    PYTHON = "python", "Python"
    SHELL = "shell", "Shell"
    NUSHELL = "nushell", "Nushell"
    DENO = "deno", "Deno"


class ScriptType(models.TextChoices):
    USER_DEFINED = "userdefined", "User Defined"
    BUILT_IN = "builtin", "Built In"


class EvtLogNames(models.TextChoices):
    APPLICATION = "Application", "Application"
    SYSTEM = "System", "System"
    SECURITY = "Security", "Security"


class EvtLogTypes(models.TextChoices):
    INFO = "INFO", "Information"
    WARNING = "WARNING", "Warning"
    ERROR = "ERROR", "Error"
    AUDIT_SUCCESS = "AUDIT_SUCCESS", "Success Audit"
    AUDIT_FAILURE = "AUDIT_FAILURE", "Failure Audit"


class EvtLogFailWhen(models.TextChoices):
    CONTAINS = "contains", "Log contains"
    NOT_CONTAINS = "not_contains", "Log does not contain"


class CheckStatus(models.TextChoices):
    PASSING = "passing", "Passing"
    FAILING = "failing", "Failing"
    PENDING = "pending", "Pending"


class PAStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"


class PAAction(models.TextChoices):
    SCHED_REBOOT = "schedreboot", "Scheduled Reboot"
    AGENT_UPDATE = "agentupdate", "Agent Update"
    CHOCO_INSTALL = "chocoinstall", "Chocolatey Software Install"
    RUN_CMD = "runcmd", "Run Command"
    RUN_SCRIPT = "runscript", "Run Script"
    RUN_PATCH_SCAN = "runpatchscan", "Run Patch Scan"
    RUN_PATCH_INSTALL = "runpatchinstall", "Run Patch Install"


class CheckType(models.TextChoices):
    DISK_SPACE = "diskspace", "Disk Space Check"
    PING = "ping", "Ping Check"
    CPU_LOAD = "cpuload", "CPU Load Check"
    MEMORY = "memory", "Memory Check"
    WINSVC = "winsvc", "Service Check"
    SCRIPT = "script", "Script Check"
    EVENT_LOG = "eventlog", "Event Log Check"


class AuditActionType(models.TextChoices):
    LOGIN = "login", "User Login"
    FAILED_LOGIN = "failed_login", "Failed User Login"
    DELETE = "delete", "Delete Object"
    MODIFY = "modify", "Modify Object"
    ADD = "add", "Add Object"
    VIEW = "view", "View Object"
    CHECK_RUN = "check_run", "Check Run"
    TASK_RUN = "task_run", "Task Run"
    AGENT_INSTALL = "agent_install", "Agent Install"
    REMOTE_SESSION = "remote_session", "Remote Session"
    EXEC_SCRIPT = "execute_script", "Execute Script"
    EXEC_COMMAND = "execute_command", "Execute Command"
    BULK_ACTION = "bulk_action", "Bulk Action"
    URL_ACTION = "url_action", "URL Action"
    # Feature 028: categoría propia para lock / alert / alarm en vez de reusar
    # EXEC_COMMAND. Estas acciones son visibles para el usuario del equipo —lo
    # interrumpen, le hablan o hacen ruido— así que tienen que poder filtrarse en
    # el registro de auditoría por sí solas, sin quedar mezcladas con la ejecución
    # de comandos.
    ENDPOINT_RESPONSE = "endpoint_response", "Endpoint Response"
    AGENT_UNINSTALL = "agent_uninstall", "Agent Uninstall"


class AuditObjType(models.TextChoices):
    USER = "user", "User"
    SCRIPT = "script", "Script"
    AGENT = "agent", "Agent"
    POLICY = "policy", "Policy"
    WINUPDATE = "winupdatepolicy", "Patch Policy"
    CLIENT = "client", "Client"
    SITE = "site", "Site"
    CHECK = "check", "Check"
    AUTOTASK = "automatedtask", "Automated Task"
    CORE = "coresettings", "Core Settings"
    BULK = "bulk", "Bulk"
    ALERT_TEMPLATE = "alerttemplate", "Alert Template"
    ROLE = "role", "Role"
    URL_ACTION = "urlaction", "URL Action"
    KEYSTORE = "keystore", "Global Key Store"
    CUSTOM_FIELD = "customfield", "Custom Field"


class DebugLogLevel(models.TextChoices):
    INFO = "info", "Info"
    WARN = "warning", "Warning"
    ERROR = "error", "Error"
    CRITICAL = "critical", "Critical"


class DebugLogType(models.TextChoices):
    AGENT_UPDATE = "agent_update", "Agent Update"
    AGENT_ISSUES = "agent_issues", "Agent Issues"
    WIN_UPDATES = "win_updates", "Windows Updates"
    SYSTEM_ISSUES = "system_issues", "System Issues"
    SCRIPTING = "scripting", "Scripting"


class URLActionType(models.TextChoices):
    WEB = "web", "Web"
    REST = "rest", "Rest"


# Feature 023 (geolocalización): las filas de ubicación se guardan en CheckHistory
# reutilizando la infraestructura de retención (prune_check_history, agnóstico al
# check_id). check_id es un PositiveIntegerField (NO una FK), así que usamos un valor
# centinela reservado, muy por encima de cualquier PK real de checks_check, para
# distinguir los puntos geo del historial de checks normales. El consumidor natsapi
# escribe este MISMO literal en su INSERT por SQL raw — mantener ambos en sincronía.
GEO_CHECK_HISTORY_ID = 2000000000

# Orígenes posibles de un punto de ubicación, del más al menos preciso. "native" y
# "wifi" son MEDIDOS por el endpoint (decenas de metros) y son los únicos que la
# geocerca evalúa. "site" es DECLARADO: son las coordenadas del Site heredadas por un
# equipo estacionario que no logró medir (feature 026) — no se evalúa porque
# compararlo contra el sitio del que salió sería tautológico. "ip" es aproximado con
# error de cientos de km y tampoco se evalúa.
GEO_SOURCE_NATIVE = "native"
GEO_SOURCE_WIFI = "wifi"
GEO_SOURCE_SITE = "site"
GEO_SOURCE_IP = "ip"
# Los únicos orígenes con precisión suficiente para decidir si un equipo salió de su
# geocerca. natsapi escribe estos MISMOS literales — mantener en sincronía.
GEO_MEASURED_SOURCES = (GEO_SOURCE_NATIVE, GEO_SOURCE_WIFI)


# Feature 028 · respuesta rápida de endpoint (lock / alert / alarm).
#
# Estos límites están DUPLICADOS a propósito en el agente (`agent/response.go`):
# el servidor valida para dar un error claro antes de gastar un viaje por NATS, y
# el agente valida porque no puede confiar en que el mensaje venga de este
# servidor. Si se cambian acá, cambiarlos allá.
ALERT_MAX_TITLE_LEN = 120
ALERT_MAX_MESSAGE_LEN = 2000

# Duración de la alarma. El tope existe porque la alarma sirve para encontrar un
# equipo, no para castigar a quien lo tenga: sin límite, un comando mal enviado
# deja una máquina sonando y la única salida es apagarla.
#
# Feature 028 Fase 2: el tope SE CONSERVA como el camino normal. La "alarma
# eterna" no lo afloja ni lo reemplaza — es una bandera aparte (`forever`) que lo
# saltea, apagada por omisión y con confirmación explícita en la consola. Así el
# camino de todos los días sigue acotado y la excepción antirrobo se ve en el
# payload, en la auditoría y en lo que el operador tuvo que confirmar.
ALARM_MIN_SECONDS = 5
ALARM_DEFAULT_SECONDS = 30
ALARM_MAX_SECONDS = 300

# Códigos que puede devolver el agente. NO son texto para mostrar: son claves que
# la consola traduce (`endpointResponse.codes.*` en es.json/en.json). El agente
# nunca manda una frase, justamente para que el operador la vea en su idioma.
#
# El prefijo evita colisiones: el interceptor de axios en la consola muestra el
# cuerpo del error 400 tal cual, y sin marcar estos códigos de forma inequívoca
# tendría que adivinar si un "error" cualquiera es uno de los nuestros.
ENDPOINT_RESPONSE_PREFIX = "endpoint_response:"
ENDPOINT_RESPONSE_CODES = (
    "ok",
    "no_user_session",
    "no_dialog_tool",
    "no_audio_player",
    "lock_unavailable",
    "empty_message",
    "error",
    # Este último NO lo produce el agente: lo agrega el servidor cuando no pudo
    # hablar con él. Se mezcla acá porque para la consola es un código más de la
    # misma familia y se traduce por el mismo camino.
    "agent_unreachable",
)

# Respuestas de nats_cmd que significan "no se pudo hablar con el agente", y no
# "el agente contestó que falló". La diferencia le importa al operador: una es un
# problema de conectividad y la otra es una condición del equipo.
NATS_UNREACHABLE = ("timeout", "natsdown")


class EndpointResponseAction(models.TextChoices):
    LOCK = "lock", "Lock Screen"
    ALERT = "alert", "On-screen Message"
    ALARM = "alarm", "Sound Alarm"
    STOP_ALARM = "stopalarm", "Stop Alarm"


class URLActionRestMethod(models.TextChoices):
    GET = "get", "Get"
    POST = "post", "Post"
    PUT = "put", "Put"
    DELETE = "delete", "Delete"
    PATCH = "patch", "Patch"


class ScheduleType(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"


class MonthlyType(models.TextChoices):
    WEEKS = "weeks", "Weeks"
    DAYS = "days", "Days"


# Agent db fields that are not needed for most queries, speeds up query
AGENT_DEFER = (
    "wmi_detail",
    "services",
    "created_by",
    "created_time",
    "modified_by",
    "modified_time",
)

AGENT_TABLE_DEFER = (
    "services",
    "created_by",
    "created_time",
    "modified_by",
    "modified_time",
)

ONLINE_AGENTS = (
    "pk",
    "agent_id",
    "last_seen",
    "overdue_time",
    "offline_time",
    "version",
    "plat",
)

FIELDS_TRIGGER_TASK_UPDATE_AGENT = [
    "run_time_bit_weekdays",
    "run_time_date",
    "expire_date",
    "daily_interval",
    "weekly_interval",
    "enabled",
    "remove_if_not_scheduled",
    "run_asap_after_missed",
    "monthly_days_of_month",
    "monthly_months_of_year",
    "monthly_weeks_of_month",
    "task_repetition_duration",
    "task_repetition_interval",
    "stop_task_at_duration_end",
    "random_task_delay",
    "run_asap_after_missed",
    "task_instance_policy",
]

POLICY_TASK_FIELDS_TO_COPY = [
    "alert_severity",
    "email_alert",
    "text_alert",
    "dashboard_alert",
    "name",
    "actions",
    "run_time_bit_weekdays",
    "run_time_date",
    "expire_date",
    "daily_interval",
    "weekly_interval",
    "task_type",
    "enabled",
    "remove_if_not_scheduled",
    "run_asap_after_missed",
    "custom_field",
    "collector_all_output",
    "monthly_days_of_month",
    "monthly_months_of_year",
    "monthly_weeks_of_month",
    "task_repetition_duration",
    "task_repetition_interval",
    "stop_task_at_duration_end",
    "random_task_delay",
    "run_asap_after_missed",
    "task_instance_policy",
    "continue_on_error",
    "task_supported_platforms",
]

CHECKS_NON_EDITABLE_FIELDS = [
    "check_type",
    "overridden_by_policy",
    "created_by",
    "created_time",
    "modified_by",
    "modified_time",
]

POLICY_CHECK_FIELDS_TO_COPY = [
    "check_type",
    "warning_threshold",
    "error_threshold",
    "alert_severity",
    "name",
    "run_interval",
    "disk",
    "fails_b4_alert",
    "ip",
    "script",
    "script_args",
    "success_return_codes",
    "info_return_codes",
    "warning_return_codes",
    "timeout",
    "svc_name",
    "svc_display_name",
    "svc_policy_mode",
    "pass_if_start_pending",
    "pass_if_svc_not_exist",
    "restart_if_stopped",
    "log_name",
    "event_id",
    "event_id_is_wildcard",
    "event_type",
    "event_source",
    "event_message",
    "fail_when",
    "search_last_days",
    "number_of_events_b4_alert",
    "email_alert",
    "text_alert",
    "dashboard_alert",
]


WEEK_DAYS = {
    "Sunday": 0x1,
    "Monday": 0x2,
    "Tuesday": 0x4,
    "Wednesday": 0x8,
    "Thursday": 0x10,
    "Friday": 0x20,
    "Saturday": 0x40,
}

MONTHS = {
    "January": 0x1,
    "February": 0x2,
    "March": 0x4,
    "April": 0x8,
    "May": 0x10,
    "June": 0x20,
    "July": 0x40,
    "August": 0x80,
    "September": 0x100,
    "October": 0x200,
    "November": 0x400,
    "December": 0x800,
}

WEEKS = {
    "First Week": 0x1,
    "Second Week": 0x2,
    "Third Week": 0x4,
    "Fourth Week": 0x8,
    "Last Week": 0x10,
}

WEEKDAY_TO_BIT = {
    0: 0x2,  # monday
    1: 0x4,
    2: 0x8,
    3: 0x10,
    4: 0x20,
    5: 0x40,
    6: 0x1,  # sunday
}

MONTH_DAYS = {f"{b}": 0x1 << a for a, b in enumerate(range(1, 32))}
MONTH_DAYS["Last Day"] = 0x80000000

DEMO_NOT_ALLOWED = [
    {"name": "AgentProcesses", "methods": ["DELETE"]},
    {"name": "AgentMeshCentral", "methods": ["GET", "POST"]},
    {"name": "update_agents", "methods": ["POST"]},
    {"name": "send_raw_cmd", "methods": ["POST"]},
    {"name": "install_agent", "methods": ["POST"]},
    {"name": "GenerateAgent", "methods": ["GET"]},
    {"name": "email_test", "methods": ["POST"]},
    {"name": "server_maintenance", "methods": ["POST"]},
    {"name": "CodeSign", "methods": ["PATCH", "POST"]},
    {"name": "TwilioSMSTest", "methods": ["POST"]},
    {"name": "GetEditActionService", "methods": ["PUT", "POST"]},
    {"name": "TestScript", "methods": ["POST"]},
    {"name": "GetUpdateDeleteAgent", "methods": ["DELETE"]},
    {"name": "Reboot", "methods": ["POST", "PATCH"]},
    {"name": "recover", "methods": ["POST"]},
    {"name": "run_script", "methods": ["POST"]},
    {"name": "bulk", "methods": ["POST"]},
    {"name": "WMI", "methods": ["POST"]},
    {"name": "PolicyAutoTask", "methods": ["POST"]},
    {"name": "RunAutoTask", "methods": ["POST"]},
    {"name": "run_checks", "methods": ["POST"]},
    {"name": "GetSoftware", "methods": ["POST", "PUT"]},
    {"name": "ScanWindowsUpdates", "methods": ["POST"]},
    {"name": "InstallWindowsUpdates", "methods": ["POST"]},
    {"name": "PendingActions", "methods": ["DELETE"]},
    {"name": "clear_cache", "methods": ["GET"]},
    {"name": "ResetPass", "methods": ["PUT"]},
    {"name": "Reset2FA", "methods": ["PUT"]},
    {"name": "bulk_run_checks", "methods": ["GET"]},
    {"name": "OpenAICodeCompletion", "methods": ["POST"]},
    {"name": "wol", "methods": ["POST"]},
    {"name": "Shutdown", "methods": ["POST"]},
    {"name": "RunTestURLAction", "methods": ["POST"]},
    {"name": "TestRunServerScript", "methods": ["POST"]},
    {"name": "DeleteActiveLoginSession", "methods": ["DELETE"]},
    {"name": "GetDeleteActiveLoginSessionsPerUser", "methods": ["DELETE"]},
    {"name": "GetAddSSOProvider", "methods": ["POST"]},
    {"name": "GetUpdateDeleteSSOProvider", "methods": ["PUT", "DELETE"]},
    {"name": "DisconnectSSOAccount", "methods": ["DELETE"]},
    {"name": "GetAccessToken", "methods": ["POST"]},
    {"name": "GetUpdateSSOSettings", "methods": ["POST"]},
    {"name": "ping", "methods": ["GET"]},
    {"name": "GetAddAPIKeys", "methods": ["POST"]},
    {"name": "GetUpdateDeleteAPIKey", "methods": ["PUT", "DELETE"]},
    {"name": "WebVNC", "methods": ["GET"]},
    {"name": "UninstallSoftware", "methods": ["POST"]},
    {"name": "browse_registry", "methods": ["GET"]},
    {"name": "create_registry_key", "methods": ["POST"]},
    {"name": "delete_registry_key", "methods": ["DELETE"]},
    {"name": "rename_registry_key", "methods": ["POST"]},
    {"name": "create_registry_value", "methods": ["POST"]},
    {"name": "delete_registry_value", "methods": ["DELETE"]},
    {"name": "rename_registry_value", "methods": ["POST"]},
    {"name": "modify_registry_value", "methods": ["POST"]},
]

CONFIG_MGMT_CMDS = (
    "api",
    "version",
    "webversion",
    "meshver",
    "natsver",
    "frontend",
    "webdomain",
    "djangoadmin",
    "setuptoolsver",
    "wheelver",
    "dbname",
    "dbuser",
    "dbhost",
    "dbpw",
    "dbport",
    "meshsite",
    "meshuser",
    "meshtoken",
    "meshdomain",
    "certfile",
    "keyfile",
)

ALL_TIMEZONES = sorted(zoneinfo.available_timezones())
