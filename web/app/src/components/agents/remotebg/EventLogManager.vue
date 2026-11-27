<template>
  <div v-if="agentPlatform.toLowerCase() !== 'windows'" class="q-pa-sm">
    {{ $t("eventLogManager.onlyWindows") }}
  </div>
  <!-- 050 (V2-G15): patrón de rejilla (la tabla lleva virtual-scroll). Los
       oyentes de la raíz atajan el foco que el reciclaje sube al scroller. -->
  <div v-else @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
    <div class="row q-pt-sm q-pl-sm">
      <div class="col-2">
        <q-select
          dense
          options-dense
          outlined
          class="obs-mono-values"
          v-model="days"
          :options="lastDaysOptions"
          :label="showDays"
        />
      </div>
      <div class="col-7"></div>
      <div class="col-3">
        <span v-if="events">{{
          $t("eventLogManager.totalRecords", {
            type: logType,
            count: events.length,
          })
        }}</span>
      </div>
    </div>
    <q-table
      ref="tablaRejilla"
      dense
      :table-class="{
        'table-bgcolor': !$q.dark.isActive,
        'table-bgcolor-dark': $q.dark.isActive,
      }"
      class="remote-bg-tbl-sticky"
      :rows="events"
      :columns="columns"
      :style="{ 'max-height': `${$q.screen.height - 85}px` }"
      :pagination="{ rowsPerPage: 0, sortBy: 'record', descending: true }"
      :filter="filter"
      row-key="uid"
      binary-state-sort
      virtual-scroll
      @virtual-scroll="alDesplazarVirtual"
      :virtual-scroll-item-size="33"
      :virtual-scroll-sticky-size-start="28"
      :rows-per-page-options="[0]"
      :loading="loading"
    >
      <template v-slot:top>
        <q-btn dense flat push @click="getEventLog" icon="refresh" />
        <q-space />
        <q-radio
          v-model="logType"
          color="primary"
          val="Application"
          :label="$t('eventLogManager.logApplication')"
          @update:model-value="getEventLog"
        />
        <q-radio
          v-model="logType"
          color="primary"
          val="System"
          :label="$t('eventLogManager.logSystem')"
        />
        <q-radio
          v-model="logType"
          color="primary"
          val="Security"
          :label="$t('eventLogManager.logSecurity')"
        />
        <q-space />
        <q-input
          v-model="filter"
          style="width: 300px"
          outlined
          :label="$t('eventLogManager.search')"
          dense
          clearable
        >
          <template v-slot:prepend>
            <q-icon name="search" />
          </template>
        </q-input>
        <!-- file download doesn't work so disabling -->
        <export-table-btn
          v-show="false"
          class="q-ml-sm"
          :columns="columns"
          :data="events"
        />
      </template>
      <template v-slot:body="props">
        <q-tr :props="props">
          <q-td>{{ props.row.eventType }}</q-td>
          <q-td>{{ props.row.source }}</q-td>
          <!-- 050 (V2-G01): Id. de evento = código crudo (clase 12) y la marca
               de tiempo con fecha y hora en su celda (clase 8): Mono. -->
          <q-td class="mono">{{ props.row.eventID }}</q-td>
          <q-td class="mono obs-nowrap">{{ props.row.time }}</q-td>
          <!-- 050 (G08, 13.ª corrida): el clic ya abria el mensaje completo,
               pero era el UNICO canal y el texto se corta en JS. El title da el
               valor completo sin abrir el dialogo. -->
          <!-- 050 (V2-G15): el mensaje es el host enfocable de la fila (una
               sola parada de tabulador por tabla); Enter y Espacio abren el
               mensaje completo igual que el clic. -->
          <q-td :title="props.row.message">
            <span
              class="obs-rej__host text-primary"
              role="button"
              :data-fila="props.rowIndex"
              :tabindex="props.rowIndex === filaFoco ? 0 : -1"
              :aria-label="props.row.message"
              style="cursor: pointer; text-decoration: underline"
              @focus="filaFoco = props.rowIndex"
              @keydown.space.prevent
              @keyup.enter="showEventMessage(props.row.message)"
              @keyup.space="showEventMessage(props.row.message)"
              @click="showEventMessage(props.row.message)"
              >{{ truncateText(props.row.message, 30) }}</span
            >
          </q-td>
        </q-tr>
      </template>
    </q-table>
  </div>
</template>

<script>
// composition imports
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar } from "quasar";
import { fetchAgentEventLog } from "@/api/agents";
import { truncateText } from "@/utils/format";
import { usarRejillaTabla } from "@/composables/rejillaTabla";

// ui imports
import ExportTableBtn from "@/components/ui/ExportTableBtn.vue";
import PreDialog from "@/components/ui/PreDialog.vue";

// static data
const lastDaysOptions = [1, 2, 3, 4, 5, 10, 30, 60, 90, 180, 360, 9999];

export default {
  name: "EventLogManager",
  components: {
    ExportTableBtn,
  },
  props: {
    agent_id: !String,
    agentPlatform: !String,
  },
  setup(props) {
    // i18n setup
    const { t } = useI18n();

    // quasar setup
    const $q = useQuasar();

    // columns (computed para reaccionar al cambio de idioma)
    const columns = computed(() => [
      {
        name: "eventType",
        label: t("eventLogManager.colType"),
        field: "eventType",
        align: "left",
        sortable: true,
      },
      {
        name: "source",
        label: t("eventLogManager.colSource"),
        field: "source",
        align: "left",
        sortable: true,
      },
      {
        name: "eventID",
        label: t("eventLogManager.colEventId"),
        field: "eventID",
        align: "left",
        sortable: true,
      },
      {
        name: "time",
        label: t("eventLogManager.colTime"),
        field: "time",
        align: "left",
        sortable: true,
      },
      {
        name: "message",
        label: t("eventLogManager.colMessage"),
        field: "message",
        align: "left",
        sortable: true,
      },
    ]);

    // eventlog manager
    const events = ref([]);
    const logType = ref("Application");
    const days = ref(1);
    const filter = ref("");
    const loading = ref(false);

    // 050 (V2-G15): patrón de rejilla para la tabla con virtual-scroll
    const tablaRejilla = ref(null);
    const { filaFoco, alEntrarFoco, alTeclaRejilla, alDesplazarVirtual } =
      usarRejillaTabla({ refTabla: tablaRejilla, filas: () => events.value });

    const showDays = computed(() =>
      t("eventLogManager.showLastDays", { days: days.value }),
    );

    watch([logType, days], getEventLog);

    async function getEventLog() {
      loading.value = true;
      events.value = await fetchAgentEventLog(
        props.agent_id,
        logType.value,
        days.value,
      );
      loading.value = false;
    }

    function showEventMessage(message) {
      $q.dialog({
        component: PreDialog,
        componentProps: {
          dialogStyle: "width: 85vw; max-width: 90vw",
          message: message,
        },
      });
    }

    // vue lifecycle hooks
    onMounted(() => {
      if (props.agentPlatform === "windows") getEventLog();
    });

    return {
      // reactive data
      events,
      logType,
      days,
      filter,
      showDays,
      loading,
      tablaRejilla,
      filaFoco,

      // non-reactive data
      columns,
      lastDaysOptions,

      // methods
      getEventLog,
      showEventMessage,
      truncateText,
      alEntrarFoco,
      alTeclaRejilla,
      alDesplazarVirtual,
    };
  },
};
</script>
