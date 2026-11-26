<template>
  <q-dialog ref="dialog" @hide="onHide">
    <q-card class="q-dialog-plugin" style="min-width: 70vw">
      <q-bar>
        <q-btn
          ref="refresh"
          @click="refresh"
          class="q-mr-sm"
          dense
          flat
          push
          icon="refresh"
        />
        <span class="ellipsis" style="min-width: 0">{{ title }}</span>
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip>{{ $t("policyStatus.close") }}</q-tooltip>
        </q-btn>
      </q-bar>
      <!-- V2-G15: patrón de rejilla (composables/rejillaTabla.js). La tabla es UNA
           parada de tabulador (el host del nombre de equipo), las flechas mueven la
           fila y la flecha derecha llega al botón «Salida». Los oyentes de la raíz
           atajan el foco cuando el reciclaje lo sube al scroller. -->
      <q-card-section @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
        <q-table
          ref="tablaRejilla"
          @virtual-scroll="alDesplazarVirtual"
          style="max-height: 35vh"
          :table-class="{
            'table-bgcolor': !$q.dark.isActive,
            'table-bgcolor-dark': $q.dark.isActive,
          }"
          class="tabs-tbl-sticky"
          :rows="data"
          :columns="columns"
          v-model:pagination="pagination"
          :rows-per-page-options="[0]"
          row-key="id"
          binary-state-sort
          dense
          virtual-scroll
          hide-pagination
          :no-data-label="$t('policyStatus.noAgents')"
        >
          <!-- header slots -->
          <template v-slot:header-cell-statusicon="props">
            <q-th auto-width :props="props"></q-th>
          </template>
          <!-- body slots -->
          <template v-slot:body="props">
            <q-tr :props="props">
              <!-- tds -->
              <!-- agent hostname -->
              <q-td>
                <span
                  class="obs-rej__host"
                  :data-fila="props.rowIndex"
                  :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                  @focus="filaFoco = props.rowIndex"
                  >{{ props.row.hostname }}</span
                >
              </q-td>
              <!-- status icon -->
              <q-td v-if="props.row.status === 'passing'">
                <q-icon
                  style="font-size: 1.3rem"
                  :color="dash_positive_color"
                  name="check_circle"
                >
                  <q-tooltip>{{ $t("policyStatus.passing") }}</q-tooltip>
                </q-icon>
              </q-td>
              <q-td v-else-if="props.row.status === 'failing'">
                <q-icon
                  v-if="props.row.alert_severity === 'info'"
                  style="font-size: 1.3rem"
                  :color="dash_info_color"
                  name="info"
                >
                  <q-tooltip>{{ $t("policyStatus.informational") }}</q-tooltip>
                </q-icon>
                <q-icon
                  v-else-if="props.row.alert_severity === 'warning'"
                  style="font-size: 1.3rem"
                  :color="dash_warning_color"
                  name="warning"
                >
                  <q-tooltip>{{ $t("policyStatus.warning") }}</q-tooltip>
                </q-icon>
                <q-icon
                  v-else
                  style="font-size: 1.3rem"
                  :color="dash_negative_color"
                  name="error"
                >
                  <q-tooltip>{{ $t("policyStatus.error") }}</q-tooltip>
                </q-icon>
              </q-td>
              <q-td v-else></q-td>
              <!-- status text -->
              <q-td v-if="props.row.status === 'pending'">{{
                $t("policyStatus.awaitingFirstSync")
              }}</q-td>
              <q-td v-else-if="props.row.sync_status === 'notsynced'">{{
                $t("policyStatus.willSync")
              }}</q-td>
              <q-td v-else-if="props.row.sync_status === 'synced'">{{
                $t("policyStatus.synced")
              }}</q-td>
              <q-td v-else-if="props.row.sync_status === 'pendingdeletion'">{{
                $t("policyStatus.pendingDeletion")
              }}</q-td>
              <q-td v-else-if="props.row.sync_status === 'initial'">{{
                $t("policyStatus.waitingTaskCreation")
              }}</q-td>
              <q-td v-else></q-td>
              <!-- more info -->
              <q-td v-if="props.row.check_type === 'ping'">
                <q-btn
                  flat
                  dense
                  no-caps
                  color="primary"
                  tabindex="-1"
                  class="ping-cell"
                  :label="$t('policyStatus.output')"
                  @click="pingInfo(props.row)"
                />
              </q-td>
              <q-td
                v-else-if="
                  props.row.check_type === 'script' ||
                  props.row.retcode ||
                  props.row.stdout ||
                  props.row.stderr
                "
              >
                <q-btn
                  flat
                  dense
                  no-caps
                  color="primary"
                  tabindex="-1"
                  class="script-cell"
                  :label="$t('policyStatus.output')"
                  @click="showScriptOutput(props.row)"
                />
              </q-td>
              <q-td v-else-if="props.row.check_type === 'eventlog'">
                <q-btn
                  flat
                  dense
                  no-caps
                  color="primary"
                  tabindex="-1"
                  class="eventlog-cell"
                  :label="$t('policyStatus.output')"
                  @click="showEventInfo(props.row)"
                />
              </q-td>
              <q-td
                v-else-if="
                  props.row.check_type === 'cpuload' ||
                  props.row.check_type === 'memory'
                "
                >{{ props.row.history_info }}</q-td
              >
              <q-td v-else-if="props.row.more_info">{{
                props.row.more_info
              }}</q-td>
              <q-td v-else>{{ $t("policyStatus.awaitingOutput") }}</q-td>
              <!-- last run -->
              <!-- V2-G01: mono sólo cuando hay marca de tiempo. -->
              <q-td :class="{ mono: !!props.row.last_run }">{{
                props.row.last_run
                  ? formatDate(props.row.last_run)
                  : $t("policyStatus.never")
              }}</q-td>
            </q-tr>
          </template>
        </q-table>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { computed } from "vue";
import { useStore, mapState } from "vuex";
import ScriptOutput from "@/components/checks/ScriptOutput.vue";
import EventLogCheckOutput from "@/components/checks/EventLogCheckOutput.vue";
import PreDialog from "@/components/ui/PreDialog.vue";
import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "PolicyStatus",
  mixins: [mixinRejillaTabla],
  emits: ["hide", "ok", "cancel"],
  props: {
    item: {
      required: true,
      type: Object,
    },
    type: {
      required: true,
      type: String,
      validator: function (value) {
        // The value must match one of these strings
        return ["task", "check"].includes(value);
      },
    },
  },
  setup() {
    // setup vuex store
    const store = useStore();
    const formatDate = computed(() => store.getters.formatDate);

    return {
      formatDate,
    };
  },
  data() {
    return {
      data: [],
      pagination: {
        rowsPerPage: 0,
        sortBy: "status",
        descending: false,
      },
    };
  },
  computed: {
    rejillaFilas() {
      return this.data;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
    ...mapState([
      "dash_info_color",
      "dash_positive_color",
      "dash_negative_color",
      "dash_warning_color",
    ]),
    columns() {
      return [
        {
          name: "agent",
          label: this.$t("policyStatus.colHostname"),
          field: "agent",
          align: "left",
          sortable: true,
        },
        { name: "statusicon", align: "left" },
        {
          name: "status",
          label: this.$t("policyStatus.colStatus"),
          field: "status",
          align: "left",
          sortable: true,
        },
        {
          name: "moreinfo",
          label: this.$t("policyStatus.colMoreInfo"),
          field: "more_info",
          align: "left",
          sortable: true,
        },
        {
          name: "datetime",
          label: this.$t("policyStatus.colDateTime"),
          field: "last_run",
          align: "left",
          sortable: true,
        },
      ];
    },
    title() {
      return this.$t("policyStatus.title", {
        name: this.item.readable_desc || this.item.name,
      });
    },
  },
  methods: {
    getCheckData() {
      this.$q.loading.show();
      this.$axios
        .get(`/automation/checks/${this.item.id}/status/`)
        .then((r) => {
          this.$q.loading.hide();
          this.data = r.data;
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    getTaskData() {
      this.$q.loading.show();
      this.$axios
        .get(`/automation/tasks/${this.item.id}/status/`)
        .then((r) => {
          this.$q.loading.hide();
          this.data = r.data;
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    pingInfo(check) {
      this.$q.dialog({
        component: PreDialog,
        componentProps: {
          title: check.readable_desc,
          dialogStyle: "width: 50vw; max-width: 60vw",
          message: check.more_info,
        },
      });
    },
    showEventInfo(data) {
      this.$q.dialog({
        component: EventLogCheckOutput,
        componentProps: {
          evtLogData: data,
        },
      });
    },
    showScriptOutput(script) {
      this.$q.dialog({
        component: ScriptOutput,
        componentProps: {
          scriptInfo: script,
        },
      });
    },
    refresh() {
      if (this.type === "task") {
        this.getTaskData();
      } else {
        this.getCheckData();
      }
    },
    show() {
      this.$refs.dialog.show();
    },
    hide() {
      this.$refs.dialog.hide();
    },
    onHide() {
      this.$emit("hide");
    },
  },
  mounted() {
    if (this.type === "task") {
      this.getTaskData();
    } else {
      this.getCheckData();
    }
  },
};
</script>
