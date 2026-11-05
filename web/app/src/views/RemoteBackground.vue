<template>
  <!--
    050 (T048): "Segundo plano remoto" en el lenguaje visual de la v2.

    Es una ventana propia (api/agents.js / ActionBar.vue la abren con openURL,
    1280x900): no vive dentro de MainLayout, así que no tiene la cabecera navy ni
    el riel de la consola. Lo que adopta es el riel de secciones de la v2
    (ObsSectionNav, el mismo del espacio de trabajo del agente) en vez de las
    pestañas planas de la v1, y los tokens --obs-* para superficies y bordes.

    UI-F09: la sección sigue viviendo en la URL como ?tab=. Al entrar se lee de
    ahí (los atajos de la barra de acción abren esta ventana ya en una pestaña) y
    al cambiar de sección se reescribe con replace, igual que la sección del
    espacio de trabajo (UI-E02): recargar la ventana reabre la misma sección.
  -->
  <div class="obs-page obs-remote">
    <ObsSectionNav
      :groups="navGroups"
      :section="tab"
      :aria-label="$t('remoteBackground.navLabel')"
      @select="selectTab"
    />
    <div class="col obs-remote__content obs-ws__content" :data-section="tab">
      <iframe
        v-if="tab === 'terminal'"
        allow="clipboard-read; clipboard-write"
        :src="terminal"
        :title="$t('remoteBackground.terminalFrame')"
      ></iframe>
      <iframe
        v-else-if="tab === 'filebrowser'"
        allow="clipboard-read; clipboard-write"
        :src="file"
        :title="$t('remoteBackground.fileFrame')"
      ></iframe>
      <ProcessManager v-else-if="tab === 'processes'" :agent_id="agent_id" />
      <ServicesManager
        v-else-if="tab === 'services'"
        :agent_id="agent_id"
        :agentPlatform="plataforma"
      />
      <EventLogManager
        v-else-if="tab === 'eventlog'"
        :agent_id="agent_id"
        :agentPlatform="plataforma"
      />
      <RegistryManager v-else-if="tab === 'registry'" :agent_id="agent_id" />
    </div>
  </div>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { useQuasar, useMeta } from "quasar";
import { fetchAgentMeshCentralURLs } from "@/api/agents";
import { fetchDashboardInfo } from "@/api/core";

// ui imports
import ObsSectionNav from "@/components/shell/ObsSectionNav.vue";
import ProcessManager from "@/components/agents/remotebg/ProcessManager.vue";
import ServicesManager from "@/components/agents/remotebg/ServicesManager.vue";
import EventLogManager from "@/components/agents/remotebg/EventLogManager.vue";
import RegistryManager from "@/components/agents/remotebg/RegistryManager.vue";
import registryIcon from "../assets/windows-registry.png";

// Clave de i18n por sección (las de las pestañas de la v1, sin renombrar).
const LABELS = {
  terminal: "terminal",
  filebrowser: "fileBrowser",
  services: "services",
  processes: "processes",
  eventlog: "eventLog",
  registry: "registry",
};

// Iconos heredados de las pestañas de la v1 para que cada sección se reconozca.
const ICONS = {
  terminal: "fas fa-terminal",
  filebrowser: "far fa-folder-open",
  services: "fas fa-cogs",
  processes: "fas fa-chart-area",
  eventlog: "fas fa-clipboard-list",
  registry: `img:${registryIcon}`,
};

export default {
  name: "RemoteBackground",
  components: {
    ObsSectionNav,
    ServicesManager,
    EventLogManager,
    ProcessManager,
    RegistryManager,
  },
  setup() {
    // setup quasar
    const $q = useQuasar();
    const { t } = useI18n();

    // vue router
    const route = useRoute();
    const router = useRouter();
    const { params } = route;

    // meshcentral tabs
    const terminal = ref("");
    const file = ref("");

    const plataforma = computed(() => route.query.agentPlatform);

    // 046: los atajos de la barra de acción abren esta ventana ya en una pestaña
    // (?tab=terminal|filebrowser|services|...). Solo se acepta una pestaña que
    // exista para la plataforma; si no, la de siempre.
    const tabsPorPlataforma =
      route.query.agentPlatform === "windows"
        ? [
            "terminal",
            "filebrowser",
            "services",
            "processes",
            "eventlog",
            "registry",
          ]
        : ["terminal", "filebrowser", "processes"];
    const tab = ref(
      tabsPorPlataforma.includes(route.query.tab)
        ? route.query.tab
        : "terminal",
    );

    const navGroups = computed(() => [
      {
        key: "remote",
        items: tabsPorPlataforma.map((key) => ({
          key,
          label: t(`remoteBackground.${LABELS[key]}`),
          icon: ICONS[key],
        })),
      },
    ]);

    // UI-F09: la pestaña elegida se refleja en ?tab= sin apilar historial, para
    // que la URL de la ventana nunca quede apuntando a otra sección.
    function selectTab(next) {
      if (next === tab.value) return;
      tab.value = next;
      router.replace({ query: { ...route.query, tab: next } });
    }

    const agent_id = computed(() => params.agent_id);

    async function getMeshURLs() {
      const data = await fetchAgentMeshCentralURLs(params.agent_id);
      terminal.value = data.terminal;
      file.value = data.file;
      useMeta({
        title: t("remoteBackground.metaTitle", {
          hostname: data.hostname,
          client: data.client,
          site: data.site,
        }),
      });
    }

    async function getDashInfo() {
      const { dark_mode } = await fetchDashboardInfo();
      $q.dark.set(dark_mode);
      $q.loadingBar.setDefaults({ size: "0px" });
    }

    // vue lifecycle hooks
    onMounted(() => {
      getDashInfo();
      getMeshURLs();
    });

    return {
      // reactive data
      terminal,
      file,
      tab,
      navGroups,
      plataforma,
      agent_id,

      // methods
      selectTab,
    };
  },
};
</script>

<style lang="sass" scoped>
// Ventana completa: el riel a la izquierda y la sección se come el resto.
// `.obs-page` aporta el remapeo de grises de Quasar a tokens (app.sass); acá se
// le quita el relleno y el gap de página y pasa a franjas horizontales.
.obs-page.obs-remote
  flex-direction: row
  height: 100vh
  padding: 0
  gap: 0
  overflow: hidden
  background: var(--obs-page)
.obs-remote__content
  display: flex
  flex-direction: column
  min-width: 0
  min-height: 0
  overflow: auto
  iframe
    flex: 1
    display: block
    width: 100%
    height: 100%
    border: 0
</style>
