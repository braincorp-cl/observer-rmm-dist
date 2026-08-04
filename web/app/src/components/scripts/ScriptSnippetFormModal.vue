<template>
  <q-dialog
    ref="dialogRef"
    maximized
    @hide="onDialogHide"
    @show="loadEditor"
    @before-hide="unloadEditor"
  >
    <q-card class="q-dialog-plugin">
      <q-bar>
        <span class="q-pr-sm">{{ title }}</span>
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("scriptsCommon.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <div v-if="isNewSnippet && openAIEnabled" class="q-px-sm q-pt-sm">
        <q-btn
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
      </div>
      <div class="row">
        <q-input
          :rules="[(val: string) => !!val || $t('scriptsCommon.required')]"
          class="q-pa-sm col-4"
          v-model="snippet.name"
          :label="$t('scriptsCommon.name')"
          filled
          dense
        />
        <q-select
          v-model="snippet.shell"
          :options="shellOptions"
          class="q-pa-sm col-2"
          :label="$t('scriptsCommon.shellType')"
          options-dense
          filled
          dense
          emit-value
          map-options
        />
        <q-input
          class="q-pa-sm col-6"
          filled
          dense
          v-model="snippet.desc"
          :label="$t('scriptsCommon.description')"
        />
      </div>

      <div
        ref="snippetEditor"
        :style="{ height: `${$q.screen.height - editorOffset}px` }"
      ></div>

      <q-card-actions align="right">
        <q-btn dense flat :label="$t('scriptsCommon.cancel')" v-close-popup />
        <q-btn
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
import { ref, watch, reactive, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";
import { useQuasar } from "quasar";
import { generateScript } from "@/api/core";
import { useDialogPluginComponent } from "quasar";
import { saveScriptSnippet, editScriptSnippet } from "@/api/scripts";
import { notifySuccess } from "@/utils/notify";

// ui imports
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
import type { ScriptSnippet } from "@/types/scripts";

// static data
import { shellOptions, useAiDraftLoader } from "@/composables/scripts";

// ui imports
import AiScriptPromptModal from "@/components/scripts/AiScriptPromptModal.vue";

// props
const props = defineProps<{ snippet?: ScriptSnippet }>();

// emits
defineEmits([...useDialogPluginComponent.emits]);

// quasar dialog setup
const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();

// setup quasar
const $q = useQuasar();

// i18n
const { t } = useI18n();

// setup store
const store = useStore();
const openAIEnabled = computed(() => store.state.openAIIntegrationEnabled);

// Mismo caso que en ScriptFormModal: la const local `snippet` sombrea al prop
// homónimo en el template y siempre es truthy, así que `!snippet` dejaba el
// botón invisible para siempre. El flag se deriva del prop aquí.
const isNewSnippet = !props.snippet;

// El botón de borrador con IA ocupa una fila propia sobre el editor: se le
// descuenta su alto para que Monaco no desborde el diálogo.
const editorOffset = computed(() =>
  isNewSnippet && openAIEnabled.value ? 184 : 132,
);

// snippet form logic
const snippet: ScriptSnippet = props.snippet
  ? reactive(Object.assign({}, props.snippet))
  : reactive({ name: "", code: "", shell: "powershell" });
const loading = ref(false);
const aiDraftLoader = useAiDraftLoader();

const title = computed(() => {
  if (props.snippet) {
    return t("scriptSnippetForm.titleEditing", { name: snippet.name });
  } else {
    return t("scriptSnippetForm.titleAdding");
  }
});

// convert highlighter language to match what ace expects
const lang = computed(() => {
  switch (snippet.shell) {
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
  try {
    const result = props.snippet
      ? await editScriptSnippet(snippet)
      : await saveScriptSnippet(snippet);
    onDialogOK();
    notifySuccess(result);
  } catch (e) {
    console.error(e);
  }

  loading.value = false;
}

const snippetEditor = ref<HTMLElement | null>(null);
let editor: monaco.editor.IStandaloneCodeEditor;

function loadEditor() {
  var model = monaco.editor.createModel(snippet.code, lang.value);

  const theme = $q.dark.isActive ? "vs-dark" : "vs-light";

  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  editor = monaco.editor.create(snippetEditor.value!, {
    automaticLayout: true,
    model: model,
    theme: theme,
  });

  editor.onDidChangeModelContent(() => {
    snippet.code = editor.getValue();
  });

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
    component: AiScriptPromptModal,
    componentProps: { shell: snippet.shell },
  }).onOk(async (prompt: string) => {
    // La llamada al proveedor puede tardar (timeout de 120 s en el backend).
    loading.value = true;
    aiDraftLoader.start();
    try {
      const completion = await generateScript({
        prompt: prompt,
      });
      snippet.code = completion;
      // Sin setValue el borrador no se ve en el editor y se pierde al teclear.
      editor.setValue(completion);
    } catch (e) {
      console.error(e);
    } finally {
      aiDraftLoader.stop();
      loading.value = false;
    }
  });
}
</script>
