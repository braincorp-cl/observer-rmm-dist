<template>
  <!--
    Cabecera del espacio de trabajo 1c (046, T018): migas Cliente / Sitio, hostname,
    estado con antigüedad, línea SO · modelo · RAM · arranque, los 4 badges de
    urgencia, y los botones de cabecera del Resumen v1 (refrescar inventario, abrir
    en ventana, tomar control, ubicación, acciones) más mantenimiento y política.
  -->
  <header class="obs-agenthdr">
    <div class="row no-wrap items-start">
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
        <div class="obs-agenthdr__sys ellipsis" :title="sysLine">
          {{ sysLine }}
        </div>
      </div>
      <div class="row no-wrap items-center q-gutter-x-sm obs-agenthdr__btns">
        <q-btn
          outline
          no-caps
          dense
          icon="construction"
          class="obs-agenthdr__btn"
          :label="
            agent.maintenance_mode
              ? $t('agentActions.disableMaintenance')
              : $t('agentActions.enableMaintenance')
          "
          @click="run('maintenance')"
        />
        <q-btn
          outline
          no-caps
          dense
          icon="policy"
          class="obs-agenthdr__btn"
          :label="$t('agentActions.assignPolicy')"
          @click="run('assignPolicy')"
        />
        <q-btn
          flat
          round
          dense
          icon="refresh"
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
        {{ $t("agentWorkspace.badges.failingChecks", urgency.failingChecks) }}
      </span>
      <span
        v-if="urgency.pendingPatches > 0"
        class="obs-badge obs-badge--warn"
        data-badge="pendingPatches"
      >
        <q-icon name="download" size="16px" />
        {{ $t("agentWorkspace.badges.pendingPatches", urgency.pendingPatches) }}
      </span>
      <span
        v-if="urgency.pendingActions > 0"
        class="obs-badge"
        data-badge="pendingActions"
      >
        <q-icon name="pending_actions" size="16px" />
        {{ $t("agentWorkspace.badges.pendingActions", urgency.pendingActions) }}
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
import { computed, ref } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { runTakeControl, openAgentWindow } from "@/api/agents";
import AgentActionMenu from "@/components/agents/AgentActionMenu.vue";
import AgentLocationDialog from "@/components/agents/AgentLocationDialog.vue";

const props = defineProps({
  agent: { type: Object, required: true },
  urgency: { type: Object, required: true },
  actions: { type: Array, required: true },
});
defineEmits(["refresh-wmi"]);

const store = useStore();
const { t } = useI18n();
const showLocation = ref(false);

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
    ? (Date.now() - new Date(props.agent.last_seen).getTime()) / 1000
    : 0;
  const key =
    props.agent.status === "online"
      ? "onlineAgo"
      : props.agent.status === "overdue"
        ? "overdueAgo"
        : "offlineAgo";
  return t(`agentWorkspace.header.${key}`, { ago: ago(since) });
});

const sysLine = computed(() => {
  const a = props.agent;
  const parts = [a.operating_system, a.make_model];
  if (a.total_ram)
    parts.push(t("agentWorkspace.header.ram", { gb: a.total_ram }));
  if (a.boot_time)
    parts.push(
      t("agentWorkspace.header.bootedAgo", {
        ago: ago(Date.now() / 1000 - a.boot_time),
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
.obs-agenthdr__sys
  font-size: 13px
  color: var(--obs-text-2)
.obs-agenthdr__btn
  color: var(--obs-text-2)
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
