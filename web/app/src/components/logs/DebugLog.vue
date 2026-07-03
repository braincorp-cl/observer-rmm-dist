<template>
  <q-card>
    <q-bar v-if="modal">
      <q-btn
        @click="getDebugLog"
        class="q-mr-sm"
        dense
        flat
        push
        icon="refresh"
      />{{ $t("debugLog.title") }}
      <q-space />
      <q-btn dense flat icon="close" v-close-popup>
        <q-tooltip content-class="bg-white text-primary">{{
          $t("debugLog.close")
        }}</q-tooltip>
      </q-btn>
    </q-bar>
    <q-table
      :table-class="{
        'table-bgcolor': !$q.dark.isActive,
        'table-bgcolor-dark': $q.dark.isActive,
      }"
      class="tabs-tbl-sticky"
      :style="{
        'max-height': tabHeight ? tabHeight : `${$q.screen.height - 33}px`,
      }"
      :rows="debugLog"
      :columns="columns"
      :title="modal ? $t('debugLog.tableTitle') : ''"
      :pagination="{ sortBy: 'entry_time', descending: true, rowsPerPage: 0 }"
      :loading="loading"
      :filter="filter"
      virtual-scroll
      dense
      binary-state-sort
      :rows-per-page-options="[0]"
    >
      <template v-slot:top>
        <q-btn
          v-if="agent"
          class="q-pr-sm"
          dense
          flat
          push
          @click="getDebugLog"
          icon="refresh"
        />
        <observer-dropdown
          v-if="!agent"
          class="q-pr-sm"
          style="width: 250px"
          v-model="agentFilter"
          :label="$t('debugLog.agentsFilter')"
          :options="agentOptions"
          mapOptions
          outlined
          clearable
          filterable
        />
        <observer-dropdown
          class="q-pr-sm"
          style="width: 250px"
          v-model="logTypeFilter"
          :label="$t('debugLog.logTypeFilter')"
          :options="logTypeOptions"
          mapOptions
          outlined
          clearable
        />
        <q-radio
          v-model="logLevelFilter"
          :color="dash_info_color"
          val="info"
          :label="$t('debugLog.levelInfo')"
        />
        <q-radio
          v-model="logLevelFilter"
          :color="dash_negative_color"
          val="critical"
          :label="$t('debugLog.levelCritical')"
        />
        <q-radio
          v-model="logLevelFilter"
          :color="dash_negative_color"
          val="error"
          :label="$t('debugLog.levelError')"
        />
        <q-radio
          v-model="logLevelFilter"
          :color="dash_warning_color"
          val="warning"
          :label="$t('debugLog.levelWarning')"
        />
        <q-space />
        <q-input
          v-model="filter"
          outlined
          :label="$t('debugLog.search')"
          dense
          clearable
          class="q-pr-sm"
        >
          <template v-slot:prepend>
            <q-icon name="search" color="primary" />
          </template>
        </q-input>
        <export-table-btn :data="debugLog" :columns="columns" />
      </template>

      <template v-slot:top-row>
        <q-tr v-if="Array.isArray(debugLog) && debugLog.length === 1000">
          <q-td colspan="100%">
            <q-icon name="warning" :color="dash_warning_color" />
            {{ $t("debugLog.limitWarning") }}
          </q-td>
        </q-tr>
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
// composition api
import { ref, toRef, watch, computed, onMounted } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { useAgentDropdown } from "@/composables/agents";
import { fetchDebugLog } from "@/api/logs";
import { formatTableColumnText } from "@/utils/format";

// ui components
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";
import ExportTableBtn from "@/components/ui/ExportTableBtn.vue";

export default {
  name: "LogModal",
  components: {
    ObserverDropdown,
    ExportTableBtn,
  },
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
    const dash_info_color = computed(() => store.state.dash_info_color);
    const dash_positive_color = computed(() => store.state.dash_positive_color);
    const dash_negative_color = computed(() => store.state.dash_negative_color);
    const dash_warning_color = computed(() => store.state.dash_warning_color);

    // setup dropdowns
    const { agentOptions, getAgentOptions } = useAgentDropdown();

    // i18n-aware columns/options (computed for language reactivity)
    const logTypeOptions = computed(() => [
      { label: t("debugLog.typeAgentUpdate"), value: "agent_update" },
      { label: t("debugLog.typeAgentIssues"), value: "agent_issues" },
      { label: t("debugLog.typeWindowsUpdates"), value: "windows_updates" },
      { label: t("debugLog.typeSystemIssues"), value: "system_issues" },
      { label: t("debugLog.typeScripting"), value: "scripting" },
    ]);

    const columns = computed(() => [
      {
        name: "entry_time",
        label: t("debugLog.colTime"),
        field: "entry_time",
        align: "left",
        sortable: true,
      },
      {
        name: "log_level",
        label: t("debugLog.colLogLevel"),
        field: "log_level",
        align: "left",
        sortable: true,
      },
      {
        name: "agent",
        label: t("debugLog.colAgent"),
        field: "agent",
        align: "left",
        sortable: true,
      },
      {
        name: "log_type",
        label: t("debugLog.colLogType"),
        field: "log_type",
        align: "left",
        sortable: true,
        format: (val) => formatTableColumnText(val),
      },
      {
        name: "message",
        label: t("debugLog.colMessage"),
        field: "message",
        align: "left",
        sortable: true,
      },
    ]);

    // set main debug log functionality
    const debugLog = ref([]);
    const agentFilter = props.agent ? toRef(props, "agent") : ref(null);
    const logLevelFilter = ref("info");
    const logTypeFilter = ref(null);
    const loading = ref(false);
    const filter = ref("");

    async function getDebugLog() {
      loading.value = true;
      try {
        const data = {
          logLevelFilter: logLevelFilter.value,
        };
        if (agentFilter.value) data["agentFilter"] = agentFilter.value;
        if (logTypeFilter.value) data["logTypeFilter"] = logTypeFilter.value;

        debugLog.value = await fetchDebugLog(data);
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    if (props.agent) {
      watch(
        () => props.agent,
        (newValue) => {
          if (newValue) {
            agentFilter.value = props.agent;
            getDebugLog();
          }
        },
      );
    }

    // watchers
    watch([logLevelFilter, agentFilter, logTypeFilter], getDebugLog);

    // vue component hooks
    onMounted(() => {
      if (!props.agent) getAgentOptions();
      getDebugLog();
    });

    return {
      // data
      debugLog,
      logLevelFilter,
      logTypeFilter,
      agentFilter,
      agentOptions,
      loading,
      filter,
      dash_info_color,
      dash_positive_color,
      dash_warning_color,
      dash_negative_color,

      // i18n-aware columns/options
      columns,
      logTypeOptions,

      // methods
      getDebugLog,
      formatDate,
    };
  },
};
</script>
