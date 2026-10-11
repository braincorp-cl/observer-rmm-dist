<template>
  <div>
    <div v-if="sinPermiso" class="text-grey">
      {{ $t("activityScope.noPermission") }}
    </div>
    <template v-else>
      <div class="row items-center q-gutter-sm q-mb-sm">
        <q-chip
          dense
          :color="globalEnabled ? 'positive' : 'grey-7'"
          text-color="white"
          icon="visibility"
        >
          {{ $t("activityScope.monitored", { n: monitoreados }) }}
        </q-chip>
        <span v-if="!globalEnabled" class="text-caption text-orange">
          {{ $t("activityScope.globalOffHint") }}
        </span>
        <q-space />
        <q-btn
          dense
          flat
          icon="refresh"
          :loading="cargando"
          @click="cargar"
        />
      </div>

      <q-table
        :rows="reglas"
        :columns="columnas"
        row-key="key"
        dense
        flat
        bordered
        :pagination="{ rowsPerPage: 0 }"
        hide-bottom
        :no-data-label="$t('activityScope.empty')"
      >
        <template v-slot:body-cell-level="props">
          <q-td :props="props">{{ $t(`activityScope.level_${props.row.level}`) }}</q-td>
        </template>
        <template v-slot:body-cell-value="props">
          <q-td :props="props">
            <q-chip
              dense
              :color="props.row.value ? 'positive' : 'negative'"
              text-color="white"
            >
              {{ props.row.value ? $t("activityScope.on") : $t("activityScope.off") }}
            </q-chip>
          </q-td>
        </template>
        <template v-slot:body-cell-actions="props">
          <q-td :props="props">
            <q-btn dense flat size="sm" icon="edit" @click="editar(props.row)" />
            <q-btn
              dense
              flat
              size="sm"
              icon="delete"
              color="negative"
              @click="quitar(props.row)"
            >
              <q-tooltip>{{ $t("activityScope.removeTooltip") }}</q-tooltip>
            </q-btn>
          </q-td>
        </template>
      </q-table>

      <!-- Agregar una regla: cliente, y opcionalmente sitio y equipo. El nivel
           es el más profundo que se elija. -->
      <div class="text-caption q-mt-md q-mb-xs">
        {{ $t("activityScope.addTitle") }}
      </div>
      <div class="row items-center q-gutter-sm">
        <q-select
          v-model="nuevo.client"
          :options="opcionesClientes"
          :label="$t('activityScope.client')"
          dense
          outlined
          emit-value
          map-options
          style="min-width: 12rem"
          @update:model-value="alCambiarCliente"
        />
        <q-select
          v-model="nuevo.site"
          :options="opcionesSitios"
          :label="$t('activityScope.siteOptional')"
          :disable="!nuevo.client"
          dense
          outlined
          clearable
          emit-value
          map-options
          style="min-width: 12rem"
          @update:model-value="alCambiarSitio"
        />
        <q-select
          v-model="nuevo.agent"
          :options="opcionesEquipos"
          :label="$t('activityScope.agentOptional')"
          :disable="!nuevo.site"
          dense
          outlined
          clearable
          emit-value
          map-options
          use-input
          input-debounce="0"
          style="min-width: 12rem"
          @filter="filtrarEquipos"
        />
        <q-btn-toggle
          v-model="nuevo.value"
          dense
          no-caps
          toggle-color="primary"
          :options="[
            { label: $t('activityScope.on'), value: true },
            { label: $t('activityScope.off'), value: false },
          ]"
        />
        <q-btn
          dense
          color="primary"
          icon="add"
          :label="$t('activityScope.add')"
          :disable="!nuevo.client"
          :loading="guardando"
          @click="agregar"
        />
      </div>
    </template>
  </div>
</template>

<script>
// Feature 049: alcance del monitoreo de actividad dentro de «Employee
// Monitoring». Lista solo los valores explícitos (los que heredan no deciden) y
// los cambios se guardan al instante, con su push al equipo.
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar } from "quasar";
import axios from "axios";
import { fetchClients } from "@/api/clients";
import { fetchAgents, saveActivityMonitoring } from "@/api/agents";
import ActivityMonitoringDialog from "@/components/agents/ActivityMonitoringDialog.vue";

export default {
  name: "ActivityScopeTable",
  props: {
    globalEnabled: { type: Boolean, default: false },
  },
  setup() {
    const { t } = useI18n();
    const $q = useQuasar();

    const reglas = ref([]);
    const monitoreados = ref(0);
    const cargando = ref(false);
    const guardando = ref(false);
    const sinPermiso = ref(false);
    const clientes = ref([]);
    const equipos = ref([]);
    const filtroEquipo = ref("");
    const nuevo = ref({ client: null, site: null, agent: null, value: true });

    const columnas = computed(() => [
      { name: "level", label: t("activityScope.level"), field: "level", align: "left" },
      { name: "name", label: t("activityScope.name"), field: "name", align: "left" },
      { name: "parent", label: t("activityScope.parent"), field: "parent", align: "left" },
      { name: "value", label: t("activityScope.state"), field: "value", align: "left" },
      { name: "actions", label: "", field: "key", align: "right" },
    ]);

    const opcionesClientes = computed(() =>
      clientes.value.map((c) => ({ label: c.name, value: c.id })),
    );
    const opcionesSitios = computed(() => {
      const c = clientes.value.find((x) => x.id === nuevo.value.client);
      return c ? c.sites.map((s) => ({ label: s.name, value: s.id })) : [];
    });
    const opcionesEquipos = computed(() =>
      equipos.value
        .filter((a) =>
          a.hostname.toLowerCase().includes(filtroEquipo.value.toLowerCase()),
        )
        .map((a) => ({ label: a.hostname, value: a.agent_id })),
    );

    async function cargar() {
      cargando.value = true;
      try {
        const { data } = await axios.get("/agents/activity-monitoring/overview/");
        reglas.value = data.rules.map((r) => ({ ...r, key: `${r.level}:${r.id}` }));
        monitoreados.value = data.monitored_agents;
        sinPermiso.value = false;
      } catch (e) {
        if (e.response && e.response.status === 403) sinPermiso.value = true;
      }
      cargando.value = false;
    }

    function alCambiarCliente() {
      nuevo.value.site = null;
      nuevo.value.agent = null;
      equipos.value = [];
    }

    async function alCambiarSitio(site) {
      nuevo.value.agent = null;
      equipos.value = [];
      if (!site) return;
      equipos.value = (await fetchAgents({ site, detail: false })) || [];
    }

    function filtrarEquipos(val, update) {
      update(() => {
        filtroEquipo.value = val || "";
      });
    }

    async function guardar(level, id, value) {
      await saveActivityMonitoring(level, id, value);
      $q.notify({ type: "positive", message: t("activityMonitoring.saved") });
      await cargar();
    }

    async function agregar() {
      const n = nuevo.value;
      const [level, id] = n.agent
        ? ["agent", n.agent]
        : n.site
          ? ["site", n.site]
          : ["client", n.client];
      guardando.value = true;
      try {
        await guardar(level, id, n.value);
        nuevo.value = { client: null, site: null, agent: null, value: true };
        equipos.value = [];
      } catch (e) {
        // el interceptor de axios ya notifica
      }
      guardando.value = false;
    }

    function editar(row) {
      $q.dialog({
        component: ActivityMonitoringDialog,
        componentProps: { level: row.level, id: row.id, name: row.name },
      }).onOk(cargar);
    }

    async function quitar(row) {
      try {
        await guardar(row.level, row.id, null);
      } catch (e) {
        // el interceptor de axios ya notifica
      }
    }

    onMounted(async () => {
      await cargar();
      if (!sinPermiso.value) clientes.value = (await fetchClients()) || [];
    });

    return {
      reglas,
      monitoreados,
      cargando,
      guardando,
      sinPermiso,
      nuevo,
      columnas,
      opcionesClientes,
      opcionesSitios,
      opcionesEquipos,
      cargar,
      alCambiarCliente,
      alCambiarSitio,
      filtrarEquipos,
      agregar,
      editar,
      quitar,
    };
  },
};
</script>
