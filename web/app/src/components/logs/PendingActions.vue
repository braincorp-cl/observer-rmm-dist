<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="height: 70vh; min-width: 70vw">
      <q-bar>
        <q-btn
          @click="getPendingActions"
          class="q-mr-sm"
          dense
          flat
          push
          icon="refresh"
        />
        {{
          agent
            ? $t("pendingActions.titleForAgent", { hostname: agent.hostname })
            : $t("pendingActions.titleAll")
        }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup />
      </q-bar>
      <!-- 🪤 050 (V2-G15): PATRÓN DE REJILLA. Con una parada de tabulador por
           fila, el tabulador aterriza en las filas SOBRE-RENDERIZADAS que el
           desplazamiento virtual deja fuera del contenedor, donde el anillo no
           se dibuja a propósito porque el control está entero fuera de
           pantalla (medido: 13 paradas en y=785..1031 y y=-321..-239 sobre un
           viewport de 757). Los dos oyentes de la raíz son el seguro: cuando el
           reciclaje destruye el nodo enfocado, Chrome SUBE el foco al scroller
           (`tabindex=-1`) y desde ahí la rejilla quedaría muerta. -->
      <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
      <q-table
        ref="tablaRejilla"
        @virtual-scroll="alDesplazarVirtual"
        :virtual-scroll-item-size="33"
        :virtual-scroll-sticky-size-start="28"
        dense
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        class="remote-bg-tbl-sticky"
        style="max-height: 65vh"
        :rows="filteredActions"
        :columns="columns"
        :visible-columns="visibleColumns"
        :pagination="{ rowsPerPage: 0, sortBy: 'status', descending: false }"
        row-key="id"
        virtual-scroll
        :rows-per-page-options="[0]"
        :no-data-label="$t('pendingActions.noData')"
        :loading="loading"
      >
        <template v-slot:top>
          <q-space />
          <q-btn
            :label="
              showCompleted
                ? $t('pendingActions.hideCompleted', { count: completedCount })
                : $t('pendingActions.showCompleted', { count: completedCount })
            "
            :icon="showCompleted ? 'visibility_off' : 'visibility'"
            @click="showCompleted = !showCompleted"
            dense
            flat
          />
        </template>

        <template v-slot:body="props">
          <q-tr class="cursor-pointer">
            <q-menu context-menu auto-close>
              <q-list dense>
                <q-item
                  :disable="
                    props.row.status === 'completed' ||
                    props.row.action_type === 'agentinstall'
                  "
                  clickable
                  @click="cancelPendingAction(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="fas fa-trash-alt" size="xs" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("pendingActions.cancelAction")
                  }}</q-item-section>
                </q-item>
                <q-separator />
                <q-item clickable v-close-popup>
                  <q-item-section>{{
                    $t("pendingActions.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
            <q-td v-if="props.row.action_type === 'schedreboot'">
              <q-icon name="power_settings_new" size="sm" />
            </q-td>
            <q-td v-else-if="props.row.action_type === 'agentupdate'">
              <q-icon name="update" size="sm" />
            </q-td>
            <q-td v-else-if="props.row.action_type === 'chocoinstall'">
              <q-icon name="download" size="sm" />
            </q-td>
            <q-td v-if="props.row.status !== 'completed'">
              <!-- 🪤 V2-G01: esta es la rama que de verdad se pinta. Con los
                   datos reales de staging las 428 filas son `agentupdate`, y
                   yo habia arreglado la OTRA dos veces seguidas. Tambien rinde
                   marca de tiempo. -->
              <span
                v-if="props.row.action_type === 'agentupdate'"
                class="mono"
                >{{ getNextAgentUpdateTime() }}</span
              >
              <!-- V2-G01: mono SIEMPRE. Mi primera versión lo condicionó a
                   schedreboot asumiendo que la otra rama no era una fecha; NO lo
                   comprobé y lo es: `props.row.due` es una marca de tiempo sin
                   formatear. Medidos 36 nodos «Nov 12, 2026 at 12:35 AM» en
                   Archivo justamente por esa rama. -->
              <span v-else class="mono">{{
                props.row.action_type === "schedreboot"
                  ? formatDate(props.row.due)
                  : props.row.due
              }}</span>
            </q-td>
            <q-td v-else>{{ $t("pendingActions.completed") }}</q-td>
            <!-- Host enfocable de la fila: la ÚNICA parada de tabulador de la
                 tabla. Desde aquí la tecla Menú abre el menú contextual de la
                 fila —que hasta ahora era sólo de ratón— y la flecha derecha
                 llega al botón de salida cuando existe. -->
            <q-td>
              <span
                class="obs-rej__host"
                :data-fila="props.rowIndex"
                :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                @focus="filaFoco = props.rowIndex"
                >{{ props.row.description }}</span
              >
            </q-td>
            <q-td v-if="!agent">{{ props.row.hostname }}</q-td>
            <q-td v-if="!agent">{{ props.row.client }}</q-td>
            <q-td v-if="!agent">{{ props.row.site }}</q-td>
            <q-td
              v-if="
                props.row.action_type === 'chocoinstall' &&
                props.row.status === 'completed'
              "
            >
              <q-btn
                color="primary"
                icon="preview"
                size="sm"
                tabindex="-1"
                :label="$t('pendingActions.viewOutput')"
                @click="showOutput(props.row.details.output)"
              />
            </q-td>
            <q-td v-else></q-td>
          </q-tr>
        </template>
      </q-table>
      </div>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent } from "quasar";
import {
  fetchPendingActions,
  fetchAgentPendingActions,
  deletePendingAction,
} from "@/api/logs";
import { getNextAgentUpdateTime } from "@/utils/format";
import { notifySuccess } from "@/utils/notify";
import PreDialog from "@/components/ui/PreDialog.vue";

import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "PendingActions",
  mixins: [mixinRejillaTabla],
  computed: {
    rejillaFilas() {
      return this.filteredActions;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
  },
  emits: [...useDialogPluginComponent.emits],
  props: {
    agent: Object,
  },
  setup(props) {
    // setup quasar dialog plugin
    const { dialogRef, onDialogHide } = useDialogPluginComponent();
    const $q = useQuasar();
    const { t } = useI18n();

    // vuex store
    const store = useStore();
    const formatDate = computed(() => store.getters.formatDate);

    // i18n-aware columns (computed for language reactivity)
    const columns = computed(() => [
      { name: "id", field: "id" },
      { name: "status", field: "status" },
      {
        name: "type",
        label: t("pendingActions.colType"),
        field: "action_type",
        align: "left",
        sortable: true,
      },
      {
        name: "due",
        label: t("pendingActions.colDue"),
        field: "due",
        align: "left",
        sortable: true,
      },
      {
        name: "desc",
        label: t("pendingActions.colDescription"),
        field: "description",
        align: "left",
        sortable: true,
      },
      {
        name: "agent",
        label: t("pendingActions.colAgent"),
        field: "hostname",
        align: "left",
        sortable: true,
      },
      {
        name: "client",
        label: t("pendingActions.colClient"),
        field: "client",
        align: "left",
        sortable: true,
      },
      {
        name: "site",
        label: t("pendingActions.colSite"),
        field: "site",
        align: "left",
        sortable: true,
      },
      { name: "details", field: "details", align: "left", sortable: false },
    ]);

    // pending actions logic
    const actions = ref([]);
    const showCompleted = ref(false);
    const loading = ref(false);
    const completedCount = computed(() => {
      try {
        return actions.value.filter((action) => action.status === "completed")
          .length;
      } catch (e) {
        console.error(e);
        return 0;
      }
    });

    const visibleColumns = computed(() => {
      if (props.agent) return ["type", "due", "desc", "details"];
      else return ["type", "due", "desc", "agent", "client", "site", "details"];
    });

    const filteredActions = computed(() => {
      if (showCompleted.value) return actions.value;
      else
        return actions.value.filter((action) => action.status !== "completed");
    });

    function showOutput(details) {
      $q.dialog({
        component: PreDialog,
        componentProps: {
          title: t("pendingActions.outputTitle"),
          dialogStyle: "width: 75vw; max-width: 85vw; max-height: 65vh;",
          message: details,
        },
      });
    }

    async function getPendingActions() {
      loading.value = true;
      try {
        actions.value = props.agent
          ? await fetchAgentPendingActions(props.agent.agent_id)
          : await fetchPendingActions();
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    function cancelPendingAction(action) {
      $q.dialog({
        title: t("pendingActions.deleteTitle"),
        cancel: true,
        ok: { label: t("pendingActions.delete"), color: "primary" },
      }).onOk(async () => {
        loading.value = true;
        try {
          const result = await deletePendingAction(action.id);
          notifySuccess(result);
          await getPendingActions();
          store.dispatch("refreshDashboard");
        } catch (e) {
          console.error(e);
        }
        loading.value = false;
      });
    }

    onMounted(getPendingActions);

    return {
      // reactive data
      filteredActions,
      loading,
      showCompleted,
      completedCount,
      visibleColumns,

      // methods
      showOutput,
      getPendingActions,
      cancelPendingAction,
      getNextAgentUpdateTime,
      formatDate,

      // i18n-aware columns
      columns,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
