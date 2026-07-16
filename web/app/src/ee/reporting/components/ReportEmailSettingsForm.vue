<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide" persistent>
    <q-card class="q-dialog-plugin" style="width: 90vw; max-width: 600px">
      <q-bar>
        {{ $t("reporting.emailSettings.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup />
      </q-bar>

      <q-card-section class="q-pa-md">
        <q-input
          v-model="localEmailSettings.subject"
          :label="$t('reporting.emailSettings.subjectLabel')"
          dense
          filled
          :hint="$t('reporting.emailSettings.subjectHint')"
        />
      </q-card-section>

      <q-card-section class="q-pa-md">
        <q-input
          v-model="localEmailSettings.body"
          type="textarea"
          :label="$t('reporting.emailSettings.bodyLabel')"
          dense
          filled
          :hint="$t('reporting.emailSettings.bodyHint')"
        />
      </q-card-section>

      <q-card-section class="q-pa-md">
        <q-input
          v-model="localEmailSettings.attachment_name"
          :label="$t('reporting.emailSettings.attachmentNameLabel')"
          dense
          filled
          :hint="$t('reporting.emailSettings.attachmentNameHint')"
        />
      </q-card-section>

      <q-card-section
        v-if="props.format === 'plaintext'"
        class="q-pa-md"
        style="padding-top: 0"
      >
        <q-input
          v-model="localEmailSettings.attachment_extension"
          :label="$t('reporting.emailSettings.attachmentExtensionLabel')"
          dense
          filled
          prefix="."
          :hint="$t('reporting.emailSettings.attachmentExtensionHint')"
        />
      </q-card-section>

      <q-card-section v-if="props.format === 'html'" class="q-pa-md">
        <q-checkbox
          v-model="localEmailSettings.include_report_link"
          :label="$t('reporting.emailSettings.includeReportLinkLabel')"
        >
          <q-tooltip class="text-caption">
            {{ $t("reporting.emailSettings.includeReportLinkTooltip") }}
          </q-tooltip>
        </q-checkbox>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat :label="$t('reporting.common.cancel')" v-close-popup dense />
        <q-btn
          flat
          :label="$t('reporting.common.save')"
          color="primary"
          class="q-ml-sm"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script lang="ts" setup>
import { reactive } from "vue";
import { useDialogPluginComponent, extend } from "quasar";

import { EmailSettings, ReportFormat } from "../types/reporting";

const props = defineProps<{
  emailSettings: EmailSettings;
  format: ReportFormat;
}>();

const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
defineEmits(useDialogPluginComponent.emits);

const localEmailSettings = reactive<EmailSettings>(
  props.emailSettings
    ? extend({}, props.emailSettings)
    : {
        subject: "",
        body: "",
        attachment_name: "",
        attachment_extension: "",
        include_report_link: false,
      },
);

async function submit() {
  onDialogOK(localEmailSettings);
}
</script>
