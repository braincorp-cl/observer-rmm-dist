<template>
  <div v-if="!selectedAgent" class="q-pa-sm">
    {{ $t("agentActivity.noAgent") }}
  </div>
  <div v-else class="q-pa-sm">
    <!-- Feature 049-B2: estado efectivo del monitoreo, para que "sin datos" no
         se confunda con "apagado", y acceso a encenderlo/apagarlo. -->
    <div v-if="estado" class="row items-center q-gutter-sm q-mb-sm">
      <q-chip
        dense
        :color="estado.active ? 'positive' : 'grey-7'"
        text-color="white"
        :icon="estado.active ? 'visibility' : 'visibility_off'"
      >
        {{ estado.active ? $t("agentActivity.monitoringOn") : $t("agentActivity.monitoringOff") }}
      </q-chip>
      <span class="text-caption text-grey">{{ $t(`agentActivity.source_${estado.source}`) }}</span>
      <q-btn
        v-if="estado.can_manage"
        dense
        flat
        size="sm"
        icon="settings"
        :label="$t('agentActivity.configure')"
        @click="configurar"
      />
    </div>
    <div v-if="sinPermiso" class="q-pa-sm text-grey">
      {{ $t("agentActivity.noPermission") }}
    </div>
    <div v-else-if="dias.length === 0" class="q-pa-sm text-grey">
      {{ $t("agentActivity.noData") }}
    </div>
    <div v-else>
      <div class="row items-center q-gutter-md q-mb-sm">
        <q-select
          v-model="diaSel"
          :options="opcionesDia"
          :label="$t('agentActivity.day')"
          dense
          outlined
          emit-value
          map-options
          style="min-width: 220px"
        />
        <q-chip v-if="diaActual && diaActual.partial" dense color="orange" text-color="white">
          {{ $t("agentActivity.partial") }}
        </q-chip>
      </div>

      <q-table
        v-if="diaActual"
        :rows="usuarios"
        :columns="columns"
        row-key="usuario"
        dense
        flat
        :pagination="{ rowsPerPage: 0 }"
        hide-bottom
      />
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { useQuasar } from "quasar";
import {
  fetchAgentActivity,
  fetchActivityMonitoringState,
} from "@/api/agents";
import ActivityMonitoringDialog from "@/components/agents/ActivityMonitoringDialog.vue";

export default {
  name: "ActividadTab",
  setup() {
    const store = useStore();
    const { t } = useI18n();
    const $q = useQuasar();
    const estado = ref(null);
    const selectedAgent = computed(() => store.state.selectedRow);

    const dias = ref([]);
    const diaSel = ref(null);
    const sinPermiso = ref(false);

    function hm(min) {
      const m = Number(min) || 0;
      return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`;
    }

    const columns = computed(() => [
      { name: "usuario", label: t("agentActivity.user"), field: "usuario", align: "left" },
      { name: "primero", label: t("agentActivity.firstSeen"), field: "primero", align: "left" },
      { name: "ultimo", label: t("agentActivity.lastSeen"), field: "ultimo", align: "left" },
      { name: "activo", label: t("agentActivity.activeTime"), field: (r) => hm(r.activo_min), align: "right" },
      { name: "inactivo", label: t("agentActivity.idleTime"), field: (r) => hm(r.inactivo_min), align: "right" },
      { name: "capturas", label: t("agentActivity.captures"), field: "capturas", align: "right" },
      { name: "procs", label: t("agentActivity.topProcesses"), field: "procsStr", align: "left" },
    ]);

    const opcionesDia = computed(() =>
      dias.value.map((d) => ({ label: d.date, value: d.date }))
    );
    const diaActual = computed(() => dias.value.find((d) => d.date === diaSel.value) || null);
    const usuarios = computed(() => {
      if (!diaActual.value) return [];
      const doc = diaActual.value.data || {};
      const u = ((doc.dias || [])[0] || {}).usuarios || [];
      return u.map((x) => ({
        ...x,
        procsStr: Object.entries(x.procs || {})
          .sort((a, b) => b[1] - a[1])
          .slice(0, 6)
          .map(([proceso, min]) => `${proceso} (${hm(min)})`)
          .join(", "),
      }));
    });

    async function cargarEstado() {
      estado.value = null;
      if (!selectedAgent.value) return;
      try {
        estado.value = await fetchActivityMonitoringState(selectedAgent.value);
      } catch (e) {
        estado.value = null;
      }
    }

    function configurar() {
      $q.dialog({
        component: ActivityMonitoringDialog,
        componentProps: { level: "agent", id: selectedAgent.value },
      }).onOk(cargarEstado);
    }

    async function cargar() {
      sinPermiso.value = false;
      dias.value = [];
      cargarEstado();
      if (!selectedAgent.value) return;
      try {
        const data = await fetchAgentActivity(selectedAgent.value);
        dias.value = Array.isArray(data) ? data : [];
        diaSel.value = dias.value.length ? dias.value[0].date : null;
      } catch (e) {
        if (e.response && e.response.status === 403) sinPermiso.value = true;
      }
    }

    onMounted(cargar);
    watch(selectedAgent, cargar);

    return { selectedAgent, estado, configurar, dias, diaSel, diaActual, usuarios, opcionesDia, columns, sinPermiso, hm };
  },
};
</script>
