<template>
  <div class="fixed-center text-center" v-if="error">
    <p class="text-faded">There was an error logging into your provider.</p>
    <q-btn color="secondary" style="width: 200px" to="/login"
      >Go back to Login</q-btn
    >
  </div>
</template>

<script lang="ts" setup>
/**
 * ProviderCallback — HUÉRFANO desde feature 001-disable-sso-ui (BrainCorp 2026-06-01).
 *
 * Este componente NO está registrado en el ruteador. La ruta `/account/provider/callback`
 * vive en `src/router/routes.js` como entrada con `beforeEnter` que redirige a `/login`
 * sin montar nada. Se conserva el archivo (no se elimina) para permitir reactivación
 * futura cuando BrainCorp habilite SSO (ADR-013 del hub `observer-rmm` o F008 greenfield).
 *
 * Referencia: `_reversa_forward/001-disable-sso-ui/roadmap.md` decisión D-07.
 * NO eliminar sin coordinar con el roadmap activo.
 */
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const error = route.query.error;

const router = useRouter();
const auth = useAuthStore();
if (!error) {
  if (auth.loggedIn) {
    if (auth.next) {
      router.push(auth.next);
      auth.next = null;
    } else {
      router.push({ name: "Dashboard" });
    }
  } else {
    router.push({ name: "Login" });
  }
}
</script>
