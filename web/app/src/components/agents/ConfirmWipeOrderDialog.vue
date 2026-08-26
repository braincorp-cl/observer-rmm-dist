<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide" persistent>
    <q-card class="q-dialog-plugin" style="min-width: 40vw; max-width: 70vw">
      <q-bar class="bg-negative text-white">
        <q-icon name="warning" />
        <div>{{ $t("erase.confirmOrder.title") }}</div>
        <q-space />
      </q-bar>

      <q-card-section>
        <!-- RF-G02: la segunda confirmación es de OTRA persona. El servidor la
             exige (rechaza con 409 si confirma quien ordenó); el aviso lo dice
             para que nadie intente confirmarse a sí mismo. -->
        <q-banner dense class="bg-orange-1 text-orange-9 q-mb-md">
          <template v-slot:avatar>
            <q-icon name="group" color="warning" />
          </template>
          {{ $t("erase.confirmOrder.twoPersonNotice", { orderedBy: order.ordered_by }) }}
        </q-banner>

        <table class="oe-order-table q-mb-md">
          <tbody>
            <tr>
              <th>{{ $t("erase.confirmOrder.action") }}</th>
              <td>{{ actionLabel(order.action) }}</td>
            </tr>
            <tr>
              <th>{{ $t("erase.confirmOrder.hostname") }}</th>
              <td>{{ order.agent_hostname || dash }}</td>
            </tr>
            <tr>
              <th>{{ $t("erase.confirmOrder.serial") }}</th>
              <td>{{ order.agent_serial || dash }}</td>
            </tr>
            <tr>
              <th>{{ $t("erase.confirmOrder.reason") }}</th>
              <td>{{ order.reason || dash }}</td>
            </tr>
            <tr>
              <th>{{ $t("erase.confirmOrder.dryRun") }}</th>
              <td>
                <q-badge :color="order.dry_run ? 'grey' : 'negative'">
                  {{
                    order.dry_run
                      ? $t("erase.confirmOrder.dryRunYes")
                      : $t("erase.confirmOrder.dryRunNo")
                  }}
                </q-badge>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Ventana de arrepentimiento (RF-G03): la orden confirmada NO se
             despacha en el acto, queda cancelable durante estos segundos. -->
        <q-input
          dense
          filled
          type="number"
          v-model.number="recoverySeconds"
          :label="$t('erase.confirmOrder.recoverySeconds')"
          :hint="$t('erase.confirmOrder.recoverySecondsHint')"
          :rules="[(val) => val >= 0 || $t('erase.confirmOrder.recoveryInvalid')]"
        />
      </q-card-section>

      <q-card-section>
        <i18n-t keypath="confirmDialog.prompt" tag="span">
          <template #yes>
            <span class="text-negative text-h6">{{ yesWord }}</span>
          </template>
          <template #action>{{ actionLabel(order.action) }}</template>
          <template #hostname>
            <span class="text-negative text-h6">{{
              order.agent_hostname || dash
            }}</span>
          </template>
        </i18n-t>
        <q-input
          v-model="typed"
          autofocus
          class="q-mt-sm"
          :label="$t('confirmDialog.typeYes')"
          :rules="[(val) => (val || '').toLowerCase() === yesWord]"
        />
      </q-card-section>

      <q-card-actions align="right">
        <q-btn
          flat
          :label="$t('confirmDialog.cancel')"
          @click="onDialogCancel"
        />
        <q-btn
          color="negative"
          :loading="loading"
          :label="$t('erase.confirmOrder.confirm')"
          :disable="(typed || '').toLowerCase() !== yesWord"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 039 · Observer Erase · T033 — segunda confirmación de una orden de
// borrado (RF-G02) con apertura de la ventana de arrepentimiento (RF-G03).
//
// No CREA la orden (eso es el Bloque A, GATED): confirma una ya existente, que
// debe estar pendiente de segunda confirmación. La confirmación es de otra
// persona —lo exige el servidor— y al confirmar arranca la ventana cancelable.

import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";

import { confirmWipeOrder } from "@/api/erase";
import { notifyError } from "@/utils/notify";

export default {
  name: "ConfirmWipeOrderDialog",
  props: {
    order: { type: Object, required: true },
  },
  emits: [...useDialogPluginComponent.emits],
  setup(props) {
    const { t } = useI18n();
    const { dialogRef, onDialogHide, onDialogOK, onDialogCancel } =
      useDialogPluginComponent();

    const dash = "—";
    // Palabra literal de confirmación: igual en todos los idiomas (la regla la
    // compara tal cual), no es texto traducible.
    const yesWord = "yes";

    const typed = ref("");
    const recoverySeconds = ref(300);
    const loading = ref(false);

    function actionLabel(action) {
      return action ? t(`erase.action.${action}`) : dash;
    }

    async function submit() {
      loading.value = true;
      try {
        const updated = await confirmWipeOrder(props.order.id, {
          recovery_seconds: recoverySeconds.value,
        });
        onDialogOK(updated);
      } catch (e) {
        console.error(e);
        // El 409 (misma persona / estado no confirmable) ya lo traduce el
        // interceptor a un toast; acá sólo se deja constancia y el diálogo
        // queda abierto para reintentar con otra cuenta.
        notifyError(t("erase.confirmOrder.error"));
      } finally {
        loading.value = false;
      }
    }

    return {
      dialogRef,
      onDialogHide,
      onDialogCancel,
      dash,
      yesWord,
      typed,
      recoverySeconds,
      loading,
      actionLabel,
      submit,
    };
  },
};
</script>

<style scoped>
.oe-order-table {
  width: 100%;
  border-collapse: collapse;
}
.oe-order-table th,
.oe-order-table td {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.2);
  font-size: 13px;
}
.oe-order-table th {
  width: 30%;
  font-weight: 600;
  opacity: 0.75;
}
</style>
