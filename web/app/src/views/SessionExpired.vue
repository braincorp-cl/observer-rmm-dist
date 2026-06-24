<template>
  <div class="fixed-center text-center">
    <p class="text-faded">{{ $t("session.expired") }}</p>
    <q-btn color="secondary" style="width: 200px" to="/login">{{
      $t("session.login")
    }}</q-btn>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useAuthStore } from "@/stores/auth";
import { useDashWSConnection } from "@/websocket/websocket";

// setup store
const auth = useAuthStore();

// setup websocket
const { close } = useDashWSConnection();

onMounted(async () => {
  await auth.logout();
  close();
});
</script>
