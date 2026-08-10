<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="bg-dark text-white">
      <q-banner
        v-if="needRefresh"
        inline-actions
        class="bg-red text-white text-center"
      >
        {{ $t("layout.outdatedVersion") }}
        <q-btn
          color="dark"
          icon="refresh"
          :label="$t('layout.refresh')"
          @click="$store.dispatch('reload')"
        />
      </q-banner>
      <q-banner
        v-if="!hosted && tokenExpired"
        inline-actions
        class="bg-yellow text-black text-center"
      >
        <q-icon size="xl" name="warning" />
        <span
          ><br />{{ $t("layout.licenseInactive1") }}<br /><br />{{
            $t("layout.licenseInactive2")
          }}<br /><br />
          {{ $t("layout.licenseInactive3") }}<br /><br />
          {{ $t("layout.licenseInactive4") }}
          <a
            href="https://support.observer.cl"
            target="_blank"
            rel="noopener"
            class="text-primary"
            >{{ $t("layout.supportUrl") }}</a
          ><br /><br
        /></span>
        <q-btn
          color="dark"
          icon="refresh"
          :label="$t('layout.refresh')"
          @click="$store.dispatch('reload')"
        />
      </q-banner>
      <!--
        Modo mantenimiento (feature 036). Tercer banner del header, mismo patrón que
        los dos de arriba. NO se puede descartar a propósito: un banner que se cierra
        vuelve a ser un olvido, y este es la ÚNICA superficie que avisa — el ícono de
        la fila y el nodo del árbol se quedan verdes por decisión (ADR-027 / rediseño
        WebUI), así que si esto no se ve, nada avisa.
      -->
      <q-banner
        v-if="maintenanceCount > 0"
        inline-actions
        class="bg-warning text-black text-center"
      >
        <q-icon size="sm" name="construction" />
        {{ $t("layout.maintenanceCount", { count: maintenanceCount }) }}
        <template v-if="maintenanceOldestDays !== null">
          {{ $t("layout.maintenanceOldest", { days: maintenanceOldestDays }) }}
        </template>
        {{ $t("layout.maintenanceSuppressed") }}
        <q-btn
          color="dark"
          icon="filter_list"
          :label="$t('layout.maintenanceViewList')"
          @click="goToMaintenanceList"
        />
      </q-banner>
      <q-toolbar>
        <q-btn
          dense
          flat
          @click="$store.dispatch('refreshDashboard')"
          icon="refresh"
          v-if="$route.name === 'Dashboard'"
        />
        <q-btn
          v-else
          dense
          flat
          @click="$router.push({ name: 'Dashboard' })"
          icon="dashboard"
        >
          <q-tooltip>{{ $t("layout.backToDashboard") }}</q-tooltip>
        </q-btn>
        <q-toolbar-title>
          Observer RMM<span class="text-overline q-ml-sm">{{
            $t("layout.version", { version: currentVersion })
          }}</span>
          <!-- update check -->
          <q-chip
            v-if="updateAvailable"
            class="text-overline q-ml-sm"
            :color="dash_warning_color"
            icon="update"
            dense
            ><a :href="latestReleaseURL" target="_blank">{{
              $t("layout.updateAvailable", { version: latestVersion })
            }}</a></q-chip
          >
          <!-- cert expiring soon check -->
          <q-chip
            v-if="daysUntilCertExpires <= 15"
            dense
            :color="dash_negative_color"
            text-color="black"
            icon="warning"
            >{{
              $t("layout.certExpires", { days: daysUntilCertExpires })
            }}</q-chip
          >
        </q-toolbar-title>
        <!-- language selector (i18n, feature 010) -->
        <q-select
          v-model="language"
          :options="languageOptions"
          :aria-label="$t('layout.language')"
          emit-value
          map-options
          dense
          borderless
          options-dense
          dropdown-icon="expand_more"
          class="lang-select q-mr-sm"
          style="min-width: 104px"
        >
          <template v-slot:prepend>
            <q-icon name="language" size="18px" />
          </template>
        </q-select>
        <!-- temp dark mode toggle -->
        <q-toggle
          v-model="darkMode"
          class="q-mr-sm"
          checked-icon="nights_stay"
          unchecked-icon="wb_sunny"
        />
        <!-- web terminal button -->
        <q-btn
          v-if="!hosted"
          label=">_"
          dense
          flat
          @click="openWebTerm"
          class="q-mr-sm"
          style="font-size: 16px"
        />
        <!-- Devices Chip -->
        <q-chip class="cursor-pointer">
          <q-avatar size="md" icon="devices" color="primary" />
          <q-tooltip :delay="600" anchor="top middle" self="top middle">{{
            $t("layout.agentCount")
          }}</q-tooltip>
          {{ serverCount + workstationCount }}
          <q-menu>
            <q-list dense>
              <q-item-label header>{{ $t("layout.servers") }}</q-item-label>
              <q-item>
                <q-item-section avatar>
                  <q-icon name="dns" size="sm" color="primary" />
                </q-item-section>

                <q-item-section no-wrap>
                  <q-item-label>{{
                    $t("layout.total", { count: serverCount })
                  }}</q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section avatar>
                  <q-icon
                    name="power_off"
                    size="sm"
                    :color="dash_negative_color"
                  />
                </q-item-section>

                <q-item-section no-wrap>
                  <q-item-label>{{
                    $t("layout.offline", { count: serverOfflineCount })
                  }}</q-item-label>
                </q-item-section>
              </q-item>
              <q-item-label header>{{
                $t("layout.workstations")
              }}</q-item-label>
              <q-item>
                <q-item-section avatar>
                  <q-icon name="computer" size="sm" color="primary" />
                </q-item-section>

                <q-item-section no-wrap>
                  <q-item-label>{{
                    $t("layout.total", { count: workstationCount })
                  }}</q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section avatar>
                  <q-icon
                    name="power_off"
                    size="sm"
                    :color="dash_negative_color"
                  />
                </q-item-section>

                <q-item-section no-wrap>
                  <q-item-label>{{
                    $t("layout.offline", { count: workstationOfflineCount })
                  }}</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-chip>

        <AlertsIcon />

        <q-btn-dropdown flat no-caps stretch :label="displayName || ''">
          <q-list>
            <q-item
              clickable
              v-ripple
              @click="showUserPreferences"
              v-close-popup
            >
              <q-item-section>
                <q-item-label>{{ $t("layout.preferences") }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item clickable>
              <q-item-section>{{ $t("layout.account") }}</q-item-section>
              <q-item-section side>
                <q-icon name="keyboard_arrow_right" />
              </q-item-section>

              <q-menu anchor="top end" self="top start">
                <q-list>
                  <q-item
                    clickable
                    v-ripple
                    @click="resetPassword"
                    v-close-popup
                  >
                    <q-item-section>
                      <q-item-label>{{
                        $t("layout.resetPassword")
                      }}</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item clickable v-ripple @click="reset2FA" v-close-popup>
                    <q-item-section>
                      <q-item-label>{{ $t("layout.reset2fa") }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-item>
            <q-item to="/expired" exact>
              <q-item-section>
                <q-item-label>{{ $t("layout.logout") }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
      </q-toolbar>
    </q-header>
    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>
<script setup lang="ts">
// composition imports
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { useQuasar } from "quasar";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import { useDashboardStore } from "@/stores/dashboard";
import { useAuthStore } from "@/stores/auth";
import { storeToRefs } from "pinia";
import { resetTwoFactor } from "@/api/accounts";
import { notifyError, notifySuccess } from "@/utils/notify";
import axios from "axios";
import { i18n, applyLocale } from "@/boot/i18n";
import { useI18n } from "vue-i18n";

// webtermn
import { checkWebTermPerms, openWebTerminal } from "@/api/core";

// ui imports
import AlertsIcon from "@/components/AlertsIcon.vue";
import UserPreferences from "@/components/modals/coresettings/UserPreferences.vue";
import ResetPass from "@/components/accounts/ResetPass.vue";

const store = useStore();
const router = useRouter();
const $q = useQuasar();
const { t } = useI18n();

const {
  serverCount,
  serverOfflineCount,
  workstationCount,
  workstationOfflineCount,
  daysUntilCertExpires,
} = storeToRefs(useDashboardStore());

const { displayName } = storeToRefs(useAuthStore());

const darkMode = computed({
  get: () => {
    return $q.dark.isActive;
  },
  set: (value) => {
    axios.patch("/accounts/users/ui/", { dark_mode: value });
    $q.dark.set(value);
  },
});

// i18n (feature 010): selector de idioma. Espeja el patrón de darkMode — aplica en vivo
// (vue-i18n + Quasar lang pack) y persiste la preferencia en el backend (User.language).
const language = computed({
  get: () => i18n.global.locale.value,
  set: (value) => {
    applyLocale(value);
    axios.patch("/accounts/users/ui/", { language: value });
  },
});
const languageOptions = [
  { label: "English", value: "en" },
  { label: "Español", value: "es" },
];

const currentVersion = computed(() => store.state.currentVersion);
const latestVersion = computed(() => store.state.latestVersion);
const needRefresh = computed(() => store.state.needrefresh);
const hosted = computed(() => store.state.hosted);
const tokenExpired = computed(() => store.state.tokenExpired);
const dash_warning_color = computed(() => store.state.dash_warning_color);
const dash_negative_color = computed(() => store.state.dash_negative_color);

// Modo mantenimiento (feature 036). El conteo llega ya filtrado por rol desde
// /core/dashinfo/ y se refresca junto al dashboard.
const maintenanceCount = computed(() => store.state.maintenanceCount);
// `null` cuando TODOS los marcados tienen since=None (contrato del nulo): el banner
// omite la frase de antigüedad en vez de mentir con "0 días".
const maintenanceOldestDays = computed(() => {
  const oldest = store.state.maintenanceOldestSince;
  if (!oldest) return null;
  const parsed = new Date(oldest).getTime();
  if (Number.isNaN(parsed)) return null;
  return Math.max(0, Math.floor((Date.now() - parsed) / 86400000));
});

function goToMaintenanceList() {
  // Limpia el nodo del árbol antes de filtrar: si el usuario tenía un sitio
  // seleccionado, la tabla mostraría sólo los de ese sitio y el listado no
  // cuadraría con el conteo del banner.
  store.dispatch("refreshDashboard", true);
  router
    .push({ name: "Dashboard", query: { search: "is:maintenance" } })
    .catch(() => {});
}

const latestReleaseURL = computed(() => {
  // Changelog público servido por el CDN propio agents.observer.cl (escribible desde
  // CI por WebDAV → siempre al día). NO GitHub: los repos son privados. El ancla
  // v{ver} la publica el workflow publish-changelog.yml a partir de CHANGELOG.md.
  return latestVersion.value
    ? `https://agents.observer.cl/changelog/#v${latestVersion.value}`
    : "";
});

function showUserPreferences() {
  $q.dialog({
    component: UserPreferences,
  }).onOk(() => store.dispatch("getDashInfo"));
}

function resetPassword() {
  $q.dialog({
    component: ResetPass,
  });
}

function reset2FA() {
  $q.dialog({
    title: t("layout.reset2fa"),
    message: t("layout.reset2faConfirm"),
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    try {
      const ret = await resetTwoFactor();
      notifySuccess(ret, 3000);
    } catch {}
  });
}

async function openWebTerm() {
  try {
    const { message, status } = await checkWebTermPerms();
    if (status === 412) {
      notifyError(message);
    } else {
      openWebTerminal();
    }
  } catch (e) {
    console.error(e);
  }
}

const updateAvailable = computed(() => {
  if (
    latestVersion.value === "error" ||
    hosted.value ||
    currentVersion.value?.includes("-dev")
  )
    return false;
  return currentVersion.value !== latestVersion.value;
});

const poll = ref(null);

function livePoll() {
  poll.value = setInterval(
    () => {
      store.dispatch("checkVer");
      store.dispatch("getDashInfo", false);
    },
    60 * 4 * 1000,
  );
}

onMounted(() => {
  store.dispatch("getDashInfo");
  store.dispatch("checkVer");
  livePoll();
});

onBeforeUnmount(() => {
  clearInterval(poll.value);
});
</script>

<style scoped lang="sass">
// El selector de idioma vive sobre el header navy en ambos modos.
// Le damos afordancia de control (pill translúcido) para que no se
// confunda con texto plano — el problema que se notaba en modo día.
.lang-select
  background: rgba(255, 255, 255, 0.06)
  border: 1px solid rgba(255, 255, 255, 0.16)
  border-radius: 7px
  padding: 0 8px
  transition: background 0.15s ease, border-color 0.15s ease
  color: #fff
  &:hover
    background: rgba(255, 255, 255, 0.12)
    border-color: rgba(255, 255, 255, 0.28)
  // El header es navy en día y noche → el texto y los íconos del selector
  // deben ser siempre blancos. En modo día Quasar los pintaría oscuros por
  // defecto (ignora el text-white del header en su lógica interna de q-field).
  :deep(.q-field__native), :deep(.q-field__native span), :deep(.q-icon)
    color: #fff !important
</style>
