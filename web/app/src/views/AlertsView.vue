<template>
  <!-- 050 (T029): el gestor como página de la consola, no como diálogo. -->
  <q-page class="obs-mgr-page" :style-fn="pageStyle">
    <AlertsManager embedded />
  </q-page>
</template>

<script>
import AlertsManager from "@/components/AlertsManager.vue";

export default {
  name: "AlertsView",
  methods: {
    // Altura fija: cada columna (navegación, lista, tabla) se desplaza sola.
    pageStyle(offset, height) {
      return { height: `${height - offset}px` };
    },
  },
  components: { AlertsManager },
};
</script>
