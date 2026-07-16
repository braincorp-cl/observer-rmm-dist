<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="width: 400px">
      <q-bar>
        {{ title }}
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip class="bg-white text-primary">{{
            $t("reporting.common.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section v-if="reportTemplates.length === 0">
        {{ $t("reporting.runDialog.noTemplates", { type: typeLabel }) }}
      </q-card-section>
      <div v-else>
        <q-card-section>
          <observer-dropdown
            v-model="reportTemplate"
            :options="reportTemplateOptions"
            :label="$t('reporting.runDialog.reportTemplateLabel')"
            outlined
            mapOptions
            filterable
          />
        </q-card-section>

        <q-card-section>
          <q-option-group
            v-model="reportFormat"
            :options="reportFormatOptions"
            inline
          />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn
            v-close-popup
            dense
            flat
            :label="$t('reporting.common.cancel')"
          />
          <q-btn
            :loading="isLoading"
            :disable="!reportTemplate"
            dense
            flat
            :label="$t('reporting.runDialog.runReport')"
            color="primary"
            @click="submit"
          />
        </q-card-actions>
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
// composition imports
import { ref, computed, onBeforeMount } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import { useSharedReportTemplates } from "../api/reporting";
import { notifyError } from "@/utils/notify";

// ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

// types
import { type ReportFormat } from "../types/reporting";

// emits
defineEmits([...useDialogPluginComponent.emits]);

// props
const props = defineProps<{
  id: string | number;
  type: "client" | "site" | "agent";
  download: boolean;
}>();

// i18n setup
const { t } = useI18n();

// quasar dialog setup
const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();

// i18n-aware title/type label (computed for language reactivity)
const typeLabel = computed(() => t(`reporting.runDialog.type_${props.type}`));

const title = computed(() =>
  props.download
    ? t("reporting.runDialog.titleDownload", { type: typeLabel.value })
    : t("reporting.runDialog.titleRun", { type: typeLabel.value }),
);

const {
  reportTemplates,
  isLoading,
  getReportTemplates,
  openReport,
  downloadReport,
} = useSharedReportTemplates;

// run report logic
const reportTemplate = ref<number | null>(null);
const reportFormat = ref<ReportFormat>("pdf");

const reportTemplateOptions = computed(() =>
  reportTemplates.value.map((template) => ({
    label: template.name,
    value: template.id,
  })),
);

const selectedTemplate = computed(() => {
  return reportTemplates.value.find(
    (template) => template.id === reportTemplate.value,
  );
});

const reportFormatOptions = computed(() => {
  if (selectedTemplate.value) {
    if (selectedTemplate.value.type !== "plaintext")
      return [
        { label: "PDF", value: "pdf" },
        { label: "HTML", value: "html" },
      ];
    else
      return [
        { label: "PDF", value: "pdf" },
        { label: t("reporting.runDialog.formatText"), value: "plaintext" },
      ];
  } else return [];
});

async function submit() {
  if (reportTemplate.value === null) {
    notifyError(t("reporting.runDialog.errorRequired"));
    return;
  }

  if (selectedTemplate.value && selectedTemplate.value.depends_on) {
    if (!props.download)
      openReport(
        reportTemplate.value,
        reportFormat.value,
        selectedTemplate.value.depends_on,
        {
          [props.type]: props.id,
        },
      );
    else
      downloadReport(selectedTemplate.value, reportFormat.value, {
        [props.type]: props.id,
      });
  }

  onDialogOK();
}

onBeforeMount(() => getReportTemplates([props.type]));
</script>
