<template>
  <!-- 050 (T027): el gestor como página de la consola, no como diálogo. -->
  <q-page class="obs-mgr-page" :style-fn="pageStyle">
    <ScriptManager embedded />
  </q-page>
</template>

<script>
import ScriptManager from "@/components/scripts/ScriptManager.vue";

export default {
  name: "ScriptsView",
  methods: {
    // Altura fija: cada columna (navegación, lista, tabla) se desplaza sola.
    pageStyle(offset, height) {
      return { height: `${height - offset}px` };
    },
  },
  components: { ScriptManager },
};
</script>
