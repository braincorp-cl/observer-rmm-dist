<template>
  <!--
    050 (V2-S06): el enrolamiento TOTP en la maqueta de acceso.

    🪤 Nota para quien la vuelva a medir: el gauntlet capturo esta pantalla
    VACIA (solo titulo y boton) porque el cerrojo de escritura bloquea
    `POST /accounts/users/setup_totp/` con 418 — y hace bien, es la llamada que
    CREA el secreto, no es inocua. Para juzgar esta pantalla hay que poblarla
    con un stub declarado de esa respuesta; si no, el QR, las instrucciones y la
    clave no existen en ninguna captura.
  -->
  <AccessLayout force-dark :heading="$t('totp.title')">
    <template v-if="qrUrl">
      <p class="obs-totp__paso">{{ $t("totp.scanInstructions") }}</p>
      <img :src="qrCode" :alt="$t('totp.qrAlt')" class="obs-totp__qr" />
    </template>
    <template v-if="totpKey">
      <p class="obs-totp__paso">{{ $t("totp.manualInstructions") }}</p>
      <!-- 050 (T049, V2-G01): la clave compartida es un dato que se transcribe
           caracter por caracter ⇒ Mono. -->
      <p class="mono obs-totp__clave obs-token-entero">{{ totpKey }}</p>
    </template>
    <q-btn
      unelevated
      no-caps
      :label="$t('totp.finish')"
      color="primary"
      class="obs-page__btn full-width"
      @click="logout"
      :loading="loading"
    />
  </AccessLayout>
</template>

<style lang="sass" scoped>
.obs-totp__paso
  margin: 0 0 12px
  font-size: 14px
  line-height: 1.5
  color: var(--obs-text-2)
.obs-totp__qr
  display: block
  margin: 0 0 20px
.obs-totp__clave
  margin: 0 0 20px
  word-break: break-all
  color: var(--obs-text)
</style>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "vue-router";

import { useQRCode } from "@vueuse/integrations/useQRCode";
import AccessLayout from "@/components/access/AccessLayout.vue";

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

// 050 (V2-S06): el forzado de oscuro y su restauración al desmontar viven
// ahora en AccessLayout (prop `force-dark`), que es el único sitio donde una
// pantalla de acceso toca el estado global de tema.

onMounted(() => {
  getQRCodeData();
});

onBeforeUnmount(async () => {
  if (clearToken.value) {
    await auth.logout();
  }
});
</script>
