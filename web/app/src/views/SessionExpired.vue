<template>
  <!--
    050 (V2-S06): la sesión expirada en la maqueta de acceso.

    🪤 Esta vista tenía CERO commits en toda la rama v2. El gauntlet lo midió
    sin margen: el diff de píxeles contra la v1 daba 0,12–0,13 % en ambos temas,
    acotado al texto y al botón. No se parecía a la v1: era la v1, con un
    `fixed-center` y un botón en MAYÚSCULAS que ninguna otra vista migrada usa.

    No lleva `force-dark`: acá el usuario venía de una sesión y ya tiene tema
    elegido, así que se respeta. Los tokens hacen que la franja se vea bien en
    los dos.
  -->
  <AccessLayout :heading="$t('session.expiredHeading')">
    <p class="obs-access__text">{{ $t("session.expired") }}</p>
    <q-btn
      unelevated
      no-caps
      color="primary"
      class="obs-page__btn full-width"
      to="/login"
    >
      {{ $t("session.login") }}
    </q-btn>
  </AccessLayout>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useAuthStore } from "@/stores/auth";
import { useDashWSConnection } from "@/websocket/websocket";
import AccessLayout from "@/components/access/AccessLayout.vue";

// setup store
const auth = useAuthStore();

// setup websocket
const { close } = useDashWSConnection();

onMounted(async () => {
  await auth.logout();
  close();
});
</script>

<style lang="sass" scoped>
.obs-access__text
  margin: 0 0 20px
  font-size: 14px
  line-height: 1.5
  color: var(--obs-text-2)
</style>
