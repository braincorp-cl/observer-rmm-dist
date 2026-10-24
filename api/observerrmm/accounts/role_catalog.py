"""Catálogo de perfiles estándar de Observer RMM.

Fuente única de verdad de los roles que la plataforma trae definidos de fábrica.
Lo consume el comando `seed_default_roles` (que corre en cada `deploy-api`) y la
documentación pública de `docs.observer.cl/administracion/roles/`.

Por qué existe
--------------
El motor RBAC es granular (≈80 permisos independientes), y eso es una virtud: el
alcance de cada usuario se puede recortar al milímetro. El costo es que una
instalación nueva arranca sin ningún perfil, y cada cliente termina inventando su
propia taxonomía —con nombres distintos para lo mismo y, lo que importa más,
repartiendo permisos sensibles sin querer. El catálogo entrega una taxonomía
formal y común a todos los tenants, de la que el cliente parte en vez de empezar
en blanco.

Invariantes de diseño
---------------------
1. **Mínimo privilegio.** Cada perfil lista explícitamente lo que puede hacer; lo
   no listado queda apagado. No hay herencia implícita entre perfiles.
2. **Separación de deberes en custodia.** Los permisos de respuesta ante pérdida,
   borrado remoto, recuperación de archivos, evidencia y actividad laboral NO se
   heredan hacia arriba: ni siquiera `Administrador de Plataforma` los trae. Viven
   solo en los perfiles de la familia "Custodia y respuesta", que se asignan de
   forma deliberada y acotada (ADR-025 / ADR-029, features 042/043/049).
3. **El bypass total es del superusuario.** Todos los perfiles se crean con
   `is_superuser = False`, incluido `Administrador de Plataforma`.
4. **El catálogo propone, el cliente dispone.** El seeder crea el perfil si falta
   y jamás pisa uno existente salvo que se le pase `--force`.

Formato de cada entrada
-----------------------
``name``     nombre formal del rol, tal como aparece en la consola.
``family``   agrupación del catálogo (gobierno / operación / especialista / custodia).
``summary``  para qué sirve, en una línea (ES / EN) — es el texto que publica la doc.
``perms``    permisos en True. Todo lo que no esté acá queda en False.
``sensitive`` marca los perfiles que otorgan capacidades de alto impacto y que
             conviene revisar en cada auditoría de accesos.
``assignable`` nombres de los perfiles que quien porta este rol puede otorgar a
             otras personas (feature 052). Ausente o vacío = ninguno.

             Solo RESTRINGE: el invariante de no-elevación bloquea igual cualquier
             perfil con permisos que el rol no tenga, así que poner uno de más en
             esta lista no lo habilita. Por eso ningún perfil de custodia puede
             figurar acá con efecto: nombrar custodios es del superusuario, que es
             justamente lo que ADR-025/ADR-029 persiguen.
"""

FAMILY_GOVERNANCE = "gobierno"
FAMILY_OPERATION = "operacion"
FAMILY_SPECIALIST = "especialista"
FAMILY_CUSTODY = "custodia"

# Permisos de lectura transversales que casi todos los perfiles necesitan para que
# la consola sea navegable (ver la flota y su organización). Se escriben completos
# en cada rol igual: la explicitud vale más que ahorrar cinco líneas.

STANDARD_ROLES = [
    # ------------------------------------------------------------------ gobierno
    {
        "name": "Administrador de Plataforma",
        "family": FAMILY_GOVERNANCE,
        "sensitive": True,
        "summary": {
            "es": "Administra la plataforma completa: usuarios, roles, ajustes del "
            "servidor, scripts, claves y llaves de API. No incluye custodia.",
            "en": "Administers the whole platform: users, roles, server settings, "
            "scripts, keystore and API keys. Custody permissions excluded.",
        },
        "perms": [
            "can_list_agents",
            "can_use_mesh",
            "can_uninstall_agents",
            "can_update_agents",
            "can_edit_agent",
            "can_manage_procs",
            "can_view_eventlogs",
            "can_send_cmd",
            "can_reboot_agents",
            "can_install_agents",
            "can_run_scripts",
            "can_run_bulk",
            "can_recover_agents",
            "can_list_agent_history",
            "can_send_wol",
            "can_use_registry",
            "can_send_alerts",
            "can_list_notes",
            "can_manage_notes",
            "can_view_core_settings",
            "can_edit_core_settings",
            "can_do_server_maint",
            "can_code_sign",
            "can_run_urlactions",
            "can_view_customfields",
            "can_manage_customfields",
            "can_run_server_scripts",
            "can_use_webterm",
            "can_view_global_keystore",
            "can_edit_global_keystore",
            "can_view_schedules",
            "can_manage_schedules",
            "can_list_checks",
            "can_manage_checks",
            "can_run_checks",
            "can_list_clients",
            "can_manage_clients",
            "can_list_sites",
            "can_manage_sites",
            "can_list_deployments",
            "can_manage_deployments",
            "can_list_automation_policies",
            "can_manage_automation_policies",
            "can_list_autotasks",
            "can_manage_autotasks",
            "can_run_autotasks",
            "can_view_auditlogs",
            "can_list_pendingactions",
            "can_manage_pendingactions",
            "can_view_debuglogs",
            "can_list_scripts",
            "can_manage_scripts",
            "can_list_alerts",
            "can_manage_alerts",
            "can_list_alerttemplates",
            "can_manage_alerttemplates",
            "can_manage_winsvcs",
            "can_list_software",
            "can_manage_software",
            "can_manage_winupdates",
            "can_list_accounts",
            "can_manage_accounts",
            "can_list_roles",
            "can_manage_roles",
            "can_list_api_keys",
            "can_manage_api_keys",
            "can_use_mcp",
            "can_view_reports",
            "can_manage_reports",
        ],
    },
    {
        "name": "Administrador de Organización",
        "family": FAMILY_GOVERNANCE,
        "sensitive": True,
        "summary": {
            "es": "Administra su propia organización: flota, sitios, tareas, alertas, "
            "parches, informes y las cuentas de su equipo. No gestiona roles ni "
            "toca la configuración del servidor.",
            "en": "Administers their own organization: fleet, sites, tasks, alerts, "
            "patching, reports and their team's accounts. Cannot manage roles or "
            "touch server configuration.",
        },
        "perms": [
            "can_list_agents",
            "can_use_mesh",
            "can_uninstall_agents",
            "can_update_agents",
            "can_edit_agent",
            "can_install_agents",
            "can_reboot_agents",
            "can_run_bulk",
            "can_list_agent_history",
            "can_send_wol",
            "can_view_eventlogs",
            "can_send_alerts",
            "can_list_notes",
            "can_manage_notes",
            "can_view_core_settings",
            "can_view_customfields",
            "can_list_checks",
            "can_manage_checks",
            "can_run_checks",
            "can_list_clients",
            "can_manage_clients",
            "can_list_sites",
            "can_manage_sites",
            "can_list_deployments",
            "can_manage_deployments",
            "can_list_automation_policies",
            "can_list_autotasks",
            "can_manage_autotasks",
            "can_run_autotasks",
            "can_view_auditlogs",
            "can_list_pendingactions",
            "can_manage_pendingactions",
            "can_view_debuglogs",
            "can_list_scripts",
            "can_list_alerts",
            "can_manage_alerts",
            "can_list_alerttemplates",
            "can_manage_alerttemplates",
            "can_manage_winsvcs",
            "can_list_software",
            "can_manage_software",
            "can_manage_winupdates",
            "can_list_accounts",
            "can_manage_accounts",
            # Feature 052: «Ver roles» vuelve, y ahora es seguro. El listado que
            # devuelve la API está filtrado a los perfiles asignables, así que este
            # permiso ya no muestra la instancia entera: muestra lo que la lista de
            # abajo autoriza. Entre la 052 y su predecesora este permiso estuvo
            # retirado a propósito, porque sin el filtro dejaba otorgar cualquier
            # perfil, el de superusuario incluido.
            "can_list_roles",
            "can_use_mcp",
            "can_view_reports",
            "can_manage_reports",
        ],
        # Los cuatro perfiles que este rol puede repartir. No es una elección
        # estética: son los únicos del catálogo cuyos permisos están contenidos en
        # los suyos, así que cualquier otro lo bloquearía el invariante de todos
        # modos. Ninguno es de gobierno ni de custodia (RF-11).
        "assignable": [
            "Técnico de Soporte Nivel 1",
            "Operador de Monitoreo",
            "Analista de Informes",
            "Integración de Solo Lectura",
        ],
    },
    # ----------------------------------------------------------------- operación
    {
        "name": "Supervisor de Servicio",
        "family": FAMILY_OPERATION,
        "sensitive": False,
        "summary": {
            "es": "Coordina la mesa de servicio: ve toda la operación y gestiona "
            "checks, tareas, alertas, políticas e informes. No administra cuentas.",
            "en": "Coordinates the service desk: sees the whole operation and manages "
            "checks, tasks, alerts, policies and reports. Does not administer accounts.",
        },
        "perms": [
            "can_list_agents",
            "can_use_mesh",
            "can_update_agents",
            "can_edit_agent",
            "can_install_agents",
            "can_reboot_agents",
            "can_run_scripts",
            "can_run_bulk",
            "can_list_agent_history",
            "can_send_wol",
            "can_view_eventlogs",
            "can_send_alerts",
            "can_list_notes",
            "can_manage_notes",
            "can_view_core_settings",
            "can_view_customfields",
            "can_view_schedules",
            "can_list_checks",
            "can_manage_checks",
            "can_run_checks",
            "can_list_clients",
            "can_list_sites",
            "can_manage_sites",
            "can_list_deployments",
            "can_list_automation_policies",
            "can_manage_automation_policies",
            "can_list_autotasks",
            "can_manage_autotasks",
            "can_run_autotasks",
            "can_view_auditlogs",
            "can_list_pendingactions",
            "can_manage_pendingactions",
            "can_list_scripts",
            "can_list_alerts",
            "can_manage_alerts",
            "can_list_alerttemplates",
            "can_manage_alerttemplates",
            "can_manage_winsvcs",
            "can_list_software",
            "can_manage_software",
            "can_manage_winupdates",
            "can_use_mcp",
            "can_view_reports",
            "can_manage_reports",
        ],
    },
    {
        "name": "Técnico de Soporte Nivel 2",
        "family": FAMILY_OPERATION,
        "sensitive": True,
        "summary": {
            "es": "Resuelve incidentes con herramientas avanzadas: control remoto, "
            "scripts, línea de comandos, procesos y registro de Windows.",
            "en": "Resolves incidents with advanced tooling: remote control, scripts, "
            "command line, processes and the Windows registry.",
        },
        "perms": [
            "can_list_agents",
            "can_use_mesh",
            "can_uninstall_agents",
            "can_update_agents",
            "can_edit_agent",
            "can_manage_procs",
            "can_view_eventlogs",
            "can_send_cmd",
            "can_reboot_agents",
            "can_install_agents",
            "can_run_scripts",
            "can_run_bulk",
            "can_recover_agents",
            "can_list_agent_history",
            "can_send_wol",
            "can_use_registry",
            "can_send_alerts",
            "can_list_notes",
            "can_manage_notes",
            "can_view_customfields",
            "can_list_checks",
            "can_run_checks",
            "can_list_clients",
            "can_list_sites",
            "can_manage_sites",
            "can_list_deployments",
            "can_list_autotasks",
            "can_run_autotasks",
            "can_list_pendingactions",
            "can_list_scripts",
            "can_list_alerts",
            "can_manage_winsvcs",
            "can_list_software",
            "can_manage_software",
            "can_manage_winupdates",
            "can_use_mcp",
            "can_view_reports",
        ],
    },
    {
        "name": "Técnico de Soporte Nivel 1",
        "family": FAMILY_OPERATION,
        "sensitive": False,
        "summary": {
            "es": "Atiende la primera línea: control remoto, reinicios, servicios de "
            "Windows, instalación de agentes y consulta del inventario técnico.",
            "en": "Handles the first line: remote control, reboots, Windows services, "
            "agent installation and read access to the technical inventory.",
        },
        "perms": [
            "can_list_agents",
            "can_use_mesh",
            "can_update_agents",
            "can_install_agents",
            "can_reboot_agents",
            "can_run_bulk",
            "can_list_agent_history",
            "can_send_wol",
            "can_view_eventlogs",
            "can_send_alerts",
            "can_list_notes",
            "can_manage_notes",
            "can_list_checks",
            "can_list_clients",
            "can_list_sites",
            "can_manage_sites",
            "can_list_deployments",
            "can_list_autotasks",
            "can_list_pendingactions",
            "can_list_alerts",
            "can_manage_winsvcs",
            "can_list_software",
            "can_use_mcp",
            "can_view_reports",
        ],
    },
    {
        "name": "Operador de Monitoreo",
        "family": FAMILY_OPERATION,
        "sensitive": False,
        "summary": {
            "es": "Turno de monitoreo (NOC): vigila checks y alertas, ejecuta "
            "verificaciones y tareas, y escala. Sin acceso remoto a los equipos.",
            "en": "Monitoring shift (NOC): watches checks and alerts, runs checks and "
            "tasks, and escalates. No remote access to machines.",
        },
        "perms": [
            "can_list_agents",
            "can_list_agent_history",
            "can_view_eventlogs",
            "can_send_alerts",
            "can_list_notes",
            "can_manage_notes",
            "can_list_checks",
            "can_manage_checks",
            "can_run_checks",
            "can_list_clients",
            "can_list_sites",
            "can_list_autotasks",
            "can_run_autotasks",
            "can_list_pendingactions",
            "can_manage_pendingactions",
            "can_list_alerts",
            "can_manage_alerts",
            "can_list_alerttemplates",
            "can_manage_alerttemplates",
            "can_list_software",
            "can_use_mcp",
            "can_view_reports",
        ],
    },
    {
        "name": "Auditor de Plataforma",
        "family": FAMILY_OPERATION,
        "sensitive": False,
        "summary": {
            "es": "Acceso de solo lectura a toda la plataforma, incluidos los "
            "registros de auditoría. No ejecuta ninguna acción sobre los equipos.",
            "en": "Read-only access to the whole platform, audit logs included. "
            "Performs no action on the machines.",
        },
        "perms": [
            "can_list_agents",
            "can_list_agent_history",
            "can_view_eventlogs",
            "can_list_notes",
            "can_view_core_settings",
            "can_view_customfields",
            "can_view_schedules",
            "can_list_checks",
            "can_list_clients",
            "can_list_sites",
            "can_list_deployments",
            "can_list_automation_policies",
            "can_list_autotasks",
            "can_view_auditlogs",
            "can_list_pendingactions",
            "can_view_debuglogs",
            "can_list_scripts",
            "can_list_alerts",
            "can_list_alerttemplates",
            "can_list_software",
            "can_list_accounts",
            "can_list_roles",
            "can_use_mcp",
            "can_view_reports",
        ],
    },
    # --------------------------------------------------------------- especialista
    {
        "name": "Administrador de Parches y Software",
        "family": FAMILY_SPECIALIST,
        "sensitive": True,
        "summary": {
            "es": "Conduce las campañas de actualización: aprueba e instala parches, "
            "gestiona software y coordina los reinicios de la flota.",
            "en": "Runs update campaigns: approves and installs patches, manages "
            "software and coordinates fleet reboots.",
        },
        "perms": [
            "can_list_agents",
            "can_list_agent_history",
            "can_view_eventlogs",
            "can_reboot_agents",
            "can_run_bulk",
            "can_run_scripts",
            "can_send_alerts",
            "can_list_notes",
            "can_manage_notes",
            "can_list_checks",
            "can_run_checks",
            "can_list_clients",
            "can_list_sites",
            "can_list_autotasks",
            "can_manage_autotasks",
            "can_run_autotasks",
            "can_list_pendingactions",
            "can_manage_pendingactions",
            "can_list_scripts",
            "can_list_alerts",
            "can_list_software",
            "can_manage_software",
            "can_manage_winupdates",
            "can_use_mcp",
            "can_view_reports",
        ],
    },
    {
        "name": "Ingeniero de Automatización",
        "family": FAMILY_SPECIALIST,
        "sensitive": True,
        "summary": {
            "es": "Construye la automatización: scripts, políticas, tareas "
            "programadas, campos personalizados y despliegues.",
            "en": "Builds the automation: scripts, policies, scheduled tasks, custom "
            "fields and deployments.",
        },
        "perms": [
            "can_list_agents",
            "can_list_agent_history",
            "can_run_scripts",
            "can_run_bulk",
            "can_run_urlactions",
            "can_view_customfields",
            "can_manage_customfields",
            "can_view_schedules",
            "can_manage_schedules",
            "can_view_global_keystore",
            "can_list_checks",
            "can_manage_checks",
            "can_run_checks",
            "can_list_clients",
            "can_list_sites",
            "can_list_deployments",
            "can_manage_deployments",
            "can_list_automation_policies",
            "can_manage_automation_policies",
            "can_list_autotasks",
            "can_manage_autotasks",
            "can_run_autotasks",
            "can_list_pendingactions",
            "can_view_debuglogs",
            "can_list_scripts",
            "can_manage_scripts",
            "can_list_alerts",
            "can_list_software",
            "can_use_mcp",
            "can_view_reports",
        ],
    },
    {
        "name": "Gestor de Inventario y Activos",
        "family": FAMILY_SPECIALIST,
        "sensitive": False,
        "summary": {
            "es": "Mantiene el inventario: clientes, sitios, altas de equipos, campos "
            "personalizados y la ficha técnica de cada activo.",
            "en": "Maintains the inventory: clients, sites, machine intake, custom "
            "fields and each asset's technical record.",
        },
        "perms": [
            "can_list_agents",
            "can_edit_agent",
            "can_list_agent_history",
            "can_list_notes",
            "can_manage_notes",
            "can_view_customfields",
            "can_manage_customfields",
            "can_list_clients",
            "can_manage_clients",
            "can_list_sites",
            "can_manage_sites",
            "can_list_deployments",
            "can_manage_deployments",
            "can_manage_asset_intake",
            "can_list_software",
            "can_use_mcp",
            "can_view_reports",
        ],
    },
    {
        "name": "Analista de Informes",
        "family": FAMILY_SPECIALIST,
        "sensitive": False,
        "summary": {
            "es": "Genera, programa y distribuye los informes de la plataforma, con "
            "acceso de lectura a los datos que los alimentan.",
            "en": "Generates, schedules and distributes platform reports, with read "
            "access to the data behind them.",
        },
        "perms": [
            "can_list_agents",
            "can_list_agent_history",
            "can_list_checks",
            "can_list_clients",
            "can_list_sites",
            "can_list_autotasks",
            "can_view_auditlogs",
            "can_list_alerts",
            "can_list_software",
            "can_use_mcp",
            "can_view_reports",
            "can_manage_reports",
        ],
    },
    {
        "name": "Integración de Solo Lectura",
        "family": FAMILY_SPECIALIST,
        "sensitive": False,
        "summary": {
            "es": "Perfil para llaves de API de sistemas externos (ITSM, CMDB, "
            "tableros): lee inventario y estado, no ejecuta nada.",
            "en": "Profile for external systems' API keys (ITSM, CMDB, dashboards): "
            "reads inventory and status, executes nothing.",
        },
        "perms": [
            "can_list_agents",
            "can_list_agent_history",
            "can_list_checks",
            "can_list_clients",
            "can_list_sites",
            "can_list_autotasks",
            "can_list_alerts",
            "can_list_software",
            "can_view_reports",
        ],
    },
    # -------------------------------------------------------------------- custodia
    # Estos cinco ya los sembraba el seeder desde la feature 042/043 y se conservan
    # con exactamente los mismos permisos: cualquier cambio acá rompería la
    # separación de deberes que pide ADR-025 / ADR-029.
    {
        "name": "Operador de Equipos Perdidos",
        "family": FAMILY_CUSTODY,
        "sensitive": True,
        "summary": {
            "es": "Opera el caso de un equipo perdido o robado: lo marca, lo bloquea, "
            "hace sonar la alarma y muestra mensajes en pantalla.",
            "en": "Operates the lost or stolen device case: flags it, locks it, sounds "
            "the alarm and shows on-screen messages.",
        },
        "perms": [
            "can_list_agents",
            "can_manage_lost_mode",
            "can_send_alerts",
            "can_lock_agents",
            "can_sound_alarm",
            "can_use_mcp",
        ],
    },
    {
        "name": "Revisor de Evidencia",
        "family": FAMILY_CUSTODY,
        "sensitive": True,
        "summary": {
            "es": "Revisa la evidencia capturada de un equipo perdido (ubicación, "
            "capturas, fotos). No puede operar el caso ni borrar el equipo.",
            "en": "Reviews the evidence captured from a lost device (location, "
            "screenshots, photos). Cannot operate the case or wipe the device.",
        },
        "perms": [
            "can_list_agents",
            "can_view_lost_evidence",
            "can_use_mcp",
        ],
    },
    {
        "name": "Recuperador de Archivos",
        "family": FAMILY_CUSTODY,
        "sensitive": True,
        "summary": {
            "es": "Recupera archivos de un equipo antes de darlo de baja o borrarlo. "
            "Permiso dedicado: recuperar no es borrar.",
            "en": "Retrieves files from a machine before decommissioning or wiping it. "
            "Dedicated permission: retrieving is not wiping.",
        },
        "perms": [
            "can_list_agents",
            "can_retrieve_files",
            "can_use_mcp",
        ],
    },
    {
        "name": "Ordenante de Borrado",
        "family": FAMILY_CUSTODY,
        "sensitive": True,
        "summary": {
            "es": "Ordena el borrado remoto de un equipo. Es la capacidad más "
            "destructiva de la plataforma y no la hereda ningún otro perfil.",
            "en": "Orders the remote wipe of a machine. The most destructive capability "
            "in the platform; no other profile inherits it.",
        },
        "perms": [
            "can_list_agents",
            "can_wipe_device",
            "can_use_mcp",
        ],
    },
    {
        "name": "Auditor de Custodia",
        "family": FAMILY_CUSTODY,
        "sensitive": False,
        "summary": {
            "es": "Custodia la cadena documental: certificados de borrado y actas de "
            "ingreso de activos.",
            "en": "Keeps the documentary chain: erase certificates and asset intake "
            "records.",
        },
        "perms": [
            "can_list_agents",
            "can_view_erase_certificates",
            "can_manage_asset_intake",
            "can_use_mcp",
        ],
    },
    {
        "name": "Supervisor de Actividad Laboral",
        "family": FAMILY_CUSTODY,
        "sensitive": True,
        "summary": {
            "es": "Consulta y configura el monitoreo de actividad laboral, sujeto a la "
            "política de uso aceptable y al consentimiento informado del personal.",
            "en": "Views and configures employee activity monitoring, subject to the "
            "acceptable use policy and to staff's informed consent.",
        },
        "perms": [
            "can_list_agents",
            "can_view_activity",
            "can_manage_activity",
            "can_list_clients",
            "can_list_sites",
            "can_use_mcp",
            "can_view_reports",
        ],
    },
]

# Superficie de permisos que gestiona el seeder: la unión de todo lo que el
# catálogo nombra. Con `--force`, un rol del catálogo queda EXACTAMENTE con sus
# permisos canónicos (los de su lista en True, el resto de la superficie en
# False). `is_superuser` queda fuera a propósito: nunca se toca.
MANAGED_PERMS = sorted({perm for role in STANDARD_ROLES for perm in role["perms"]})

ROLES_BY_NAME = {role["name"]: role for role in STANDARD_ROLES}

# Feature 052: qué perfiles otorga cada rol. Solo los que lo declaran aparecen.
ASSIGNABLE_BY_ROLE = {
    role["name"]: role["assignable"]
    for role in STANDARD_ROLES
    if role.get("assignable")
}
