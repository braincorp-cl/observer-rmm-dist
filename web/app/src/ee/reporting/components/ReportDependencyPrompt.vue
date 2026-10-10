<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="width: 400px">
      <q-bar>
        {{ $t("reporting.dependencyPrompt.title") }}
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip class="bg-white text-primary">{{
            $t("reporting.common.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section v-for="label in dependsOn" :key="label" class="q-pb-none">
        <observer-dropdown
          v-if="field(label) === 'client'"
          v-model="dependencies[label]"
          :label="controlLabel(label)"
          :options="clientOptions"
          outlined
          mapOptions
          filterable
          :clearable="isOptional(label)"
        />

        <observer-dropdown
          v-else-if="field(label) === 'site'"
          v-model="dependencies[label]"
          :label="controlLabel(label)"
          :options="siteOptions"
          outlined
          mapOptions
          filterable
          :clearable="isOptional(label)"
        />

        <!-- "agent" (legado): emite el id del equipo. "equipo": emite el hostname,
             que es lo que cruzan los filtros de los reportes de actividad. -->
        <observer-dropdown
          v-else-if="field(label) === 'agent'"
          v-model="dependencies[label]"
          :label="controlLabel(label)"
          :options="agentOptions"
          outlined
          mapOptions
          filterable
          :clearable="isOptional(label)"
        />

        <observer-dropdown
          v-else-if="field(label) === 'equipo'"
          v-model="dependencies[label]"
          :label="controlLabel(label)"
          :options="agentOptions"
          outlined
          filterable
          :clearable="isOptional(label)"
        />

        <q-input
          v-else-if="isDate(label)"
          v-model="dependencies[label]"
          type="date"
          :label="controlLabel(label)"
          outlined
          dense
          stack-label
          :clearable="isOptional(label)"
        />

        <q-input
          v-else
          v-model="dependencies[label]"
          :label="controlLabel(label)"
          outlined
          dense
          :clearable="isOptional(label)"
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
          :loading="loading"
          dense
          flat
          :label="$t('reporting.dependencyPrompt.submit')"
          color="primary"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onBeforeMount } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import { notifyError } from "@/utils/notify";
import { capitalize } from "@/utils/format";
import { useAgentDropdown } from "@/composables/agents";
import { useClientDropdown, useSiteDropdown } from "@/composables/clients";

// ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";
import { ReportDependencies } from "../types/reporting";

// emits
defineEmits([...useDialogPluginComponent.emits]);

// props
const props = defineProps<{
  dependsOn: string[];
  values?: ReportDependencies;
}>();

// i18n setup
const { t } = useI18n();

// quasar dialog setup
const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();

// setup dropdown options
const { agentOptions, getAgentOptions } = useAgentDropdown();
const { clientOptions, getClientOptions } = useClientDropdown();
const { siteOptions, getSiteOptions } = useSiteDropdown();

// Una dependencia que empieza con "_" es OPCIONAL: puede quedar vacia (= sin
// filtrar) y la plantilla la lee con `| default('')`. Asi un reporte puede pedir
// Cliente y Fecha obligatorios y, ademas, acotar por Equipo o Usuario sin volver
// esos campos obligatorios. El backend no mapea "_equipo"/"_usuario" a modelos
// (solo client/site/agent), asi que llegan como texto al contexto de la plantilla.
function isOptional(label: string) {
  return label.startsWith("_");
}

// Nombre base (sin el "_" de opcional) para decidir el tipo de control.
function field(label: string) {
  return (isOptional(label) ? label.slice(1) : label).toLowerCase();
}

// Los campos de fecha se muestran con un selector de calendario (input date
// nativo), que devuelve el formato AAAA-MM-DD que esperan los filtros.
const DATE_FIELDS = ["fecha", "desde", "hasta", "date", "from", "to"];
function isDate(label: string) {
  return DATE_FIELDS.includes(field(label));
}

function controlLabel(label: string) {
  const base = capitalize(field(label));
  return isOptional(label) ? `${base} (${t("reporting.dependencyPrompt.optional")})` : base;
}

// logic
const dependencies = props.values
  ? reactive(props.values)
  : reactive<{ [x: string]: string | number | null }>({});

props.dependsOn.forEach((dep) => {
  if (!dependencies[dep]) dependencies[dep] = null;
});

const loading = ref(false);

function validate() {
  let valid = true;
  props.dependsOn.forEach((dep) => {
    // Las opcionales ("_...") pueden quedar vacias.
    if (!isOptional(dep) && !dependencies[dep]) valid = false;
  });

  return valid;
}

function submit() {
  if (!validate()) {
    notifyError(t("reporting.dependencyPrompt.errorAllFields"));
    return;
  }
  // Las opcionales vacias viajan como "" (no null): el backend las inyecta en el
  // contexto de la plantilla, donde `| default('')` las trata como "sin filtro".
  props.dependsOn.forEach((dep) => {
    if (isOptional(dep) && !dependencies[dep]) dependencies[dep] = "";
  });
  onDialogOK(dependencies);
}

onBeforeMount(() => {
  if (props.dependsOn.some((d) => field(d) === "client")) {
    getClientOptions();
  }

  if (props.dependsOn.some((d) => field(d) === "site")) {
    getSiteOptions();
  }

  // "equipo" necesita hostnames planos (el filtro cruza por hostname); "agent"
  // (legado) usa las opciones con id. Si el reporte pide "equipo", cargamos planas.
  if (props.dependsOn.some((d) => field(d) === "equipo")) {
    getAgentOptions(true);
  } else if (props.dependsOn.some((d) => field(d) === "agent")) {
    getAgentOptions();
  }
});
</script>
