<template>
  <q-dialog
    ref="dialogRef"
    :persistent="hasText"
    @hide="onDialogHide"
    @keydown.esc.stop="onEsc"
  >
    <q-card class="ai-prompt-card">
      <q-card-section class="row items-center no-wrap q-pb-sm">
        <q-avatar
          color="primary"
          text-color="white"
          icon="auto_awesome"
          size="34px"
        />
        <div class="col q-ml-md">
          <div class="text-subtitle1 text-weight-medium">
            {{ $t("aiScriptPrompt.title") }}
          </div>
          <div class="text-caption text-grey-6">
            {{ $t("aiScriptPrompt.subtitle") }}
          </div>
        </div>
        <q-chip square dense outline color="primary" :label="shellLabel" />
      </q-card-section>

      <q-card-section class="q-pt-none">
        <!-- El prefijo se muestra como entrada de la frase: el operador escribe
             la continuación, no un enunciado suelto. Es el MISMO texto que se
             antepone al enviar, así que no hay dos redacciones que mantener. -->
        <div class="text-body2 text-weight-medium q-mb-sm">
          {{ lead }}
        </div>
        <q-input
          v-model="promptText"
          type="textarea"
          filled
          autofocus
          autogrow
          counter
          maxlength="2000"
          input-class="ai-prompt-textarea"
          :placeholder="$t('aiScriptPrompt.placeholder')"
          @keydown.ctrl.enter.prevent="submit"
          @keydown.meta.enter.prevent="submit"
        />

        <div class="row items-center q-gutter-xs q-mt-sm">
          <span class="text-caption text-grey-6 q-mr-xs">
            {{ $t("aiScriptPrompt.examplesLabel") }}
          </span>
          <q-chip
            v-for="example in examples"
            :key="example"
            clickable
            dense
            outline
            color="primary"
            :label="example"
            @click="applyExample(example)"
          />
        </div>
      </q-card-section>

      <q-card-section class="q-py-none">
        <div class="text-caption text-grey-6">
          {{ $t("aiScriptPrompt.hint") }}
        </div>
      </q-card-section>

      <q-card-actions align="right" class="q-px-md q-pb-md q-pt-md">
        <q-btn
          flat
          no-caps
          :label="$t('scriptsCommon.cancel')"
          @click="onDialogCancel"
        />
        <q-btn
          unelevated
          no-caps
          color="primary"
          icon="auto_awesome"
          :disable="!hasText"
          :label="$t('aiScriptPrompt.submit')"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";

import { shellOptions } from "@/composables/scripts";

const props = defineProps<{
  // valor de `script.shell` (powershell / cmd / python / shell / nushell / deno)
  shell: string;
}>();

defineEmits([...useDialogPluginComponent.emits]);

const { dialogRef, onDialogHide, onDialogOK, onDialogCancel } =
  useDialogPluginComponent();

const { t } = useI18n();

const promptText = ref("");
const hasText = computed(() => !!promptText.value.trim());

// Se muestra el nombre del shell tal como aparece en el selector del formulario
// ("Batch", no "bat"): es lo que el operador acaba de elegir y también lo que
// entiende el modelo.
const shellLabel = computed(
  () =>
    shellOptions.find((option) => option.value === props.shell)?.label ??
    props.shell,
);

const prefix = computed(() =>
  t("scriptsCommon.chatGptPrompt", { lang: shellLabel.value }),
);
const lead = computed(() => `${prefix.value.trim()}…`);

const examples = computed(() => [
  t("aiScriptPrompt.example1"),
  t("aiScriptPrompt.example2"),
  t("aiScriptPrompt.example3"),
]);

function applyExample(example: string) {
  promptText.value = example;
}

// Con texto escrito el diálogo es `persistent`, así que Esc no lo cierra solo;
// se atiende aquí para que igual cancele de forma explícita y no quede la
// sensación de que la tecla no hace nada.
function onEsc() {
  onDialogCancel();
}

function submit() {
  if (!hasText.value) return;
  onDialogOK(`${prefix.value}${promptText.value.trim()}`);
}
</script>

<style scoped>
.ai-prompt-card {
  width: 760px;
  max-width: 92vw;
}

/* El motivo de todo esto: el prompt tiene que verse completo mientras se
   escribe. `autogrow` crece hasta el tope y desde ahí hace scroll interno. */
:deep(.ai-prompt-textarea) {
  min-height: 180px;
  max-height: 42vh;
  line-height: 1.5;
}
</style>
