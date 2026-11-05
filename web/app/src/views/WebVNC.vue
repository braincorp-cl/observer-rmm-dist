<template>
  <!--
    050 (V2-P10): la ventana de VNC en el lenguaje visual de la v2.

    🪤 Hasta 2026-11-05 esta vista no se había tocado NUNCA en la rama v2: cero
    commits desde `fb59a20`. El gauntlet de la ola 8 lo probó de la forma más
    seca posible — `v1-abre-webvnc-5900.png` y `v2-abre-webvnc-5900.png` tenían
    el MISMO md5 (315f99763b288efc76698aa517cf4748): no parecidos, el mismo
    archivo byte a byte. Era un iframe suelto sin cabecera y sin arranque de
    tema, así que salía en claro aunque el usuario tuviera el tema oscuro.

    Hereda el chrome de `RemoteWindowChrome`, que es donde vive también el
    `$q.dark.set()` que faltaba. No lleva botones: la sesión de noVNC se
    gobierna desde dentro del iframe.
  -->
  <RemoteWindowChrome
    :crumbs="crumbs"
    :hostname="hostname"
    :title="$t('webVNC.connecting')"
  >
    <iframe
      v-show="vnc"
      :src="vnc"
      :title="$t('webVNC.frameTitle')"
      allow="clipboard-read; clipboard-write"
      allowfullscreen
      frameborder="0"
    ></iframe>
  </RemoteWindowChrome>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { useMeta } from "quasar";
import { useI18n } from "vue-i18n";

import RemoteWindowChrome from "@/components/remote/RemoteWindowChrome.vue";
import { fetchAgentWebVNCUrl } from "@/api/agents";

const { params } = useRoute();
const { t } = useI18n();

const vnc = ref("");
const hostname = ref("");
const client = ref("");
const site = ref("");

const crumbs = computed(() =>
  [client.value, site.value].filter(Boolean).join(" / "),
);

async function getVNCUrl() {
  try {
    const data = await fetchAgentWebVNCUrl(params.agent_id, params.port);
    vnc.value = data.vnc;
    hostname.value = data.hostname;
    client.value = data.client;
    site.value = data.site;
    useMeta({
      title: t("webVNC.metaTitle", {
        hostname: data.hostname,
        client: data.client,
        site: data.site,
      }),
    });
  } catch (e) {
    console.error(e);
  }
}

onMounted(async () => {
  getVNCUrl();
});
</script>
