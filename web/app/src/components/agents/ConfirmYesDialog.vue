<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide" persistent>
    <q-card class="q-dialog-plugin" style="min-width: 25vw; max-width: 70vw">
      <q-card-section class="text-h6">{{ title }}</q-card-section>

      <q-card-section>
        <i18n-t keypath="confirmDialog.prompt" tag="span">
          <template #yes>
            <span class="text-negative text-h5">{{ yesWord }}</span>
          </template>
          <template #action>{{ actionVerb }}</template>
          <template #hostname>
            <span class="text-negative text-h5">{{ hostname }}</span>
          </template>
        </i18n-t>
      </q-card-section>

      <q-card-section>
        <q-input
          v-model="model"
          autofocus
          :label="$t('confirmDialog.typeYes')"
          :rules="[(val) => (val || '').toLowerCase() === yesWord]"
        />
      </q-card-section>

      <q-card-actions align="right">
        <q-btn
          flat
          :label="$t('confirmDialog.cancel')"
          @click="onDialogCancel"
        />
        <q-btn
          :color="okColor"
          :label="okLabel"
          :disable="(model || '').toLowerCase() !== 'yes'"
          @click="onDialogOK()"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref } from "vue";
import { useDialogPluginComponent } from "quasar";

defineProps({
  hostname: { type: String, required: true },
  actionVerb: { type: String, required: true },
  title: { type: String, default: "Confirm action" },
  okLabel: { type: String, default: "Confirm" },
  okColor: { type: String, default: "negative" },
});

defineEmits([...useDialogPluginComponent.emits]);

const model = ref("");

// palabra literal de confirmación: se escribe igual en todos los idiomas
// (la regla de validación la compara tal cual); no es texto traducible.
const yesWord = "yes";

const { dialogRef, onDialogHide, onDialogOK, onDialogCancel } =
  useDialogPluginComponent();
</script>
