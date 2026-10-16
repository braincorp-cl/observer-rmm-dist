<template>
  <!--
    050 (T025) · Navegación lateral genérica de la v2, generalizada de
    SectionNav.vue (046): grupos e ítems por props y la sección elegida la decide
    la URL de quien la usa. Es una lista de navegación, no un tablist (UI-E04).
  -->
  <nav class="obs-secnav" :aria-label="ariaLabel">
    <slot name="top" />
    <template v-for="group in groups" :key="group.key">
      <div v-if="group.label" class="obs-secnav__group">{{ group.label }}</div>
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
          <q-item-section v-if="item.icon" avatar class="obs-secnav__icon">
            <q-icon :name="item.icon" size="16px" />
          </q-item-section>
          <q-item-section class="ellipsis">
            <span :title="item.full || item.label">{{ item.label }}</span>
          </q-item-section>
          <q-item-section v-if="item.count || item.count === 0" side>
            <span class="mono obs-secnav__count" :class="item.countClass">{{
              item.count
            }}</span>
          </q-item-section>
        </q-item>
      </q-list>
    </template>
  </nav>
</template>

<script setup>
// groups: [{ key, label?, items: [{ key, label, full?, icon?, count?, countClass? }] }]
defineProps({
  groups: { type: Array, required: true },
  section: { type: String, default: null },
  ariaLabel: { type: String, default: null },
});
defineEmits(["select"]);
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
</style>
