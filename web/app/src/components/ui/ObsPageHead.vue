<template>
  <!-- 050 ola 3: cabecera de página con el lenguaje de la flota (migas + título + acciones). -->
  <div class="row items-end q-gutter-y-sm obs-page__head">
    <div class="col">
      <div class="obs-page__crumbs">{{ crumbs.join(" / ") }}</div>
      <h1 class="obs-page__title">{{ title }}</h1>
    </div>
    <div class="row q-gutter-sm">
      <slot />
    </div>
  </div>
</template>

<script>
export default {
  name: "ObsPageHead",
  props: {
    title: { type: String, required: true },
    crumbs: { type: Array, default: () => [] },
  },
};
</script>
