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

      <!-- Feature 049-C: capturas del día (servidas por la vista autenticada) -->
      <div v-if="capturas.length" class="q-mt-md">
        <div class="text-subtitle2 q-mb-xs">
          {{ $t("agentActivity.screenshots", { n: capturas.length }) }}
        </div>
        <div class="row q-gutter-sm">
          <div
            v-for="c in capturas"
            :key="c.id"
            class="cursor-pointer"
            style="width: 180px"
            @click="verCaptura(c)"
          >
            <q-img
              v-if="c.url"
              :src="c.url"
              :ratio="16 / 9"
              fit="cover"
              style="border-radius: 4px"
            />
            <q-skeleton v-else type="rect" style="height: 101px" />
            <div class="text-caption ellipsis">
              {{ leyenda(c) }}
            </div>
            <q-tooltip v-if="c.title">{{ c.title }}</q-tooltip>
          </div>
        </div>
      </div>
      <q-dialog v-model="capturaAbierta">
        <q-card v-if="capturaSel" style="max-width: 95vw; width: 1200px">
          <q-bar>
            {{ leyenda(capturaSel) }}
            <q-space />
            <q-btn dense flat icon="close" v-close-popup />
          </q-bar>
          <q-img :src="capturaSel.url" fit="contain" />
          <q-card-section v-if="capturaSel.title" class="text-caption">
            {{ capturaSel.title }}
          </q-card-section>
        </q-card>
      </q-dialog>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { useQuasar } from "quasar";
import {
  fetchAgentActivity,
  fetchActivityMonitoringState,
  fetchActivityScreenshots,
  fetchActivityScreenshotBlob,
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
      { name: "sitios", label: t("agentActivity.topSites"), field: "sitiosStr", align: "left" },
      { name: "red", label: t("agentActivity.network"), field: "redStr", align: "left" },
    ]);

    function topStr(m, n, fmt) {
      return Object.entries(m || {})
        .sort((a, b) => fmt.valor(b[1]) - fmt.valor(a[1]))
        .slice(0, n)
        .map(([k, v]) => fmt.texto(k, v))
        .join(", ");
    }

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
        sitiosStr: topStr(x.sitios, 5, {
          valor: (v) => v,
          texto: (k, v) => `${k} (${hm(v)})`,
        }),
        redStr: topStr(x.red, 4, {
          valor: (v) => v.min || 0,
          texto: (k, v) =>
            t("agentActivity.networkItem", {
              app: k,
              tiempo: hm(v.min),
              destinos: v.destinos,
            }),
        }),
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
        componentProps: {
          level: "agent",
          id: selectedAgent.value,
          name: estado.value ? estado.value.hostname : "",
        },
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
        // Al cambiar de equipo la fecha puede ser la misma y el watch no salta.
        cargarCapturas();
      } catch (e) {
        if (e.response && e.response.status === 403) sinPermiso.value = true;
      }
    }

    // --- 049-C: capturas del día ---
    const capturas = ref([]);
    const capturaSel = ref(null);
    const capturaAbierta = ref(false);
    let cargaCapturas = 0;

    function liberarCapturas() {
      capturas.value.forEach((c) => c.url && URL.revokeObjectURL(c.url));
      capturas.value = [];
    }

    async function cargarCapturas() {
      const turno = ++cargaCapturas;
      liberarCapturas();
      if (!selectedAgent.value || !diaSel.value || sinPermiso.value) return;
      let lista = [];
      try {
        lista = await fetchActivityScreenshots(selectedAgent.value, diaSel.value);
      } catch (e) {
        return;
      }
      if (turno !== cargaCapturas) return;
      capturas.value = lista.map((c) => ({ ...c, url: "" }));
      // Miniaturas de a cuatro, para no abrir 100 descargas a la vez.
      const cola = [...capturas.value];
      const agente = selectedAgent.value;
      async function trabajador() {
        while (cola.length && turno === cargaCapturas) {
          const c = cola.shift();
          try {
            const blob = await fetchActivityScreenshotBlob(agente, c.id);
            if (turno === cargaCapturas) c.url = URL.createObjectURL(blob);
          } catch (e) {
            // una captura ilegible no corta la galería
          }
        }
      }
      await Promise.all([trabajador(), trabajador(), trabajador(), trabajador()]);
    }

    function verCaptura(c) {
      if (!c.url) return;
      capturaSel.value = c;
      capturaAbierta.value = true;
    }

    function leyenda(c) {
      return [hora(c.captured_at), c.username, c.process].filter(Boolean).join(" · ");
    }

    function hora(iso) {
      const d = new Date(iso);
      return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    }

    onMounted(cargar);
    watch(selectedAgent, cargar);
    watch(diaSel, cargarCapturas);
    onBeforeUnmount(liberarCapturas);

    return { selectedAgent, estado, configurar, capturas, capturaSel, capturaAbierta, verCaptura, hora, leyenda, dias, diaSel, diaActual, usuarios, opcionesDia, columns, sinPermiso, hm };
  },
};
</script>
