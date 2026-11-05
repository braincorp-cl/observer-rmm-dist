<template>
  <!--
    050 (V2-S06): el acceso en la maqueta aprobada (`referencia/acceso.png`).

    Antes era una `q-card` centrada al 30 % — la tarjeta de la v1 con otros
    tokens. El gauntlet lo midió: `columnas_de_pagina` = 1, `imgs_svg` = [], y
    el diff de pixeles contra la v1 en tema claro daba 2,83 % acotado a la
    tarjeta. Era la v1 con otro degradado, no la maqueta.

    Ahora hereda `AccessLayout`: franja de marca + panel de formulario, con los
    rotulos ARRIBA de los campos y el pie que anuncia el segundo paso.
  -->
  <AccessLayout
    force-dark
    :heading="$t('login.heading')"
    :footnote="$t('login.twoStepNote')"
  >
    <q-form ref="form" @submit.prevent="checkCreds">
      <div class="obs-access__field">
        <label class="obs-access__label" for="obs-login-user">
          {{ $t("login.username") }}
        </label>
        <q-input
          for="obs-login-user"
          filled
          dense
          v-model="credentials.username"
          autocomplete="username"
          lazy-rules
          :rules="[
            (val) => (val && val.length > 0) || $t('login.fieldRequired'),
          ]"
        />
      </div>
      <div class="obs-access__field">
        <label class="obs-access__label" for="obs-login-pass">
          {{ $t("login.password") }}
        </label>
        <q-input
          for="obs-login-pass"
          v-model="credentials.password"
          filled
          dense
          autocomplete="current-password"
          :type="showPassword ? 'password' : 'text'"
          lazy-rules
          :rules="[
            (val) => (val && val.length > 0) || $t('login.fieldRequired'),
          ]"
        >
          <template v-slot:append>
            <q-icon
              :name="showPassword ? 'visibility_off' : 'visibility'"
              class="cursor-pointer"
              @click="showPassword = !showPassword"
            />
          </template>
        </q-input>
      </div>
      <q-btn
        unelevated
        no-caps
        :label="$t('login.submit')"
        type="submit"
        color="primary"
        class="obs-page__btn full-width"
      />
    </q-form>

    <!-- SSO descartado (ADR-010, 2026-06-17): seccion "Log in with SSO" eliminada (modulo ee/sso vaciado). -->

    <!-- 2 factor modal -->
    <q-dialog persistent v-model="prompt">
      <q-card style="min-width: 400px">
        <q-form ref="formToken" @submit.prevent="onSubmit">
          <q-card-section class="text-center text-h6">{{
            $t("login.twoFactorTitle")
          }}</q-card-section>

          <q-card-section>
            <q-input
              autofocus
              outlined
              autocomplete="one-time-code"
              inputmode="numeric"
              v-model="twofactor"
              :rules="[
                (val) => (val && val.length > 0) || $t('login.fieldRequired'),
              ]"
            />
          </q-card-section>

          <q-card-actions align="right" class="text-primary">
            <q-btn flat no-caps :label="$t('login.cancel')" v-close-popup />
            <q-btn
              flat
              no-caps
              :label="$t('login.twoFactorSubmit')"
              type="submit"
            />
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>
  </AccessLayout>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { type QForm } from "quasar";
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "vue-router";
import AccessLayout from "@/components/access/AccessLayout.vue";

// SSO descartado (ADR-010, 2026-06-17): imports y lógica SSO eliminados (módulo ee/sso vaciado).

// El forzado de tema oscuro (y su restauración al desmontar) vive ahora en
// AccessLayout, con la prop `force-dark`.

// setup auth store
const auth = useAuthStore();

// setup router
const router = useRouter();

const form = ref<QForm | null>(null);
const formToken = ref<QForm | null>(null);

// login logic
const credentials = reactive({ username: "", password: "" });
const twofactor = ref("");
const prompt = ref(false);
const showPassword = ref(true);

async function checkCreds() {
  try {
    const { totp } = await auth.checkCredentials(credentials);

    if (!totp) {
      router.push({ name: "TOTPSetup" });
    } else {
      twofactor.value = "";
      prompt.value = true;
    }
  } catch (err) {
    console.error(err);
  }
}

async function onSubmit() {
  try {
    await auth.login({ ...credentials, twofactor: twofactor.value });
    if (auth.next) {
      router.push(auth.next);
      auth.next = null;
    } else {
      router.push({ name: "Dashboard" });
    }
  } catch (err) {
    console.error(err);
  } finally {
    form.value?.reset();
    formToken.value?.reset();
    prompt.value = false;
  }
}
</script>

<style lang="sass" scoped>
// 050 (T049, V2-G02): el lienzo del acceso venía de tres rgba() literales del
// tema anterior a la paleta 1c. Queda el mismo gesto — degradado horizontal de
// tres paradas en las mismas posiciones, bordes hundidos y centro elevado —
// escrito con tokens: sigue al tema y ningún hex vive fuera de
// quasar.variables.sass.
.obs-login
  background-image: linear-gradient(90deg, var(--obs-deep) 0%, var(--obs-surface) 49%, var(--obs-rail) 100%)
</style>
