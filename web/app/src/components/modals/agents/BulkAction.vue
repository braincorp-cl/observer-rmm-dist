<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="min-width: 50vw">
      <q-bar>
        {{ modalTitle }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("bulkAction.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-form @submit.prevent="submit">
        <q-card-section>
          <p>{{ $t("bulkAction.chooseTarget") }}</p>
          <q-option-group
            v-model="state.target"
            :options="targetOptions"
            color="primary"
            dense
            inline
            class="q-pl-sm"
          />
        </q-card-section>

        <q-card-section>
          <observer-dropdown
            v-if="state.target === 'client'"
            :rules="[(val) => !!val || $t('bulkAction.required')]"
            v-model="state.client"
            :options="clientOptions"
            :label="$t('bulkAction.selectClient')"
            outlined
            mapOptions
            filterable
          />
          <observer-dropdown
            v-else-if="state.target === 'site'"
            :rules="[(val) => !!val || $t('bulkAction.required')]"
            v-model="state.site"
            :options="siteOptions"
            :label="$t('bulkAction.selectSite')"
            outlined
            mapOptions
            filterable
          />
          <observer-dropdown
            v-else-if="state.target === 'agents'"
            :rules="[(val) => !!val || $t('bulkAction.required')]"
            v-model="state.agents"
            :options="agentOptions"
            :label="$t('bulkAction.selectAgents')"
            filled
            multiple
            mapOptions
            filterable
          />
        </q-card-section>

        <q-card-section>
          <p>{{ $t("bulkAction.agentOs") }}</p>
          <q-option-group
            v-model="state.osType"
            :options="filteredOsTypeOptions"
            color="primary"
            dense
            inline
            class="q-pl-sm"
          />
        </q-card-section>

        <q-card-section v-show="state.target !== 'agents'">
          <p>{{ $t("bulkAction.agentType") }}</p>
          <q-option-group
            v-model="state.monType"
            :options="monTypeOptions"
            color="primary"
            dense
            inline
            class="q-pl-sm"
          />
        </q-card-section>

        <q-card-section v-if="mode === 'script'" class="q-pt-none">
          <observer-dropdown
            :rules="[(val) => !!val || '*Required']"
            v-model="state.script"
            :options="filterByPlatformOptions"
            :label="$t('bulkAction.selectScript')"
            outlined
            mapOptions
            filterable
          >
            <template v-slot:after>
              <q-btn
                size="sm"
                round
                dense
                flat
                icon="info"
                @click="openScriptURL"
              >
                <q-tooltip
                  v-if="syntax"
                  class="bg-white text-primary text-body1"
                  >{{ syntax }}</q-tooltip
                >
              </q-btn>
            </template>
          </observer-dropdown>
        </q-card-section>
        <q-card-section v-if="mode === 'script'" class="q-pt-none">
          <observer-dropdown
            v-model="state.args"
            :label="$t('bulkAction.scriptArgs')"
            filled
            use-input
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add"
          />
        </q-card-section>
        <q-card-section v-if="mode === 'script'" class="q-pt-none">
          <observer-dropdown
            v-model="state.env_vars"
            :label="envVarsLabel"
            filled
            use-input
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add"
          />
        </q-card-section>

        <q-card-section v-if="mode === 'command'">
          <p>{{ $t("bulkAction.shell") }}</p>
          <q-option-group
            v-model="state.shell"
            :options="shellOptions"
            color="primary"
            dense
            inline
            class="q-pl-sm"
            @update:model-value="state.custom_shell = null"
          />
        </q-card-section>
        <q-card-section v-if="state.shell === 'custom'">
          <q-input
            v-model="state.custom_shell"
            outlined
            :label="$t('bulkAction.customShell')"
            stack-label
            :placeholder="$t('bulkAction.customShellPlaceholder')"
            :rules="[(val) => !!val || $t('bulkAction.required')]"
          />
        </q-card-section>
        <q-card-section v-if="mode === 'command'">
          <q-input
            v-model="state.cmd"
            outlined
            :label="$t('bulkAction.command')"
            stack-label
            :placeholder="cmdPlaceholder(state.shell)"
            :rules="[(val) => !!val || $t('bulkAction.required')]"
          />
        </q-card-section>
        <q-card-section v-if="supportsRunAsUser()" class="q-pt-none">
          <q-checkbox
            v-model="state.run_as_user"
            :label="$t('bulkAction.runAsUser')"
          >
            <q-tooltip>{{ runAsUserToolTip }}</q-tooltip>
          </q-checkbox>
        </q-card-section>

        <q-card-section v-if="mode === 'script'" class="q-pt-none">
          <div class="q-gutter-sm">
            <q-checkbox
              :label="$t('bulkAction.saveToCustomField')"
              v-model="collector"
              @update:model-value="
                state.custom_field = null;
                state.collector_all_output = false;
              "
            />
            <q-checkbox
              v-model="state.save_to_agent_note"
              :label="$t('bulkAction.saveToAgentNote')"
            />
          </div>
        </q-card-section>

        <q-card-section v-if="mode === 'script' && collector">
          <observer-dropdown
            :rules="[(val) => !!val || $t('bulkAction.required')]"
            outlined
            v-model="state.custom_field"
            :options="customFieldOptions"
            :label="$t('bulkAction.selectCustomField')"
            mapOptions
            filterable
          />
          <q-checkbox
            v-model="state.collector_all_output"
            :label="$t('bulkAction.saveAllOutput')"
          />
        </q-card-section>

        <q-card-section v-if="mode === 'script' || mode === 'command'">
          <q-input
            v-model.number="state.timeout"
            dense
            outlined
            type="number"
            style="max-width: 150px"
            :label="$t('bulkAction.timeoutSeconds')"
            stack-label
            :rules="[
              (val) => !!val || $t('bulkAction.required'),
              (val) => val >= 5 || $t('bulkAction.ruleMinSeconds5'),
            ]"
          />
        </q-card-section>

        <q-card-section v-if="mode === 'patch'">
          <p>{{ $t("bulkAction.action") }}</p>
          <q-option-group
            v-model="state.patchMode"
            :options="patchModeOptions"
            color="primary"
            dense
            inline
            class="q-pl-sm"
          />
        </q-card-section>

        <!-- respuesta rápida de endpoint (feature 028) -->
        <q-card-section v-if="mode === 'alert'" class="q-pt-none">
          <q-input
            outlined
            dense
            v-model="state.title"
            :label="$t('endpointResponse.alertFieldTitle')"
            :maxlength="120"
            counter
          />
        </q-card-section>

        <q-card-section v-if="mode === 'alert'" class="q-pt-none">
          <q-input
            outlined
            dense
            type="textarea"
            autogrow
            v-model="state.message"
            :label="$t('endpointResponse.alertFieldMessage')"
            :maxlength="2000"
            counter
            :rules="[
              (val) => !!val.trim() || $t('endpointResponse.alertRequired'),
            ]"
          />
        </q-card-section>

        <q-card-section v-if="mode === 'alarm'" class="q-pt-none">
          <q-input
            outlined
            dense
            type="number"
            v-model.number="state.duration"
            :label="$t('endpointResponse.alarmDurationLabel')"
            :min="5"
            :max="300"
            :hint="$t('endpointResponse.alarmDurationHint')"
          />
        </q-card-section>

        <q-card-section
          v-if="['lock', 'alarm', 'stopalarm', 'alert'].includes(mode)"
          class="q-pt-none text-caption text-grey-7"
        >
          {{ $t("endpointResponse.bulkNoPerAgentResult") }}
        </q-card-section>

        <q-card-section v-show="false">
          <q-checkbox
            v-model="state.offlineAgents"
            :label="$t('bulkAction.offlineAgents')"
          >
            <q-tooltip>{{ $t("bulkAction.offlineAgentsTooltip") }}</q-tooltip>
          </q-checkbox>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn :label="$t('bulkAction.cancel')" v-close-popup />
          <q-btn
            :label="$t('bulkAction.run')"
            color="primary"
            type="submit"
            :disable="loading"
            :loading="loading"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import {
  ref,
  reactive,
  computed,
  watch,
  onMounted,
  defineComponent,
} from "vue";
import { useDialogPluginComponent, openURL } from "quasar";
import { useI18n } from "vue-i18n";
import { useScriptDropdown } from "@/composables/scripts";
import { useAgentDropdown } from "@/composables/agents";
import { useClientDropdown, useSiteDropdown } from "@/composables/clients";
import { useCustomFieldDropdown } from "@/composables/core";
import { runBulkAction } from "@/api/agents";
import { notifySuccess } from "@/utils/notify";
import { cmdPlaceholder } from "@/composables/agents";
import { envVarsLabel, runAsUserToolTip } from "@/constants/constants";

// ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

export default defineComponent({
  name: "BulkAction",
  components: { ObserverDropdown },
  emits: [...useDialogPluginComponent.emits],
  props: {
    mode: !String,
  },
  setup(props) {
    const { t } = useI18n();

    // Option arrays son computed (no estáticas de módulo) para que las etiquetas
    // traducidas reaccionen al cambio de idioma en vivo.
    const monTypeOptions = computed(() => [
      { label: t("bulkAction.monTypeAll"), value: "all" },
      { label: t("bulkAction.monTypeServers"), value: "servers" },
      { label: t("bulkAction.monTypeWorkstations"), value: "workstations" },
    ]);

    const osTypeOptions = computed(() => [
      { label: t("bulkAction.osWindows"), value: "windows" },
      { label: t("bulkAction.osLinux"), value: "linux" },
      { label: t("bulkAction.osMacos"), value: "darwin" },
      { label: t("bulkAction.osAll"), value: "all" },
    ]);

    const targetOptions = computed(() => [
      { label: t("bulkAction.targetClient"), value: "client" },
      { label: t("bulkAction.targetSite"), value: "site" },
      { label: t("bulkAction.targetSelectedAgents"), value: "agents" },
      { label: t("bulkAction.targetAll"), value: "all" },
    ]);

    const patchModeOptions = computed(() => [
      { label: t("bulkAction.patchScan"), value: "scan" },
      { label: t("bulkAction.patchInstall"), value: "install" },
    ]);

    const shellOptions = computed(() => {
      if (state.osType === "windows") {
        return [
          { label: t("bulkAction.shellCmd"), value: "cmd" },
          { label: t("bulkAction.shellPowershell"), value: "powershell" },
        ];
      } else {
        return [
          { label: t("bulkAction.shellBash"), value: "/bin/bash" },
          { label: t("bulkAction.shellCustom"), value: "custom" },
        ];
      }
    });

    const filteredOsTypeOptions = computed(() => {
      if (props.mode === "command")
        return osTypeOptions.value.filter((i) => i.value !== "all");
      else if (props.mode === "patch")
        return osTypeOptions.value.filter((i) => i.value === "windows");
      return osTypeOptions.value;
    });

    // quasar dialog setup
    const { dialogRef, onDialogHide } = useDialogPluginComponent();

    // dropdown setup
    const {
      script,
      plat,
      filterByPlatformOptions,
      defaultTimeout,
      defaultArgs,
      defaultEnvVars,
      syntax,
      link,
      getScriptOptions,
    } = useScriptDropdown();
    const { agents, agentOptions, getAgentOptions } = useAgentDropdown();
    const { site, siteOptions, getSiteOptions } = useSiteDropdown();
    const { client, clientOptions, getClientOptions } = useClientDropdown();
    const { customFieldOptions } = useCustomFieldDropdown({ onMount: true });

    function openScriptURL() {
      link.value ? openURL(link.value) : null;
    }

    // bulk action logic
    const state = reactive({
      mode: props.mode,
      target: "client",
      monType: "all",
      osType: "windows",
      cmd: "",
      shell: "cmd",
      custom_shell: null,
      custom_field: null,
      collector_all_output: false,
      save_to_agent_note: false,
      patchMode: "scan",
      offlineAgents: false,
      // respuesta rápida de endpoint (feature 028)
      title: "",
      message: "",
      duration: 30,
      client,
      site,
      agents,
      script,
      timeout: defaultTimeout,
      args: defaultArgs,
      env_vars: defaultEnvVars,
      run_as_user: false,
    });
    const loading = ref(false);
    const collector = ref(false);

    watch(
      () => state.target,
      () => {
        client.value = null;
        site.value = null;
        agents.value = [];
      },
    );

    // Los modos de respuesta rápida aplican a los tres SO. Dejar el default en
    // "windows" acotaría en silencio un mensaje a toda la flota, que es el caso de
    // uso principal, a solo los equipos Windows.
    if (["lock", "alert", "alarm", "stopalarm"].includes(props.mode)) {
      state.osType = "all";
    }

    plat.value = state.osType;

    watch(
      () => state.osType,
      (newValue) => {
        state.custom_shell = null;
        state.run_as_user = false;

        if (newValue === "windows") {
          state.shell = "cmd";
        } else {
          state.shell = "/bin/bash";
        }

        // set plat to filter script options
        if (newValue === "all") plat.value = undefined;
        else plat.value = newValue;
      },
    );

    async function submit() {
      loading.value = true;

      try {
        const data = await runBulkAction(state);
        // Los modos de respuesta rápida devuelven {mode, count} en vez de una
        // frase, justamente para poder traducir el aviso acá. Los modos heredados
        // devuelven texto ya armado por el backend (que todavía no tiene i18n).
        if (data && typeof data === "object" && data.mode) {
          notifySuccess(
            t("endpointResponse.bulkSuccess", { count: data.count }),
          );
        } else {
          notifySuccess(data);
        }
        onDialogHide();
      } catch (e) {}

      loading.value = false;
    }

    const supportsRunAsUser = () => {
      const modes = ["script", "command"];
      return state.osType === "windows" && modes.includes(state.mode);
    };

    // set modal title and caption
    const modalTitle = computed(() => {
      return props.mode === "command"
        ? t("bulkAction.titleCommand")
        : props.mode === "script"
          ? t("bulkAction.titleScript")
          : props.mode === "patch"
            ? t("bulkAction.titlePatch")
            : props.mode === "alert"
              ? t("endpointResponse.bulkTitleAlert")
              : props.mode === "lock"
                ? t("endpointResponse.bulkTitleLock")
                : props.mode === "alarm"
                  ? t("endpointResponse.bulkTitleAlarm")
                  : props.mode === "stopalarm"
                    ? t("endpointResponse.bulkTitleStopAlarm")
                    : "";
    });

    // component lifecycle hooks
    onMounted(() => {
      getAgentOptions();
      getSiteOptions();
      getClientOptions();
      if (props.mode === "script") getScriptOptions();
    });

    return {
      // reactive data
      state,
      agentOptions,
      clientOptions,
      collector,
      customFieldOptions,
      siteOptions,
      filterByPlatformOptions,
      loading,
      shellOptions,
      filteredOsTypeOptions,

      // non-reactive data
      monTypeOptions,
      osTypeOptions,
      targetOptions,
      patchModeOptions,
      runAsUserToolTip,
      envVarsLabel,
      syntax,

      //computed
      modalTitle,

      //methods
      submit,
      cmdPlaceholder,
      supportsRunAsUser,
      openScriptURL,

      // quasar dialog plugin
      dialogRef,
      onDialogHide,
    };
  },
});
</script>
