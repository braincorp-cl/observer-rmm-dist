<template>
  <div v-if="!selectedAgent" class="q-pa-sm">
    {{ $t("agentTabs.noAgentSelected") }}
  </div>
  <div v-else-if="agentPlatform.toLowerCase() !== 'windows'" class="q-pa-sm">
    {{ $t("agentTabs.common.windowsOnly") }}
  </div>
  <div v-else>
    <q-tabs
      v-model="tab"
      dense
      class="text-grey"
      active-color="primary"
      indicator-color="primary"
      align="justify"
      narrow-indicator
      no-caps
    >
      <q-tab name="os" :label="$t('agentTabs.assets.os')" />
      <q-tab name="cpu" :label="$t('agentTabs.assets.cpu')" />
      <q-tab name="mem" :label="$t('agentTabs.assets.mem')" />
      <q-tab name="usb" :label="$t('agentTabs.assets.usb')" />
      <q-tab name="bios" :label="$t('agentTabs.assets.bios')" />
      <q-tab name="disk" :label="$t('agentTabs.assets.disk')" />
      <q-tab name="comp_sys" :label="$t('agentTabs.assets.compSys')" />
      <q-tab name="base_board" :label="$t('agentTabs.assets.baseBoard')" />
      <q-tab name="comp_sys_prod" :label="$t('agentTabs.assets.compSysProd')" />
      <q-tab
        name="network_config"
        :label="$t('agentTabs.assets.networkConfig')"
      />
      <q-tab name="graphics" :label="$t('agentTabs.assets.graphics')" />
      <q-tab
        name="desktop_monitor"
        :label="$t('agentTabs.assets.desktopMonitor')"
      />
      <q-tab
        name="network_adapter"
        :label="$t('agentTabs.assets.networkAdapter')"
      />
      <!-- Feature 037 · el cifrado es un activo del equipo, junto al resto. -->
      <q-tab name="encryption" :label="$t('agentTabs.assets.encryption')" />
    </q-tabs>

    <q-separator />

    <q-tab-panels v-model="tab">
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
      selectedAgent,
      agentPlatform,
      agentStatus,
    };
  },
};
</script>
