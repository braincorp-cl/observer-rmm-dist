<template>
  <!--
    Barra de acción anclada abajo (046, T022/T024). Todo sale de
    useAgentActions().actionDescriptors(agent): los mismos handlers que el menú
    contextual de la tabla (UI-F03/F08). Botones directos como en la maqueta 1c y
    el resto en "Más acciones" (≤ 2 interacciones). Los atajos Terminal web /
    Servicios / Archivos abren la misma ventana de Administración en segundo plano
    ya posicionada en esa pestaña (UI-F09): ninguna llamada nueva a la API.
  -->
  <footer class="obs-actionbar row no-wrap items-center">
    <!-- 046 T029 (UI-R01/F03): si los botones con texto no caben (1280 px con la
         columna de contexto), los atajos pasan a solo ícono + tooltip y
         "Más acciones" sigue siempre a la vista. -->
    <q-resize-observer @resize="fit" />
    <div
      ref="mainEl"
      class="row no-wrap items-center q-gutter-x-sm obs-actionbar__main"
    >
      <q-btn
        v-for="b in primary"
        :key="b.key"
        no-caps
        :unelevated="b.key === 'takeControl'"
        :outline="b.key !== 'takeControl'"
        :color="b.key === 'takeControl' ? 'primary' : undefined"
        :icon="b.icon"
        :label="compact && b.key !== 'takeControl' ? undefined : b.label"
        :aria-label="b.label"
        :data-action="b.key"
        class="obs-actionbar__btn"
        @click="b.run()"
      >
        <q-tooltip v-if="compact && b.key !== 'takeControl'">{{
          b.label
        }}</q-tooltip>
      </q-btn>
    </div>
    <div class="row no-wrap items-center q-gutter-x-sm obs-actionbar__right">
      <!-- Respuesta rápida: solo ícono + tooltip, para que "Más acciones" quepa
           siempre en pantalla a 1280/1440 (UI-F03, corrida 2026-10-05). -->
      <q-btn
        v-for="b in response"
        :key="b.key"
        outline
        :icon="b.icon"
        :aria-label="b.label"
        :data-action="b.key"
        class="obs-actionbar__btn"
        @click="b.run()"
      >
        <q-tooltip>{{ b.label }}</q-tooltip>
      </q-btn>
      <q-btn
        no-caps
        outline
        icon="more_horiz"
        :label="$t('agentWorkspace.actionBar.more')"
        data-action="more"
        class="obs-actionbar__btn"
      >
        <!--
          Menú PLANO en dos columnas: toda acción hoja a 2 interacciones (abrir +
          elegir), sin submenús anidados (UI-F03). Las listas dinámicas (URL
          actions, favoritos) se recargan al abrir, como el menú v1, que las pide
          cada vez que se monta.
        -->
        <q-menu
          anchor="top right"
          self="bottom right"
          class="obs-moremenu"
          max-height="88vh"
          @before-show="$emit('refresh-lists')"
        >
          <div class="row no-wrap q-pa-xs">
            <q-list dense class="obs-moremenu__col">
              <q-item
                v-for="a in simple"
                :key="a.key"
                clickable
                v-close-popup
                :data-action="a.key"
                @click="a.run()"
              >
                <q-item-section side>
                  <q-icon size="xs" :name="a.icon" />
                </q-item-section>
                <q-item-section>{{ a.label }}</q-item-section>
              </q-item>
            </q-list>
            <q-separator vertical />
            <q-list dense class="obs-moremenu__col">
              <template v-for="g in groups" :key="g.key">
                <q-item-label header class="obs-moremenu__hdr">
                  <q-icon size="xs" :name="g.icon" class="q-mr-xs" />{{
                    g.label
                  }}
                </q-item-label>
                <!-- clickable + disable + aria-disabled: igual que el ítem padre
                     deshabilitado del menú v1 (UI-F04). -->
                <q-item
                  v-if="!g.children.length"
                  clickable
                  disable
                  aria-disabled="true"
                  :data-action="g.key"
                >
                  <q-item-section class="q-pl-md">{{ g.label }}</q-item-section>
                </q-item>
                <q-item
                  v-for="c in g.children"
                  :key="c.key"
                  clickable
                  v-close-popup
                  :disable="g.disabled"
                  :data-action="c.key"
                  @click="c.run()"
                >
                  <q-item-section class="q-pl-md">{{ c.label }}</q-item-section>
                </q-item>
              </template>
              <template v-if="agentIntegrations.length">
                <q-item-label header class="obs-moremenu__hdr">
                  <q-icon size="xs" name="analytics" class="q-mr-xs" />{{
                    $t("agentActions.reporting")
                  }}
                </q-item-label>
                <q-item
                  v-for="integration in agentIntegrations"
                  :key="integration.name"
                  clickable
                  v-close-popup
                  data-action="reporting"
                  :to="
                    integration.type === 'route' ? integration.uri : undefined
                  "
                  @click="
                    integration.type === 'dialog'
                      ? $q.dialog({
                          component: integration.component,
                          componentProps: integration.props
                            ? integration.props(agent.agent_id, 'agent')
                            : undefined,
                        })
                      : undefined
                  "
                >
                  <q-item-section class="q-pl-md">{{
                    integration.name
                  }}</q-item-section>
                </q-item>
              </template>
            </q-list>
          </div>
        </q-menu>
      </q-btn>
    </div>
  </footer>
</template>

<script setup>
import { computed, getCurrentInstance, nextTick, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { openURL } from "quasar";
import { router } from "@/router";
import { getCenteredWindowOptions } from "@/utils/helpers";

const props = defineProps({
  agent: { type: Object, required: true },
  actions: { type: Array, required: true },
});
defineEmits(["refresh-lists"]);
const { t } = useI18n();
const instance = getCurrentInstance();
// Misma condición que el menú v1 (AgentActionMenu): integraciones de agente.
const agentIntegrations = computed(
  () => instance?.proxy?.$integrations?.agentMenuIntegrations ?? [],
);

function find(key) {
  for (const a of props.actions) {
    if (a.key === key) return a;
    for (const c of a.children || []) if (c.key === key) return c;
  }
  return null;
}

// Misma ventana que runRemoteBackground (api/agents.js), con la pestaña inicial.
function openRemoteTab(tab) {
  const url = router.resolve(
    `/remotebackground/${props.agent.agent_id}?agentPlatform=${props.agent.plat}&tab=${tab}`,
  ).href;
  openURL(url, null, { ...getCenteredWindowOptions(1280, 900) });
}

const primary = computed(() => {
  const isWin = props.agent.plat === "windows";
  const out = [];
  const take = find("takeControl");
  if (take) out.push(take);
  out.push({
    key: "shortcut-terminal",
    icon: "terminal",
    label: t("agentWorkspace.shortcuts.webTerminal"),
    run: () => openRemoteTab("terminal"),
  });
  const script = find("runScript");
  if (script) out.push({ ...script, icon: "play_arrow" });
  if (isWin)
    out.push({
      key: "shortcut-services",
      icon: "settings_applications",
      label: t("agentWorkspace.shortcuts.services"),
      run: () => openRemoteTab("services"),
    });
  out.push({
    key: "shortcut-files",
    icon: "folder_open",
    label: t("agentWorkspace.shortcuts.files"),
    run: () => openRemoteTab("filebrowser"),
  });
  return out;
});

const simple = computed(() => props.actions.filter((a) => !a.children));
const groups = computed(() => props.actions.filter((a) => a.children));

// Ancho que piden los atajos con texto; se mide la primera vez que no caben.
const mainEl = ref(null);
const compact = ref(false);
let fullWidth = 0;
async function fit() {
  const el = mainEl.value;
  if (!el) return;
  if (!compact.value) {
    if (el.scrollWidth > el.clientWidth + 1) {
      fullWidth = el.scrollWidth;
      compact.value = true;
    }
  } else if (el.clientWidth >= fullWidth) {
    compact.value = false;
    await nextTick();
    fit();
  }
}
// Cambiar de equipo puede cambiar los atajos (Servicios solo en Windows).
watch(
  () => primary.value.length,
  async () => {
    compact.value = false;
    await nextTick();
    fit();
  },
);

const response = computed(() =>
  ["lock", "sendAlert", "alarm"].map((k) => find(k)).filter(Boolean),
);
</script>

<style lang="sass" scoped>
.obs-actionbar
  flex: none
  gap: 8px
  padding: 10px 16px
  border-top: 1px solid var(--obs-border)
  background: var(--obs-surface)
  overflow: hidden
.obs-actionbar__btn
  color: var(--obs-text-2)
  white-space: nowrap
  :deep(.q-btn__content)
    flex-wrap: nowrap
.obs-actionbar__btn.bg-primary
  color: var(--obs-on-brand)
.obs-actionbar__main
  flex: 1 1 auto
  min-width: 0
  overflow: hidden
.obs-actionbar__right
  flex: none
.obs-moremenu__col
  min-width: 250px
.obs-moremenu__hdr
  display: flex
  align-items: center
  padding: 6px 12px 0
  color: var(--obs-muted)
</style>
