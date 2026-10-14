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
        <q-chip v-if="diaActual && diaActual.partial" dense color="warning" text-color="white">
          {{ $t("agentActivity.partial") }}
        </q-chip>
        <q-space />
        <!-- 049-E: captura del momento y exportación a Excel -->
        <q-btn
          v-if="estado && estado.active"
          dense
          flat
          size="sm"
          icon="photo_camera"
          :label="$t('agentActivity.captureNow')"
          :loading="capturando"
          :disable="enLinea === false"
          @click="capturarAhora"
        >
          <q-tooltip v-if="enLinea === false">{{ $t("activityLive.offline") }}</q-tooltip>
        </q-btn>
        <q-btn dense flat size="sm" icon="download" :label="$t('agentActivity.exportXlsx')" :loading="exportando" @click="exportar" />
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

      <!-- Feature 049-D: tramos de 10 min por usuario (% activo, apagado,
           suspendido, sin datos) y pausas. -->
      <div v-for="u in usuarios.filter((x) => x.tramosVista)" :key="`tr-${u.usuario}`" class="q-mt-md">
        <div class="text-subtitle2">
          {{ u.usuario }}
          <span v-if="u.primer_activo" class="text-caption text-grey q-ml-sm">
            {{ $t("agentActivity.workday", { desde: u.primer_activo, hasta: u.ultimo_activo }) }}
          </span>
        </div>
        <div class="tramos-horas">
          <div v-for="h in 24" :key="h" class="tramos-hora">
            {{ h % 2 === 1 ? String(h - 1).padStart(2, "0") : "" }}
          </div>
        </div>
        <div class="tramos">
          <div
            v-for="(tr, i) in u.tramosVista"
            :key="i"
            class="tramo"
            :class="{ 'tramo-hora': i % 6 === 0 }"
            :style="{ background: colorTramo(tr) }"
          >
            <q-tooltip>{{ textoTramo(tr) }}</q-tooltip>
          </div>
        </div>
        <div v-if="u.entrada" class="tramos tramos-entrada">
          <div
            v-for="(e, i) in u.entradaVista"
            :key="`e-${i}`"
            class="tramo"
            :style="{ background: e[0] ? 'var(--obs-act-keys)' : e[1] ? 'var(--obs-act-mouse)' : 'transparent' }"
          >
            <q-tooltip v-if="e[0] || e[1]">{{ $t("agentActivity.slotInput", { k: e[0], m: e[1] }) }}</q-tooltip>
          </div>
        </div>
        <!-- 049-E: aplicaciones con tiempo activo e inactivo -->
        <div v-if="u.apps.length" class="q-mt-sm">
          <div v-for="a in u.apps" :key="a.p" class="row items-center no-wrap text-caption">
            <div class="ellipsis" style="width: 160px">{{ a.p }}</div>
            <div class="col row no-wrap" style="height: 10px">
              <div :style="{ width: `${(100 * a.a) / u.appsMax}%`, background: 'var(--obs-act-app)' }" />
              <div :style="{ width: `${(100 * a.i) / u.appsMax}%`, background: 'var(--obs-act-app-idle)' }" />
            </div>
            <div class="q-ml-sm text-grey" style="width: 110px">{{ `${hm(a.a)} / ${hm(a.i)}` }}</div>
          </div>
        </div>
        <div v-if="(u.pausas || []).length" class="text-caption text-grey q-mt-xs">
          {{ `${$t("agentActivity.breaks")}: ${u.pausas.map((p) => `${p[0]}–${p[1]}`).join(" · ")}` }}
        </div>
      </div>
      <div v-if="usuarios.some((x) => x.tramosVista)" class="row items-center q-gutter-sm q-mt-xs text-caption text-grey">
        <span><span class="leyenda" :style="{ background: colorTramo({ estado: 'medido', pct: 100 }) }" /> {{ $t("agentActivity.legendActive") }}</span>
        <span><span class="leyenda" :style="{ background: colorTramo({ estado: 'medido', pct: 0 }) }" /> {{ $t("agentActivity.legendIdle") }}</span>
        <span><span class="leyenda" :style="{ background: colorTramo({ estado: 'apagado' }) }" /> {{ $t("agentActivity.legendOff") }}</span>
        <span><span class="leyenda" :style="{ background: colorTramo({ estado: 'suspendido' }) }" /> {{ $t("agentActivity.legendSuspended") }}</span>
        <span><span class="leyenda leyenda-vacia" /> {{ $t("agentActivity.legendNoData") }}</span>
        <span><span class="leyenda" style="background: var(--obs-act-keys)" /> {{ $t("agentActivity.legendKeys") }}</span>
        <span><span class="leyenda" style="background: var(--obs-act-mouse)" /> {{ $t("agentActivity.legendMouse") }}</span>
        <span><span class="leyenda" style="background: var(--obs-act-app)" /> {{ $t("agentActivity.legendAppActive") }}</span>
        <span><span class="leyenda" style="background: var(--obs-act-app-idle)" /> {{ $t("agentActivity.legendAppIdle") }}</span>
      </div>

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
  fetchAgent,
  fetchAgentActivity,
  fetchActivityMonitoringState,
  fetchActivityScreenshots,
  fetchActivityScreenshotBlob,
  forceActivityScreenshot,
  downloadActivityExport,
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
      {
        name: "jornada",
        label: t("agentActivity.workdayCol"),
        field: (r) => (r.primer_activo ? `${r.primer_activo}–${r.ultimo_activo}` : "—"),
        align: "left",
      },
      {
        name: "pausas",
        label: t("agentActivity.breaks"),
        field: (r) => (r.pausasMin ? `${(r.pausas || []).length} · ${hm(r.pausasMin)}` : "—"),
        align: "right",
      },
      {
        name: "meta",
        label: t("agentActivity.goalPct"),
        field: (r) => (metaMin.value ? `${Math.round((100 * (r.activo_min || 0)) / metaMin.value)}%` : "—"),
        align: "right",
      },
      {
        name: "entrada",
        label: t("agentActivity.keysMouse"),
        field: (r) => ("teclas" in r || r.entrada ? `${r.teclas || 0} / ${r.mouse || 0}` : "—"),
        align: "right",
      },
      { name: "capturas", label: t("agentActivity.captures"), field: "capturas", align: "right" },
      { name: "procs", label: t("agentActivity.topProcesses"), field: "procsStr", align: "left" },
      { name: "sitios", label: t("agentActivity.topSites"), field: "sitiosStr", align: "left" },
      { name: "urls", label: t("agentActivity.topUrls"), field: "urlsStr", align: "left" },
      { name: "red", label: t("agentActivity.network"), field: "redStr", align: "left" },
    ]);

    // "Zoho Mail (persona@dominio)" -> "Zoho Mail" (mismo criterio que los reportes).
    function sinCorreo(m) {
      const out = {};
      Object.entries(m || {}).forEach(([k, v]) => {
        const n = k.replace(/\s*\([^()]*@[^()]*\)/g, "").trim();
        if (n) out[n] = (out[n] || 0) + v;
      });
      return out;
    }

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
    const metaMin = computed(() => (estado.value && estado.value.expected_min) || 0);

    // --- 049-D: tramos de 10 min (mismo criterio que los reportes) ---
    function aMin(hhmm) {
      const [h, m] = String(hhmm || "").split(":").map(Number);
      return Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : null;
    }

    function tramosDe(u, huecos) {
      if (!u.tramos || !Object.keys(u.tramos).length) return null;
      const motivo = {};
      (huecos || []).forEach((h) => {
        const a = aMin(h.desde);
        const b = aMin(h.hasta);
        if (a === null || b === null) return;
        for (let i = Math.floor(a / 10); i < Math.min(Math.floor((b + 9) / 10), 144); i++) {
          if (!(i in motivo)) motivo[i] = h.motivo || "apagado";
        }
      });
      return Array.from({ length: 144 }, (_, i) => {
        const par = u.tramos[String(i)];
        const t = `${String(Math.floor(i / 6)).padStart(2, "0")}:${(i % 6) * 10 || "00"}`;
        if (par && par[1] > 0) {
          return { t, estado: "medido", pct: Math.min(Math.round((100 * par[0]) / par[1]), 100) };
        }
        return { t, estado: motivo[i] || "sin_datos", pct: null };
      });
    }

    function colorTramo(tr) {
      if (tr.estado === "medido") {
        return tr.pct === 0 ? "var(--obs-act-idle)" : `color-mix(in srgb, var(--obs-act-on) ${Math.round(15 + 0.85 * tr.pct)}%, transparent)`;
      }
      if (tr.estado === "apagado") return "var(--obs-act-off)";
      if (tr.estado === "suspendido") return "var(--obs-act-susp)";
      return "transparent";
    }

    function textoTramo(tr) {
      if (tr.estado === "medido") return t("agentActivity.slotActive", { t: tr.t, pct: tr.pct });
      const clave = { apagado: "legendOff", suspendido: "legendSuspended" }[tr.estado] || "legendNoData";
      return `${tr.t} · ${t(`agentActivity.${clave}`)}`;
    }

    // 049-E: activo e inactivo por aplicación (top 8).
    function appsDe(x) {
      const a = x.procs || {};
      const i = x.procs_i || {};
      const apps = [...new Set([...Object.keys(a), ...Object.keys(i)])]
        .map((p) => ({ p, a: a[p] || 0, i: i[p] || 0 }))
        .sort((m, n) => n.a + n.i - (m.a + m.i))
        .slice(0, 8);
      const appsMax = Math.max(1, ...apps.map((m) => m.a + m.i));
      return { apps: Object.keys(i).length ? apps : [], appsMax };
    }

    const usuarios = computed(() => {
      if (!diaActual.value) return [];
      const doc = diaActual.value.data || {};
      const dia = (doc.dias || [])[0] || {};
      const u = dia.usuarios || [];
      return u.map((x) => ({
        ...x,
        tramosVista: tramosDe(x, dia.huecos),
        entradaVista: Array.from({ length: 144 }, (_, i) => (x.entrada || {})[String(i)] || [0, 0]),
        ...appsDe(x),
        urlsStr: topStr(x.urls, 4, { valor: (v) => v, texto: (k, v) => `${k} (${hm(v)})` }),
        pausasMin: (x.pausas || []).reduce((acc, p) => {
          const a = aMin(p[0]);
          const b = aMin(p[1]);
          return a !== null && b !== null && b >= a ? acc + (b - a) : acc;
        }, 0),
        procsStr: Object.entries(x.procs || {})
          .sort((a, b) => b[1] - a[1])
          .slice(0, 6)
          .map(([proceso, min]) => `${proceso} (${hm(min)})`)
          .join(", "),
        sitiosStr: topStr(sinCorreo(x.sitios), 5, {
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

    // 049-E: sin conexión no se ofrece «Captura ahora» (no hay a quién pedírsela).
    const enLinea = ref(null);

    async function cargarEstado() {
      estado.value = null;
      enLinea.value = null;
      if (!selectedAgent.value) return;
      try {
        estado.value = await fetchActivityMonitoringState(selectedAgent.value);
      } catch (e) {
        estado.value = null;
      }
      try {
        const agent = await fetchAgent(selectedAgent.value);
        enLinea.value = agent ? agent.status === "online" : null;
      } catch (e) {
        enLinea.value = null;
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

    // --- 049-E: captura del momento y exportación XLSX ---
    const capturando = ref(false);
    const exportando = ref(false);

    async function capturarAhora() {
      capturando.value = true;
      try {
        const r = await forceActivityScreenshot(selectedAgent.value);
        if (r.estado === "ok") {
          await cargarCapturas();
          $q.notify({ type: "positive", message: t("activityLive.state_ok") });
        } else {
          $q.notify({ type: "warning", message: t(`activityLive.state_${r.estado}`) });
        }
      } catch (e) {
        $q.notify({ type: "negative", message: t("activityLive.state_error") });
      } finally {
        capturando.value = false;
      }
    }

    async function exportar() {
      exportando.value = true;
      try {
        const hasta = diaSel.value || new Date().toISOString().slice(0, 10);
        const d = new Date(`${hasta}T12:00:00`);
        d.setDate(d.getDate() - 29);
        const desde = d.toISOString().slice(0, 10);
        const blob = await downloadActivityExport({ agent_id: selectedAgent.value, desde, hasta });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `actividad_${estado.value ? estado.value.hostname : "equipo"}_${desde}_${hasta}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
      } catch (e) {
        $q.notify({ type: "negative", message: t("activityLive.state_error") });
      } finally {
        exportando.value = false;
      }
    }

    onMounted(cargar);
    watch(selectedAgent, cargar);
    watch(diaSel, cargarCapturas);
    onBeforeUnmount(liberarCapturas);

    return { enLinea, capturando, exportando, capturarAhora, exportar, colorTramo, textoTramo, selectedAgent, estado, configurar, capturas, capturaSel, capturaAbierta, verCaptura, hora, leyenda, dias, diaSel, diaActual, usuarios, opcionesDia, columns, sinPermiso, hm };
  },
};
</script>

<style scoped>
.tramos-horas,
.tramos {
  display: flex;
  width: 100%;
}
.tramos-hora {
  flex: 6;
  font-size: 10px;
  color: var(--obs-faint);
}
.tramos {
  height: 16px;
  border: 1px solid var(--obs-border);
  border-radius: 3px;
  overflow: hidden;
}
.tramo {
  flex: 1;
}
.tramos-entrada {
  height: 5px;
  margin-top: 2px;
}
.tramo-hora {
  border-left: 1px solid var(--obs-border);
}
.leyenda {
  display: inline-block;
  width: 12px;
  height: 12px;
  vertical-align: middle;
  border-radius: 2px;
}
.leyenda-vacia {
  border: 1px solid var(--obs-border);
}
</style>
