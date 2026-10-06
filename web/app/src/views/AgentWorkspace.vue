<template>
  <!--
    Espacio de trabajo del agente, dirección 1c (046, T016/T020). Reemplaza a
    AgentView.vue (Resumen fijo + SubTableTabs). Franjas: [columna de contexto, F4]
    | cabecera + (nav de secciones | contenido) + barra de acción anclada abajo.
    Las secciones son los *Tab.vue de la v1 sin reescribir: cambia la estructura,
    no el contenido. La sección vive en la URL (/agents/:agent_id/:section?):
    cambiar de sección usa replace y cambiar de equipo usa push (UI-E02).
  -->
  <q-page :style-fn="pageStyle" class="obs-ws row no-wrap">
    <!-- 046 T029 (UI-R01): bajo 1200 px la columna de contexto se pliega y se abre
         superpuesta desde el botón de lista de la cabecera. -->
    <ContextColumn
      v-if="agent && (!narrow || ctxOpen)"
      :agent="agent"
      :class="{ 'obs-ws__ctx--overlay': narrow }"
    />
    <div
      v-if="narrow && ctxOpen"
      class="obs-ws__scrim"
      @click="ctxOpen = false"
    />
    <div class="col column no-wrap obs-ws__main" style="min-width: 0">
      <div v-if="!agent" class="flex flex-center col">
        <q-circular-progress indeterminate size="44px" color="secondary" />
      </div>
      <template v-else>
        <AgentHeader
          :agent="agent"
          :urgency="urgency"
          :actions="descriptors"
          :context-toggle="narrow"
          :context-open="ctxOpen"
          @refresh-wmi="refreshWMI"
          @toggle-context="ctxOpen = !ctxOpen"
        />
        <div class="col row no-wrap" style="min-height: 0">
          <SectionNav
            :section="section"
            :counts="navCounts"
            @select="selectSection"
          />
          <div
            ref="contentEl"
            class="col obs-ws__content"
            :data-section="section"
          >
            <component :is="sectionComponent" v-bind="sectionProps" />
          </div>
        </div>
        <ActionBar
          :agent="agent"
          :actions="descriptors"
          @refresh-lists="refreshLists"
        />
      </template>
    </div>
  </q-page>
</template>

<script>
import { computed, provide, ref, watch, reactive, onBeforeUnmount } from "vue";
import { useStore } from "vuex";
import { useQuasar } from "quasar";
import { useRoute, useRouter } from "vue-router";
import { fetchAgent, refreshAgentWMI } from "@/api/agents";
import { notifySuccess } from "@/utils/notify";
import { useAgentActions } from "@/composables/useAgentActions";
import { useAgentUrgency } from "@/composables/useAgentUrgency";

import AgentHeader from "@/components/agents/workspace/AgentHeader.vue";
import SectionNav from "@/components/agents/workspace/SectionNav.vue";
import ActionBar from "@/components/agents/workspace/ActionBar.vue";
import ContextColumn from "@/components/agents/workspace/ContextColumn.vue";
import SummaryTab from "@/components/agents/SummaryTab.vue";
import ChecksTab from "@/components/agents/ChecksTab.vue";
import AutomatedTasksTab from "@/components/agents/AutomatedTasksTab.vue";
import WinUpdateTab from "@/components/agents/WinUpdateTab.vue";
import SoftwareTab from "@/components/agents/SoftwareTab.vue";
import HistoryTab from "@/components/agents/HistoryTab.vue";
import NotesTab from "@/components/agents/NotesTab.vue";
import AssetsTab from "@/components/agents/AssetsTab.vue";
import DebugTab from "@/components/agents/DebugTab.vue";
import AuditTab from "@/components/agents/AuditTab.vue";
import EraseCertificatesTab from "@/components/agents/EraseCertificatesTab.vue";

const SECTIONS = {
  summary: SummaryTab,
  checks: ChecksTab,
  tasks: AutomatedTasksTab,
  patches: WinUpdateTab,
  software: SoftwareTab,
  assets: AssetsTab,
  history: HistoryTab,
  notes: NotesTab,
  debug: DebugTab,
  audit: AuditTab,
  erase: EraseCertificatesTab,
};

// Alto aproximado de la cabecera (~150) y de la barra de acción (~58): el resto es
// para la sección. Los *Tab.vue leen store.state.tabHeight para sus tablas.
const CHROME = 150 + 58;

export default {
  name: "AgentWorkspace",
  components: { AgentHeader, SectionNav, ActionBar, ContextColumn },
  setup() {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();
    const agent = ref(null);
    const contentEl = ref(null);
    const pageHeight = ref(0);
    const $q = useQuasar();
    const narrow = computed(() => $q.screen.width < 1200);
    const ctxOpen = ref(false);

    const {
      failingChecks,
      pendingPatches,
      pendingActions,
      rebootRequired,
      loadUrgency,
    } = useAgentUrgency();
    const urgency = reactive({
      failingChecks,
      pendingPatches,
      pendingActions,
      rebootRequired,
    });

    async function load() {
      const id = route.params.agent_id;
      if (!id) return;
      store.commit("setActiveRow", id);
      const data = await fetchAgent(id);
      if (!data || route.params.agent_id !== id) return; // falló o se cambió de equipo
      agent.value = data;
      store.commit("setAgentPlatform", data.plat);
      loadUrgency(data);
    }

    // Lo que en el dashboard refrescaba la tabla: acá refresca cabecera y resumen.
    provide("refreshDashboard", () => {
      store.commit("setRefreshSummaryTab", true);
      load();
    });

    // useAgentActions usa inject("refreshDashboard"): va después del provide.
    const { actionDescriptors, getURLActions, getFavoriteScripts } =
      useAgentActions();
    // Como el menú v1, que las pide al montarse: se recargan al abrir "Más".
    function refreshLists() {
      getURLActions();
      getFavoriteScripts();
    }
    const descriptors = computed(() =>
      agent.value ? actionDescriptors(agent.value) : [],
    );

    const section = computed(() =>
      SECTIONS[route.params.section] ? route.params.section : "summary",
    );
    const sectionComponent = computed(() => SECTIONS[section.value]);
    const sectionProps = computed(() =>
      section.value === "summary" ? { embedded: true } : {},
    );

    const navCounts = computed(() => ({
      checks: urgency.failingChecks,
      patches: urgency.pendingPatches,
    }));

    function selectSection(key) {
      router.replace({
        name: "Agent",
        params: { agent_id: route.params.agent_id, section: key },
      });
    }

    async function refreshWMI() {
      try {
        const result = await refreshAgentWMI(route.params.agent_id);
        notifySuccess(result);
      } catch (e) {
        console.error(e);
      }
      store.commit("setRefreshSummaryTab", true);
      load();
    }

    function pageStyle(offset, height) {
      pageHeight.value = height - offset;
      store.state.tabHeight = `${Math.max(240, height - offset - CHROME)}px`;
      return { height: `${height - offset}px` };
    }

    // Estado y última respuesta frescos sin recargar todo: el agente hace check-in
    // cada pocos segundos y la cabecera muestra "hace N s" (UI-E06). Solo la misma
    // GET del detalle, sin tocar badges ni secciones.
    const poll = setInterval(async () => {
      const id = route.params.agent_id;
      if (!agent.value || !id || document.hidden) return;
      try {
        const data = await fetchAgent(id);
        if (data && agent.value && route.params.agent_id === id) {
          agent.value.last_seen = data.last_seen;
          agent.value.status = data.status;
        }
      } catch (e) {
        console.error(e);
      }
    }, 15000);
    onBeforeUnmount(() => clearInterval(poll));

    // Elegir otro equipo en la columna superpuesta la cierra.
    watch(
      () => route.params.agent_id,
      () => (ctxOpen.value = false),
    );
    watch(narrow, (n) => {
      if (!n) ctxOpen.value = false;
    });

    watch(
      () => route.params.agent_id,
      (n, o) => {
        if (n && n !== o) load();
      },
      { immediate: true },
    );

    return {
      agent,
      narrow,
      ctxOpen,
      urgency,
      descriptors,
      section,
      sectionComponent,
      sectionProps,
      navCounts,
      contentEl,
      selectSection,
      refreshWMI,
      refreshLists,
      pageStyle,
    };
  },
};
</script>

<style lang="sass" scoped>
.obs-ws
  position: relative
  background: var(--obs-page)
.obs-ws__ctx--overlay
  position: absolute
  top: 0
  bottom: 0
  left: 0
  z-index: 5
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35)
.obs-ws__scrim
  position: absolute
  inset: 0
  z-index: 4
.obs-ws__content
  overflow: auto
  background: var(--obs-page)
  padding: 8px 12px
</style>
