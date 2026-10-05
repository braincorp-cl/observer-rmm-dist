<template>
  <!--
    Navegación del detalle en la dirección 1c (046, T017): las 11 secciones de la
    v1 agrupadas en Operación / Inventario / Registro, en vez de 10 pestañas planas.
    Es una lista de navegación, no un tablist (UI-E04).
  -->
  <nav class="obs-secnav" :aria-label="$t('agentWorkspace.navLabel')">
    <template v-for="group in groups" :key="group.key">
      <div class="obs-secnav__group">
        {{ $t(`agentWorkspace.groups.${group.key}`) }}
      </div>
      <q-list dense>
        <q-item
          v-for="item in group.items"
          :key="item.key"
          clickable
          :active="item.key === section"
          active-class="obs-secnav__item--active"
          class="obs-secnav__item"
          :data-section="item.key"
          @click="$emit('select', item.key)"
        >
          <q-item-section avatar class="obs-secnav__icon">
            <q-icon :name="item.icon" size="16px" />
          </q-item-section>
          <q-item-section class="ellipsis">
            <span :title="$t(`agentTabs.labels.${item.key}`)">{{
              $t(`agentTabs.labels.${item.key}`)
            }}</span>
          </q-item-section>
          <q-item-section v-if="counts[item.key]" side>
            <span
              class="mono obs-secnav__count"
              :class="`obs-secnav__count--${item.key}`"
              >{{ counts[item.key] }}</span
            >
          </q-item-section>
        </q-item>
      </q-list>
    </template>
  </nav>
</template>

<script setup>
defineProps({
  section: { type: String, required: true },
  counts: { type: Object, default: () => ({}) },
});
defineEmits(["select"]);

// Iconos heredados de SubTableTabs.vue (v1) para que cada sección se reconozca.
const groups = [
  {
    key: "operation",
    items: [
      { key: "summary", icon: "fas fa-info-circle" },
      { key: "checks", icon: "fas fa-check-double" },
      { key: "tasks", icon: "fas fa-tasks" },
      { key: "patches", icon: "system_update" },
    ],
  },
  {
    key: "inventory",
    items: [
      { key: "software", icon: "fab fa-windows" },
      { key: "assets", icon: "fas fa-barcode" },
    ],
  },
  {
    key: "record",
    items: [
      { key: "history", icon: "history" },
      { key: "notes", icon: "far fa-sticky-note" },
      { key: "debug", icon: "bug_report" },
      { key: "audit", icon: "travel_explore" },
      { key: "erase", icon: "verified" },
    ],
  },
];
</script>

<style lang="sass" scoped>
.obs-secnav
  width: 196px
  flex: none
  padding: 12px 8px
  border-right: 1px solid var(--obs-border)
  background: var(--obs-surface)
  overflow-y: auto
.obs-secnav__group
  font-size: 10.5px
  font-weight: 600
  letter-spacing: .08em
  text-transform: uppercase
  color: var(--obs-faint)
  padding: 10px 10px 4px
.obs-secnav__item
  border-radius: 8px
  color: var(--obs-text-2)
  min-height: 30px
.obs-secnav__item--active
  background: var(--obs-selected)
  color: var(--q-primary)
.obs-secnav__icon
  min-width: 26px
  padding-right: 6px
.obs-secnav__count
  font-size: 11.5px
  color: var(--obs-muted)
.obs-secnav__count--checks
  color: var(--q-negative)
.obs-secnav__count--patches
  color: var(--q-warning)
</style>
