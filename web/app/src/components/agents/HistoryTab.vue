<template>
  <div v-if="!selectedAgent" class="q-pa-sm">
    {{ $t("agentTabs.noAgentSelected") }}
  </div>
  <div v-else>
    <!-- 050 (V2-G15): patron de rejilla (composables/rejillaTabla.js). La tabla
         lleva desplazamiento virtual y un control por fila (Salida): la tabla
         es UNA parada de tabulador, las flechas mueven la fila y la flecha
         derecha llega al boton de la fila. -->
    <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
    <q-table
      ref="tablaRejilla"
      @virtual-scroll="alDesplazarVirtual"
      :table-class="{
        'table-bgcolor': !$q.dark.isActive,
        'table-bgcolor-dark': $q.dark.isActive,
      }"
      :rows="history"
      :columns="columns"
      :pagination="{ sortBy: 'time', descending: true, rowsPerPage: 0 }"
      :style="{ 'max-height': tabHeight }"
      :loading="loading"
      :rows-per-page-options="[0]"
      :filter="filter"
      virtual-scroll
      dense
      binary-state-sort
    >
      <template v-slot:top>
        <q-btn dense flat push @click="getHistory" icon="refresh" />
        <q-space />
        <q-input
          v-model="filter"
          outlined
          :label="$t('agentTabs.common.search')"
          dense
          clearable
          class="q-pr-sm"
        >
          <template v-slot:prepend>
            <q-icon name="search" />
          </template>
        </q-input>
        <export-table-btn :data="history" :columns="columns" />
      </template>

      <template v-slot:loading>
        <q-inner-loading showing color="secondary" />
      </template>

      <template v-slot:body-cell-output="props">
        <q-td :props="props">
          <!-- 050 (V2-G15): control real; `tabindex="-1"`: se alcanza con la
               flecha derecha desde la hora (host de la fila). -->
          <q-btn
            flat
            dense
            no-caps
            color="primary"
            tabindex="-1"
            :label="$t('agentTabs.history.output')"
            @click="
              props.row.type === 'cmd_run'
                ? showCommandOutput(props.row.command, props.row.results)
                : showScriptOutput(props.row.script_results)
            "
          />
        </q-td>
      </template>

      <template v-slot:body-cell-time="props">
        <q-td :props="props" class="mono">
          <!-- Host enfocable de la fila (rejilla): existe en TODAS las filas. -->
          <span
            class="obs-rej__host"
            :data-fila="props.rowIndex"
            :tabindex="props.rowIndex === filaFoco ? 0 : -1"
            @focus="filaFoco = props.rowIndex"
            >{{ formatDate(props.row.time) }}</span
          >
        </q-td>
      </template>
    </q-table>
    </div>
  </div>
</template>

<script>
// composition imports
import { ref, computed, watch, onMounted } from "vue";
import { useStore } from "vuex";
import { useQuasar, Notify } from "quasar";
import { useI18n } from "vue-i18n";
import { formatTableColumnText } from "@/utils/format";
import { fetchAgentHistory } from "@/api/agents";

// ui imports
import ScriptOutput from "@/components/checks/ScriptOutput.vue";
import ExportTableBtn from "@/components/ui/ExportTableBtn.vue";
import PreDialog from "@/components/ui/PreDialog.vue";

import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "HistoryTab",
  mixins: [mixinRejillaTabla],
  computed: {
    rejillaFilas() {
      return this.history;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
  },
  components: {
    ExportTableBtn,
  },
  setup() {
    const $q = useQuasar();
    const { t } = useI18n();

    // table columns (computed so labels follow the active locale)
    const columns = computed(() => [
      {
        name: "time",
        label: t("agentTabs.history.colTime"),
        field: "time",
        align: "left",
        sortable: true,
      },
      {
        name: "type",
        label: t("agentTabs.history.colAction"),
        field: "type",
        align: "left",
        sortable: true,
        // El backend manda el valor del enum (`script_run`, `cmd_run`, `task_run`).
        // Antes se mostraba con formatTableColumnText, que solo pasa snake_case a
        // Title Case: la columna quedaba en inglés ("Script Run") dentro de una
        // consola en español. Se traduce por clave, con el formateo genérico como
        // respaldo para cualquier tipo nuevo que el backend agregue.
        format: (val) => {
          const claves = {
            script_run: "agentTabs.history.typeScriptRun",
            cmd_run: "agentTabs.history.typeCmdRun",
            task_run: "agentTabs.history.typeTaskRun",
          };
          return claves[val] ? t(claves[val]) : formatTableColumnText(val);
        },
      },
      {
        name: "command",
        // 046 (UI-D01): un comando es dato (mono); el nombre de un script, no.
        classes: (row) => (row.type === "script_run" ? "" : "mono"),
        label: t("agentTabs.history.colCommand"),
        field: (row) =>
          row.type === "script_run" ? row.script_name : row.command,
        align: "left",
        sortable: true,
      },
      {
        name: "username",
        label: t("agentTabs.history.colInitiatedBy"),
        field: "username",
        align: "left",
        sortable: true,
      },
      {
        name: "output",
        label: t("agentTabs.history.colOutput"),
        field: "output",
        align: "left",
        sortable: true,
      },
    ]);

    const store = useStore();
    const selectedAgent = computed(() => store.state.selectedRow);
    const tabHeight = computed(() => store.state.tabHeight);
    const formatDate = computed(() => store.getters.formatDate);

    // setup main history functionality
    const history = ref([]);
    const loading = ref(false);
    const filter = ref("");

    async function getHistory() {
      loading.value = true;
      history.value = await fetchAgentHistory(selectedAgent.value);
      loading.value = false;
    }

    watch(selectedAgent, (newValue) => {
      if (newValue) {
        getHistory();
      }
    });

    // quasar dialogs
    function showScriptOutput(output) {
      if (!output) {
        Notify.create({
          message: t("agentTabs.history.noOutputYet"),
          type: "negative",
        });
        return;
      }
      $q.dialog({
        component: ScriptOutput,
        componentProps: {
          scriptInfo: output,
        },
      });
    }

    function showCommandOutput(title, output) {
      $q.dialog({
        component: PreDialog,
        componentProps: {
          title: title,
          dialogStyle: "width: 70vw; max-width: 80vw",
          message: output,
        },
      });
    }

    // vue component hooks
    onMounted(() => {
      if (selectedAgent.value) getHistory();
    });

    return {
      // reactive
      history,
      loading,
      tabHeight,
      filter,

      // non-reactive data
      columns,

      // methods
      formatDate,
      showScriptOutput,
      showCommandOutput,
      getHistory,

      // computed
      selectedAgent,
    };
  },
};
</script>
