<template>
  <div>
    <q-inner-loading
      :showing="isLoading"
      label="Please wait..."
      label-class="text-teal"
      label-style="font-size: 1.1em"
    />
    <iframe
      :srcdoc="$route.query.format !== 'pdf' ? reportData : undefined"
      :src="$route.query.format === 'pdf' ? reportData : undefined"
      :style="{
        'max-height': `${$q.screen.height}px`,
        'min-height': `${$q.screen.height}px`,
        'min-width': '100%',
        'background-color': 'white',
      }"
      id="report-iframe"
    ></iframe>
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import { useQuasar } from "quasar";
import { useReportTemplates } from "../api/reporting";

// ui imports
import ReportDependencyPrompt from "../components/ReportDependencyPrompt.vue";

// type
import type { ReportFormat, ReportDependencies } from "../types/reporting";

// props
const props = defineProps<{
  id: number;
  format: ReportFormat;
  dependencies?: ReportDependencies;
  dependsOn?: string[];
}>();

// setup vue router
const $route = useRoute();

// setup quasar
const $q = useQuasar();

// logic
const dependsOn = props.dependsOn || [];
const dependencies = ref(Object.assign({}, props.dependencies));

const { reportData, isLoading, runReport, openReport } = useReportTemplates();

// Feature 004 — revocar Object URL blob al desmontar para evitar memory leak (Q-REP-07)
onBeforeUnmount(() => {
  if (reportData.value?.startsWith("blob:")) {
    URL.revokeObjectURL(reportData.value);
  }
});

const needsPrompt = dependsOn.filter((dep) => !dependencies.value[dep]);

if (needsPrompt.length > 0) {
  // WI-DECISION-01 / Q-REP-01 fix: ejecutar solo si el usuario confirma
  // (onDismiss disparaba doble ejecución openReport+runReport al cancelar)
  $q.dialog({
    component: ReportDependencyPrompt,
    componentProps: { dependsOn: needsPrompt },
  }).onOk((deps) => {
    dependencies.value = { ...dependencies.value, ...deps };
    openReport(props.id, props.format, dependsOn, dependencies.value, false);
    runReport(props.id, {
      format: props.format,
      dependencies: dependencies.value,
    });
  });
} else {
  runReport(props.id, {
    format: props.format,
    dependencies: dependencies.value,
  });
}
</script>
