<template>
  <!--
    050 (T048): "Segundo plano remoto" en el lenguaje visual de la v2.

    Es una ventana propia (api/agents.js / ActionBar.vue la abren con openURL,
    1280x900): no vive dentro de MainLayout, así que no tiene la cabecera navy ni
    el riel de la consola. Lo que adopta es el riel de secciones de la v2
    (ObsSectionNav, el mismo del espacio de trabajo del agente) en vez de las
    pestañas planas de la v1, y los tokens --obs-* para superficies y bordes.

    🔴 V2-P10 (2026-11-15): y TAMBIÉN la cabecera propia. Esta ventana era la
    única de las cuatro remotas sin `h1` ni migas —medido en 8 de 8 lecturas de
    la pasada final—, así que no se veía a qué equipo estabas conectado justo en
    la ventana donde se ejecutan comandos y se borran archivos. La enmienda del
    2026-11-04 define shell como tokens + cabecera propia + ObsSectionNav, y es
    una SUMA: el riel no sustituye la cabecera. `RemoteWindowChrome` ya existía
    para que las ventanas la hereden; acá sólo faltaba usarlo. Él aporta además
    el arranque de tema y el color de la barra de carga, que esta vista hacía
    por su cuenta (y apagaba la barra; ahora se comporta como las otras tres).

    UI-F09: la sección sigue viviendo en la URL como ?tab=. Al entrar se lee de
    ahí (los atajos de la barra de acción abren esta ventana ya en una pestaña) y
    al cambiar de sección se reescribe con replace, igual que la sección del
    espacio de trabajo (UI-E02): recargar la ventana reabre la misma sección.
  -->
  <RemoteWindowChrome
    :crumbs="crumbs"
    :hostname="hostname"
    :title="$t('agentActions.remoteBackground')"
  >
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
  </RemoteWindowChrome>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { useMeta } from "quasar";
import { fetchAgentMeshCentralURLs } from "@/api/agents";

// ui imports
import ObsSectionNav from "@/components/shell/ObsSectionNav.vue";
import RemoteWindowChrome from "@/components/remote/RemoteWindowChrome.vue";
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
    RemoteWindowChrome,
    ServicesManager,
    EventLogManager,
    ProcessManager,
    RegistryManager,
  },
  setup() {
    const { t } = useI18n();

    // vue router
    const route = useRoute();
    const router = useRouter();
    const { params } = route;

    // meshcentral tabs
    const terminal = ref("");
    const file = ref("");

    // V2-P10: la cabecera propia. `fetchAgentMeshCentralURLs` ya traía estos
    // tres campos en la misma respuesta que da las URL de las pestañas; la
    // vista los descartaba y sólo los usaba para el título de la ventana.
    const hostname = ref("");
    const client = ref("");
    const site = ref("");
    const crumbs = computed(() =>
      [client.value, site.value].filter(Boolean).join(" / "),
    );

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
      hostname.value = data.hostname;
      client.value = data.client;
      site.value = data.site;
      useMeta({
        title: t("remoteBackground.metaTitle", {
          hostname: data.hostname,
          client: data.client,
          site: data.site,
        }),
      });
    }

    // vue lifecycle hooks
    onMounted(() => {
      // El tema y la barra de carga los arranca RemoteWindowChrome, igual que
      // en las otras tres ventanas remotas: tenerlo acá lo llamaba dos veces.
      getMeshURLs();
    });

    return {
      // reactive data
      terminal,
      file,
      hostname,
      crumbs,
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
// V2-P10: la caja de la ventana (alto, relleno, fondo) la define ahora
// RemoteWindowChrome, que es el nodo raíz. 🪤 Un `scoped` del padre SÍ alcanza
// el raíz del hijo, así que dejar acá el `flex-direction: row` de antes pondría
// la cabecera y el lienzo en fila. El riel y la sección quedan en fila porque
// `.obs-remote__canvas` del chrome ya es flex.
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
