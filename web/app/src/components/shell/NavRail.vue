<template>
  <!--
    Riel de iconos de la dirección 1c (046): reemplaza la barra de menús v1 en toda
    la consola. Arriba, el inicio (dashboard); debajo, los 7 menús de la barra v1
    (NavMenu.vue), cada uno en un ícono con tooltip y su menú desplegado a la
    derecha. Las utilidades del encabezado (idioma, tema, alertas, usuario) siguen
    en la barra superior en esta fase.
  -->
  <q-drawer
    :model-value="true"
    side="left"
    :width="60"
    :breakpoint="0"
    persistent
    class="obs-rail"
  >
    <div class="column items-center no-wrap q-py-sm obs-rail__inner">
      <q-btn
        flat
        round
        dense
        icon="radar"
        class="obs-rail__home"
        :aria-label="$t('navRail.home')"
        @click="goHome"
      >
        <q-tooltip anchor="center right" self="center left">{{
          $t("navRail.home")
        }}</q-tooltip>
      </q-btn>
      <!-- 050 (ola 4): accesos directos a los gestores-página, con estado activo. -->
      <q-btn
        v-for="g in managers"
        :key="g.route"
        flat
        round
        dense
        :icon="g.icon"
        class="obs-rail__mgr"
        :class="{ 'obs-rail__mgr--active': route.name === g.route }"
        :aria-label="$t(g.label)"
        :aria-current="route.name === g.route ? 'page' : undefined"
        :to="{ name: g.route }"
      >
        <q-tooltip anchor="center right" self="center left">{{
          $t(g.label)
        }}</q-tooltip>
      </q-btn>
      <q-separator class="obs-rail__sep" />
      <NavMenu />
    </div>
  </q-drawer>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";
import NavMenu from "@/components/shell/NavMenu.vue";

const route = useRoute();
const managers = [
  { route: "Scripts", icon: "code", label: "nav.scriptManager" },
  { route: "Automation", icon: "account_tree", label: "nav.automationManager" },
  { route: "Alerts", icon: "warning_amber", label: "nav.alertsManager" },
];
const router = useRouter();
const store = useStore();

function goHome() {
  if (route.name === "Dashboard") store.dispatch("refreshDashboard");
  else router.push({ name: "Dashboard" });
}
</script>

<style lang="sass" scoped>
.obs-rail
  background: var(--obs-rail)
  border-right: 1px solid var(--obs-border)
.obs-rail__inner
  gap: 6px
.obs-rail__home
  color: var(--q-primary)
.obs-rail__mgr
  color: var(--obs-muted)
  border-radius: 10px
.obs-rail__mgr--active
  background: var(--obs-selected)
  color: var(--q-primary)
.obs-rail__sep
  width: 28px
  background: var(--obs-border)
  color: var(--obs-border)
  margin: 4px 0
</style>
