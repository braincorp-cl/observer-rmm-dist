<template>
  <!-- 050 (T049): mismo andamiaje que LoginView — q-layout / q-page-container /
       q-page centrada — y el mismo ancho responsivo de tarjeta, en vez del `row`
       con dos columnas vacías. `obs-ws` es el ámbito de tokens de las vistas
       migradas: re-resuelve los grises internos de Quasar desde --obs-*
       (V2-G02). -->
  <q-layout>
    <q-page-container>
      <q-page class="flex flex-center obs-ws">
        <q-card
          v-bind:style="$q.screen.lt.sm ? { width: '80%' } : { width: '30%' }"
        >
          <q-card-section class="row items-center">
            <h1 class="obs-page__title">{{ $t("totp.title") }}</h1>
          </q-card-section>
          <q-card-section v-if="qrUrl">
            <p>{{ $t("totp.scanInstructions") }}</p>
            <img :src="qrCode" :alt="$t('totp.qrAlt')" />
          </q-card-section>
          <q-card-section v-if="totpKey">
            <p>{{ $t("totp.manualInstructions") }}</p>
            <!-- 050 (T049, V2-G01): la clave compartida es un dato que se
                 transcribe carácter por carácter ⇒ Mono. -->
            <p class="mono">{{ totpKey }}</p>
          </q-card-section>
          <q-card-actions align="center">
            <q-btn
              no-caps
              :label="$t('totp.finish')"
              color="primary"
              class="full-width"
              @click="logout"
              :loading="loading"
            />
          </q-card-actions>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";
import { useQuasar } from "quasar";
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "vue-router";

import { useQRCode } from "@vueuse/integrations/useQRCode";

// setup quasar
const $q = useQuasar();

// setup auth store
const auth = useAuthStore();

// setup router
const router = useRouter();

const totpKey = ref("");
const qrUrl = ref("");
const clearToken = ref(true);
const loading = ref(false);

const qrCode = useQRCode(qrUrl);

async function getQRCodeData() {
  loading.value = true;

  try {
    const data = await auth.setupTotp();

    if (!data) {
      //don't logout user if totp is already set
      clearToken.value = false;
      router.push({ name: "Login" });
    } else {
      totpKey.value = data.totp_key;
      qrUrl.value = data.qr_url;
    }
  } finally {
    loading.value = false;
  }
}

async function logout() {
  await auth.logout();
  clearToken.value = false;
  router.push({ name: "Login" });
}

onMounted(() => {
  getQRCodeData();
  // 050 (T049): el acceso fuerza oscuro y esta pantalla forzaba claro, así que
  // el mismo flujo cambiaba de tema a mitad de camino. Ahora las dos van oscuras.
  $q.dark.set(true);
});

onBeforeUnmount(async () => {
  if (clearToken.value) {
    await auth.logout();
  }
});
</script>
