<template>
  <!-- 050 (T028): el gestor como página de la consola, no como diálogo. -->
  <q-page class="obs-mgr-page" :style-fn="pageStyle">
    <AutomationManager embedded />
  </q-page>
</template>

<script>
import AutomationManager from "@/components/automation/AutomationManager.vue";

export default {
  name: "AutomationView",
  methods: {
    // Altura fija: cada columna (navegación, lista, tabla) se desplaza sola.
    pageStyle(offset, height) {
      return { height: `${height - offset}px` };
    },
  },
  components: { AutomationManager },
};
</script>
