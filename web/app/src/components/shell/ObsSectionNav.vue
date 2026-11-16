<template>
  <!--
    050 (T025) · Navegación lateral genérica de la v2, generalizada de
    SectionNav.vue (046): grupos e ítems por props y la sección elegida la decide
    la URL de quien la usa. Es una lista de navegación, no un tablist (UI-E04).
  -->
  <nav
    ref="navEl"
    class="obs-secnav"
    :class="{ 'obs-secnav--wide': wide }"
    :aria-label="ariaLabel"
  >
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
          <q-item-section class="ellipsis" :title="item.full || item.label">
            <span>{{ item.label }}</span>
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
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from "vue";

// groups: [{ key, label?, items: [{ key, label, full?, icon?, count?, countClass? }] }]
const props = defineProps({
  groups: { type: Array, required: true },
  section: { type: String, default: null },
  ariaLabel: { type: String, default: null },
  // Ancho mayor para rótulos largos (categorías de Scripts).
  wide: { type: Boolean, default: false },
});
defineEmits(["select"]);

const navEl = ref(null);

// 🔴 V2-P11 (2026-11-15): esta caja YA tenía `overflow-y: auto`, así que la
// sección se podía alcanzar desplazando. Lo que faltaba es que al ENTRAR por URL
// la nav se desplazara hasta el ítem activo. Medido en el espacio del agente: en
// cuanto la cabecera trae fila de badges la nav baja de 463 a 424 px y el 12.º
// ítem («Borrado») queda en top 706,9 contra una caja que termina en bottom 700,
// con `activo = true` — o sea, estando el usuario en esa sección no veía ni el
// ítem ni cuál estaba activa: la nav de 12 secciones presentaba 11.
// 🪤 Se ajusta `scrollTop` a mano y NO con `scrollIntoView`, que también
// desplaza los ancestros scrollables y movería la página entera.
function verElActivo() {
  const nav = navEl.value;
  if (!nav || !props.section) return;
  const it = nav.querySelector(`[data-section="${props.section}"]`);
  if (!it) return;
  const r = it.getBoundingClientRect();
  const rn = nav.getBoundingClientRect();
  if (r.bottom > rn.bottom) nav.scrollTop += r.bottom - rn.bottom;
  else if (r.top < rn.top) nav.scrollTop -= rn.top - r.top;
}

// 🪤 Y hace falta un ResizeObserver, no basta con montar y mirar la seccion: los
// badges de la cabecera llegan de la API DESPUES del montaje, asi que la nav se
// encoge -de 463 a 424 px en el caso medido- cuando `verElActivo` ya corrio con
// la caja grande. Sin esto el arreglo no cubre justo el caso que fallo.
let ro = null;
onMounted(() => {
  nextTick(verElActivo);
  if (typeof ResizeObserver !== "undefined" && navEl.value) {
    ro = new ResizeObserver(() => verElActivo());
    ro.observe(navEl.value);
  }
});
onBeforeUnmount(() => {
  if (ro) ro.disconnect();
  ro = null;
});
watch(
  () => props.section,
  () => nextTick(verElActivo),
);
</script>

<style lang="sass" scoped>
.obs-secnav
  width: 196px
  flex: none
  padding: 12px 8px
  border-right: 1px solid var(--obs-border)
  background: var(--obs-surface)
  overflow-y: auto
.obs-secnav--wide
  width: 240px
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
