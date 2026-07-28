<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="dialog-plugin" style="min-width: 40vw">
      <q-bar>
        {{ $t("endpointResponse.alarmTitle", { hostname: hostname }) }}
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
          type="number"
          v-model.number="state.duration"
          :disable="state.forever"
          :label="$t('endpointResponse.alarmDurationLabel')"
          :min="ALARM_MIN_SECONDS"
          :max="ALARM_MAX_SECONDS"
          :hint="$t('endpointResponse.alarmDurationHint')"
        />
      </q-card-section>

      <q-card-section class="q-pt-none">
        <q-checkbox
          dense
          v-model="state.max_volume"
          :label="$t('endpointResponse.alarmMaxVolume')"
        />
        <div class="text-caption text-grey-7 q-ml-lg">
          {{ $t("endpointResponse.alarmMaxVolumeHint") }}
        </div>
      </q-card-section>

      <q-card-section class="q-pt-none">
        <q-checkbox
          dense
          v-model="state.forever"
          :label="$t('endpointResponse.alarmForever')"
        />
        <div class="text-caption text-grey-7 q-ml-lg">
          {{ $t("endpointResponse.alarmForeverHint") }}
        </div>
      </q-card-section>

      <!--
        El aviso aparece SOLO cuando alguna casilla está encendida, y nombra las
        que lo están. Esta ventana es la confirmación del caso de máximo daño: no
        hay un segundo paso donde el operador pueda leer lo que va a pasar.
      -->
      <q-card-section v-if="warning" class="q-pt-none">
        <q-banner dense class="bg-red-1 text-negative">
          <template v-slot:avatar>
            <q-icon name="warning" color="negative" />
          </template>
          {{ warning }}
        </q-banner>
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
          dense
          flat
          push
          :label="$t('endpointResponse.alarm')"
          :color="warning ? 'negative' : 'primary'"
          @click="send"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 028 Fase 2 · alarma antirrobo (homologación del `alarm` de Prey con
// sonido máximo y sin límite de tiempo).
//
// Por qué esto es un modal y no el `$q.dialog` con `prompt` que había antes: un
// `prompt` de Quasar admite un solo campo y no admite casillas. El cambio es de
// forma, no sólo de campos.
//
// Las dos casillas nacen APAGADAS, igual que los tres permisos RBAC de la 028.
// El camino de todos los días —una alarma acotada, al volumen del usuario— tiene
// que seguir siendo el que sale por omisión: la variante antirrobo es una
// excepción que alguien elige, no un default que se hereda por descuido.

// composition imports
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import { agentSoundAlarm } from "@/api/agents";
import { notifySuccess } from "@/utils/notify";

// Duplicados de observerrmm/constants.py (ALARM_*). Acá sólo evitan que el
// operador escriba un valor que el servidor va a recortar sin avisarle.
const ALARM_MIN_SECONDS = 5;
const ALARM_DEFAULT_SECONDS = 30;
const ALARM_MAX_SECONDS = 300;

export default {
  name: "SoundEndpointAlarm",
  emits: [...useDialogPluginComponent.emits],
  props: {
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
      duration: ALARM_DEFAULT_SECONDS,
      forever: false,
      max_volume: false,
    });
    const loading = ref(false);

    // El aviso son TRES frases completas y no una armada por partes. Componer
    // "sin límite de tiempo" + conjunción + "al volumen máximo" obliga a un orden
    // y a una conjunción que no son iguales en todos los idiomas; con frases
    // enteras, cada catálogo la escribe como corresponda.
    const warning = computed(() => {
      const { forever, max_volume } = state.value;
      if (forever && max_volume) return t("endpointResponse.alarmWarnBoth");
      if (forever) return t("endpointResponse.alarmWarnForever");
      if (max_volume) return t("endpointResponse.alarmWarnMaxVolume");
      return "";
    });

    async function send() {
      loading.value = true;
      try {
        // La duración viaja siempre, incluso con la eterna encendida: el servidor
        // la acota igual y un agente viejo —que no conoce la bandera— suena los
        // segundos pedidos en vez de quedar con un valor sin sentido.
        await agentSoundAlarm(props.agent_id, {
          duration: Number(state.value.duration) || ALARM_DEFAULT_SECONDS,
          forever: state.value.forever,
          max_volume: state.value.max_volume,
        });
        notifySuccess(
          t("endpointResponse.alarmSuccess", { hostname: props.hostname }),
        );
        onDialogOK();
      } catch (e) {
        // El motivo ya se le mostró al operador traducido por el interceptor de
        // axios; acá sólo queda el detalle en consola para diagnóstico.
        console.error(e);
      }
      loading.value = false;
    }

    return {
      state,
      loading,
      warning,
      ALARM_MIN_SECONDS,
      ALARM_MAX_SECONDS,
      send,
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
