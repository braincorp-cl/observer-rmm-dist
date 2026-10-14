<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="dialog-plugin" style="min-width: 30vw">
      <q-bar>
        {{ $t("activityMonitoring.title", { name }) }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup />
      </q-bar>
      <q-card-section v-if="loaded && !globalEnabled" class="q-pb-none">
        <q-banner dense class="bg-orange-2 text-black">
          <template v-slot:avatar>
            <q-icon name="warning" />
          </template>
          {{ $t("activityMonitoring.globalOff") }}
        </q-banner>
      </q-card-section>
      <q-card-section>
        <q-option-group v-model="value" :options="opciones" type="radio" />
        <div class="text-caption text-grey q-mt-sm">
          {{ $t("activityMonitoring.hint") }}
        </div>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn dense flat :label="$t('activityMonitoring.cancel')" v-close-popup />
        <q-btn
          dense
          flat
          color="primary"
          :loading="loading"
          :disable="!loaded"
          :label="$t('activityMonitoring.save')"
          @click="guardar"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 049-B2: encender/apagar el monitoreo de actividad de un cliente, sitio
// o equipo. Tri-estado: heredar (null) / encender / apagar.
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent } from "quasar";
import {
  fetchActivityMonitoring,
  saveActivityMonitoring,
} from "@/api/agents";

export default {
  name: "ActivityMonitoringDialog",
  emits: [...useDialogPluginComponent.emits],
  props: {
    level: { type: String, required: true },
    id: { type: [String, Number], required: true },
    name: { type: String, default: "" },
  },
  setup(props) {
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
    const $q = useQuasar();
    const { t } = useI18n();

    // q-option-group no admite null como valor: se mapea a "inherit".
    const value = ref("inherit");
    const globalEnabled = ref(false);
    const loaded = ref(false);
    const loading = ref(false);

    const opciones = computed(() => [
      {
        label:
          props.level === "client"
            ? t("activityMonitoring.notDecided")
            : t("activityMonitoring.inherit"),
        value: "inherit",
      },
      { label: t("activityMonitoring.on"), value: "on" },
      { label: t("activityMonitoring.off"), value: "off" },
    ]);

    onMounted(async () => {
      try {
        const data = await fetchActivityMonitoring(props.level, props.id);
        value.value =
          data.value === true ? "on" : data.value === false ? "off" : "inherit";
        globalEnabled.value = data.global_enabled;
        loaded.value = true;
      } catch (e) {
        onDialogHide();
      }
    });

    async function guardar() {
      loading.value = true;
      const v = value.value === "on" ? true : value.value === "off" ? false : null;
      try {
        await saveActivityMonitoring(props.level, props.id, v);
        $q.notify({ type: "positive", message: t("activityMonitoring.saved") });
        onDialogOK(v);
      } catch (e) {
        // el interceptor de axios ya notifica el error
      }
      loading.value = false;
    }

    return {
      dialogRef,
      onDialogHide,
      value,
      opciones,
      globalEnabled,
      loaded,
      loading,
      guardar,
    };
  },
};
</script>
