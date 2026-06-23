<template>
  <q-layout>
    <q-page-container>
      <q-page class="flex bg-image flex-center">
        <q-card
          v-bind:style="$q.screen.lt.sm ? { width: '80%' } : { width: '30%' }"
        >
          <q-card-section>
            <div class="text-center q-pt-lg">
              <div class="col text-h4 ellipsis">Observer RMM</div>
            </div>
          </q-card-section>
          <q-card-section>
            <q-form ref="form" @submit.prevent="checkCreds" class="q-gutter-md">
              <q-input
                filled
                v-model="credentials.username"
                :label="$t('login.username')"
                lazy-rules
                :rules="[
                  (val) => (val && val.length > 0) || $t('login.fieldRequired'),
                ]"
              />
              <q-input
                v-model="credentials.password"
                filled
                :type="showPassword ? 'password' : 'text'"
                :label="$t('login.password')"
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
              <div>
                <q-btn
                  :label="$t('login.submit')"
                  type="submit"
                  color="primary"
                  class="full-width"
                />
              </div>
            </q-form>
          </q-card-section>

          <!-- SSO descartado (ADR-010, 2026-06-17): sección "Log in with SSO" eliminada (módulo ee/sso vaciado). -->
        </q-card>

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
                  v-model="twofactor"
                  :rules="[
                    (val) =>
                      (val && val.length > 0) || $t('login.fieldRequired'),
                  ]"
                />
              </q-card-section>

              <q-card-actions align="right" class="text-primary">
                <q-btn flat :label="$t('login.cancel')" v-close-popup />
                <q-btn flat :label="$t('login.twoFactorSubmit')" type="submit" />
              </q-card-actions>
            </q-form>
          </q-card>
        </q-dialog>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { type QForm, useQuasar } from "quasar";
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "vue-router";

// SSO descartado (ADR-010, 2026-06-17): imports y lógica SSO eliminados (módulo ee/sso vaciado).

// setup quasar
const $q = useQuasar();
$q.dark.set(true);

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

<style>
.bg-image {
  background-image: linear-gradient(
    90deg,
    rgba(20, 20, 29, 1) 0%,
    rgba(38, 42, 56, 1) 49%,
    rgba(15, 18, 20, 1) 100%
  );
}
</style>
