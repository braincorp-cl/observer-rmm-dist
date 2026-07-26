<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="dialog-plugin" style="min-width: 40vw">
      <q-bar>
        {{ $t("endpointResponse.alertTitle", { hostname: hostname }) }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("endpointResponse.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section>
        <q-input
          dense
          filled
          stack-label
          v-model="state.title"
          :label="$t('endpointResponse.alertFieldTitle')"
          :maxlength="MAX_TITLE_LEN"
          counter
          :hint="$t('endpointResponse.alertFieldTitleHint')"
        />
      </q-card-section>

      <q-card-section>
        <q-input
          dense
          filled
          stack-label
          type="textarea"
          autogrow
          v-model="state.message"
          :label="$t('endpointResponse.alertFieldMessage')"
          :maxlength="MAX_MESSAGE_LEN"
          counter
          :rules="[
            (val) => !!val.trim() || $t('endpointResponse.alertRequired'),
          ]"
        />
      </q-card-section>

      <q-card-section class="text-caption text-grey-7">
        {{ $t("endpointResponse.alertPreviewNote") }}
      </q-card-section>

      <q-card-actions align="right">
        <q-btn
          dense
          flat
          push
          :label="$t('endpointResponse.cancel')"
          v-close-popup
        />
        <q-btn
          :loading="loading"
          :disable="!state.message.trim()"
          dense
          flat
          push
          :label="$t('endpointResponse.send')"
          color="primary"
          @click="send"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 028 · redacción del mensaje en pantalla (homologación del `alert` de Prey).
//
// El texto lo escribe el operador y el agente lo pinta tal cual, sin traducirlo:
// el agente no tiene catálogo de idiomas ni sabe quién está frente al equipo. Lo
// que sí está traducido es todo lo de esta ventana, incluido el título por
// defecto que se precarga — así el operador arranca con un texto sensato en SU
// idioma y puede cambiarlo.

// composition imports
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import { agentSendAlert } from "@/api/agents";
import { notifySuccess } from "@/utils/notify";

// Duplicados de observerrmm/constants.py (ALERT_MAX_*). Acá sólo evitan que el
// operador escriba un texto que el servidor va a recortar sin avisarle.
const MAX_TITLE_LEN = 120;
const MAX_MESSAGE_LEN = 2000;

export default {
  name: "SendEndpointAlert",
  emits: [...useDialogPluginComponent.emits],
  props: {
    // Un solo agente: se manda el agent_id. Varios: se delega en la vista bulk,
    // que recibe los mismos campos.
    agent_id: {
      type: String,
      default: "",
    },
    hostname: {
      type: String,
      default: "",
    },
  },
  setup(props) {
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
    const { t } = useI18n();

    const state = ref({
      title: t("endpointResponse.alertDefaultTitle"),
      message: "",
    });
    const loading = ref(false);

    async function send() {
      if (!state.value.message.trim()) return;

      loading.value = true;
      try {
        await agentSendAlert(props.agent_id, {
          title: state.value.title,
          message: state.value.message,
        });
        notifySuccess(
          t("endpointResponse.alertSuccess", { hostname: props.hostname }),
        );
        onDialogOK();
      } catch (e) {
        // El motivo ya se le mostró al operador traducido por el interceptor de
        // axios; acá sólo se deja el detalle en consola para diagnóstico.
        console.error(e);
      }
      loading.value = false;
    }

    return {
      state,
      loading,
      MAX_TITLE_LEN,
      MAX_MESSAGE_LEN,
      send,
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
