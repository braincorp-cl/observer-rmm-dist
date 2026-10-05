<template>
  <div v-if="!selectedAgent" class="q-pa-sm">
    {{ $t("agentTabs.noAgentSelected") }}
  </div>
  <div v-else-if="agentPlatform.toLowerCase() !== 'windows'" class="q-pa-sm">
    {{ $t("agentTabs.common.windowsOnly") }}
  </div>
  <div v-else>
    <!--
      046 (dirección 1c): las subsecciones de Activos van apiladas como bloques
      desplegables (q-expansion-item), no como pestañas ni como un selector que
      conmuta paneles: la vista de agente no tiene pestañas (UI-E04). Mismo
      contenido por subsección; Sistema operativo abierto de entrada.
    -->
    <q-list separator class="obs-assets">
      <q-expansion-item
        v-for="opt in assetOptions"
        :key="opt.value"
        dense
        dense-toggle
        :default-opened="opt.value === 'os'"
        :label="opt.label"
        :data-asset="opt.value"
        header-class="obs-assets__hdr"
      >
        <div class="q-px-md q-pb-sm">
          <DiskEncryptionDetail
            v-if="opt.value === 'encryption' && selectedAgent"
            :agent-id="selectedAgent"
            :status="agentStatus"
          />
          <WmiDetail
            v-else-if="opt.value !== 'encryption'"
            :info="assets[opt.value]"
          />
        </div>
      </q-expansion-item>
    </q-list>
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
      assetOptions,
      selectedAgent,
      agentPlatform,
      agentStatus,
    };
  },
};
</script>

<style lang="sass" scoped>
.obs-assets
  :deep(.obs-assets__hdr)
    color: var(--obs-text-2)
    font-weight: 500
</style>
