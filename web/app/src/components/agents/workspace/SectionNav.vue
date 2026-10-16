<template>
  <!--
    Navegación del detalle en la dirección 1c (046, T017): las 12 secciones de la
    v1 agrupadas en Operación / Inventario / Registro, en vez de 10 pestañas planas.
    050 (T025): se dibuja con ObsSectionNav, la versión genérica.
  -->
  <ObsSectionNav
    :groups="navGroups"
    :section="section"
    :aria-label="$t('agentWorkspace.navLabel')"
    @select="$emit('select', $event)"
  />
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import ObsSectionNav from "@/components/shell/ObsSectionNav.vue";

const props = defineProps({
  section: { type: String, required: true },
  counts: { type: Object, default: () => ({}) },
});
defineEmits(["select"]);

const { t } = useI18n();

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
      { key: "actividad", icon: "timeline" },
      { key: "notes", icon: "far fa-sticky-note" },
      { key: "debug", icon: "bug_report" },
      { key: "audit", icon: "travel_explore" },
      { key: "erase", icon: "verified" },
    ],
  },
];

// Los conteos de chequeos y parches son estado: rojo y ámbar (046).
const COUNT_CLASS = { checks: "text-negative", patches: "text-warning" };

const navGroups = computed(() =>
  groups.map((g) => ({
    key: g.key,
    label: t(`agentWorkspace.groups.${g.key}`),
    items: g.items.map((i) => ({
      ...i,
      label: t(`agentTabs.labels.${i.key}`),
      count: props.counts[i.key] || null,
      countClass: COUNT_CLASS[i.key],
    })),
  })),
);
</script>
