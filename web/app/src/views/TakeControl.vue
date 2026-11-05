<template>
  <!--
    050 (T048): "Tomar control" en el lenguaje visual de la v2.

    Es una ventana propia (api/agents.js la abre con openURL, 1600x900), así que
    no tiene el shell ni el riel de la consola: no vive dentro de MainLayout. Lo
    que adopta es el resto del lenguaje — cabecera con migas / hostname / estado
    como AgentHeader (046 T018), botones de contorno con el borde de control, y
    el lienzo del escritorio remoto a sangre. Los colores salen de los tokens
    --obs-* / --q-*; nada de hex en la vista (V2-G02).
  -->
  <div class="obs-page obs-remote">
    <header class="obs-remote__head row no-wrap items-center q-gutter-x-sm">
      <div class="col" style="min-width: 0">
        <div v-if="crumbs" class="obs-page__crumbs ellipsis" :title="crumbs">
          {{ crumbs }}
        </div>
        <div class="row items-center no-wrap q-gutter-x-sm">
          <h1 class="obs-remote__host ellipsis" :title="hostname">
            {{ hostname || $t("takeControl.connecting") }}
          </h1>
          <!-- 046 (UI-D05) / V2-G05: el estado se dice con un punto de color de
               estado sobre píldora neutra, no pintando el texto ni el fondo. -->
          <span
            class="obs-remote__status"
            :class="`obs-remote__status--${status || 'unknown'}`"
          >
            <span class="obs-remote__dot" />
            {{ statusText }}
          </span>
        </div>
      </div>
      <!-- V2-G05 (enmienda 2026-10-18): "Recuperar conexión" es una acción, no
           un estado: va neutra de contorno. Antes iba en el negativo del tablero. -->
      <div class="row no-wrap items-center q-gutter-sm obs-remote__btns">
        <q-btn
          outline
          no-caps
          class="obs-page__btn"
          icon="refresh"
          :label="$t('takeControl.restartConnection')"
          @click="restartMeshService"
        />
        <q-btn
          outline
          no-caps
          class="obs-page__btn"
          icon="fas fa-first-aid"
          :label="$t('takeControl.recoverConnection')"
          @click="repairMeshCentral"
        />
      </div>
    </header>
    <div class="obs-remote__canvas">
      <iframe
        v-show="control"
        :src="control"
        :title="$t('takeControl.frameTitle')"
        allow="clipboard-read; clipboard-write"
        allowfullscreen
        frameborder="0"
      ></iframe>
    </div>
  </div>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";
import { useRoute } from "vue-router";
import { useMeta, useQuasar } from "quasar";
import { fetchAgentMeshCentralURLs, sendAgentRecoverMesh } from "@/api/agents";
import { fetchDashboardInfo } from "@/api/core";
import { sendAgentServiceAction } from "@/api/services";
import { notifySuccess } from "@/utils/notify";

export default {
  name: "TakeControl",
  setup() {
    // vue lifecycle hooks
    onMounted(() => {
      dashInfo();
      getDashInfo();
      getMeshURLs();
    });

    // quasar setup
    const $q = useQuasar();
    const { t } = useI18n();
    const store = useStore();

    // vue router
    const { params } = useRoute();

    // take control setup
    const control = ref("");
    const status = ref(null);
    const hostname = ref("");
    const client = ref("");
    const site = ref("");

    const crumbs = computed(() =>
      [client.value, site.value].filter(Boolean).join(" / "),
    );

    // 050 (T048): el estado llegaba crudo del backend ("online") y se pintaba
    // tal cual en un badge; ahora pasa por i18n como el resto de la v2.
    const statusText = computed(() => {
      switch (status.value) {
        case "online":
          return t("takeControl.statusOnline");
        case "offline":
          return t("takeControl.statusOffline");
        default:
          return t("takeControl.statusUnknown");
      }
    });

    // TODO refactor this so we're not calling the api twice
    const dashInfo = () => {
      store.dispatch("getDashInfo", false);
    };

    async function getMeshURLs() {
      $q.loading.show();
      try {
        const data = await fetchAgentMeshCentralURLs(params.agent_id);
        control.value = data.control;
        status.value = data.status;
        hostname.value = data.hostname;
        client.value = data.client;
        site.value = data.site;
        useMeta({
          title: t("takeControl.metaTitle", {
            hostname: data.hostname,
            client: data.client,
            site: data.site,
          }),
        });
      } catch (e) {
        console.error(e);
      }
      $q.loading.hide();
    }

    async function getDashInfo() {
      const { dark_mode, loading_bar_color } = await fetchDashboardInfo();
      $q.dark.set(dark_mode);
      $q.loadingBar.setDefaults({ color: loading_bar_color });
    }

    async function repairMeshCentral() {
      control.value = "";
      $q.loading.show({ message: t("takeControl.repairingMesh") });
      try {
        const data = await sendAgentRecoverMesh(params.agent_id);
        await getMeshURLs();
        setTimeout(() => {
          notifySuccess(data);
        }, 500);
      } catch (e) {
        console.error(e);
      }
      $q.loading.hide();
    }

    async function restartMeshService() {
      $q.loading.show({ message: t("takeControl.restartingMesh") });
      const data = {
        sv_action: "restart",
      };

      try {
        await sendAgentServiceAction(params.agent_id, "mesh agent", data);
        setTimeout(() => {
          notifySuccess(t("takeControl.meshRestarted"));
        }, 500);
      } catch (e) {
        console.error(e);
      }

      $q.loading.hide();
    }

    return {
      // reactive data
      control,
      status,
      statusText,
      hostname,
      crumbs,

      // methods
      repairMeshCentral,
      restartMeshService,
    };
  },
};
</script>

<style lang="sass" scoped>
// Ventana completa: cabecera fija arriba y el lienzo remoto se come el resto.
// `.obs-page` aporta el remapeo de grises de Quasar a tokens (app.sass); acá se
// le quita el relleno y el gap de página porque el lienzo va a sangre.
.obs-page.obs-remote
  height: 100vh
  padding: 0
  gap: 0
  overflow: hidden
  background: var(--obs-page)
.obs-remote__head
  flex: none
  padding: 10px 16px
  border-bottom: 1px solid var(--obs-border)
  background: var(--obs-page)
// El hostname es el título de la ventana, pero acá manda el lienzo: mismo papel
// que .obs-agenthdr__host con menos cuerpo para no comerse el escritorio remoto.
.obs-remote__host
  margin: 0
  font-size: 18px
  line-height: 1.25
  font-weight: 600
  min-width: 90px
  flex: 0 1 auto
  color: var(--obs-text)
.obs-remote__status
  display: inline-flex
  align-items: center
  gap: 6px
  flex: none
  font-size: 12.5px
  padding: 3px 10px
  border-radius: 99px
  background: var(--obs-raised)
  color: var(--obs-text-2)
  white-space: nowrap
.obs-remote__dot
  width: 7px
  height: 7px
  border-radius: 99px
  background: var(--obs-faint)
.obs-remote__status--online .obs-remote__dot
  background: var(--q-positive)
.obs-remote__status--offline .obs-remote__dot
  background: var(--q-warning)
.obs-remote__btns
  flex: none
.obs-remote__canvas
  flex: 1
  min-height: 0
  background: var(--obs-deep)
  iframe
    display: block
    width: 100%
    height: 100%
    border: 0
// Pantallas angostas: los botones bajan a su fila para que el hostname y el
// estado conserven el ancho (misma regla que .obs-agenthdr a 700 px).
@media (max-width: 700px)
  .obs-remote__head
    flex-wrap: wrap
  .obs-remote__btns
    width: 100%
    order: 2
    flex-wrap: wrap
</style>
