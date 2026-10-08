<template>
  <!--
    Cabecera del espacio de trabajo 1c (046, T018): migas Cliente / Sitio, hostname,
    estado con antigüedad, línea SO · modelo · RAM · arranque, los 4 badges de
    urgencia, y los botones de cabecera del Resumen v1 (refrescar inventario, abrir
    en ventana, tomar control, ubicación, acciones) más mantenimiento y política.
  -->
  <header class="obs-agenthdr">
    <div class="row no-wrap items-start">
      <!-- 046 T029 (UI-R01): con la columna de contexto plegada (< 1200 px),
           este botón la abre superpuesta. -->
      <q-btn
        v-if="contextToggle"
        flat
        round
        dense
        icon="view_list"
        class="q-mr-sm"
        data-action="toggle-context"
        :aria-label="$t('agentWorkspace.header.showList')"
        :aria-expanded="contextOpen ? 'true' : 'false'"
        @click="$emit('toggle-context')"
      >
        <q-tooltip>{{ $t("agentWorkspace.header.showList") }}</q-tooltip>
      </q-btn>
      <div class="col" style="min-width: 0">
        <div class="obs-agenthdr__crumbs ellipsis" :title="crumbs">
          {{ crumbs }}
        </div>
        <div class="row items-center no-wrap q-gutter-x-sm">
          <h1 class="obs-agenthdr__host ellipsis" :title="agent.hostname">
            {{ agent.hostname }}
          </h1>
          <span
            class="obs-agenthdr__status"
            :class="`obs-agenthdr__status--${agent.status}`"
          >
            <span class="obs-agenthdr__dot" />
            {{ statusText }}
            <q-tooltip>{{
              store.getters.formatDate(agent.last_seen)
            }}</q-tooltip>
          </span>
          <q-badge
            v-if="agent.maintenance_mode"
            class="obs-agenthdr__maint"
            :label="$t('agentTabs.summary.maintenanceMode')"
          >
            <q-tooltip>
              {{
                $t("agentTable.maintenanceSince", {
                  since: agent.maintenance_mode_since
                    ? store.getters.formatDate(agent.maintenance_mode_since)
                    : $t("agentTable.maintenanceUnknown"),
                })
              }}<br />
              {{
                $t("agentTable.maintenanceBy", {
                  by:
                    agent.maintenance_mode_by ||
                    $t("agentTable.maintenanceUnknown"),
                })
              }}
            </q-tooltip>
          </q-badge>
        </div>
        <!-- 046 (UI-D01): solo el valor de especificación (RAM) va en mono; nombres
             con versión y frases quedan en Archivo. El separador lo pone el CSS. -->
        <div class="obs-agenthdr__sys" :title="sysLine">
          <span
            v-for="(part, i) in sysParts"
            :key="i"
            class="obs-sys-part"
            :class="{ mono: part.mono && !part.label }"
            ><template v-if="part.label"
              >{{ part.label }} <span class="mono">{{ part.t }}</span></template
            ><template v-else>{{ part.t }}</template></span
          >
        </div>
      </div>
      <div class="row no-wrap items-center q-gutter-x-sm obs-agenthdr__btns">
        <!-- 046 (UI-E02): mantenimiento y política como íconos con tooltip; el
             hostname tiene prioridad de ancho (con la columna de contexto, los
             botones con texto lo truncaban a 1440 px). -->
        <!-- 046 (UI-D05): control encendido (mantenimiento activo) en teal, no en
             ámbar de estado (enmienda 2026-10-06). El estado lo muestra el badge. -->
        <q-btn
          flat
          round
          dense
          icon="construction"
          :color="agent.maintenance_mode ? 'primary' : undefined"
          data-action="maintenance"
          :aria-label="maintenanceLabel"
          @click="run('maintenance')"
        >
          <q-tooltip>{{ maintenanceLabel }}</q-tooltip>
        </q-btn>
        <q-btn
          flat
          round
          dense
          icon="policy"
          data-action="assignPolicy"
          :aria-label="$t('agentActions.assignPolicy')"
          @click="run('assignPolicy')"
        >
          <q-tooltip>{{ $t("agentActions.assignPolicy") }}</q-tooltip>
        </q-btn>
        <q-btn
          flat
          round
          dense
          icon="refresh"
          :loading="refreshing"
          :aria-label="$t('agentWorkspace.header.refresh')"
          @click="$emit('refresh-wmi')"
        >
          <q-tooltip>{{ $t("agentWorkspace.header.refresh") }}</q-tooltip>
        </q-btn>
        <q-btn
          flat
          round
          dense
          icon="open_in_new"
          :aria-label="$t('agentTabs.summary.popout')"
          @click="openAgentWindow(agent.agent_id)"
        >
          <q-tooltip>{{ $t("agentTabs.summary.popout") }}</q-tooltip>
        </q-btn>
        <q-btn
          flat
          round
          dense
          icon="computer"
          :aria-label="$t('agentTabs.summary.takeControl')"
          @click="runTakeControl(agent.agent_id)"
        >
          <q-tooltip>{{ $t("agentTabs.summary.takeControl") }}</q-tooltip>
        </q-btn>
        <q-btn
          flat
          round
          dense
          icon="place"
          :aria-label="$t('agentTabs.location.button')"
          @click="showLocation = true"
        >
          <q-tooltip>{{ $t("agentTabs.location.button") }}</q-tooltip>
        </q-btn>
        <q-btn
          flat
          round
          dense
          icon="more_horiz"
          :aria-label="$t('agentTabs.summary.actions')"
        >
          <q-tooltip>{{ $t("agentTabs.summary.actions") }}</q-tooltip>
          <q-menu>
            <AgentActionMenu :agent="agent" />
          </q-menu>
        </q-btn>
      </div>
    </div>
    <div class="row q-gutter-sm q-mt-sm obs-agenthdr__badges">
      <span
        v-if="urgency.failingChecks > 0"
        class="obs-badge obs-badge--neg"
        data-badge="failingChecks"
      >
        <q-icon name="error_outline" size="16px" />
        <i18n-t
          keypath="agentWorkspace.badges.failingChecks"
          :plural="urgency.failingChecks"
          tag="span"
          ><template #n
            ><span class="mono">{{ urgency.failingChecks }}</span></template
          ></i18n-t
        >
      </span>
      <span
        v-if="urgency.pendingPatches > 0"
        class="obs-badge obs-badge--warn"
        data-badge="pendingPatches"
      >
        <q-icon name="download" size="16px" />
        <i18n-t
          keypath="agentWorkspace.badges.pendingPatches"
          :plural="urgency.pendingPatches"
          tag="span"
          ><template #n
            ><span class="mono">{{ urgency.pendingPatches }}</span></template
          ></i18n-t
        >
      </span>
      <span
        v-if="urgency.pendingActions > 0"
        class="obs-badge"
        data-badge="pendingActions"
      >
        <q-icon name="pending_actions" size="16px" />
        <i18n-t
          keypath="agentWorkspace.badges.pendingActions"
          :plural="urgency.pendingActions"
          tag="span"
          ><template #n
            ><span class="mono">{{ urgency.pendingActions }}</span></template
          ></i18n-t
        >
      </span>
      <span
        v-if="urgency.rebootRequired"
        class="obs-badge obs-badge--warn"
        data-badge="rebootRequired"
      >
        <q-icon name="restart_alt" size="16px" />
        {{ $t("agentWorkspace.badges.rebootRequired") }}
      </span>
    </div>
    <AgentLocationDialog
      v-model="showLocation"
      :agent-id="agent.agent_id"
      :hostname="agent.hostname"
    />
  </header>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { runTakeControl, openAgentWindow } from "@/api/agents";
import AgentActionMenu from "@/components/agents/AgentActionMenu.vue";
import AgentLocationDialog from "@/components/agents/AgentLocationDialog.vue";

const props = defineProps({
  agent: { type: Object, required: true },
  urgency: { type: Object, required: true },
  actions: { type: Array, required: true },
  contextToggle: { type: Boolean, default: false },
  contextOpen: { type: Boolean, default: false },
  refreshing: { type: Boolean, default: false },
});
defineEmits(["refresh-wmi", "toggle-context"]);

const store = useStore();
const { t } = useI18n();
const showLocation = ref(false);

// Reloj reactivo: "hace N s" se recalcula cada segundo. Date.now() dentro de un
// computed no es reactivo y la antigüedad quedaba congelada al montar (UI-E06).
const now = ref(Date.now());
let tick = null;
onMounted(() => {
  tick = setInterval(() => (now.value = Date.now()), 1000);
});
onBeforeUnmount(() => clearInterval(tick));

const maintenanceLabel = computed(() =>
  props.agent.maintenance_mode
    ? t("agentActions.disableMaintenance")
    : t("agentActions.enableMaintenance"),
);

function run(key) {
  const a = props.actions.find((x) => x.key === key);
  if (a && a.run) a.run();
}

function ago(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return t("agentWorkspace.units.s", { n: s });
  if (s < 3600) return t("agentWorkspace.units.min", { n: Math.round(s / 60) });
  if (s < 86400)
    return t("agentWorkspace.units.h", { n: Math.round(s / 3600) });
  return t("agentWorkspace.units.d", { n: Math.round(s / 86400) });
}

const crumbs = computed(() =>
  [props.agent.client, props.agent.site_name].filter(Boolean).join(" / "),
);

const statusText = computed(() => {
  const since = props.agent.last_seen
    ? (now.value - new Date(props.agent.last_seen).getTime()) / 1000
    : 0;
  const key =
    props.agent.status === "online"
      ? "onlineAgo"
      : props.agent.status === "overdue"
        ? "overdueAgo"
        : "offlineAgo";
  return t(`agentWorkspace.header.${key}`, { ago: ago(since) });
});

const sysParts = computed(() => {
  const a = props.agent;
  // SO = nombre con versión (Archivo); modelo de hardware = especificación (mono).
  const parts = [];
  if (a.operating_system) parts.push({ t: a.operating_system, mono: false });
  if (a.make_model) parts.push({ t: a.make_model, mono: true });
  if (a.total_ram)
    parts.push({
      t: t("agentWorkspace.header.ram", { gb: a.total_ram }),
      mono: true,
    });
  // Versión del agente: la v1 la muestra en la barra del Resumen (UI-F06).
  if (a.version)
    parts.push({
      label: t("agentWorkspace.header.agentLabel"),
      t: `v${a.version}`,
      mono: true,
    });
  if (a.boot_time)
    parts.push({
      t: t("agentWorkspace.header.bootedAgo", {
        ago: ago(now.value / 1000 - a.boot_time),
      }),
      mono: false,
    });
  return parts;
});

const sysLine = computed(() => {
  const a = props.agent;
  const parts = [a.operating_system, a.make_model];
  if (a.total_ram)
    parts.push(t("agentWorkspace.header.ram", { gb: a.total_ram }));
  if (a.version)
    parts.push(`${t("agentWorkspace.header.agentLabel")} v${a.version}`);
  if (a.boot_time)
    parts.push(
      t("agentWorkspace.header.bootedAgo", {
        ago: ago(now.value / 1000 - a.boot_time),
      }),
    );
  return parts.filter(Boolean).join(" · ");
});
</script>

<style lang="sass" scoped>
.obs-agenthdr
  padding: 16px 20px 14px
  border-bottom: 1px solid var(--obs-border)
  background: var(--obs-page)
.obs-agenthdr__crumbs
  font-size: 12.5px
  color: var(--obs-muted)
.obs-agenthdr__host
  font-size: 26px
  flex: 0 1 auto
  min-width: 120px
  line-height: 1.2
  font-weight: 600
  margin: 2px 0
  color: var(--obs-text)
.obs-agenthdr__status
  display: inline-flex
  align-items: center
  gap: 6px
  font-size: 12.5px
  padding: 3px 10px
  border-radius: 99px
  background: var(--obs-raised)
  color: var(--obs-text-2)
  white-space: nowrap
.obs-agenthdr__dot
  width: 7px
  height: 7px
  border-radius: 99px
  background: var(--obs-faint)
.obs-agenthdr__status--online .obs-agenthdr__dot
  background: var(--q-positive)
.obs-agenthdr__status--offline .obs-agenthdr__dot
  background: var(--q-warning)
.obs-agenthdr__status--overdue .obs-agenthdr__dot
  background: var(--q-negative)
.obs-agenthdr__maint
  background: var(--obs-raised)
  color: var(--obs-text-2)
.obs-sys-part + .obs-sys-part::before
  content: " · "
// Hasta 2 líneas: con la versión del agente la línea no cabía a 1440 px y el
// tiempo encendido quedaba oculto tras la elipsis (UI-E06).
.obs-agenthdr__sys
  font-size: 13px
  color: var(--obs-text-2)
  display: -webkit-box
  -webkit-line-clamp: 2
  -webkit-box-orient: vertical
  overflow: hidden
.obs-agenthdr__btns
  flex: none
  color: var(--obs-text-2)
// Pantallas angostas (móvil): los botones bajan a su propia fila para que migas,
// estado y línea de sistema conserven el ancho (UI-E06 a 390 px).
@media (max-width: 700px)
  .obs-agenthdr > .row
    flex-wrap: wrap
  .obs-agenthdr__btns
    width: 100%
    order: 2
    flex-wrap: wrap
  .obs-agenthdr .row.no-wrap
    flex-wrap: wrap
  .obs-agenthdr__sys
    -webkit-line-clamp: unset
    display: block
.obs-badge
  display: inline-flex
  align-items: center
  gap: 6px
  font-size: 12.5px
  padding: 5px 12px
  border-radius: 10px
  border: 1px solid var(--obs-border)
  background: var(--obs-raised)
  color: var(--obs-text-2)
.obs-badge--neg
  color: var(--q-negative)
  border-color: var(--q-negative)
.obs-badge--warn
  color: var(--q-warning)
  border-color: var(--q-warning)
</style>
