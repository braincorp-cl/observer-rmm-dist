<template>
  <q-dialog
    ref="dialogRef"
    maximized
    no-esc-dismiss
    @hide="onDialogHide"
    @show="loadEditor"
    @before-hide="unloadEditor"
    @keydown.esc.stop="closeEditor"
  >
    <q-card class="q-dialog-plugin">
      <q-bar>
        <span class="q-pr-sm">{{ title }}</span>
        <q-space />
        <q-btn dense flat icon="close" @click="closeEditor">
          <q-tooltip class="bg-white text-primary">{{
            $t("scriptsCommon.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-banner
        v-if="script.script_body && missingShebang"
        dense
        inline-actions
        class="text-black bg-warning"
      >
        <template v-slot:avatar>
          <q-icon class="text-center" name="warning" color="black" />
        </template>
        <i18n-t
          keypath="scriptFormModal.shebangWarning"
          tag="span"
          scope="global"
        >
          <template #bash
            ><code>{{ $t("scriptFormModal.shebangBash") }}</code></template
          >
          <template #python
            ><code>{{ $t("scriptFormModal.shebangPython") }}</code></template
          >
          <template #br><br /></template>
        </i18n-t>
      </q-banner>
      <div class="row q-pa-sm">
        <q-scroll-area
          :thumb-style="{
            right: '4px',
            borderRadius: '5px',
            width: '5px',
            opacity: '0.75',
          }"
          :bar-style="{
            right: '2px',
            borderRadius: '9px',
            width: '9px',
            opacity: '0.2',
          }"
          class="col-4 q-mb-none q-pb-none"
          :style="{ height: `${$q.screen.height - 106}px` }"
        >
          <div class="q-gutter-sm q-pr-sm">
            <q-btn
              v-if="isNewScript && openAIEnabled"
              class="full-width"
              :disable="loading"
              :label="$t('scriptsCommon.generateScript')"
              icon="auto_awesome"
              color="primary"
              unelevated
              no-caps
              @click="generateScriptOpenAI"
            >
              <q-tooltip>{{ $t("scriptsCommon.generateScriptTip") }}</q-tooltip>
            </q-btn>
            <q-input
              filled
              dense
              :readonly="readonly"
              v-model="script.name"
              :label="$t('scriptsCommon.name')"
              :rules="[(val) => !!val || $t('scriptsCommon.required')]"
              hide-bottom-space
            />
            <q-input
              filled
              dense
              :readonly="readonly"
              v-model="script.description"
              :label="$t('scriptsCommon.description')"
              type="textarea"
              rows="2"
            />
            <q-select
              :readonly="readonly"
              options-dense
              filled
              dense
              v-model="script.shell"
              :options="shellOptions"
              emit-value
              map-options
              :label="$t('scriptsCommon.shellType')"
            />
            <observer-dropdown
              v-model="script.supported_platforms"
              :options="agentPlatformOptions"
              :label="$t('scriptsCommon.supportedPlatforms')"
              clearable
              mapOptions
              filled
              multiple
              :readonly="readonly"
            />
            <observer-dropdown
              filled
              v-model="script.category"
              :options="categories"
              use-input
              clearable
              new-value-mode="add-unique"
              filterable
              :label="$t('scriptsCommon.category')"
              :readonly="readonly"
              hide-bottom-space
            />
            <observer-dropdown
              v-model="script.args"
              :label="$t('scriptFormModal.scriptArgsLabel')"
              filled
              use-input
              multiple
              hide-dropdown-icon
              input-debounce="0"
              new-value-mode="add"
              :readonly="readonly"
            />
            <observer-dropdown
              v-model="script.env_vars"
              :label="envVarsLabel"
              filled
              use-input
              multiple
              hide-dropdown-icon
              input-debounce="0"
              new-value-mode="add"
              :readonly="readonly"
            />
            <q-input
              type="number"
              filled
              dense
              :readonly="readonly"
              v-model.number="script.default_timeout"
              :label="$t('scriptFormModal.timeoutSeconds')"
              :rules="[(val) => val >= 5 || $t('scriptsCommon.minTimeout')]"
              hide-bottom-space
            />
            <q-input
              :label="$t('scriptFormModal.syntax')"
              v-model="script.syntax"
              dense
              filled
              autogrow
              :readonly="readonly"
            />
            <q-checkbox
              v-model="script.run_as_user"
              :label="$t('scriptFormModal.runAsUser')"
            >
              <q-tooltip>{{ $t("scriptFormModal.runAsUserTip") }}</q-tooltip>
            </q-checkbox>
          </div>
        </q-scroll-area>
        <div
          ref="scriptEditor"
          class="col-8 q-mb-none q-pb-none"
          :style="{ height: `${$q.screen.height - 106}px` }"
        ></div>
      </div>
      <q-card-actions>
        <observer-dropdown
          style="width: 550px"
          dense
          :loading="agentLoading"
          filled
          v-model="agent"
          :options="agentOptions"
          :label="$t('scriptFormModal.agentToTest')"
          mapOptions
          filterable
        >
          <template v-slot:after>
            <q-btn
              size="md"
              color="primary"
              dense
              flat
              :label="$t('scriptFormModal.testScript')"
              :disable="
                !agent || !script.script_body || !script.default_timeout
              "
              @click="openTestScriptModal('agent')"
            />
            <q-btn
              v-if="!hosted"
              size="md"
              color="secondary"
              dense
              flat
              :label="$t('scriptFormModal.testOnServer')"
              :disable="
                !script.script_body ||
                !script.default_timeout ||
                !server_scripts_enabled
              "
              @click="openTestScriptModal('server')"
            >
              <q-tooltip
                anchor="top middle"
                self="bottom middle"
                transition-show="fade"
                transition-hide="fade"
              >
                <div>
                  <i18n-t
                    keypath="scriptFormModal.testOnServerTip"
                    tag="span"
                    scope="global"
                  >
                    <template #strong>
                      <strong>{{
                        $t("scriptFormModal.testOnServerTipStrong")
                      }}</strong>
                    </template>
                    <template #em>
                      <em>{{
                        $t("scriptFormModal.testOnServerTipExample")
                      }}</em>
                    </template>
                    <template #br1><br /></template>
                    <template #br2><br /></template>
                  </i18n-t>
                </div>
              </q-tooltip>
            </q-btn>
          </template>
        </observer-dropdown>
        <q-space />
        <q-btn
          dense
          flat
          :label="$t('scriptsCommon.cancel')"
          @click="closeEditor"
        />
        <q-btn
          v-if="!readonly"
          :loading="loading"
          dense
          flat
          :label="$t('scriptsCommon.save')"
          color="primary"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
// composable imports
import { ref, reactive, watch, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";
import { useQuasar, useDialogPluginComponent } from "quasar";
import { saveScript, editScript, downloadScript } from "@/api/scripts";
import { useAgentDropdown, agentPlatformOptions } from "@/composables/agents";
import { generateScript } from "@/api/core";
import { notifyError, notifySuccess } from "@/utils/notify";

// ui imports
import TestScriptModal from "@/components/scripts/TestScriptModal.vue";
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";
import * as monaco from "monaco-editor";

import jsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";
import cssWorker from "monaco-editor/esm/vs/language/css/css.worker?worker";
import htmlWorker from "monaco-editor/esm/vs/language/html/html.worker?worker";
import jsWorker from "monaco-editor/esm/vs/language/typescript/ts.worker?worker";
import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

// https://github.com/microsoft/monaco-editor/issues/4045#issuecomment-1723787448
self.MonacoEnvironment = {
  getWorker: function (workerId, label) {
    switch (label) {
      case "json":
        return new jsonWorker();
      case "css":
      case "scss":
      case "less":
        return new cssWorker();
      case "html":
      case "handlebars":
      case "razor":
        return new htmlWorker();
      case "typescript":
      case "javascript":
        return new jsWorker();
      default:
        return new editorWorker();
    }
  },
};

// types
import type { Script } from "@/types/scripts";

// static data
import { shellOptions } from "@/composables/scripts";
import { envVarsLabel } from "@/constants/constants";

// props
const props = withDefaults(
  defineProps<{
    script?: Script;
    categories?: string[];
    readonly: boolean;
    clone?: boolean;
  }>(),
  {
    clone: false,
    readonly: false,
  },
);

// emits
defineEmits([...useDialogPluginComponent.emits]);

// setup quasar plugins
const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
const $q = useQuasar();

// i18n
const { t } = useI18n();

// setup store
const store = useStore();
const openAIEnabled = computed(() => store.state.openAIIntegrationEnabled);

// El borrador con IA solo aplica al crear un script nuevo. No se puede usar
// `!script` en el template: la const local `script` (más abajo) sombrea al prop
// homónimo y es siempre un objeto reactivo (truthy), así que el botón nunca
// llegaba a renderizarse. El flag se deriva del prop aquí, en el setup.
const isNewScript = !props.script;

// setup agent dropdown
const { agent, agentOptions, getAgentOptions } = useAgentDropdown();
const hosted = computed(() => store.state.hosted);
const server_scripts_enabled = computed(
  () => store.state.server_scripts_enabled,
);

// script form logic
const script: Script = props.script
  ? reactive(Object.assign({}, { ...props.script, script_body: "" }))
  : reactive({
      name: "",
      shell: "powershell",
      default_timeout: 90,
      args: [],
      script_body: "",
      run_as_user: false,
      env_vars: [],
    });

if (props.clone)
  script.name = t("scriptFormModal.copyName", { name: script.name });
const loading = ref(false);
const agentLoading = ref(false);

const missingShebang = computed(() => {
  if (script.shell === "shell" || script.shell === "python") {
    return !script.script_body.startsWith("#!");
  } else {
    return false;
  }
});

const title = computed(() => {
  if (props.script) {
    return props.readonly
      ? t("scriptFormModal.titleViewing", { name: script.name })
      : props.clone
        ? t("scriptFormModal.titleCopying", { name: script.name })
        : t("scriptFormModal.titleEditing", { name: script.name });
  } else {
    return t("scriptFormModal.titleAdding");
  }
});

// convert highlighter language to match what ace expects
const lang = computed(() => {
  switch (script.shell) {
    case "cmd":
      return "bat";
    case "powershell":
      return "powershell";
    case "python":
      return "python";
    case "shell":
    case "nushell":
      return "shell";
    case "deno":
      return "typescript";
    default:
      return "";
  }
});

async function submit() {
  loading.value = true;
  let result = "";
  try {
    // edit existing script
    if (props.script && !props.clone) {
      result = await editScript(script);

      // add or save cloned script
    } else {
      result = await saveScript(script);
    }

    onDialogOK();
    notifySuccess(result);
  } catch (e) {
    console.error(e);
  }

  loading.value = false;
}

function openTestScriptModal(ctx: string) {
  if (ctx === "server" && !script.script_body.startsWith("#!")) {
    notifyError(t("scriptFormModal.shebangRequiredError"), 7000);
    return;
  }
  $q.dialog({
    component: TestScriptModal,
    componentProps: {
      script: { ...script },
      agent: agent.value,
      ctx: ctx,
    },
  });
}

const scriptEditor = ref<HTMLElement | null>(null);
let editor: monaco.editor.IStandaloneCodeEditor;

function loadEditor() {
  var model = monaco.editor.createModel(script.script_body, lang.value);

  const theme = $q.dark.isActive ? "vs-dark" : "vs-light";

  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  editor = monaco.editor.create(scriptEditor.value!, {
    readOnly: props.readonly,
    automaticLayout: true,
    model: model,
    theme: theme,
  });

  editor.onDidChangeModelContent(() => {
    script.script_body = editor.getValue();
  });

  // get code if editing or cloning script
  if (props.script)
    downloadScript(script.id, { with_snippets: props.readonly }).then((r) => {
      script.script_body = r.code;
      editor.setValue(r.code);

      // need to add this in the download function otherwise the above will trigger an edit
      watch(
        () => script.script_body,
        () => {
          edited.value = true;
        },
      );
    });
  else {
    watch(
      () => script.script_body,
      () => {
        edited.value = true;
      },
    );
  }

  // watch for changes in language
  watch(lang, () => {
    monaco.editor.setModelLanguage(model, lang.value);
  });
}

function unloadEditor() {
  editor.getModel()?.dispose();
  editor.dispose();
  onDialogHide();
}

function generateScriptOpenAI() {
  $q.dialog({
    title: t("scriptsCommon.chatGptTitle"),
    prompt: {
      model: t("scriptsCommon.chatGptPrompt", { lang: lang.value }),
      type: "text",
    },
    cancel: true,
    persistent: true,
  }).onOk(async (data) => {
    // La llamada al proveedor puede tardar (timeout de 60 s en el backend):
    // se deshabilita el botón y se muestra el spinner mientras responde.
    loading.value = true;
    $q.loading.show({ message: t("scriptsCommon.generatingScript") });
    try {
      const completion = await generateScript({
        prompt: data,
      });
      script.script_body = completion;
      // El editor Monaco no observa el estado: sin setValue el borrador
      // generado no se ve y se pierde al primer tecleo.
      editor.setValue(completion);
    } catch (e) {
      console.error(e);
    } finally {
      $q.loading.hide();
      loading.value = false;
    }
  });
}

// add are you sure prompt to unsaved script
const edited = ref(false);

function closeEditor() {
  if (edited.value)
    $q.dialog({
      title: t("scriptFormModal.unsavedChanges"),
      cancel: true,
      ok: true,
    }).onOk(async () => {
      unloadEditor();
    });
  else unloadEditor();
}

// component life cycle hooks
onMounted(async () => {
  agentLoading.value = true;
  await getAgentOptions();
  agentLoading.value = false;
});
</script>
