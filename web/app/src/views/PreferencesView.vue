<template>
  <!-- 050 (T034): Preferencias de usuario como página, con la maqueta de ajustes. -->
  <q-page class="obs-mgr-page" :style-fn="pageStyle">
    <UserPreferences embedded />
  </q-page>
</template>

<script>
import UserPreferences from "@/components/modals/coresettings/UserPreferences.vue";

export default {
  name: "PreferencesView",
  methods: {
    // Altura fija: el contenido se desplaza y la barra de guardado queda a la vista.
    pageStyle(offset, height) {
      return { height: `${height - offset}px` };
    },
  },
  components: { UserPreferences },
};
</script>
