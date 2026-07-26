<template>
  <q-card>
    <q-bar v-if="modal">
      <q-btn @click="search" class="q-mr-sm" dense flat push icon="refresh" />
      <q-space />{{ $t("auditManager.title") }}
      <q-space />
      <q-btn dense flat icon="close" v-close-popup>
        <q-tooltip class="bg-white text-primary">{{
          $t("auditManager.close")
        }}</q-tooltip>
      </q-btn>
    </q-bar>
    <q-table
      @request="onRequest"
      :title="modal ? $t('auditManager.tableTitle') : ''"
      :rows="auditLogs"
      :columns="columns"
      class="tabs-tbl-sticky"
      :table-class="{
        'table-bgcolor': !$q.dark.isActive,
        'table-bgcolor-dark': $q.dark.isActive,
      }"
      :style="{
        'max-height': tabHeight ? tabHeight : `${$q.screen.height - 33}px`,
      }"
      row-key="id"
      dense
      binary-state-sort
      v-model:pagination="pagination"
      :rows-per-page-options="[25, 50, 100, 500, 1000]"
      :no-data-label="tableNoDataText"
      @row-click="openAuditDetail"
      virtual-scroll
      :loading="loading"
    >
      <template v-slot:top>
        <q-btn
          v-if="agent"
          class="q-pr-sm"
          dense
          flat
          push
          @click="search"
          icon="refresh"
        />
        <q-option-group
          v-if="!agent"
          class="q-pr-sm"
          v-model="filterType"
          :options="filterTypeOptions"
          color="primary"
        />
        <observer-dropdown
          v-if="filterType === 'agents' && !agent"
          class="q-pr-sm"
          style="width: 200px"
          v-model="agentFilter"
          :options="agentOptions"
          :label="$t('auditManager.filterAgent')"
          clearable
          mapOptions
          multiple
          filled
          filterable
        />
        <observer-dropdown
          v-if="filterType === 'clients' && !agent"
          class="q-pr-sm"
          style="width: 200px"
          v-model="clientFilter"
          :options="clientOptions"
          :label="$t('auditManager.filterClients')"
          clearable
          multiple
          filled
          mapOptions
          filterable
        />
        <observer-dropdown
          class="q-pr-sm"
          style="width: 200px"
          v-model="userFilter"
          :options="userOptions"
          :label="$t('auditManager.filterUsers')"
          clearable
          filled
          multiple
        />
        <observer-dropdown
          class="q-pr-sm"
          style="width: 200px"
          v-model="actionFilter"
          :options="actionOptions"
          :label="$t('auditManager.filterAction')"
          clearable
          filled
          multiple
          mapOptions
        />
        <observer-dropdown
          class="q-pr-sm"
          style="width: 200px"
          v-if="!agent"
          v-model="objectFilter"
          :options="objectOptions"
          :label="$t('auditManager.filterObject')"
          clearable
          filled
          multiple
          mapOptions
        />
        <observer-dropdown
          class="q-pr-sm"
          style="width: 200px"
          v-model="timeFilter"
          :options="timeOptions"
          :label="$t('auditManager.filterTime')"
          filled
          mapOptions
        />
        <q-btn
          v-if="!agent"
          color="primary"
          :label="$t('auditManager.search')"
          @click="search"
        />

        <q-space />
        <export-table-btn :data="auditLogs" :columns="columns" />
      </template>
      <template v-slot:body-cell-action="props">
        <q-td :props="props">
          <div>
            <q-badge
              :color="formatActionColor(props.value)"
              :label="props.value"
            />
          </div>
        </q-td>
      </template>
      <template v-slot:body-cell-client="props">
        <q-td :props="props">
          <span v-if="props.value">{{ props.value.client_name }}</span>
        </q-td>
      </template>
      <template v-slot:body-cell-site="props">
        <q-td :props="props">
          <span v-if="props.value">{{ props.value.name }}</span>
        </q-td>
      </template>

      <template v-slot:body-cell-entry_time="props">
        <q-td :props="props">
          {{ formatDate(props.value) }}
        </q-td>
      </template>
    </q-table>
  </q-card>
</template>

<script>
// composition imports
import { ref, computed, watch, onMounted } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { useClientDropdown } from "@/composables/clients";
import { useAgentDropdown } from "@/composables/agents";
import { useUserDropdown } from "@/composables/accounts";
import { useQuasar } from "quasar";
import { fetchAuditLog } from "@/api/logs";
import { formatTableColumnText } from "@/utils/format";

// ui imported
import AuditLogDetailModal from "@/components/logs/AuditLogDetailModal.vue";
import ExportTableBtn from "@/components/ui/ExportTableBtn.vue";
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

export default {
  name: "AuditManager",
  components: { ObserverDropdown, ExportTableBtn },
  props: {
    agent: String,
    tabHeight: String,
    modal: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    // setup vuex
    const store = useStore();
    const { t } = useI18n();
    const formatDate = computed(() => store.getters.formatDate);
    const dash_positive_color = computed(() => store.state.dash_positive_color);
    const dash_negative_color = computed(() => store.state.dash_negative_color);
    const dash_warning_color = computed(() => store.state.dash_warning_color);

    // setup dropdowns
    const { clientOptions, getClientOptions } = useClientDropdown();
    const { agentOptions, getAgentOptions } = useAgentDropdown();
    const { userOptions, getUserOptions } = useUserDropdown();

    // i18n-aware columns/options (computed for language reactivity)
    const columns = computed(() => [
      {
        name: "entry_time",
        label: t("auditManager.colTime"),
        field: "entry_time",
        align: "left",
        sortable: true,
      },
      {
        name: "username",
        label: t("auditManager.colUsername"),
        field: "username",
        align: "left",
        sortable: true,
      },
      {
        name: "agent",
        label: t("auditManager.colAgent"),
        field: "agent",
        align: "left",
        sortable: true,
      },
      {
        name: "client",
        label: t("auditManager.colClient"),
        field: "site",
        align: "left",
        sortable: true,
      },
      {
        name: "site",
        label: t("auditManager.colSite"),
        field: "site",
        align: "left",
        sortable: true,
      },
      {
        name: "action",
        label: t("auditManager.colAction"),
        field: "action",
        align: "left",
        sortable: true,
        format: (val) => formatTableColumnText(val),
      },
      {
        name: "object_type",
        label: t("auditManager.colObject"),
        field: "object_type",
        align: "left",
        sortable: true,
        format: (val) => formatTableColumnText(val),
      },
      {
        name: "message",
        label: t("auditManager.colMessage"),
        field: "message",
        align: "left",
        sortable: true,
      },
      {
        name: "client_ip",
        label: t("auditManager.colClientIp"),
        field: "ip_address",
        align: "left",
        sortable: true,
      },
    ]);

    const agentActionOptions = computed(() => [
      { value: "add", label: t("auditManager.actAdd") },
      { value: "modify", label: t("auditManager.actModify") },
      { value: "execute_command", label: t("auditManager.actExecuteCommand") },
      { value: "execute_script", label: t("auditManager.actExecuteScript") },
      { value: "remote_session", label: t("auditManager.actRemoteSession") },
      {
        // feature 028: lock / alert / alarm. Es su propia categoría para poder
        // responder "¿quién me bloqueó la sesión?" sin filtrar entre comandos.
        value: "endpoint_response",
        label: t("auditManager.actEndpointResponse"),
      },
      { value: "url_action", label: t("auditManager.actUrlAction") },
    ]);

    const extraActionOptions = computed(() => [
      { value: "agent_install", label: t("auditManager.actAgentInstall") },
      { value: "bulk_action", label: t("auditManager.actBulkAction") },
      { value: "delete", label: t("auditManager.actDelete") },
      { value: "failed_login", label: t("auditManager.actFailedLogin") },
      { value: "login", label: t("auditManager.actLogin") },
      { value: "modify", label: t("auditManager.actModify") },
      { value: "task_run", label: t("auditManager.actTaskRun") },
    ]);

    const actionOptions = computed(() =>
      props.agent
        ? [...agentActionOptions.value]
        : [...agentActionOptions.value, ...extraActionOptions.value],
    );

    const objectOptions = computed(() => [
      { value: "agent", label: t("auditManager.objAgent") },
      { value: "automatedtask", label: t("auditManager.objAutomatedTask") },
      { value: "bulk", label: t("auditManager.objBulk") },
      { value: "coresettings", label: t("auditManager.objCoreSettings") },
      { value: "check", label: t("auditManager.objCheck") },
      { value: "client", label: t("auditManager.objClient") },
      { value: "policy", label: t("auditManager.objPolicy") },
      { value: "site", label: t("auditManager.objSite") },
      { value: "script", label: t("auditManager.objScript") },
      { value: "user", label: t("auditManager.objUser") },
      { value: "winupdatepolicy", label: t("auditManager.objPatchPolicy") },
      { value: "alerttemplate", label: t("auditManager.objAlertTemplate") },
      { value: "role", label: t("auditManager.objRole") },
      { value: "urlaction", label: t("auditManager.objUrlAction") },
      { value: "keystore", label: t("auditManager.objKeyStore") },
      { value: "customfield", label: t("auditManager.objCustomField") },
      { value: "schedule", label: t("auditManager.objSchedule") },
      { value: "reportschedule", label: t("auditManager.objReportSchedule") },
    ]);

    const timeOptions = computed(() => [
      { value: 1, label: t("auditManager.time1Day") },
      { value: 7, label: t("auditManager.time1Week") },
      { value: 30, label: t("auditManager.time30Days") },
      { value: 90, label: t("auditManager.time3Months") },
      { value: 180, label: t("auditManager.time6Months") },
      { value: 365, label: t("auditManager.time1Year") },
      { value: 0, label: t("auditManager.timeEverything") },
    ]);

    const filterTypeOptions = computed(() => [
      { label: t("auditManager.optClients"), value: "clients" },
      { label: t("auditManager.optAgents"), value: "agents" },
    ]);

    // setup main audit log functionality
    const auditLogs = ref([]);
    const agentFilter = ref(null);
    const userFilter = ref(null);
    const actionFilter = ref(null);
    const clientFilter = ref(null);
    const objectFilter = ref(null);
    const timeFilter = ref(7);
    const filterType = ref("clients");
    const loading = ref(false);
    const searched = ref(false);

    const pagination = ref({
      rowsPerPage: 25,
      rowsNumber: null,
      sortBy: "entry_time",
      descending: true,
      page: 1,
    });

    async function search() {
      loading.value = true;
      searched.value = true;

      const data = {
        pagination: pagination.value,
      };

      if (agentFilter.value && agentFilter.value.length > 0)
        data["agentFilter"] = agentFilter.value;
      else if (clientFilter.value && clientFilter.value.length > 0)
        data["clientFilter"] = clientFilter.value;
      if (userFilter.value && userFilter.value.length > 0)
        data["userFilter"] = userFilter.value;
      if (timeFilter.value) data["timeFilter"] = timeFilter.value;
      if (actionFilter.value && actionFilter.value.length > 0)
        data["actionFilter"] = actionFilter.value;
      if (objectFilter.value && objectFilter.value.length > 0)
        data["objectFilter"] = objectFilter.value;
      try {
        const { audit_logs, total } = await fetchAuditLog(data);
        auditLogs.value = audit_logs;
        pagination.value.rowsNumber = total;
      } catch (e) {}

      loading.value = false;
    }

    function onRequest(data) {
      const { page, rowsPerPage, sortBy, descending } = data.pagination;

      pagination.value.page = page;
      pagination.value.rowsPerPage = rowsPerPage;
      pagination.value.sortBy = sortBy;
      pagination.value.descending = descending;

      search();
    }

    // audit detail modal
    const { dialog } = useQuasar();
    function openAuditDetail(evt, log) {
      dialog({
        component: AuditLogDetailModal,
        componentProps: {
          log,
        },
      });
    }

    function formatActionColor(action) {
      switch (action.toLowerCase()) {
        case "modify":
          return dash_warning_color.value;
        case "add":
        case "agent_install":
          return dash_positive_color.value;
        case "delete":
        case "failed_login":
          return dash_negative_color.value;
        default:
          return "primary";
      }
    }

    // watchers
    watch(filterType, () => {
      agentFilter.value = null;
      clientFilter.value = null;
    });

    if (props.agent) {
      agentFilter.value = [props.agent];
      watch([userFilter, actionFilter, timeFilter], search);
      watch(
        () => props.agent,
        (newValue) => {
          if (newValue) {
            agentFilter.value = [props.agent];
            search();
          }
        },
      );
    }

    // vue component hooks
    onMounted(() => {
      if (!props.agent) {
        getClientOptions();
        getAgentOptions();
      } else {
        search();
      }

      getUserOptions(true);
    });

    return {
      // data
      auditLogs,
      agentFilter,
      userFilter,
      actionFilter,
      clientFilter,
      objectFilter,
      timeFilter,
      filterType,
      loading,
      searched,
      pagination,
      userOptions,

      // dropdowns
      clientOptions,
      agentOptions,

      // i18n-aware columns/options
      columns,
      actionOptions,
      objectOptions,
      timeOptions,
      filterTypeOptions,

      //computed
      tableNoDataText: computed(() =>
        searched.value
          ? t("auditManager.noDataSearched")
          : t("auditManager.noDataInitial"),
      ),

      // methods
      search,
      onRequest,
      openAuditDetail,
      formatActionColor,
      formatDate,
    };
  },
};
</script>
