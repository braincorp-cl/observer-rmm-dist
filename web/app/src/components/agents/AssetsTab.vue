<template>
  <div v-if="!selectedAgent" class="q-pa-sm">
    {{ $t("agentTabs.noAgentSelected") }}
  </div>
  <div v-else-if="agentPlatform.toLowerCase() !== 'windows'" class="q-pa-sm">
    {{ $t("agentTabs.common.windowsOnly") }}
  </div>
  <div v-else>
    <!--
      046 (dirección 1c): selector segmentado en vez de q-tabs, para que la vista
      de agente no tenga pestañas (UI-E04). Mismas subsecciones, mismo contenido.
    -->
    <q-btn-toggle
      v-model="tab"
      dense
      no-caps
      flat
      spread
      toggle-color="primary"
      class="obs-assets-toggle"
      :options="assetOptions"
    />

    <q-separator />

    <q-tab-panels v-model="tab" :animated="false">
      <q-tab-panel name="os">
        <WmiDetail :info="assets.os" />
      </q-tab-panel>
      <q-tab-panel name="cpu">
        <WmiDetail :info="assets.cpu" />
      </q-tab-panel>
      <q-tab-panel name="mem">
        <WmiDetail :info="assets.mem" />
      </q-tab-panel>
      <q-tab-panel name="usb">
        <WmiDetail :info="assets.usb" />
      </q-tab-panel>
      <q-tab-panel name="bios">
        <WmiDetail :info="assets.bios" />
      </q-tab-panel>
      <q-tab-panel name="disk">
        <WmiDetail :info="assets.disk" />
      </q-tab-panel>
      <q-tab-panel name="comp_sys">
        <WmiDetail :info="assets.comp_sys" />
      </q-tab-panel>
      <q-tab-panel name="base_board">
        <WmiDetail :info="assets.base_board" />
      </q-tab-panel>
      <q-tab-panel name="comp_sys_prod">
        <WmiDetail :info="assets.comp_sys_prod" />
      </q-tab-panel>
      <q-tab-panel name="network_config">
        <WmiDetail :info="assets.network_config" />
      </q-tab-panel>
      <q-tab-panel name="desktop_monitor">
        <WmiDetail :info="assets.desktop_monitor" />
      </q-tab-panel>
      <q-tab-panel name="graphics">
        <WmiDetail :info="assets.graphics" />
      </q-tab-panel>
      <q-tab-panel name="network_adapter">
        <WmiDetail :info="assets.network_adapter" />
      </q-tab-panel>
      <q-tab-panel name="encryption">
        <DiskEncryptionDetail
          v-if="selectedAgent"
          :agent-id="selectedAgent"
          :status="agentStatus"
        />
      </q-tab-panel>
    </q-tab-panels>
  </div>
</template>

<script>
// composition imports
import { ref, computed, watch, onMounted } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { fetchAgent } from "@/api/agents";

// ui imports
import WmiDetail from "@/components/agents/WmiDetail.vue";
import DiskEncryptionDetail from "@/components/agents/DiskEncryptionDetail.vue";

export default {
  name: "AssetsTab",
  components: { WmiDetail, DiskEncryptionDetail },
  setup() {
    // setup vuex
    const store = useStore();
    const selectedAgent = computed(() => store.state.selectedRow);
    const agentPlatform = computed(() => store.state.agentPlatform);
    const loading = ref(false);

    // assets tab logic
    const assets = ref({});
    const tab = ref("os");
    const { t } = useI18n();
    // Mismas subsecciones y rótulos que las pestañas v1, ahora en el selector.
    const assetOptions = computed(() =>
      [
        ["os", "os"],
        ["cpu", "cpu"],
        ["mem", "mem"],
        ["usb", "usb"],
        ["bios", "bios"],
        ["disk", "disk"],
        ["comp_sys", "compSys"],
        ["base_board", "baseBoard"],
        ["comp_sys_prod", "compSysProd"],
        ["network_config", "networkConfig"],
        ["graphics", "graphics"],
        ["desktop_monitor", "desktopMonitor"],
        ["network_adapter", "networkAdapter"],
        ["encryption", "encryption"],
      ].map(([value, key]) => ({ value, label: t(`agentTabs.assets.${key}`) })),
    );
    // Feature 037: el estado de última señal del agente lo lee el detalle de
    // cifrado para no mandar el refresco a un equipo fuera de línea. Sale del
    // mismo `fetchAgent` que ya trae los activos, sin una segunda llamada.
    const agentStatus = ref("");

    async function getWMIData() {
      loading.value = true;
      const agent = await fetchAgent(selectedAgent.value);
      assets.value = agent?.wmi_detail ?? {};
      agentStatus.value = agent?.status ?? "";
      loading.value = false;
    }

    watch(selectedAgent, (newValue) => {
      if (newValue) {
        getWMIData();
      }
    });

    onMounted(() => {
      if (selectedAgent.value) getWMIData();
    });

    return {
      // reactive data
      assets,
      tab,
      assetOptions,
      selectedAgent,
      agentPlatform,
      agentStatus,
    };
  },
};
</script>
