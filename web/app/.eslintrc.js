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
      // UserForm / UserResetPasswordForm. (RolesForm: 2 refs legacy "TRMM
      // Server" debrandeadas a "Observer" al migrar, regla cero-tactical.)
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
        // Ola 8f: chicos varios (App/ObserverTable limpios). AgentDownload DIFERIDO
        // (bloques <code> con flags CLI requieren decisión de config del gate).
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
