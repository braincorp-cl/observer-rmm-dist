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
      <div class="obs-ctx__site ellipsis" :title="siteName">
        <i18n-t keypath="agentWorkspace.context.siteLine" tag="span">
          <template #site>{{ siteName }}</template>
          <template #count>
            <i18n-t
              keypath="agentWorkspace.context.equipmentCount"
              :plural="agents.length"
              tag="span"
              ><template #n
                ><span class="mono">{{ agents.length }}</span></template
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
          <i18n-t keypath="agentWorkspace.context.filterFailingN" tag="span"
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
      <div v-if="!loading && !shown.length" class="q-pa-md obs-ctx__empty">
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
            <span class="obs-ctx__dot" :class="`obs-ctx__dot--${dot(item)}`" />
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
                  ><span class="mono">{{ item.checks.failing }}</span></template
                ></i18n-t
              ></q-item-label
            >
          </q-item-section>
        </q-item>
      </q-virtual-scroll>
    </div>
    <div class="obs-ctx__foot">
      <i18n-t keypath="agentWorkspace.context.shownOf" tag="span">
        <template #shown
          ><span class="mono">{{ shown.length }}</span></template
        >
        <template #total
          ><span class="mono">{{ agents.length }}</span></template
        >
      </i18n-t>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { fetchAgents } from "@/api/agents";

const props = defineProps({
  agent: { type: Object, required: true },
});

const route = useRoute();
const router = useRouter();
const agents = ref([]);
const loading = ref(false);
const onlyFailing = ref(false);
const onlyOnline = ref(false);

const currentId = computed(() => route.params.agent_id);
const clientName = computed(() => props.agent.client || "");
const siteName = computed(() => props.agent.site_name || "");

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
  try {
    const data = await fetchAgents({ site: siteId });
    agents.value = Array.isArray(data) ? data : [];
  } catch (e) {
    console.error(e);
  }
  loading.value = false;
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
.obs-ctx__chip--on-neg
  background: var(--obs-selected)
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
.obs-ctx__host
  font-weight: 600
  color: var(--obs-text)
.obs-ctx__desc
  color: var(--obs-muted)
.obs-ctx__fail
  color: var(--q-negative)
.obs-ctx__foot
  padding: 8px 14px
  font-size: 12px
  color: var(--obs-muted)
  border-top: 1px solid var(--obs-border)
</style>
