<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="width: 60vw">
      <q-bar>
        {{
          check ? $t("eventLogCheck.titleEdit") : $t("eventLogCheck.titleAdd")
        }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("checksCommon.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-form @submit.prevent="beforeSubmit">
        <div style="max-height: 70vh" class="scroll">
          <q-card-section>
            <q-input
              dense
              outlined
              v-model="state.name"
              :label="$t('checksCommon.descriptiveName')"
              :rules="[(val) => !!val || $t('checksCommon.required')]"
            />
          </q-card-section>
          <q-card-section>
            <q-select
              dense
              options-dense
              outlined
              v-model="state.log_name"
              :options="logNameOptions"
              :label="$t('eventLogCheck.eventLogToQuery')"
            />
          </q-card-section>
          <q-card-section>
            <q-select
              dense
              options-dense
              outlined
              v-model="state.fail_when"
              :options="failWhenOptions"
              :label="$t('eventLogCheck.failWhen')"
              emit-value
              map-options
            />
          </q-card-section>
          <q-card-section>
            <q-input
              dense
              outlined
              v-model="state.event_id"
              :label="$t('eventLogCheck.eventId')"
              :rules="[
                (val) =>
                  validateEventID(val) || $t('eventLogCheck.invalidEventId'),
              ]"
            />
          </q-card-section>
          <q-card-section>
            <q-checkbox
              v-model="eventSource"
              :label="$t('eventLogCheck.eventSource')"
            />
            <q-input
              dense
              outlined
              v-model="state.event_source"
              :disable="!eventSource"
            />
          </q-card-section>
          <q-card-section>
            <q-checkbox
              v-model="eventMessage"
              :label="$t('eventLogCheck.messageContains')"
            />
            <q-input
              dense
              outlined
              v-model="state.event_message"
              :disable="!eventMessage"
            />
          </q-card-section>
          <q-card-section>
            <q-input
              dense
              outlined
              v-model.number="state.search_last_days"
              :label="$t('eventLogCheck.searchLastDays')"
              :rules="[
                (val) => !!val.toString() || $t('checksCommon.required'),
                (val) => val >= 0 || $t('eventLogCheck.min0'),
                (val) => val <= 9999 || $t('eventLogCheck.max9999'),
              ]"
            />
          </q-card-section>
          <q-card-section>
            <span>{{ $t("eventLogCheck.eventType") }}</span>
            <div class="q-gutter-sm">
              <q-radio
                dense
                v-model="state.event_type"
                val="INFO"
                :label="$t('eventLogCheck.typeInfo')"
              />
              <q-radio
                dense
                v-model="state.event_type"
                val="WARNING"
                :label="$t('eventLogCheck.typeWarning')"
              />
              <q-radio
                dense
                v-model="state.event_type"
                val="ERROR"
                :label="$t('eventLogCheck.typeError')"
              />
              <q-radio
                dense
                v-model="state.event_type"
                val="AUDIT_SUCCESS"
                :label="$t('eventLogCheck.typeAuditSuccess')"
              />
              <q-radio
                dense
                v-model="state.event_type"
                val="AUDIT_FAILURE"
                :label="$t('eventLogCheck.typeAuditFailure')"
              />
            </div>
          </q-card-section>
          <q-card-section>
            <q-select
              outlined
              dense
              options-dense
              map-options
              emit-value
              v-model="state.alert_severity"
              :options="severityOptions"
              :label="$t('checksCommon.alertSeverity')"
            />
          </q-card-section>
          <q-card-section>
            <q-input
              :label="$t('eventLogCheck.numberOfEventsB4Alert')"
              dense
              outlined
              type="number"
              v-model.number="state.number_of_events_b4_alert"
            />
          </q-card-section>
          <q-card-section>
            <q-select
              outlined
              dense
              options-dense
              v-model="state.fails_b4_alert"
              :options="failOptions"
              :label="$t('checksCommon.failsBeforeAlert')"
            />
          </q-card-section>
          <q-card-section>
            <q-input
              outlined
              dense
              type="number"
              v-model.number="state.run_interval"
              :label="$t('checksCommon.runIntervalLabel')"
              :hint="$t('checksCommon.runIntervalHint')"
            />
          </q-card-section>
        </div>
        <q-card-actions align="right">
          <q-btn dense flat :label="$t('checksCommon.cancel')" v-close-popup />
          <q-btn
            :loading="loading"
            dense
            flat
            :label="$t('checksCommon.save')"
            color="primary"
            type="submit"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import { ref, watch } from "vue";
import { useDialogPluginComponent } from "quasar";
import { useCheckModal } from "@/composables/checks";
import { validateEventID } from "@/utils/validation";

export default {
  name: "EventLogCheck",
  emits: [...useDialogPluginComponent.emits],
  props: {
    check: Object,
    parent: Object, // {agent: agent.agent_id} or {policy: policy.id}
  },
  setup(props) {
    // setup quasar dialog
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();

    // check logic
    const {
      state,
      loading,
      submit,
      failOptions,
      logNameOptions,
      failWhenOptions,
      severityOptions,
    } = useCheckModal({
      editCheck: props.check,
      initialState: {
        ...props.parent,
        check_type: "eventlog",
        log_name: "Application",
        event_id: null,
        event_source: null,
        event_message: null,
        event_type: "INFO",
        fail_when: "contains",
        search_last_days: 1,
        fails_b4_alert: 1,
        number_of_events_b4_alert: 1,
        event_id_is_wildcard: false,
        alert_severity: "warning",
        run_interval: 0,
      },
    });

    const eventMessage = ref(false);
    const eventSource = ref(false);

    // set check boxes on load
    if (props.check) {
      if (state.value.event_id_is_wildcard) {
        state.value.event_id = "*";
      }
      if (state.value.event_source) {
        eventSource.value = true;
      }
      if (state.value.event_message) {
        eventMessage.value = true;
      }
    }

    watch(eventMessage, () => {
      state.value.event_message = null;
    });

    watch(eventSource, () => {
      state.value.event_source = null;
    });

    function beforeSubmit() {
      // format check data for saving
      state.value.event_id_is_wildcard =
        state.value.event_id === "*" ? true : false;
      if (state.value.event_source === "") state.value.event_source = null;
      if (state.value.event_message === "") state.value.event_message = null;

      submit(onDialogOK);
    }

    return {
      // reactive data
      state,
      eventMessage,
      eventSource,
      loading,

      // non-reactive data
      failOptions,
      logNameOptions,
      failWhenOptions,
      severityOptions,

      // methods
      beforeSubmit,
      validateEventID,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
