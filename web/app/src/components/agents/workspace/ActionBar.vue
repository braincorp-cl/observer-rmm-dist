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
    <div class="row no-wrap items-center q-gutter-x-sm obs-actionbar__main">
      <q-btn
        v-for="b in primary"
        :key="b.key"
        no-caps
        :unelevated="b.key === 'takeControl'"
        :outline="b.key !== 'takeControl'"
        :color="b.key === 'takeControl' ? 'primary' : undefined"
        :icon="b.icon"
        :label="b.label"
        :data-action="b.key"
        class="obs-actionbar__btn"
        @click="b.run()"
      />
    </div>
    <q-space />
    <div class="row no-wrap items-center q-gutter-x-sm">
      <q-btn
        v-for="b in response"
        :key="b.key"
        no-caps
        outline
        :icon="b.icon"
        :label="b.label"
        :data-action="b.key"
        class="obs-actionbar__btn"
        @click="b.run()"
      />
      <q-btn
        no-caps
        outline
        icon="more_horiz"
        :label="$t('agentWorkspace.actionBar.more')"
        data-action="more"
        class="obs-actionbar__btn"
      >
        <q-menu anchor="top right" self="bottom right">
          <q-list dense style="min-width: 240px">
            <template v-for="a in actions" :key="a.key">
              <q-item
                v-if="!a.children"
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
              <q-item
                v-else
                clickable
                :disable="a.disabled"
                :data-action="a.key"
              >
                <q-item-section side>
                  <q-icon size="xs" :name="a.icon" />
                </q-item-section>
                <q-item-section>{{ a.label }}</q-item-section>
                <q-item-section side>
                  <q-icon name="keyboard_arrow_right" />
                </q-item-section>
                <q-menu auto-close anchor="top end" self="top start">
                  <q-list dense>
                    <q-item
                      v-for="c in a.children"
                      :key="c.key"
                      clickable
                      v-close-popup
                      :data-action="c.key"
                      @click="c.run()"
                    >
                      <q-item-section v-if="c.icon" side>
                        <q-icon size="xs" :name="c.icon" />
                      </q-item-section>
                      <q-item-section>{{ c.label }}</q-item-section>
                    </q-item>
                  </q-list>
                </q-menu>
              </q-item>
            </template>
          </q-list>
        </q-menu>
      </q-btn>
    </div>
  </footer>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { openURL } from "quasar";
import { router } from "@/router";
import { getCenteredWindowOptions } from "@/utils/helpers";

const props = defineProps({
  agent: { type: Object, required: true },
  actions: { type: Array, required: true },
});
const { t } = useI18n();

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
  overflow-x: auto
.obs-actionbar__btn
  color: var(--obs-text-2)
  white-space: nowrap
.obs-actionbar__btn.bg-primary
  color: var(--obs-on-brand)
</style>
