<template>
  <!-- 050 (T032): Ajustes globales como página; la sección va en la URL. -->
  <q-page class="obs-mgr-page" :style-fn="pageStyle">
    <EditCoreSettings embedded :section="$route.params.section || null" />
  </q-page>
</template>

<script>
import EditCoreSettings from "@/components/modals/coresettings/EditCoreSettings.vue";

export default {
  name: "SettingsView",
  methods: {
    // Altura fija: la navegación y el contenido se desplazan solos y la barra
    // de guardado queda siempre a la vista.
    pageStyle(offset, height) {
      return { height: `${height - offset}px` };
    },
  },
  components: { EditCoreSettings },
};
</script>
