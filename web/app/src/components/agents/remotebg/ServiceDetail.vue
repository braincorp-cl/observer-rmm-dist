<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="width: 600px; max-width: 80vw">
      <q-bar>
        {{ $t("serviceDetail.title", { name: service.display_name }) }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("servicesCommon.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section>
        <div class="row">
          <div class="col-3">{{ $t("serviceDetail.serviceName") }}</div>
          <div class="col-9">{{ service.name }}</div>
        </div>
        <br />
        <div class="row">
          <div class="col-3">{{ $t("serviceDetail.displayName") }}</div>
          <div class="col-9">{{ service.display_name }}</div>
        </div>
        <br />
        <div class="row">
          <div class="col-3">{{ $t("serviceDetail.description") }}</div>
          <div class="col-9">
            <q-field outlined :color="$q.dark.isActive ? 'white' : 'black'">{{
              service.description
            }}</q-field>
          </div>
        </div>
        <br />
        <div class="row">
          <div class="col-3">{{ $t("serviceDetail.path") }}</div>
          <div class="col-9">
            <code>{{ service.binpath }}</code>
          </div>
        </div>
        <br />
        <br />
        <div class="row">
          <div class="col-3">{{ $t("serviceDetail.startupType") }}</div>
          <div class="col-5">
            <q-select
              dense
              options-dense
              outlined
              v-model="startupType"
              :options="startupOptions"
              map-options
              emit-value
            />
          </div>
        </div>
      </q-card-section>
      <q-separator />
      <q-card-section>
        <div class="row">
          <div class="col-3">{{ $t("serviceDetail.serviceStatus") }}</div>
          <div class="col-9">{{ service.status }}</div>
        </div>
        <br />
        <div class="row">
          <q-btn-group color="primary" push>
            <q-btn
              :label="$t('servicesCommon.start')"
              @click="sendServiceAction(service, 'start')"
            />
            <q-btn
              :label="$t('servicesCommon.stop')"
              @click="sendServiceAction(service, 'stop')"
            />
            <q-btn
              :label="$t('servicesCommon.restart')"
              @click="sendServiceAction(service, 'restart')"
            />
          </q-btn-group>
        </div>
      </q-card-section>
      <q-separator />
      <q-card-actions align="right">
        <q-btn flat dense :label="$t('serviceDetail.cancel')" v-close-popup />
        <q-btn
          :loading="loading"
          :disable="!startupTypeEdited"
          dense
          flat
          :label="$t('serviceDetail.save')"
          color="primary"
          @click="editServiceStartup"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import {
  editAgentServiceStartType,
  sendAgentServiceAction,
} from "@/api/services";
import { notifySuccess } from "@/utils/notify";

export default {
  name: "ServiceDetail",
  emits: [...useDialogPluginComponent.emits],
  props: {
    service: !Object,
    agent_id: !String,
  },
  setup(props) {
    // setup quasar dialog plugin
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
    const { t } = useI18n();

    // static data (computed para reactividad de idioma en caliente)
    const startupOptions = computed(() => [
      {
        label: t("servicesCommon.startupAutodelay"),
        value: "autodelay",
      },
      {
        label: t("servicesCommon.startupAutomatic"),
        value: "automatic",
      },
      {
        label: t("servicesCommon.startupManual"),
        value: "manual",
      },
      {
        label: t("servicesCommon.startupDisabled"),
        value: "disabled",
      },
    ]);

    // services detail
    const startupType = ref("");
    const loading = ref(false);

    const startupTypeEdited = computed(() => {
      if (
        props.service.start_type.toLowerCase() === "automatic" &&
        props.service.autodelay
      )
        return startupType.value !== "autodelay";
      else return props.service.start_type.toLowerCase() !== startupType.value;
    });

    async function sendServiceAction(service, action) {
      loading.value = true;
      try {
        const result = await sendAgentServiceAction(
          props.agent_id,
          service.name,
          { sv_action: action },
        );
        notifySuccess(result);
        onDialogOK();
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    async function editServiceStartup() {
      const data = {
        startType:
          startupType.value === "automatic" ? "auto" : startupType.value,
      };

      loading.value = true;
      try {
        const result = await editAgentServiceStartType(
          props.agent_id,
          props.service.name,
          data,
        );
        notifySuccess(result);
        onDialogOK();
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    onMounted(() => {
      if (
        props.service.start_type.toLowerCase() === "automatic" &&
        props.service.autodelay
      )
        startupType.value = "autodelay";
      else startupType.value = props.service.start_type.toLowerCase();
    });

    return {
      // reactive data
      startupType,
      loading,
      startupTypeEdited,

      // non-reactive data
      startupOptions,

      // methods
      sendServiceAction,
      editServiceStartup,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
