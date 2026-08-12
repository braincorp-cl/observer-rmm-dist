module.exports = {
  // https://eslint.org/docs/user-guide/configuring#configuration-cascading-and-hierarchy
  // This option interrupts the configuration hierarchy at this file
  // Remove this if you have an higher level ESLint config file (it usually happens into a monorepos)
  root: true,

  // https://eslint.vuejs.org/user-guide/#how-to-use-a-custom-parser
  // Must use parserOptions instead of "parser" to allow vue-eslint-parser to keep working
  // `parser: 'vue-eslint-parser'` is already included with any 'plugin:vue/**' config and should be omitted
  parserOptions: {
    parser: require.resolve("@typescript-eslint/parser"),
    extraFileExtensions: [".vue"],
  },

  env: {
    browser: true,
    es2021: true,
    node: true,
    "vue/setup-compiler-macros": true,
  },

  // Rules order is important, please avoid shuffling them
  extends: [
    // Base ESLint recommended rules
    // 'eslint:recommended',

    // https://github.com/typescript-eslint/typescript-eslint/tree/master/packages/eslint-plugin#usage
    // ESLint typescript rules
    "plugin:@typescript-eslint/recommended",

    // Uncomment any of the lines below to choose desired strictness,
    // but leave only one uncommented!
    // See https://eslint.vuejs.org/rules/#available-rules
    "plugin:vue/vue3-essential", // Priority A: Essential (Error Prevention)
    // 'plugin:vue/vue3-strongly-recommended', // Priority B: Strongly Recommended (Improving Readability)
    // 'plugin:vue/vue3-recommended', // Priority C: Recommended (Minimizing Arbitrary Choices and Cognitive Overhead)

    // https://github.com/prettier/eslint-config-prettier#installation
    // usage with Prettier, provided by 'eslint-config-prettier'.
    "prettier",
  ],

  plugins: [
    // required to apply rules which need type information
    "@typescript-eslint",

    // https://eslint.vuejs.org/user-guide/#why-doesn-t-it-work-on-vue-files
    // required to lint *.vue files
    "vue",

    // https://github.com/typescript-eslint/typescript-eslint/issues/389#issuecomment-509292674
    // Prettier has not been included as plugin to avoid performance impact
    // add it as an extension for your IDE
  ],

  globals: {
    ga: "readonly", // Google Analytics
    cordova: "readonly",
    __statics: "readonly",
    __QUASAR_SSR__: "readonly",
    __QUASAR_SSR_SERVER__: "readonly",
    __QUASAR_SSR_CLIENT__: "readonly",
    __QUASAR_SSR_PWA__: "readonly",
    process: "readonly",
    Capacitor: "readonly",
    chrome: "readonly",
  },

  // add your custom rules here
  rules: {
    "prefer-promise-reject-errors": "off",

    quotes: ["warn", "double", { avoidEscape: true }],

    // this rule, if on, would require explicit return type on the `render` function
    "@typescript-eslint/explicit-function-return-type": "off",

    // in plain CommonJS modules, you can't use `import foo = require('foo')` to pass this rule, so it has to be disabled
    "@typescript-eslint/no-var-requires": "off",

    // The core 'no-unused-vars' rules (in the eslint:recommended ruleset)
    // does not work with type definitions
    "no-unused-vars": "off",

    // allow debugger during development only
    "no-debugger": process.env.NODE_ENV === "production" ? "error" : "off",
  },

  // i18n (feature 010): el plugin lee los catálogos para validar claves.
  settings: {
    "vue-i18n": {
      localeDir: "./src/i18n/*.json",
      messageSyntaxVersion: "^9.0.0",
    },
  },

  overrides: [
    {
      // Gate i18n ESTRICTO acotado a las superficies ya migradas.
      // - no-missing-keys: toda clave usada debe existir en es Y en (falla build).
      // - no-raw-text: prohíbe texto hardcodeado nuevo en la vista migrada.
      // El resto de la UI aún sin migrar NO entra al gate (RN-07), por eso el scope
      // por glob en vez de aplicar no-raw-text globalmente.
      // Ola 1 (F010): login/2FA. Ola 2: chrome de navegación + onboarding + vistas chicas.
      // Ola 3: DashboardView. Ola 4: AgentTable. Ola 5a: InstallAgent.
      // Ola 5b: modales de agente (EditAgent / BulkAction / PatchPolicyForm).
      // Ola 6a: barra de pestañas del detalle de agente (SubTableTabs).
      // Ola 6 (completa, GAP-046): interiores de las 10 agents/*Tab.vue
      // (Summary/Checks/Tasks/Patches/Software/History/Notes/Assets/Debug/Audit),
      // labels de columnas via computed con t() y diálogos/notify via t().
      // Ola 7: cluster admin cuentas/roles (accounts/ + modals/admin/):
      // ResetPass / UserSessionsTable / PermissionsManager / RolesForm +
      // UserForm / UserResetPasswordForm. (RolesForm: 2 refs al nombre del
      // producto de origen, debrandeadas a "Observer" al migrar.)
      files: [
        "src/views/LoginView.vue",
        "src/components/FileBar.vue",
        "src/views/InitialSetup.vue",
        "src/views/TOTPSetup.vue",
        "src/views/SessionExpired.vue",
        "src/views/NotFound.vue",
        "src/views/DashboardView.vue",
        "src/components/AgentTable.vue",
        "src/components/modals/agents/InstallAgent.vue",
        "src/components/modals/agents/EditAgent.vue",
        "src/components/modals/agents/BulkAction.vue",
        "src/components/modals/agents/PatchPolicyForm.vue",
        "src/components/SubTableTabs.vue",
        "src/components/agents/AuditTab.vue",
        "src/components/agents/DebugTab.vue",
        "src/components/agents/AssetsTab.vue",
        "src/components/agents/HistoryTab.vue",
        "src/components/agents/NotesTab.vue",
        "src/components/agents/SoftwareTab.vue",
        "src/components/agents/SummaryTab.vue",
        "src/components/agents/ChecksTab.vue",
        "src/components/agents/AutomatedTasksTab.vue",
        "src/components/agents/WinUpdateTab.vue",
        "src/components/agents/AgentActionMenu.vue",
        "src/components/agents/ConfirmYesDialog.vue",
        "src/components/accounts/ResetPass.vue",
        "src/components/accounts/UserSessionsTable.vue",
        "src/components/accounts/PermissionsManager.vue",
        "src/components/accounts/RolesForm.vue",
        // feature 030 · módulo de equipos perdidos, en el gate estricto desde el
        // día uno: entrar después obliga a repasar un archivo ya escrito.
        "src/views/LostEquipmentView.vue",
        "src/components/modals/admin/UserForm.vue",
        "src/components/modals/admin/UserResetPasswordForm.vue",
        // Ola 8a: widgets compartidos ui/ (2 sin texto entran limpios al gate).
        "src/components/ui/ConfirmDialog.vue",
        "src/components/ui/CustomField.vue",
        "src/components/ui/DialogWrapper.vue",
        "src/components/ui/ExportTableBtn.vue",
        "src/components/ui/IntegrationsContextMenu.vue",
        "src/components/ui/ObserverDropdown.vue",
        "src/components/ui/PreDialog.vue",
        "src/components/ui/WinUpdateDialog.vue",
        // Ola 8b: diálogos de chequeo chicos (checksCommon compartido) + salida de scripts.
        "src/components/checks/CpuLoadCheck.vue",
        "src/components/checks/MemCheck.vue",
        "src/components/checks/DiskSpaceCheck.vue",
        "src/components/checks/PingCheck.vue",
        "src/components/checks/EventLogCheckOutput.vue",
        "src/components/checks/ScriptOutput.vue",
        "src/components/scripts/ScriptOutputCopyClip.vue",
        // Ola 8c: formularios chicos clients/.
        "src/components/clients/ClientsForm.vue",
        "src/components/clients/SitesForm.vue",
        "src/components/clients/NewDeployment.vue",
        "src/components/clients/DeleteClient.vue",
        // Ola 8d: vistas remotas (WebVNC/WebTerminal/AgentView sin texto entran limpias).
        "src/views/TakeControl.vue",
        "src/views/RemoteBackground.vue",
        "src/views/WebVNC.vue",
        "src/views/WebTerminal.vue",
        "src/views/AgentView.vue",
        // Ola 8e: modales chicos de coresettings/.
        "src/components/modals/coresettings/CustomFields.vue",
        "src/components/modals/coresettings/CodeSign.vue",
        "src/components/modals/coresettings/KeyStoreForm.vue",
        "src/components/modals/coresettings/ResetPatchPolicy.vue",
        "src/components/modals/coresettings/TestURLAction.vue",
        // Ola 8f: chicos varios (App/ObserverTable limpios). AgentDownload se
        // gateó en la ola 28 (ver más abajo; flags CLI en <code> vía $t es/en idéntico).
        "src/App.vue",
        "src/core/dashboard/ui/ObserverTable.vue",
        "src/components/agents/WmiDetail.vue",
        "src/components/agents/CommandStream.vue",
        "src/components/core/APIKeysForm.vue",
        "src/components/logs/AuditLogDetailModal.vue",
        "src/components/modals/agents/RebootLater.vue",
        "src/components/modals/agents/AgentRecovery.vue",
        "src/components/modals/core/ServerMaintenance.vue",
        "src/components/software/InstallSoftware.vue",
        "src/components/software/UninstallSoftware.vue",
        "src/components/scripts/TestScriptModal.vue",
        // Ola 9a: chequeos MEDIANOS (formularios densos), reusan checksCommon.*
        // (+ 2 claves nuevas descriptiveName/alertSeverity) + namespaces propios.
        "src/components/checks/EventLogCheck.vue",
        "src/components/checks/ScriptCheck.vue",
        // Ola 9b: automation/ MEDIANOS (Options API; columns movidas a computed
        // con this.$t para reactividad de idioma) + namespaces propios.
        "src/components/automation/AutomationManager.vue",
        "src/components/automation/modals/PolicyStatus.vue",
        // Ola 9c: WinSvcCheck (cierra checks/ medianos, reusa checksCommon.*) +
        // UserPreferences (Options API; options movidas a computed con this.$t).
        "src/components/checks/WinSvcCheck.vue",
        "src/components/modals/coresettings/UserPreferences.vue",
        // Ola 9d: completa automation/ — PolicyOverview + los dos tabs gemelos
        // (namespace COMPARTIDO policyTabsCommon para alertas/edit/delete/etc.).
        // Options API: columns/labels movidas a computed con this.$t.
        "src/components/automation/PolicyOverview.vue",
        "src/components/automation/PolicyChecksTab.vue",
        "src/components/automation/PolicyAutomatedTasksTab.vue",
        // Ola 9e: alerts — AlertsOverview + AlertsManager. Options API: columns/
        // options movidas a computed con this.$t; diálogos/notify interpolados.
        "src/components/modals/alerts/AlertsOverview.vue",
        "src/components/AlertsManager.vue",
        // Ola 10a: logs/ MEDIANOS (Composition API; columns/options movidas a
        // computed con useI18n t; interpolación {hostname}/{count}). Namespaces
        // propios auditManager/debugLog/pendingActions.
        "src/components/logs/AuditManager.vue",
        "src/components/logs/DebugLog.vue",
        "src/components/logs/PendingActions.vue",
        // Ola 10b: clients/ MEDIANOS (Composition API; columns a computed con
        // useI18n t; interpolación {name}/{count}). Namespaces propios
        // clientsManager/sitesTable/deploymentTable.
        "src/components/clients/ClientsManager.vue",
        "src/components/clients/SitesTable.vue",
        "src/components/clients/DeploymentTable.vue",
        // Ola 11: modals/agents/ comandos al agente — SendCommand +
        // WebsocketSendCommand (casi-clones, namespace COMPARTIDO
        // sendCommandCommon) + RunScript (<script setup>: outputOptions a
        // computed con t). Labels de radios/inputs a $t; reglas interpoladas
        // (min/max timeout). Constantes JS (envVarsLabel/runAsUserToolTip) no
        // se traducen.
        "src/components/modals/agents/SendCommand.vue",
        "src/components/modals/agents/WebsocketSendCommand.vue",
        "src/components/modals/agents/RunScript.vue",
        // Ola 12: agents/remotebg/ servicios — ServicesManager + ServiceDetail
        // (namespace COMPARTIDO servicesCommon: start/stop/restart + opciones de
        // arranque idénticas). Options API: columns/startupOptions a computed
        // con t. Valores del backend (start_type/status) NO se traducen.
        "src/components/agents/remotebg/ServicesManager.vue",
        "src/components/agents/remotebg/ServiceDetail.vue",
        // Ola 13: scripts/ MEDIANOS — ScriptFormModal + ScriptSnippets +
        // ScriptSnippetFormModal + ScriptUploadModal. Namespace COMPARTIDO
        // scriptsCommon (campos name/description/shellType/category/... + nombres
        // de shell idénticos es/en + botones save/cancel/close/add). i18n-t con
        // slots para avisos con <code>/<strong>/<em> (shebang + test-on-server).
        // Constante JS envVarsLabel NO se traduce; shellOptions vive en composable.
        "src/components/scripts/ScriptFormModal.vue",
        "src/components/scripts/ScriptSnippets.vue",
        "src/components/scripts/ScriptSnippetFormModal.vue",
        "src/components/scripts/ScriptUploadModal.vue",
        // AiScriptPromptModal: nace traducido (namespace propio aiScriptPrompt),
        // reusa scriptsCommon.chatGptPrompt como entrada de la frase y como
        // prefijo real del prompt, así no hay dos redacciones que sincronizar.
        "src/components/scripts/AiScriptPromptModal.vue",
        // Ola 14: coresettings/ CustomFields — CustomFieldsForm + CustomFieldsTable
        // (Options API puro: modelOptions/typeOptions/columns a computed con
        // this.$t). Namespace COMPARTIDO customFieldsCommon (name/fieldType/
        // defaultValue/required/hideInSummary/edit/delete/close). El valor de tipo
        // renderizado en la tabla (capitalize(type)) es dato, NO se traduce.
        "src/components/modals/coresettings/CustomFieldsForm.vue",
        "src/components/modals/coresettings/CustomFieldsTable.vue",
        // Ola 15: coresettings/ URLActions — URLActionsForm + URLActionsTable.
        // Par form/tabla (script setup, useI18n). Namespace COMPARTIDO
        // urlActionsCommon (name/description/urlPattern/edit/delete/close/cancel/
        // submit). Títulos/labels dependen de type (web=acción de URL vs Web Hook)
        // vía computed. "Web Hook" es tecnología: se mantiene en ambos idiomas.
        // Los métodos HTTP (GET/POST/...) vienen de un array JS, no de literales
        // en la vista, así que no los marca no-raw-text.
        "src/components/modals/coresettings/URLActionsForm.vue",
        "src/components/modals/coresettings/URLActionsTable.vue",
        // Ola 16: modals/alerts/ — AlertExclusions + AlertTemplateAdd +
        // AlertTemplateRelated (cierran el dominio alerts salvo el GRANDE
        // AlertTemplateForm). Options API (this.$t). Namespace COMPARTIDO
        // alertsModalsCommon (close/cancel/save/submit). Interpolación {name}/
        // {type}. En AlertTemplateAdd el {type} del título es el valor crudo del
        // prop (site/client/policy); selectLabel usa capitalize(type) como var.
        "src/components/modals/alerts/AlertExclusions.vue",
        "src/components/modals/alerts/AlertTemplateAdd.vue",
        "src/components/modals/alerts/AlertTemplateRelated.vue",
        // Ola 17: automation/modals/ policies — PolicyAdd + PolicyForm +
        // PolicyExclusions. Options API (this.$t). Namespace COMPARTIDO
        // policyModalsCommon (close/cancel/save/submit). {type} crudo del prop
        // (client/site/agent) en título y tooltip de PolicyAdd. PolicyForm usa
        // <i18n-t keypath="policyForm.copyIntro" scope="global"> con slot #name
        // (<b>) para el HTML. Interpolación {name} en títulos.
        "src/components/automation/modals/PolicyAdd.vue",
        "src/components/automation/modals/PolicyForm.vue",
        "src/components/automation/modals/PolicyExclusions.vue",
        // Ola 18: core/settings/ schedules — ScheduleForm + ScheduleTable
        // (par form/tabla, script setup, useI18n; se renderiza dentro de
        // EditCoreSettings). Namespace COMPARTIDO scheduleCommon (name/edit/
        // delete/close/cancel/save/required + daily/weekly/monthly). Arrays de
        // opciones (días/meses/semanas) movidos a computed con t() para reaccionar
        // al cambio de idioma en caliente. En la tabla, las funciones format() de
        // las columnas (abreviaturas de mes/día, ordinales de semana, "Every X")
        // NO las marca no-raw-text (son bindings {{col.value}}, no literales en la
        // vista) pero se traducen igual por calidad; schedule_type se mapea a
        // scheduleCommon.daily/weekly/monthly (antes capitalize() del valor crudo).
        "src/core/settings/components/ScheduleForm.vue",
        "src/core/settings/components/ScheduleTable.vue",
        // Ola 19: agents/remotebg/ restantes — EventLogManager + ProcessManager
        // (Options API con setup(): columns movidas a computed con t() para
        // reaccionar al cambio de idioma) + RegistryValueModal (<script setup>,
        // useI18n; mensajes de error del validador vía t()). Cierran el dominio
        // remotebg salvo el GRANDE RegistryManager. Ternario de título y spans de
        // tipo (DWORD/QWORD/Multi-String/String) y símbolos sueltos ({value}%,
        // {used}/{total} GB, "/") interpolados vía $t para no dejar VText crudo.
        // Los val de los radios (Application/System/Security) y el {type} de
        // totalRecords son valores del backend: se mantienen crudos; solo su label
        // visible se traduce (Aplicación/Sistema/Seguridad).
        "src/components/agents/remotebg/EventLogManager.vue",
        "src/components/agents/remotebg/ProcessManager.vue",
        "src/components/agents/remotebg/RegistryValueModal.vue",
        // Ola 20: settings/admin dispersos — AdminManager + APIKeysTable +
        // KeyStoreTable. Tres tablas de administración con menú contextual
        // (Editar/Eliminar/Cerrar), columnas y diálogos de confirmación. Columnas
        // movidas de data()/const de módulo a computed con $t para reaccionar al
        // idioma. Diálogos $q.dialog (título + ok + notifySuccess) traducidos vía
        // $t con placeholders {username}/{name}. "SSO" y "****" van a clave con
        // valor idéntico es/en (acrónimo y máscara). Los val de radios/estados del
        // backend se mantienen crudos.
        "src/components/AdminManager.vue",
        "src/components/core/APIKeysTable.vue",
        "src/components/modals/coresettings/KeyStoreTable.vue",
        // Ola 21: medianos dispersos — MainLayout + AlertsIcon + RelationsView.
        // MainLayout (<script setup>): toolbar, banners (versión desactualizada +
        // licencia inactiva partida en 4 segmentos con <br> estructurales), chip de
        // dispositivos (Servers/Workstations, Total/Offline con {count}), menú de
        // usuario y diálogo reset2FA (t() de useI18n). Extiende el namespace layout
        // existente (language). AlertsIcon (Options API): tooltips, path de agente
        // ({client} - {site} - {hostname} identico es/en), viewAll con {count} y
        // diálogos snooze/resolve vía this.$t. RelationsView (Options API): título
        // {name} Relations, tabs y etiquetas "Applied to..." vía $t.
        "src/layouts/MainLayout.vue",
        "src/components/AlertsIcon.vue",
        "src/components/automation/modals/RelationsView.vue",
        // ola 22 (long tail medianos dispersos): CheckGraph (Options API): gráfico
        // apexcharts de historial de check — Close/No Data (VText), title/seriesName/
        // timeFilterOptions a computed con this.$t, textos de config del chart
        // (umbrales, Passing/Failing, tooltips de script) traducidos en mounted por
        // calidad. FileBrowser (script setup ts): no-data-label + columnas
        // Name/Type/Size (const→computed con t()). UpdateAgents (Options API):
        // título/Close/banner auto-update/Select Version/Select Agent (VText),
        // label/placeholder estáticos y notifySuccess vía this.$t.
        "src/components/graphs/CheckGraph.vue",
        "src/components/FileBrowser.vue",
        "src/components/modals/agents/UpdateAgents.vue",
        // Ola 23 (primer GRANDE): EditCoreSettings — modal de configuración global
        // con 11 pestañas (General/Email/SMS/MeshCentral/CustomFields/KeyStore/
        // URLActions/WebHooks/Retention/APIKeys/Schedules). Options API ($t global
        // en template, this.$t en script). Namespace propio editCoreSettings.
        // Tabs/labels/hints estáticos → binding $t; VText (títulos, "col-*" labels,
        // tooltips) → {{ $t }}; reglas de validación (:rules) e :hint traducidos
        // por calidad aunque no los marque no-raw-text. logLevelOptions movido de
        // data() a computed con this.$t (reactividad de idioma). Diálogos $q.dialog
        // (confirmSync/addEmail/addNumber con HTML en message) + loading + notify
        // vía this.$t. DEBRANDEO: 3 refs al nombre del producto de origen en textos
        // visibles (tooltip server scripts + el toggle de Sync Mesh Perms +
        // tooltip permisos) → "Observer RMM" en AMBOS idiomas (precedente RolesForm). placeholder de
        // ejemplo (+12131231234) se mantiene literal (no es texto traducible).
        "src/components/modals/coresettings/EditCoreSettings.vue",
        // Ola 24 (GRANDE): ScriptManager — modal gestor de scripts (vista árbol +
        // tabla, menú contextual, dropdown "New"). Options API con setup()
        // Composition (const { t } = useI18n()). REUSA namespace scriptsCommon
        // (name/description/category/close/edit/delete/newBtn/shell*) de la ola 13
        // + namespace propio scriptManager para lo específico. columns movido de
        // const de módulo a computed dentro de setup() con t() (reactividad de
        // idioma), igual que ScriptSnippets. VText (título, ítems de menú, tooltips
        // de shell, headers, badge "All", no-data) → {{ $t }}; ternarios favorito/
        // oculto dentro de {{}} → $t; labels/no-*-label estáticos → binding $t por
        // calidad. Notificaciones (favorited/hidden) y diálogo de borrado vía t().
        // "ID: {id}" con interpolación. ormmLogo es asset (logo scripts community
        // builtin), no texto traducible.
        "src/components/scripts/ScriptManager.vue",
        // Ola 25 (long tail i18n, GRANDE 1013 líneas): AlertTemplateForm es el
        // wizard de 5 pasos (q-stepper) para crear/editar plantillas de alerta:
        // General/Actions/Agent Overdue/Check/Task Settings. <script setup>
        // (const { t } = useI18n()). REUSA alertsModalsCommon (close/submit) de
        // la ola 16 + namespace propio alertTemplate para lo específico (70 claves).
        // VText de los subtítulos y tooltips → {{ $t }}; título ternario del q-bar
        // → $t ambas ramas; labels/hints/titles estáticos → binding $t por calidad;
        // mensajes de :rules → $t. severityOptions y staticActionTypeOptions movidos
        // a computed con t() (reactividad de idioma); actionTypeOptions usa .value.
        // Diálogos $q.dialog (Add email/Add number, HTML E.164) y notificaciones vía
        // t(). Debranding: el nombre del producto de origen → "Observer RMM Server".
        "src/components/modals/alerts/AlertTemplateForm.vue",
        // Ola 26 (long tail i18n, GRANDE 1066 líneas): RegistryManager — editor de
        // registro de Windows (q-tree lazy + q-splitter + q-table de valores).
        // <script setup>. Cierra el dominio agents/remotebg/. registryTableColumns
        // y registryValueTypes se usaban SOLO aquí → movidos de constants.ts a
        // computed locales con t() (reactividad de idioma; columns/valueTypes).
        // VText de menús contextuales (New/Refresh/Rename/Delete/Modify) → {{ $t }};
        // label="Load More" y no-data-label → binding; props title/message de los
        // ConfirmDialog → $t; notify REG_BINARY → t(). Namespace propio
        // registryManager (23 claves). "Computer" (token de path) y "New_Key"
        // (nombre real de clave escrito al registro) quedan como datos, no se traducen.
        "src/components/agents/remotebg/RegistryManager.vue",
        // Ola 27 (long tail i18n, GRANDE 1293 líneas, ÚLTIMO GRANDE):
        // AutomatedTaskForm — wizard q-stepper de 3 pasos (Options API con setup()).
        // 8 constantes de opciones de módulo (severity/taskType/dayOfWeek/dayOfMonth/
        // month/week/taskInstancePolicy/plat) usadas SOLO aquí → movidas a computed
        // locales con t() (reactividad de idioma; toggle* usan .value). VText, labels,
        // hints, placeholders, mensajes de reglas de validación y notifyError → $t/t().
        // Namespace propio automatedTask (123 claves). envVarsLabel (constante de
        // config compartida) se deja sin traducir por consistencia con el resto.
        "src/components/tasks/AutomatedTaskForm.vue",
        // Ola 28 (long tail i18n, ÚLTIMO de 128): AgentDownload — modal de
        // instrucciones de instalación manual (Options API con setup()). Los
        // literales de flags CLI dentro de <code> (-log debug, -silent, -nomesh,
        // -cert "...", etc.) se enrutan por $t con clave de valor IDÉNTICO es/en
        // (patrón token técnico, precedente shebangBash/Python de ScriptFormModal);
        // NO se tocó la config del gate. Texto de UI (título, intros win/darwin,
        // descripciones de cada flag, nota del auth token, labels) traducido normal.
        // authNote usa interpolación {expires}. Namespace agentDownload (24 claves).
        // CIERRA i18n UI 128/128.
        "src/components/modals/agents/AgentDownload.vue",
        // Ola 30: módulo ee/reporting (Reportería, re-adoptada ADR-022). 23
        // componentes + 2 vistas. Namespace raíz `reporting.*` (hijo por
        // componente + `common`/`notify` compartidos). Options/setup mixtos:
        // columnas/opciones visibles movidas a computed con t() por reactividad.
        "src/ee/reporting/components/AssetFileUpload.vue",
        "src/ee/reporting/components/DataQuerySelect.vue",
        "src/ee/reporting/components/EditorToolbar.vue",
        "src/ee/reporting/components/ReportAssetSelect.vue",
        "src/ee/reporting/components/ReportAssets.vue",
        "src/ee/reporting/components/ReportChartSelect.vue",
        "src/ee/reporting/components/ReportDataQueryForm.vue",
        "src/ee/reporting/components/ReportDataQueryTable.vue",
        "src/ee/reporting/components/ReportDependencyPrompt.vue",
        "src/ee/reporting/components/ReportEmailSettingsForm.vue",
        "src/ee/reporting/components/ReportHistoryTable.vue",
        "src/ee/reporting/components/ReportHTMLTemplateForm.vue",
        "src/ee/reporting/components/ReportHTMLTemplateTable.vue",
        "src/ee/reporting/components/ReportingHelpMenu.vue",
        "src/ee/reporting/components/ReportScheduleForm.vue",
        "src/ee/reporting/components/ReportScheduleTable.vue",
        "src/ee/reporting/components/ReportsManager.vue",
        "src/ee/reporting/components/ReportTableMaker.vue",
        "src/ee/reporting/components/ReportTemplateForm.vue",
        "src/ee/reporting/components/ReportTemplateImport.vue",
        "src/ee/reporting/components/ReportTemplatePreview.vue",
        "src/ee/reporting/components/RunReportDialog.vue",
        "src/ee/reporting/components/VariablesSelector.vue",
        "src/ee/reporting/views/ReportHistoryView.vue",
        "src/ee/reporting/views/ReportView.vue",
        // Ola 31 (feature 028): modales de respuesta rápida de endpoint.
        //
        // ⚠️ Los DOS estaban en la lista de `lint:i18n` de package.json pero NO
        // acá, o sea que el gate los recorría con las reglas base y sin
        // `no-raw-text` ni `no-missing-keys`. `SendEndpointAlert.vue` arrastraba
        // ese hueco desde la Fase 1 de la 028: figuraba en el comando y parecía
        // gateado. Las dos listas tienen que coincidir — comprobado con un
        // literal sintético que antes de este cambio pasaba sin quejas.
        "src/components/modals/agents/SendEndpointAlert.vue",
        "src/components/modals/agents/SoundEndpointAlarm.vue",
        // Campo de credencial de la configuración global (contraseña SMTP,
        // tokens de Twilio y Mesh, clave de API del asistente de IA).
        "src/components/ui/SecretInput.vue",
      ],
      extends: ["plugin:@intlify/vue-i18n/recommended"],
      rules: {
        // "Observer RMM" es el nombre de marca: literal por diseño, no se traduce.
        "@intlify/vue-i18n/no-raw-text": [
          "error",
          { ignoreText: ["Observer RMM"] },
        ],
        "@intlify/vue-i18n/no-missing-keys": "error",
      },
    },
  ],
};
