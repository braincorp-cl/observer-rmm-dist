<template>
  <!-- 050 (T028): el gestor como página de la consola, no como diálogo. -->
  <q-page class="obs-mgr-page">
    <AutomationManager embedded />
  </q-page>
</template>

<script>
import AutomationManager from "@/components/automation/AutomationManager.vue";

export default {
  name: "AutomationView",
  components: { AutomationManager },
};
</script>
