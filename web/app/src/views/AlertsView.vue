<template>
  <!-- 050 (T029): el gestor como página de la consola, no como diálogo. -->
  <q-page class="obs-mgr-page">
    <AlertsManager embedded />
  </q-page>
</template>

<script>
import AlertsManager from "@/components/AlertsManager.vue";

export default {
  name: "AlertsView",
  components: { AlertsManager },
};
</script>
