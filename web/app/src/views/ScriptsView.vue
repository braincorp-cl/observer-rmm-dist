<template>
  <!-- 050 (T027): el gestor como página de la consola, no como diálogo. -->
  <q-page class="obs-mgr-page">
    <ScriptManager embedded />
  </q-page>
</template>

<script>
import ScriptManager from "@/components/scripts/ScriptManager.vue";

export default {
  name: "ScriptsView",
  components: { ScriptManager },
};
</script>
