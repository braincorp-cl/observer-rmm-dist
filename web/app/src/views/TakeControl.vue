<template>
  <!--
    050 (T048): "Tomar control" en el lenguaje visual de la v2.

    Es una ventana propia (api/agents.js la abre con openURL, 1600x900), así que
    no tiene el shell ni el riel de la consola: no vive dentro de MainLayout. Lo
    que adopta es el resto del lenguaje — cabecera con migas / hostname / estado
    como AgentHeader (046 T018), botones de contorno con el borde de control, y
    el lienzo del escritorio remoto a sangre. Los colores salen de los tokens
    --obs-* / --q-*; nada de hex en la vista (V2-G02).

    050 (V2-P10, 2026-11-05): esa cabecera y su sass se mudaron tal cual a
    `RemoteWindowChrome`, para que la VNC web y la terminal web la hereden en
    vez de copiarla. El marcado que se pinta es el mismo; lo que cambió es
    dónde vive. El `$q.dark.set()` también se fue allá: era lo único que hacía
    que esta ventana respetara el tema y a `WebVNC` le faltaba.
  -->
  <RemoteWindowChrome
    :crumbs="crumbs"
    :hostname="hostname"
    :title="$t('takeControl.connecting')"
    :status="status"
    :status-text="statusText"
  >
    <!-- V2-G05 (enmienda 2026-10-18): "Recuperar conexión" es una acción, no
         un estado: va neutra de contorno. Antes iba en el negativo del tablero. -->
    <template #actions>
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
    </template>
    <iframe
      v-show="control"
      :src="control"
      :title="$t('takeControl.frameTitle')"
      allow="clipboard-read; clipboard-write"
      allowfullscreen
      frameborder="0"
    ></iframe>
  </RemoteWindowChrome>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";
import { useRoute } from "vue-router";
import { useMeta, useQuasar } from "quasar";
import { fetchAgentMeshCentralURLs, sendAgentRecoverMesh } from "@/api/agents";
import { sendAgentServiceAction } from "@/api/services";
import { notifySuccess } from "@/utils/notify";
import RemoteWindowChrome from "@/components/remote/RemoteWindowChrome.vue";

export default {
  name: "TakeControl",
  components: { RemoteWindowChrome },
  setup() {
    // vue lifecycle hooks
    onMounted(() => {
      dashInfo();
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
