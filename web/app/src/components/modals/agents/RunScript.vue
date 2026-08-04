<template>
  <q-dialog
    ref="dialogRef"
    @hide="onDialogHide"
    persistent
    @keydown.esc="onDialogHide"
    :maximized="maximized"
  >
    <q-card class="dialog-plugin" style="min-width: 60vw">
      <q-bar>
        {{ $t("runScript.title", { hostname: agent.hostname }) }}
        <q-space />
        <q-btn
          dense
          flat
          icon="minimize"
          @click="maximized = false"
          :disable="!maximized"
        >
          <q-tooltip v-if="maximized" class="bg-white text-primary">{{
            $t("runScript.minimize")
          }}</q-tooltip>
        </q-btn>
        <q-btn
          dense
          flat
          icon="crop_square"
          @click="maximized = true"
          :disable="maximized"
        >
          <q-tooltip v-if="!maximized" class="bg-white text-primary">{{
            $t("runScript.maximize")
          }}</q-tooltip>
        </q-btn>
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("runScript.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-form @submit.prevent="sendScript">
        <q-card-section>
          <observer-dropdown
            :rules="[(val: number) => !!val || $t('runScript.required')]"
            v-model="state.script"
            :options="filterByPlatformOptions"
            :label="$t('runScript.selectScript')"
            outlined
            mapOptions
            filterable
          >
            <template v-slot:after>
              <q-btn size="sm" round dense flat icon="info">
                <q-tooltip
                  v-if="syntax"
                  class="bg-white text-primary text-body1"
                  >{{ syntax }}</q-tooltip
                >
              </q-btn>
            </template>
          </observer-dropdown>
        </q-card-section>
        <q-card-section>
          <observer-dropdown
            v-model="state.args"
            :label="$t('runScript.scriptArgs')"
            filled
            use-input
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add"
          />
        </q-card-section>
        <q-card-section>
          <observer-dropdown
            v-model="state.env_vars"
            :label="$t('scriptsCommon.envVarsLabel')"
            filled
            use-input
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add"
          />
        </q-card-section>
        <q-card-section v-if="!state.run_on_server">
          <q-option-group
            v-model="state.output"
            :options="outputOptions"
            color="primary"
            inline
            dense
          />
        </q-card-section>
        <q-card-section v-if="state.output === 'email'">
          <div class="q-gutter-sm">
            <q-radio
              dense
              v-model="state.emailMode"
              val="default"
              :label="$t('runScript.emailGlobal')"
            />
            <q-radio
              dense
              v-model="state.emailMode"
              val="custom"
              :label="$t('runScript.emailCustom')"
            />
          </div>
        </q-card-section>
        <q-card-section
          v-if="state.emailMode === 'custom' && state.output === 'email'"
        >
          <observer-dropdown
            v-model="state.emails"
            :label="$t('runScript.emailRecipients')"
            filled
            use-input
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add"
          />
        </q-card-section>
        <q-card-section v-if="state.output === 'collector'">
          <observer-dropdown
            :rules="[(val: number) => !!val || $t('runScript.required')]"
            outlined
            v-model="state.custom_field"
            :options="customFieldOptions"
            :label="$t('runScript.selectCustomField')"
            mapOptions
            filterable
          />
          <q-checkbox
            v-model="state.save_all_output"
            :label="$t('runScript.saveAllOutput')"
          />
        </q-card-section>
        <q-card-section>
          <q-checkbox
            v-if="agent.plat === 'windows' && !state.run_on_server"
            v-model="state.run_as_user"
            :label="$t('runScript.runAsUser')"
          >
            <q-tooltip>{{ $t('scriptsCommon.runAsUserTip') }}</q-tooltip>
          </q-checkbox>
          <q-checkbox
            v-if="!hosted"
            :disable="!server_scripts_enabled"
            v-model="state.run_on_server"
            :label="$t('runScript.runOnServer')"
            @update:model-value="ret = null"
          >
            <q-tooltip v-if="!server_scripts_enabled">{{
              $t("runScript.runOnServerDisabledTip")
            }}</q-tooltip>
            <q-tooltip v-else>{{ $t("runScript.runOnServerTip") }}</q-tooltip>
          </q-checkbox>
        </q-card-section>
        <q-card-section>
          <q-input
            v-model.number="state.timeout"
            dense
            outlined
            type="number"
            style="max-width: 150px"
            :label="$t('runScript.timeoutSeconds')"
            stack-label
            :rules="[
              (val) => !!val || $t('runScript.required'),
              (val) => val >= 5 || $t('runScript.minTimeout', { min: 5 }),
            ]"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn :label="$t('runScript.cancel')" v-close-popup />
          <q-btn
            :loading="loading"
            :disabled="loading"
            :label="$t('runScript.run')"
            color="primary"
            type="submit"
          />
        </q-card-actions>
        <q-card-section
          v-if="ret !== null"
          class="q-pl-md q-pr-md q-pt-none q-ma-none scroll"
          style="max-height: 50vh"
        >
          <script-output-copy-clip
            v-if="!state.run_on_server"
            :label="$t('runScript.output')"
            :data="ret"
          />
          <q-separator />
          <pre v-if="!state.run_on_server">{{ ret }}</pre>
          <q-card-section v-if="state.run_on_server" class="scroll">
            <div>
              {{ $t("runScript.runTime") }}
              <code
                >{{ ret.execution_time }} {{ $t("runScript.seconds") }}</code
              >
              <br />{{ $t("runScript.returnCode") }}
              <code>{{ ret.retcode }}</code>
              <br />
            </div>
            <br />
            <div v-if="ret.stdout">
              <script-output-copy-clip
                :label="$t('runScript.standardOutput')"
                :data="ret.stdout"
              />
              <q-separator />
              <pre>{{ ret.stdout }}</pre>
            </div>
            <div v-if="ret.stderr">
              <script-output-copy-clip
                :label="$t('runScript.standardError')"
                :data="ret.stderr"
              />
              <q-separator />
              <pre>{{ ret.stderr }}</pre>
            </div>
          </q-card-section>
        </q-card-section>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
// composition imports
import { computed, ref, watch } from "vue";
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import { useScriptDropdown } from "@/composables/scripts";
import { useCustomFieldDropdown } from "@/composables/core";
import { runScript } from "@/api/agents";
import { notifySuccess } from "@/utils/notify";

//ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";
import ScriptOutputCopyClip from "@/components/scripts/ScriptOutputCopyClip.vue";

// types
import type { Agent } from "@/types/agents";

// i18n
const { t } = useI18n();

// store
const store = useStore();
const hosted = computed(() => store.state.hosted);
const server_scripts_enabled = computed(
  () => store.state.server_scripts_enabled,
);

// static data
const outputOptions = computed(() => [
  { label: t("runScript.outputWait"), value: "wait" },
  { label: t("runScript.outputForget"), value: "forget" },
  { label: t("runScript.outputEmail"), value: "email" },
  { label: t("runScript.outputCollector"), value: "collector" },
  { label: t("runScript.outputNote"), value: "note" },
]);

// emits
defineEmits([...useDialogPluginComponent.emits]);

// props
const props = defineProps<{
  agent: Agent;
  script?: number;
}>();

// setup quasar dialog plugin
const { dialogRef, onDialogHide } = useDialogPluginComponent();

// setup dropdowns
const {
  script,
  filterByPlatformOptions,
  defaultTimeout,
  defaultArgs,
  defaultEnvVars,
  syntax,
} = useScriptDropdown({
  script: props.script,
  plat: props.agent.plat,
  onMount: true,
});
const { customFieldOptions } = useCustomFieldDropdown({ onMount: true });

// main run script functionaity
const state = ref({
  output: "wait",
  emails: [],
  emailMode: "default",
  custom_field: null,
  save_all_output: false,
  script,
  args: defaultArgs,
  env_vars: defaultEnvVars,
  timeout: defaultTimeout,
  run_as_user: false,
  run_on_server: false,
});

const ret = ref(null);
const loading = ref(false);
const maximized = ref(false);

async function sendScript() {
  ret.value = null;
  loading.value = true;

  ret.value = await runScript(props.agent.agent_id, state.value);
  loading.value = false;
  if (state.value.output === "forget") {
    onDialogHide();
    if (ret.value) notifySuccess(ret.value);
  }
}

// watchers
watch(
  [() => state.value.output, () => state.value.emailMode],
  () => (state.value.emails = []),
);
</script>
