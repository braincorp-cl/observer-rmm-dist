<template>
  <div>
    <q-inner-loading
      :showing="isLoading"
      :label='$t("reporting.common.pleaseWait")'
      label-style="font-size: 1.1em"
      color="primary"
    />
    <!-- 050 (T045, G02): el lienzo del reporte es papel y sale del token
         --obs-paper, igual en ambos temas; el documento no se re-tematiza. -->
    <iframe
      :srcdoc="$route.query.format !== 'pdf' ? reportData : undefined"
      :src="$route.query.format === 'pdf' ? reportData : undefined"
      :title="$t('reporting.common.reportContent')"
      :style="{
        'max-height': `${$q.screen.height}px`,
        'min-height': `${$q.screen.height}px`,
        'min-width': '100%',
        'background-color': 'var(--obs-paper)',
      }"
      id="report-iframe"
    ></iframe>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import { useQuasar } from "quasar";
import { useSharedReportHistory } from "../api/reporting";

// type
import type { ReportFormat } from "../types/reporting";

// props
const props = defineProps<{
  id: number;
  format: ReportFormat;
}>();

// setup vue router
const $route = useRoute();

// setup quasar
const $q = useQuasar();

// logic
const { reportData, runReportHistory, isLoading } = useSharedReportHistory;

// Feature 004 — revocar Object URL blob al desmontar para evitar memory leak (Q-REP-07)
onBeforeUnmount(() => {
  if (reportData.value?.startsWith("blob:")) {
    URL.revokeObjectURL(reportData.value);
  }
});

runReportHistory(props.id, props.format);
</script>
