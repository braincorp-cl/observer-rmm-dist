<template>
  <!--
    Columna de contexto de la dirección 1c (046, T026): los equipos del mismo sitio,
    con filtros "chequeos fallando" y "solo en línea" y conteo "N de M", para saltar
    de un equipo a otro sin volver a la tabla (UI-E02). Usa la misma GET que la
    tabla del dashboard (fetchAgents con ?site=): ninguna llamada nueva (RN-01).
    Elegir un equipo hace router.push: "atrás" vuelve al anterior.
  -->
  <aside
    class="obs-ctx column no-wrap"
    :aria-label="$t('agentWorkspace.context.label')"
  >
    <div class="obs-ctx__head">
      <div class="obs-ctx__client ellipsis" :title="clientName">
        {{ clientName }}
      </div>
      <div class="obs-ctx__site ellipsis" :title="siteLineText">
        <i18n-t keypath="agentWorkspace.context.siteLine" tag="span">
          <template #site>{{ siteName }}</template>
          <template #count>
            <!-- 050 V2-P11 / UI-E02 (2026-11-19): antes del primer GET el conteo
                 era agents.length = 0 y se leía «Sin equipos» durante 0,4–1,1 s
                 con la API devolviendo 1. Mientras no hay dato, la frase cambia
                 ENTERA (una por estado) y no se muestra un número que no se sabe. -->
            <span v-if="estado === 'cargando'" data-estado="cargando">{{
              $t("agentWorkspace.context.equipmentLoading")
            }}</span>
            <span v-else-if="estado === 'error'" data-estado="error">{{
              $t("agentWorkspace.context.equipmentUnknown")
            }}</span>
            <i18n-t
              v-else
              keypath="agentWorkspace.context.equipmentCount"
              :plural="agents.length"
              tag="span"
              ><template #n
                ><span>{{ agents.length }}</span></template
              ></i18n-t
            >
          </template>
        </i18n-t>
      </div>
      <div class="row q-gutter-xs q-mt-sm">
        <q-chip
          clickable
          dense
          :outline="!onlyFailing"
          class="obs-ctx__chip"
          :class="{ 'obs-ctx__chip--on-neg': onlyFailing }"
          data-filter="failing"
          :aria-pressed="onlyFailing ? 'true' : 'false'"
          @click="onlyFailing = !onlyFailing"
        >
          <!-- V2-P11 / UI-E02 (2026-11-20): sin dato, el chip no inventa un 0. -->
          <span v-if="estado !== 'ok'">{{
            $t("agentWorkspace.context.filterFailing")
          }}</span>
          <i18n-t
            v-else
            keypath="agentWorkspace.context.filterFailingN"
            tag="span"
            ><template #n
              ><span class="mono">{{ failingCount }}</span></template
            ></i18n-t
          >
        </q-chip>
        <q-chip
          clickable
          dense
          :outline="!onlyOnline"
          class="obs-ctx__chip"
          :class="{ 'obs-ctx__chip--on': onlyOnline }"
          data-filter="online"
          :aria-pressed="onlyOnline ? 'true' : 'false'"
          @click="onlyOnline = !onlyOnline"
        >
          {{ $t("agentWorkspace.context.filterOnline") }}
        </q-chip>
      </div>
    </div>
    <div class="col obs-ctx__list" style="min-height: 0">
      <div
        v-if="estado === 'ok' && !shown.length"
        class="q-pa-md obs-ctx__empty"
      >
        {{ $t("agentWorkspace.context.empty") }}
      </div>
      <q-virtual-scroll
        v-else
        :items="shown"
        separator
        class="fit"
        v-slot="{ item }"
      >
        <q-item
          :key="item.agent_id"
          clickable
          :active="item.agent_id === currentId"
          active-class="obs-ctx__item--active"
          class="obs-ctx__item"
          :data-agent="item.agent_id"
          @click="open(item)"
        >
          <q-item-section avatar class="obs-ctx__dotcol">
            <span
              class="obs-ctx__dot"
              :class="`obs-ctx__dot--${dot(item)}`"
              role="img"
              :aria-label="dotText(item)"
              :title="dotText(item)"
            />
          </q-item-section>
          <q-item-section>
            <q-item-label
              class="ellipsis obs-ctx__host"
              :title="item.hostname"
              >{{ item.hostname }}</q-item-label
            >
            <q-item-label
              v-if="item.description"
              caption
              class="ellipsis obs-ctx__desc"
              :title="item.description"
              >{{ item.description }}</q-item-label
            >
            <q-item-label
              v-if="item.checks && item.checks.failing > 0"
              caption
              class="obs-ctx__fail"
              ><i18n-t
                keypath="agentWorkspace.badges.failingChecks"
                :plural="item.checks.failing"
                tag="span"
                ><template #n
                  ><span>{{ item.checks.failing }}</span></template
                ></i18n-t
              ></q-item-label
            >
          </q-item-section>
        </q-item>
      </q-virtual-scroll>
    </div>
    <!-- V2-P11 / UI-E02 (2026-11-20): «0 de 0» mientras carga contradecía a la API. -->
    <div v-if="estado === 'ok'" class="obs-ctx__foot">
      <i18n-t keypath="agentWorkspace.context.shownOf" tag="span">
        <template #shown
          ><span>{{ shown.length }}</span></template
        >
        <template #total
          ><span>{{ agents.length }}</span></template
        >
      </i18n-t>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { fetchAgents } from "@/api/agents";

const props = defineProps({
  agent: { type: Object, required: true },
});

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const agents = ref([]);
const loading = ref(false);
// "cargando" hasta que el GET del sitio responde; "error" si falla. El conteo y
// el estado vacío solo se dibujan con dato ("ok").
const estado = ref("cargando");
const onlyFailing = ref(false);
const onlyOnline = ref(false);

const currentId = computed(() => route.params.agent_id);
const clientName = computed(() => props.agent.client || "");
const siteName = computed(() => props.agent.site_name || "");
// V2-G08: si la línea se corta, el title la devuelve ENTERA, con el conteo.
const siteLineText = computed(() => {
  const count =
    estado.value === "cargando"
      ? t("agentWorkspace.context.equipmentLoading")
      : estado.value === "error"
        ? t("agentWorkspace.context.equipmentUnknown")
        : t("agentWorkspace.context.equipmentCount", agents.value.length, {
            n: agents.value.length,
          });
  return t("agentWorkspace.context.siteLine", { site: siteName.value, count });
});

const failingCount = computed(
  () => agents.value.filter((a) => a.checks && a.checks.failing > 0).length,
);

const shown = computed(() =>
  agents.value
    .filter((a) => !onlyFailing.value || (a.checks && a.checks.failing > 0))
    .filter((a) => !onlyOnline.value || a.status === "online")
    .slice()
    .sort((a, b) => a.hostname.localeCompare(b.hostname)),
);

function dot(a) {
  if (a.status !== "online")
    return a.status === "overdue" ? "overdue" : "offline";
  if (a.checks && a.checks.failing > 0) return "fail";
  return "ok";
}

// El punto de salud mide 8 px y no lleva texto: sin rótulo el color era la única
// señal del estado del equipo. Mismo patrón que AgentHeader (statusText): el
// estado traducido va al elemento, no sólo al color.
function dotText(a) {
  return t(`agentWorkspace.context.status.${dot(a)}`);
}

function open(a) {
  if (a.agent_id === currentId.value) return;
  router.push({
    name: "Agent",
    params: { agent_id: a.agent_id, section: route.params.section },
  });
}

async function load(siteId) {
  if (!siteId) return;
  loading.value = true;
  estado.value = "cargando";
  agents.value = [];
  try {
    const data = await fetchAgents({ site: siteId });
    if (props.agent.site !== siteId) return; // respuesta de un sitio anterior
    agents.value = Array.isArray(data) ? data : [];
    estado.value = "ok";
  } catch (e) {
    console.error(e);
    if (props.agent.site === siteId) estado.value = "error";
  } finally {
    if (props.agent.site === siteId) loading.value = false;
  }
}

watch(
  () => props.agent.site,
  (n, o) => {
    if (n !== o) load(n);
  },
  { immediate: true },
);
</script>

<style lang="sass" scoped>
.obs-ctx
  width: 296px
  flex: none
  border-right: 1px solid var(--obs-border)
  background: var(--obs-surface)
.obs-ctx__head
  padding: 14px 14px 10px
  border-bottom: 1px solid var(--obs-border)
.obs-ctx__client
  font-size: 15px
  font-weight: 600
  color: var(--obs-text)
.obs-ctx__site
  font-size: 12.5px
  color: var(--obs-muted)
.obs-ctx__chip
  color: var(--obs-text-2)
.obs-ctx__chip--on
  background: var(--obs-selected)
  color: var(--obs-text)
// 🔴 050 (G05, 19.a corrida): el mismo defecto, latente. Esta clase se aplica al
// q-chip `clickable` MISMO cuando el filtro «con fallas» esta encendido, asi que
// el rotulo del control se iba entero a --q-negative. Ningun critico lo midio
// porque el filtro arranca apagado y ese estado no se ejercio: lo encontro el
// censo de la clase. Mismo arreglo y mismo patron aprobado: el numero en rojo,
// el rotulo del control neutro, igual que .obs-ctx__chip--on.
.obs-ctx__chip--on-neg
  background: var(--obs-selected)
  color: var(--obs-text)
  .mono
    color: var(--q-negative)
.obs-ctx__list
  overflow: hidden
.obs-ctx__empty
  color: var(--obs-muted)
  font-size: 13px
.obs-ctx__item
  padding: 8px 12px
.obs-ctx__item--active
  background: var(--obs-selected)
.obs-ctx__dotcol
  min-width: 18px
  padding-right: 4px
.obs-ctx__dot
  width: 8px
  height: 8px
  border-radius: 99px
  background: var(--obs-faint)
.obs-ctx__dot--ok
  background: var(--q-positive)
.obs-ctx__dot--fail
  background: var(--q-negative)
.obs-ctx__dot--overdue
  background: var(--q-warning)
// Desconectado tenía clase en el template pero no regla: caía al --obs-faint
// base, indistinguible de "sin estado". Mismo token que AgentHeader.
.obs-ctx__dot--offline
  background: var(--q-warning)
.obs-ctx__host
  font-weight: 600
  color: var(--obs-text)
.obs-ctx__desc
  color: var(--obs-muted)
// 🔴 050 (G05, 19.a corrida): esta clase pintaba el ROTULO COMPLETO del
// q-item-label en --q-negative, y el q-item es `clickable` (@click=open), o sea
// color de estado sobre el rotulo de un control de navegacion. Medido en el DOM:
// texto «1 chequeo fallando», rgb(197,40,45) claro y rgb(242,90,95) oscuro, sin
// fondo ni borde propios, rect [90,236,253,14] contenido en el del control
// [60,207,295,51], sin rotulo accesible propio. Tres de seis criticos lo
// cazaron; la clausula del 2026-10-14 lo nombra: «viola si la superficie propia
// del control, es decir su fondo, borde o ROTULO, lleva color de estado».
// 🔑 Y el patron correcto ya estaba en el proyecto, aprobado el 2026-10-14 con
// el ejemplo del «numero rojo de un KPI que filtra»: el NUMERO lleva el color de
// estado y el ROTULO del control se queda neutro, que es exactamente como vive
// .obs-fleet__kpi-num--neg junto a .obs-fleet__kpi-label. Acá el numero ya tenia
// su propio span.mono, asi que el arreglo es mover el color a ese span. El dato
// (item.checks.failing) no se pierde y el punto de salud de la izquierda sigue
// llevando el estado en color con su fondo propio y su title.
.obs-ctx__fail
  color: var(--obs-muted)
  .mono
    color: var(--q-negative)
.obs-ctx__foot
  padding: 8px 14px
  font-size: 12px
  color: var(--obs-muted)
  border-top: 1px solid var(--obs-border)
</style>
