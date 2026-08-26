<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="min-width: 75vw; max-heigth: 75vh" class="q-dialog-plugin">
      <q-bar>
        {{
          localRole ? $t("rolesForm.titleEditing") : $t("rolesForm.titleAdding")
        }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup />
      </q-bar>
      <q-form ref="form" @submit="onSubmit">
        <q-card-section class="row">
          <q-input
            :label="$t('rolesForm.roleName')"
            class="col-6"
            dense
            outlined
            v-model="localRole.name"
            :rules="[(val) => !!val || $t('rolesForm.required')]"
          />
        </q-card-section>
        <q-card-section class="scroll" style="height: 70vh">
          <!-- Permissions -->
          <div class="text-subtitle2">{{ $t("rolesForm.secSuperUser") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.is_superuser"
                :label="$t('rolesForm.superUser')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secReporting") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_view_reports"
                :label="$t('rolesForm.reportingViewer')"
              />
              <q-checkbox
                v-model="localRole.can_manage_reports"
                :label="$t('rolesForm.reportingManager')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secAccounts") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_accounts"
                :label="$t('rolesForm.listUserAccounts')"
              />
              <q-checkbox
                v-model="localRole.can_manage_accounts"
                :label="$t('rolesForm.manageUserAccounts')"
              />
              <q-checkbox
                v-model="localRole.can_list_roles"
                :label="$t('rolesForm.listRoles')"
              />
              <q-checkbox
                v-model="localRole.can_manage_roles"
                :label="$t('rolesForm.manageRoles')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secAgents") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_agents"
                :label="$t('rolesForm.listAgents')"
              />
              <q-checkbox
                v-model="localRole.can_list_agent_history"
                :label="$t('rolesForm.listAgentHistory')"
              />
              <q-checkbox
                v-model="localRole.can_use_mesh"
                :label="$t('rolesForm.useMeshCentral')"
              />
              <q-checkbox
                v-model="localRole.can_uninstall_agents"
                :label="$t('rolesForm.uninstallAgents')"
              />
              <q-checkbox
                v-model="localRole.can_update_agents"
                :label="$t('rolesForm.updateAgents')"
              />
              <q-checkbox
                v-model="localRole.can_edit_agent"
                :label="$t('rolesForm.editAgents')"
              />
              <q-checkbox
                v-model="localRole.can_manage_procs"
                :label="$t('rolesForm.manageProcesses')"
              />
              <q-checkbox
                v-model="localRole.can_view_eventlogs"
                :label="$t('rolesForm.viewEventLogs')"
              />
              <q-checkbox
                v-model="localRole.can_send_cmd"
                :label="$t('rolesForm.sendCommand')"
              />
              <q-checkbox
                v-model="localRole.can_reboot_agents"
                :label="$t('rolesForm.rebootAgents')"
              />
              <q-checkbox
                v-model="localRole.can_send_wol"
                :label="$t('rolesForm.wolAgents')"
              />
              <q-checkbox
                v-model="localRole.can_install_agents"
                :label="$t('rolesForm.installAgents')"
              />
              <q-checkbox
                v-model="localRole.can_run_scripts"
                :label="$t('rolesForm.runScript')"
              />
              <q-checkbox
                v-model="localRole.can_run_bulk"
                :label="$t('rolesForm.bulkActions')"
              />
              <q-checkbox
                v-model="localRole.can_recover_agents"
                :label="$t('rolesForm.recoverAgents')"
              />
              <q-checkbox
                v-model="localRole.can_use_registry"
                :label="$t('rolesForm.useRegistry')"
              />
              <!-- respuesta rápida de endpoint (feature 028) -->
              <q-checkbox
                v-model="localRole.can_send_alerts"
                :label="$t('rolesForm.sendAlerts')"
              />
              <q-checkbox
                v-model="localRole.can_lock_agents"
                :label="$t('rolesForm.lockAgents')"
              />
              <q-checkbox
                v-model="localRole.can_sound_alarm"
                :label="$t('rolesForm.soundAlarm')"
              />
              <!-- modo perdido/robado (feature 030) -->
              <q-checkbox
                v-model="localRole.can_manage_lost_mode"
                :label="$t('rolesForm.manageLostMode')"
              />
              <q-checkbox
                v-model="localRole.can_view_lost_evidence"
                :label="$t('rolesForm.viewLostEvidence')"
              />
            </div>
          </q-card-section>

          <!-- Observer Erase (feature 039). `can_wipe_device` es la llave del
               borrado destructivo: separada del modo perdido y off por omisión.
               Ver certificados y gestionar ingresos son permisos aparte, más
               laxos. -->
          <div class="text-subtitle2">{{ $t("rolesForm.secErase") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_wipe_device"
                :label="$t('rolesForm.wipeDevice')"
              />
              <q-checkbox
                v-model="localRole.can_view_erase_certificates"
                :label="$t('rolesForm.viewEraseCertificates')"
              />
              <q-checkbox
                v-model="localRole.can_manage_asset_intake"
                :label="$t('rolesForm.manageAssetIntake')"
              />
              <!-- fileretrieval (feature 042): recuperar archivos antes de
                   borrar. Permiso liviano, separado de can_wipe_device: recuperar
                   no es destruir. -->
              <q-checkbox
                v-model="localRole.can_retrieve_files"
                :label="$t('rolesForm.retrieveFiles')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secCore") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_notes"
                :label="$t('rolesForm.listNotes')"
              />
              <q-checkbox
                v-model="localRole.can_manage_notes"
                :label="$t('rolesForm.manageNotes')"
              />
              <q-checkbox
                v-model="localRole.can_view_core_settings"
                :label="$t('rolesForm.viewGlobalSettings')"
              />
              <q-checkbox
                v-model="localRole.can_edit_core_settings"
                :label="$t('rolesForm.editGlobalSettings')"
              />
              <q-checkbox
                v-model="localRole.can_view_global_keystore"
                :label="$t('rolesForm.viewGlobalKeyStore')"
              />
              <q-checkbox
                v-model="localRole.can_edit_global_keystore"
                :label="$t('rolesForm.editGlobalKeyStore')"
              />
              <q-checkbox
                v-model="localRole.can_do_server_maint"
                :label="$t('rolesForm.doServerMaintenance')"
              />
              <q-checkbox
                v-model="localRole.can_code_sign"
                :label="$t('rolesForm.manageCodeSigning')"
              />
              <q-checkbox
                v-model="localRole.can_list_api_keys"
                :label="$t('rolesForm.listApiKeys')"
              />
              <q-checkbox
                v-model="localRole.can_manage_api_keys"
                :label="$t('rolesForm.manageApiKeys')"
              />
              <q-checkbox
                v-model="localRole.can_run_urlactions"
                :label="$t('rolesForm.runUrlActions')"
              />
              <q-checkbox
                v-model="localRole.can_view_customfields"
                :label="$t('rolesForm.viewCustomFields')"
              />
              <q-checkbox
                v-model="localRole.can_manage_customfields"
                :label="$t('rolesForm.editCustomFields')"
              />
              <q-checkbox
                v-model="localRole.can_view_schedules"
                :label="$t('rolesForm.listSchedules')"
              />
              <q-checkbox
                v-model="localRole.can_manage_schedules"
                :label="$t('rolesForm.manageSchedules')"
              />
              <q-checkbox
                v-if="!hosted"
                v-model="localRole.can_use_webterm"
                :label="$t('rolesForm.useServerWebTerminal')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secChecks") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_checks"
                :label="$t('rolesForm.listChecks')"
              />
              <q-checkbox
                v-model="localRole.can_manage_checks"
                :label="$t('rolesForm.manageChecks')"
              />
              <q-checkbox
                v-model="localRole.can_run_checks"
                :label="$t('rolesForm.runChecks')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secClients") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_clients"
                :label="$t('rolesForm.listClients')"
              />
              <q-checkbox
                v-model="localRole.can_manage_clients"
                :label="$t('rolesForm.manageClients')"
              />
              <q-checkbox
                v-model="localRole.can_list_sites"
                :label="$t('rolesForm.listSites')"
              />
              <q-checkbox
                v-model="localRole.can_manage_sites"
                :label="$t('rolesForm.manageSites')"
              />
              <q-checkbox
                v-model="localRole.can_list_deployments"
                :label="$t('rolesForm.listDeployments')"
              />
              <q-checkbox
                v-model="localRole.can_manage_deployments"
                :label="$t('rolesForm.manageDeployments')"
              />
            </div>
          </q-card-section>

          <q-card-section class="row">
            <observer-dropdown
              class="col-6"
              :label="$t('rolesForm.allowedClients')"
              :options="clientOptions"
              v-model="localRole.can_view_clients"
              :hint="$t('rolesForm.allowedClientsHint')"
              outlined
              mapOptions
              multiple
              filterable
            />
          </q-card-section>
          <q-card-section class="row">
            <observer-dropdown
              class="col-6"
              :label="$t('rolesForm.allowedSites')"
              :options="siteOptions"
              v-model="localRole.can_view_sites"
              :hint="$t('rolesForm.allowedSitesHint')"
              outlined
              mapOptions
              multiple
              filterable
            />
          </q-card-section>

          <div class="text-subtitle2">
            {{ $t("rolesForm.secAutomationPolicies") }}
          </div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_automation_policies"
                :label="$t('rolesForm.listAutomationPolicies')"
              />
              <q-checkbox
                v-model="localRole.can_manage_automation_policies"
                :label="$t('rolesForm.manageAutomationPolicies')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secTasks") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_autotasks"
                :label="$t('rolesForm.listTasks')"
              />
              <q-checkbox
                v-model="localRole.can_manage_autotasks"
                :label="$t('rolesForm.manageTasks')"
              />
              <q-checkbox
                v-model="localRole.can_run_autotasks"
                :label="$t('rolesForm.runTasks')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secLogs") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_view_auditlogs"
                :label="$t('rolesForm.viewAuditLogs')"
              />
              <q-checkbox
                v-model="localRole.can_view_debuglogs"
                :label="$t('rolesForm.viewDebugLogs')"
              />
              <q-checkbox
                v-model="localRole.can_list_pendingactions"
                :label="$t('rolesForm.listPendingActions')"
              />
              <q-checkbox
                v-model="localRole.can_manage_pendingactions"
                :label="$t('rolesForm.managePendingActions')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secScripts") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_scripts"
                :label="$t('rolesForm.listScripts')"
              />
              <q-checkbox
                v-model="localRole.can_manage_scripts"
                :label="$t('rolesForm.manageScripts')"
              />
              <q-checkbox
                v-if="!hosted"
                v-model="localRole.can_run_server_scripts"
                :label="$t('rolesForm.runServerScripts')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secAlerts") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_alerts"
                :label="$t('rolesForm.listAlerts')"
              />
              <q-checkbox
                v-model="localRole.can_manage_alerts"
                :label="$t('rolesForm.manageAlerts')"
              />
              <q-checkbox
                v-model="localRole.can_list_alerttemplates"
                :label="$t('rolesForm.listAlertTemplates')"
              />
              <q-checkbox
                v-model="localRole.can_manage_alerttemplates"
                :label="$t('rolesForm.manageAlertTemplates')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secWinServices") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_manage_winsvcs"
                :label="$t('rolesForm.manageWinServices')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secSoftware") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_list_software"
                :label="$t('rolesForm.listSoftware')"
              />
              <q-checkbox
                v-model="localRole.can_manage_software"
                :label="$t('rolesForm.manageSoftware')"
              />
            </div>
          </q-card-section>

          <div class="text-subtitle2">{{ $t("rolesForm.secWinUpdates") }}</div>
          <q-separator />
          <q-card-section class="row">
            <div class="q-gutter-sm">
              <q-checkbox
                v-model="localRole.can_manage_winupdates"
                :label="$t('rolesForm.manageWinUpdates')"
              />
            </div>
          </q-card-section>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn dense flat :label="$t('rolesForm.cancel')" v-close-popup />
          <q-btn
            :loading="loading"
            dense
            flat
            :label="$t('rolesForm.save')"
            color="primary"
            type="submit"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import { computed, ref, watch } from "vue";
import { useStore } from "vuex";
import { useDialogPluginComponent } from "quasar";
import { saveRole, editRole } from "@/api/accounts";
import { useClientDropdown, useSiteDropdown } from "@/composables/clients";
import { notifySuccess } from "@/utils/notify";

// ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

export default {
  components: { ObserverDropdown },
  name: "RolesForm",
  emits: [...useDialogPluginComponent.emits],
  props: { role: Object },
  setup(props) {
    // quasar setup
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();

    // store
    const store = useStore();
    const hosted = computed(() => store.state.hosted);

    // dropdown setup
    const { clientOptions } = useClientDropdown(true);
    const { siteOptions } = useSiteDropdown(true);

    const role = props.role
      ? ref(Object.assign({}, props.role))
      : ref({
          name: "",
          is_superuser: false,
          // agent perms
          can_list_agents: false,
          can_recover_agents: false,
          can_use_mesh: false,
          can_uninstall_agents: false,
          can_update_agents: false,
          can_edit_agent: false,
          can_manage_procs: false,
          can_view_eventlogs: false,
          can_send_cmd: false,
          can_reboot_agents: false,
          can_install_agents: false,
          can_run_scripts: false,
          can_run_bulk: false,
          can_manage_winsvcs: false,
          can_list_agent_history: false,
          can_send_wol: false,
          // software perms
          can_list_software: false,
          can_manage_software: false,
          // note perms
          can_list_notes: false,
          can_manage_notes: false,
          // settings perms
          can_view_core_settings: false,
          can_edit_core_settings: false,
          can_view_global_keystore: false,
          can_edit_global_keystore: false,
          can_do_server_maint: false,
          can_code_sign: false,
          can_run_urlactions: false,
          can_view_customfields: false,
          can_manage_customfields: false,
          can_view_schedules: false,
          can_manage_schedules: false,
          // api key perms
          can_list_api_keys: false,
          can_manage_api_keys: false,
          // check perms
          can_list_checks: false,
          can_manage_checks: false,
          can_run_checks: false,
          // client perms
          can_list_clients: false,
          can_manage_clients: false,
          can_list_sites: false,
          can_manage_sites: false,
          // deployment perms
          can_list_deployments: false,
          can_manage_deployments: false,
          // automation perms
          can_list_automation_policies: false,
          can_manage_automation_policies: false,
          // task perms
          can_list_autotasks: false,
          can_manage_autotasks: false,
          can_run_autotasks: false,
          // log perms
          can_view_auditlogs: false,
          can_view_debuglogs: false,
          can_list_pendingactions: false,
          can_manage_pendingactions: false,
          // script perms
          can_list_scripts: false,
          can_manage_scripts: false,
          // alert perms
          can_list_alerts: false,
          can_manage_alerts: false,
          can_list_alerttemplates: false,
          can_manage_alerttemplates: false,
          // update perms
          can_manage_winupdates: false,
          // account perms
          can_list_accounts: false,
          can_manage_accounts: false,
          can_list_roles: false,
          can_manage_roles: false,
          can_view_clients: [],
          can_view_sites: [],
          // server scripts and web terminal
          can_run_server_scripts: false,
          can_use_webterm: false,
          // reporting perms
          can_view_reports: false,
          can_manage_reports: false,
          can_use_registry: false,
          // respuesta rápida de endpoint (feature 028)
          can_send_alerts: false,
          can_lock_agents: false,
          can_sound_alarm: false,
          // modo perdido/robado (feature 030)
          can_manage_lost_mode: false,
          can_view_lost_evidence: false,
          // Observer Erase (feature 039). El borrado destructivo off por
          // omisión (ADR-029); ver certificados y gestionar ingresos aparte.
          can_wipe_device: false,
          can_view_erase_certificates: false,
          can_manage_asset_intake: false,
          // fileretrieval (feature 042): recuperar antes de borrar, off por omisión.
          can_retrieve_files: false,
        });

    const loading = ref(false);

    async function onSubmit() {
      loading.value = true;
      try {
        const result = props.role
          ? await editRole(role.value.id, role.value)
          : await saveRole(role.value);
        notifySuccess(result);
        onDialogOK();
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    watch(
      () => role.value.is_superuser,
      (newValue) => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        Object.keys(role.value).forEach((key, index) => {
          if (typeof role.value[key] === "boolean") {
            role.value[key] = newValue;
          }
        });
      },
    );

    return {
      // reactive data
      localRole: role,
      loading,
      clientOptions,
      siteOptions,
      hosted,

      onSubmit,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
