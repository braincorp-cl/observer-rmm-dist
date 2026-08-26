<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="min-width: 38vw">
      <q-bar :class="expired ? 'bg-grey-7 text-white' : 'bg-warning text-black'">
        <q-icon :name="expired ? 'timer_off' : 'hourglass_bottom'" />
        <div>{{ $t("erase.recovery.title") }}</div>
        <q-space />
        <q-btn dense flat icon="close" v-close-popup />
      </q-bar>

      <q-card-section class="text-center">
        <div class="text-caption text-grey q-mb-xs">
          {{ $t("erase.recovery.forHost", { hostname: order.agent_hostname || dash }) }}
        </div>

        <!-- La cuenta regresiva es la ventana de arrepentimiento (RF-G03): hasta
             que llegue a cero la orden confirmada sigue cancelable. -->
        <div v-if="!expired" class="text-h3 text-warning q-my-sm">
          {{ countdownText }}
        </div>
        <div v-else class="text-h5 text-grey q-my-sm">
          {{ $t("erase.recovery.expired") }}
        </div>

        <div class="text-caption text-grey">
          {{ $t("erase.recovery.deadline", { when: formatDate(order.recovery_deadline) }) }}
        </div>
      </q-card-section>

      <q-separator />

      <q-card-section v-if="!expired">
        <q-input
          dense
          filled
          type="textarea"
          autogrow
          v-model="cancelReason"
          :label="$t('erase.recovery.cancelReason')"
        />
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat :label="$t('erase.recovery.close')" v-close-popup />
        <q-btn
          v-if="!expired"
          color="positive"
          icon="undo"
          :loading="cancelling"
          :label="$t('erase.recovery.cancelOrder')"
          @click="cancel"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 039 · Observer Erase · T033 — la ventana de arrepentimiento (RF-G03).
//
// Muestra la cuenta regresiva hasta `recovery_deadline` y deja cancelar la
// orden mientras la ventana siga abierta. Cuando la cuenta llega a cero, la
// cancelación desde acá deja de ofrecerse: pasada la ventana el despacho es
// cosa del servidor (y sigue GATED por ADR-029, Bloque A).

import { onMounted, onUnmounted, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";

import { cancelWipeOrder } from "@/api/erase";
import { formatDate } from "@/utils/format";
import { notifySuccess, notifyError } from "@/utils/notify";

export default {
  name: "RecoveryWindowDialog",
  props: {
    order: { type: Object, required: true },
  },
  emits: [...useDialogPluginComponent.emits],
  setup(props) {
    const { t } = useI18n();
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();

    const dash = "—";
    const remaining = ref(0);
    const cancelReason = ref("");
    const cancelling = ref(false);
    let timer = null;

    const deadlineMs = props.order.recovery_deadline
      ? new Date(props.order.recovery_deadline).getTime()
      : 0;

    function tick() {
      const now = Date.now();
      remaining.value = Math.max(0, Math.round((deadlineMs - now) / 1000));
      if (remaining.value <= 0 && timer) {
        clearInterval(timer);
        timer = null;
      }
    }

    const expired = computed(() => remaining.value <= 0);

    // mm:ss — el minutero se arma acá, no como literal en el template.
    const countdownText = computed(() => {
      const m = Math.floor(remaining.value / 60);
      const s = remaining.value % 60;
      return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    });

    async function cancel() {
      cancelling.value = true;
      try {
        const updated = await cancelWipeOrder(props.order.id, {
          reason: cancelReason.value,
        });
        notifySuccess(t("erase.recovery.cancelled"));
        onDialogOK(updated);
      } catch (e) {
        console.error(e);
        notifyError(t("erase.recovery.cancelError"));
      } finally {
        cancelling.value = false;
      }
    }

    onMounted(() => {
      tick();
      timer = setInterval(tick, 1000);
    });

    onUnmounted(() => {
      if (timer) clearInterval(timer);
    });

    return {
      dialogRef,
      onDialogHide,
      dash,
      remaining,
      expired,
      countdownText,
      cancelReason,
      cancelling,
      cancel,
      formatDate,
    };
  },
};
</script>
