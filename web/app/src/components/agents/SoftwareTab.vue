<template>
  <div v-if="!selectedAgent" class="q-pa-sm">
    {{ $t("agentTabs.noAgentSelected") }}
  </div>
  <div v-else-if="agentPlatform.toLowerCase() !== 'windows'" class="q-pa-sm">
    {{ $t("agentTabs.common.windowsOnly") }}
  </div>
  <div v-else>
    <!-- 🪤 050 (V2-G15): PATRON DE REJILLA. Con una parada de tabulador por fila,
         el tabulador aterriza en las filas SOBRE-RENDERIZADAS que el
         desplazamiento virtual deja fuera del contenedor, donde el anillo no se
         dibuja a proposito porque el control esta entero fuera de pantalla
         (medido en el dialogo de instalar software: 13 paradas en y=785..1031 y
         en y=-321..-239 sobre un viewport de 757, en los dos temas). La tabla
         pasa a ser UNA parada y las flechas mueven la fila, con `scrollTo` POR
         INDICE. Los dos oyentes de la raiz son el seguro: cuando el reciclaje
         destruye el nodo enfocado, Chrome SUBE el foco al scroller
         (`tabindex=-1`) y desde ahi la rejilla quedaria muerta. -->
    <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
    <q-table
        ref="tablaRejilla"
        @virtual-scroll="alDesplazarVirtual"
        :virtual-scroll-item-size="33"
        :virtual-scroll-sticky-size-start="28"
      :table-class="{
        'table-bgcolor': !$q.dark.isActive,
        'table-bgcolor-dark': $q.dark.isActive,
      }"
      class="tabs-tbl-sticky"
      dense
      :rows="software"
      :columns="columns"
      :filter="filter"
      :style="{ 'max-height': tabHeight }"
      v-model:pagination="pagination"
      binary-state-sort
      row-key="id"
      virtual-scroll
      :rows-per-page-options="[0]"
      :loading="loading"
    >
      <template v-slot:loading>
        <q-inner-loading showing color="secondary" />
      </template>

      <template v-slot:top>
        <q-btn
          class="q-mr-sm"
          dense
          flat
          push
          @click="refreshSoftware"
          icon="refresh"
        />
        <q-btn
          icon="add"
          :label="$t('agentTabs.software.installSoftware')"
          no-caps
          dense
          flat
          push
          @click="showInstallSoftwareModal"
        />

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
        <export-table-btn :data="software" :columns="columns" />
      </template>

      <!-- Host enfocable de la fila: la ÚNICA parada de tabulador de la tabla.
           🪤 Va en la columna del NOMBRE y no en el botón de desinstalar, que es
           condicional (`v-if="props.row.uninstall"`): en las filas sin ese botón
           la tabla se quedaría sin parada de tabulador y dejaría de ser
           alcanzable. El host tiene que existir en TODAS las filas. -->
      <template v-slot:body-cell-name="props">
        <td class="obs-wrap-words">
          <span
            class="obs-rej__host"
            :data-fila="props.rowIndex"
            :tabindex="props.rowIndex === filaFoco ? 0 : -1"
            @focus="filaFoco = props.rowIndex"
            >{{ props.row.name }}</span
          >
        </td>
      </template>
      <template v-slot:body-cell-uninstall="props">
        <td class="obs-nowrap">
          <!-- `tabindex="-1"`: se alcanza con la flecha derecha desde el nombre. -->
          <q-btn
            v-if="props.row.uninstall"
            :label="$t('agentTabs.software.uninstall')"
            color="primary"
            dense
            size="sm"
            tabindex="-1"
            @click="openUninstallSoftware(props.row)"
          />
        </td>
      </template>
    </q-table>
    </div>
  </div>
</template>

<script>
// composition imports
import { ref, computed, watch, onMounted } from "vue";
import { useQuasar } from "quasar";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import {
  fetchAgentSoftware,
  refreshAgentSoftware,
  uninstallAgentSoftware,
} from "@/api/software";

// ui imports
import InstallSoftware from "@/components/software/InstallSoftware.vue";
import UninstallSoftware from "@/components/software/UninstallSoftware.vue";
import ExportTableBtn from "@/components/ui/ExportTableBtn.vue";
import { notifySuccess } from "@/utils/notify";

import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "SoftwareTab",
  mixins: [mixinRejillaTabla],
  computed: {
    rejillaFilas() {
      return this.software;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
  },
  components: {
    ExportTableBtn,
  },
  setup() {
    // setup quasar
    const $q = useQuasar();
    const { t } = useI18n();

    // table columns (computed so labels follow the active locale)
    const columns = computed(() => [
      {
        name: "name",
        align: "left",
        label: t("agentTabs.software.colName"),
        field: "name",
        classes: "obs-wrap-words",
        sortable: true,
      },
      {
        name: "publisher",
        align: "left",
        label: t("agentTabs.software.colPublisher"),
        field: "publisher",
        classes: "mono obs-wrap-words",
        sortable: true,
      },
      {
        name: "install_date",
        align: "left",
        label: t("agentTabs.software.colInstalledOn"),
        field: "install_date",
        classes: "obs-nowrap",
        sortable: false,
        format: (val) => {
          return val === "01/01/1" || val === "01-1-01" ? "" : val;
        },
      },
      {
        name: "size",
        align: "left",
        label: t("agentTabs.software.colSize"),
        field: "size",
        classes: "mono obs-nowrap",
        sortable: false,
      },
      {
        name: "version",
        align: "left",
        label: t("agentTabs.software.colVersion"),
        field: "version",
        classes: "mono obs-wrap-words",
        sortable: false,
      },
      {
        name: "uninstall",
        align: "left",
        label: "",
        field: "uninstall",
        sortable: false,
      },
    ]);

    // setup vuex
    const store = useStore();
    const selectedAgent = computed(() => store.state.selectedRow);
    const tabHeight = computed(() => store.state.tabHeight);
    const agentPlatform = computed(() => store.state.agentPlatform);

    // software tab logic
    const software = ref([]);
    const loading = ref(false);
    const filter = ref("");
    const pagination = ref({
      rowsPerPage: 0,
      sortBy: "name",
      descending: false,
    });

    async function getSoftware() {
      loading.value = true;
      software.value = (await fetchAgentSoftware(selectedAgent.value)) || [];
      loading.value = false;
    }

    async function refreshSoftware() {
      loading.value = true;
      await refreshAgentSoftware(selectedAgent.value);
      await getSoftware();
      loading.value = false;
    }

    function showInstallSoftwareModal() {
      $q.dialog({
        component: InstallSoftware,
        componentProps: {
          agent_id: selectedAgent.value,
        },
      });
    }

    function openUninstallSoftware(software) {
      $q.dialog({
        component: UninstallSoftware,

        componentProps: {
          softwareName: software.name,
          initialUninstallString:
            software.uninstall +
            (software.uninstall.toLowerCase().includes("msiexec")
              ? " /qn /norestart"
              : ""),
        },
      }).onOk(async (data) => {
        try {
          loading.value = true;
          const ret = await uninstallAgentSoftware(selectedAgent.value, {
            name: software.name,
            command: data.uninstallString, // use user supplied value, not the one from db. to prevent db injection attack
            run_as_user: data.run_as_user,
            timeout: data.timeout,
          });
          notifySuccess(ret);
        } catch (e) {
          console.error(e);
        } finally {
          loading.value = false;
        }
      });
    }

    watch(selectedAgent, (newValue) => {
      if (newValue) {
        getSoftware();
      }
    });

    onMounted(() => {
      if (selectedAgent.value) getSoftware();
    });

    return {
      // reactive data
      software,
      loading,
      filter,
      pagination,
      selectedAgent,
      tabHeight,
      agentPlatform,

      // non-reactive data
      columns,

      // methods
      refreshSoftware,
      showInstallSoftwareModal,
      openUninstallSoftware,
    };
  },
};
</script>
