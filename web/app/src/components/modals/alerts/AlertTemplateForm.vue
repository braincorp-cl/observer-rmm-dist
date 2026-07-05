<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="width: 90vw; max-width: 90vw">
      <q-bar>
        {{
          alertTemplate
            ? $t("alertTemplate.editTitle")
            : $t("alertTemplate.addTitle")
        }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("alertsModalsCommon.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-stepper
        v-model="step"
        ref="stepper"
        alternative-labels
        header-nav
        color="primary"
        animated
      >
        <q-step
          :name="1"
          :error="!template.name && step > 1"
          :title="$t('alertTemplate.stepGeneral')"
          icon="settings"
        >
          <q-card flat>
            <q-card-section>
              <q-input
                :label="$t('alertTemplate.name')"
                class="q-mb-none"
                outlined
                dense
                v-model="template.name"
                :rules="[(val) => !!val || $t('alertTemplate.required')]"
              />
            </q-card-section>

            <q-card-section>
              <q-toggle
                v-model="template.is_active"
                color="green"
                :label="$t('alertTemplate.enabled')"
                left-label
              />
            </q-card-section>

            <div class="q-pl-md text-subtitle1">
              {{ $t("alertTemplate.emailSettings") }}
            </div>

            <q-card-section>
              <q-input
                :label="$t('alertTemplate.emailFrom')"
                class="q-mb-sm"
                outlined
                dense
                v-model="template.email_from"
              />
            </q-card-section>

            <q-card-section class="row">
              <div class="col-2 q-mb-sm">
                {{ $t("alertTemplate.emailRecipients") }}
              </div>
              <div class="col-4 q-mb-sm">
                <q-list dense v-if="template.email_recipients.length !== 0">
                  <q-item
                    v-for="email in template.email_recipients"
                    :key="email"
                    dense
                  >
                    <q-item-section>
                      <q-item-label>{{ email }}</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <q-icon
                        class="cursor-pointer"
                        name="delete"
                        color="red"
                        @click="removeEmail(email)"
                      />
                    </q-item-section>
                  </q-item>
                </q-list>
                <q-list v-else>
                  <q-item-section>
                    <q-item-label>{{
                      $t("alertTemplate.noRecipients")
                    }}</q-item-label>
                  </q-item-section>
                </q-list>
              </div>
              <div class="col-3 q-mb-sm"></div>
              <div class="col-3 q-mb-sm">
                <q-btn
                  size="sm"
                  icon="fas fa-plus"
                  color="secondary"
                  :label="$t('alertTemplate.addEmail')"
                  @click="toggleAddEmail"
                />
              </div>
            </q-card-section>

            <div class="q-pl-md text-subtitle1">
              {{ $t("alertTemplate.smsSettings") }}
            </div>

            <q-card-section class="row">
              <div class="col-2 q-mb-sm">
                {{ $t("alertTemplate.smsRecipients") }}
              </div>
              <div class="col-4 q-mb-md">
                <q-list dense v-if="template.text_recipients.length !== 0">
                  <q-item
                    v-for="num in template.text_recipients"
                    :key="num"
                    dense
                  >
                    <q-item-section>
                      <q-item-label>{{ num }}</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <q-icon
                        class="cursor-pointer"
                        name="delete"
                        color="red"
                        @click="removeSMSNumber(num)"
                      />
                    </q-item-section>
                  </q-item>
                </q-list>
                <q-list v-else>
                  <q-item-section>
                    <q-item-label>{{
                      $t("alertTemplate.noRecipients")
                    }}</q-item-label>
                  </q-item-section>
                </q-list>
              </div>
              <div class="col-3 q-mb-sm"></div>
              <div class="col-3 q-mb-sm">
                <q-btn
                  class="cursor-pointer"
                  size="sm"
                  icon="fas fa-plus"
                  color="secondary"
                  :label="$t('alertTemplate.addSmsNumber')"
                  @click="toggleAddSMSNumber"
                />
              </div>
            </q-card-section>
          </q-card>
        </q-step>

        <q-step
          :name="2"
          :title="$t('alertTemplate.stepActions')"
          icon="warning"
        >
          <q-card flat>
            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.alertFailureSettings") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipFailureAction") }}
                </q-tooltip>
              </span>
            </div>

            <q-card-section>
              <q-option-group
                v-model="template.action_type"
                class="q-pb-sm"
                :options="actionTypeOptions"
                dense
                inline
              />

              <observer-dropdown
                v-if="template.action_type == 'script'"
                class="q-mb-sm"
                :label="$t('alertTemplate.failureScript')"
                outlined
                clearable
                v-model="template.action"
                :options="scriptOptions"
                mapOptions
                filterable
                :rules="[(val) => !!val || $t('alertTemplate.required')]"
              />

              <observer-dropdown
                v-else-if="template.action_type == 'server'"
                class="q-mb-sm"
                :label="$t('alertTemplate.failureScript')"
                outlined
                clearable
                v-model="template.action"
                :options="serverScriptOptions"
                mapOptions
                filterable
              />

              <observer-dropdown
                v-else
                class="q-mb-sm"
                :label="$t('alertTemplate.failureWebHook')"
                outlined
                clearable
                v-model="template.action_rest"
                :options="restActionOptions"
                mapOptions
                filterable
              />

              <q-select
                v-if="template.action_type !== 'rest'"
                class="q-mb-sm"
                dense
                :label="$t('alertTemplate.failureArgs')"
                filled
                v-model="template.action_args"
                use-input
                use-chips
                multiple
                hide-dropdown-icon
                input-debounce="0"
                new-value-mode="add"
              />

              <q-select
                v-if="template.action_type !== 'rest'"
                class="q-mb-sm"
                dense
                :label="$t('alertTemplate.failureEnvVars')"
                filled
                v-model="template.action_env_vars"
                use-input
                use-chips
                multiple
                hide-dropdown-icon
                input-debounce="0"
                new-value-mode="add"
              />

              <q-input
                v-if="template.action_type !== 'rest'"
                class="q-mb-sm"
                :label="$t('alertTemplate.failureTimeout')"
                outlined
                type="number"
                v-model.number="template.action_timeout"
                dense
                :rules="[
                  (val) => !!val || $t('alertTemplate.failureTimeoutRequired'),
                ]"
              />
            </q-card-section>

            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.alertResolvedSettings") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipResolvedAction") }}
                </q-tooltip>
              </span>
            </div>

            <q-card-section>
              <q-option-group
                v-model="template.resolved_action_type"
                class="q-pb-sm"
                :options="actionTypeOptions"
                dense
                inline
              />

              <observer-dropdown
                v-if="template.resolved_action_type === 'script'"
                class="q-mb-sm"
                :label="$t('alertTemplate.resolvedScript')"
                outlined
                clearable
                v-model="template.resolved_action"
                :options="scriptOptions"
                mapOptions
                filterable
              />

              <observer-dropdown
                v-else-if="template.resolved_action_type === 'server'"
                class="q-mb-sm"
                :label="$t('alertTemplate.resolvedScript')"
                outlined
                clearable
                v-model="template.resolved_action"
                :options="serverScriptOptions"
                mapOptions
                filterable
              />

              <observer-dropdown
                v-else
                class="q-mb-sm"
                :label="$t('alertTemplate.resolvedWebHook')"
                outlined
                clearable
                v-model="template.resolved_action_rest"
                :options="restActionOptions"
                mapOptions
                filterable
              />

              <q-select
                v-if="template.resolved_action_type !== 'rest'"
                class="q-mb-sm"
                dense
                :label="$t('alertTemplate.resolvedArgs')"
                filled
                v-model="template.resolved_action_args"
                use-input
                use-chips
                multiple
                hide-dropdown-icon
                input-debounce="0"
                new-value-mode="add"
              />

              <q-select
                v-if="template.resolved_action_type !== 'rest'"
                class="q-mb-sm"
                dense
                :label="$t('alertTemplate.resolvedEnvVars')"
                filled
                v-model="template.resolved_action_env_vars"
                use-input
                use-chips
                multiple
                hide-dropdown-icon
                input-debounce="0"
                new-value-mode="add"
              />

              <q-input
                v-if="template.resolved_action_type !== 'rest'"
                class="q-mb-sm"
                :label="$t('alertTemplate.resolvedTimeout')"
                outlined
                type="number"
                v-model.number="template.resolved_action_timeout"
                dense
                :rules="[
                  (val) => !!val || $t('alertTemplate.resolvedTimeoutRequired'),
                ]"
              />
            </q-card-section>

            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.runActionsOnlyOn") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipRunActionsOnlyOn") }}
                </q-tooltip>
              </span>
            </div>

            <q-card-section>
              <q-toggle
                v-model="template.agent_script_actions"
                :label="$t('alertTemplate.agents')"
                color="green"
                left-label
              />

              <q-toggle
                v-model="template.check_script_actions"
                :label="$t('alertTemplate.checks')"
                color="green"
                left-label
              />

              <q-toggle
                v-model="template.task_script_actions"
                :label="$t('alertTemplate.tasks')"
                color="green"
                left-label
              />
            </q-card-section>
          </q-card>
        </q-step>

        <q-step
          :name="3"
          :title="$t('alertTemplate.stepAgentOverdue')"
          icon="devices"
        >
          <q-card flat>
            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.alertFailureSettings") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipAgentFailure") }}
                </q-tooltip>
              </span>
            </div>
            <q-card-section>
              <q-toggle
                v-model="template.agent_always_email"
                :label="$t('alertTemplate.email')"
                color="green"
                left-label
                toggle-indeterminate
              />
              <q-toggle
                v-model="template.agent_always_text"
                :label="$t('alertTemplate.text')"
                color="green"
                left-label
                toggle-indeterminate
              />
              <q-toggle
                v-model="template.agent_always_alert"
                :label="$t('alertTemplate.dashboard')"
                color="green"
                left-label
                toggle-indeterminate
              />
            </q-card-section>
            <q-card-section>
              <q-input
                :label="$t('alertTemplate.alertAgainDays')"
                outlined
                type="number"
                v-model.number="template.agent_periodic_alert_days"
                dense
                :rules="[
                  (val) => val >= 0 || $t('alertTemplate.periodicDaysMin'),
                ]"
              />
            </q-card-section>

            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.alertResolvedSettings") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipAgentResolved") }}
                </q-tooltip>
              </span>
            </div>
            <q-card-section>
              <q-toggle
                v-model="template.agent_email_on_resolved"
                :label="$t('alertTemplate.email')"
                color="green"
                left-label
              />
              <q-toggle
                v-model="template.agent_text_on_resolved"
                :label="$t('alertTemplate.text')"
                color="green"
                left-label
              />
            </q-card-section>
          </q-card>
        </q-step>

        <q-step
          :name="4"
          :title="$t('alertTemplate.stepCheck')"
          icon="fas fa-check-double"
        >
          <q-card flat>
            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.alertFailureSettings") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipCheckFailure") }}
                </q-tooltip>
              </span>
            </div>

            <q-card-section>
              <q-toggle
                v-model="template.check_always_email"
                :label="$t('alertTemplate.email')"
                color="green"
                left-label
                toggle-indeterminate
              />
              <q-toggle
                v-model="template.check_always_text"
                :label="$t('alertTemplate.text')"
                color="green"
                left-label
                toggle-indeterminate
              />
              <q-toggle
                v-model="template.check_always_alert"
                :label="$t('alertTemplate.dashboard')"
                color="green"
                left-label
                toggle-indeterminate
              />
            </q-card-section>

            <q-card-section>
              <q-select
                :label="$t('alertTemplate.onlyEmailSeverity')"
                :hint="$t('alertTemplate.hintDefaultErrorWarning')"
                v-model="template.check_email_alert_severity"
                outlined
                dense
                options-dense
                multiple
                use-chips
                emit-value
                map-options
                :options="severityOptions"
              />
            </q-card-section>

            <q-card-section>
              <q-select
                :label="$t('alertTemplate.onlyTextSeverity')"
                :hint="$t('alertTemplate.hintDefaultErrorWarning')"
                v-model="template.check_text_alert_severity"
                outlined
                dense
                options-dense
                multiple
                use-chips
                emit-value
                map-options
                :options="severityOptions"
              />
            </q-card-section>

            <q-card-section>
              <q-select
                :label="$t('alertTemplate.onlyDashboardSeverity')"
                :hint="$t('alertTemplate.hintDefaultErrorWarningInfo')"
                v-model="template.check_dashboard_alert_severity"
                outlined
                dense
                options-dense
                multiple
                use-chips
                emit-value
                map-options
                :options="severityOptions"
              />
            </q-card-section>

            <q-card-section>
              <q-input
                :label="$t('alertTemplate.alertAgainDays')"
                outlined
                type="number"
                v-model.number="template.check_periodic_alert_days"
                dense
                :rules="[
                  (val) => val >= 0 || $t('alertTemplate.periodicDaysMin'),
                ]"
              />
            </q-card-section>

            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.alertResolvedSettings") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipCheckResolved") }}
                </q-tooltip>
              </span>
            </div>
            <q-card-section>
              <q-toggle
                v-model="template.check_email_on_resolved"
                :label="$t('alertTemplate.email')"
                color="green"
                left-label
              />
              <q-toggle
                v-model="template.check_text_on_resolved"
                :label="$t('alertTemplate.text')"
                color="green"
                left-label
              />
            </q-card-section>
          </q-card>
        </q-step>

        <q-step
          :name="5"
          :title="$t('alertTemplate.stepTask')"
          icon="fas fa-tasks"
        >
          <q-card flat>
            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.alertFailureSettings") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipTaskFailure") }}
                </q-tooltip>
              </span>
            </div>

            <q-card-section>
              <q-toggle
                v-model="template.task_always_email"
                :label="$t('alertTemplate.email')"
                color="green"
                left-label
                toggle-indeterminate
              />
              <q-toggle
                v-model="template.task_always_text"
                :label="$t('alertTemplate.text')"
                color="green"
                left-label
                toggle-indeterminate
              />
              <q-toggle
                v-model="template.task_always_alert"
                :label="$t('alertTemplate.dashboard')"
                color="green"
                left-label
                toggle-indeterminate
              />
            </q-card-section>

            <q-card-section>
              <q-select
                :label="$t('alertTemplate.onlyEmailSeverity')"
                :hint="$t('alertTemplate.hintDefaultErrorWarning')"
                v-model="template.task_email_alert_severity"
                outlined
                dense
                options-dense
                multiple
                use-chips
                emit-value
                map-options
                :options="severityOptions"
              />
            </q-card-section>

            <q-card-section>
              <q-select
                :label="$t('alertTemplate.onlyTextSeverity')"
                :hint="$t('alertTemplate.hintDefaultErrorWarning')"
                v-model="template.task_text_alert_severity"
                outlined
                dense
                options-dense
                multiple
                use-chips
                emit-value
                map-options
                :options="severityOptions"
              />
            </q-card-section>

            <q-card-section>
              <q-select
                :label="$t('alertTemplate.onlyDashboardSeverity')"
                :hint="$t('alertTemplate.hintDefaultErrorWarningInfo')"
                v-model="template.task_dashboard_alert_severity"
                outlined
                dense
                options-dense
                multiple
                use-chips
                emit-value
                map-options
                :options="severityOptions"
              />
            </q-card-section>

            <q-card-section>
              <q-input
                :label="$t('alertTemplate.alertAgainDaysTask')"
                outlined
                type="number"
                v-model.number="template.task_periodic_alert_days"
                dense
                :rules="[
                  (val) => val >= 0 || $t('alertTemplate.periodicDaysMin'),
                ]"
              />
            </q-card-section>

            <div class="q-pl-md text-subtitle1">
              <span style="text-decoration: underline; cursor: help"
                >{{ $t("alertTemplate.alertResolvedSettings") }}
                <q-tooltip>
                  {{ $t("alertTemplate.tooltipTaskResolved") }}
                </q-tooltip>
              </span>
            </div>
            <q-card-section>
              <q-toggle
                v-model="template.task_email_on_resolved"
                :label="$t('alertTemplate.email')"
                color="green"
                left-label
              />
              <q-toggle
                v-model="template.task_text_on_resolved"
                :label="$t('alertTemplate.text')"
                color="green"
                left-label
              />
            </q-card-section>
          </q-card>
        </q-step>
        <template v-slot:navigation>
          <q-stepper-navigation class="row">
            <q-btn
              v-if="step > 1"
              flat
              color="primary"
              @click="stepper?.previous()"
              :label="$t('alertTemplate.back')"
              class="q-mr-xs"
            />
            <q-btn
              v-if="step < 5"
              @click="stepper?.next()"
              color="primary"
              :label="$t('alertTemplate.next')"
            />
            <q-space />
            <q-btn
              @click="onSubmit"
              color="primary"
              :label="$t('alertsModalsCommon.submit')"
              :loading="loading"
            />
          </q-stepper-navigation>
        </template>
      </q-stepper>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, reactive, watch, nextTick } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";
import { useQuasar, useDialogPluginComponent, type QStepper } from "quasar";
import { useScriptDropdown } from "@/composables/scripts";
import { useURLActionDropdown } from "@/composables/core";
import { notifyError, notifySuccess } from "@/utils/notify";
import { addAlertTemplate, saveAlertTemplate } from "@/api/alerts";
import { isValidEmail } from "@/utils/validation";

// components
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

// types
import type { AlertTemplate, AlertSeverity } from "@/types/alerts";

// store
const store = useStore();
const hosted = computed(() => store.state.hosted);
const server_scripts_enabled = computed(
  () => store.state.server_scripts_enabled,
);

// props
const props = defineProps<{
  alertTemplate?: AlertTemplate;
}>();

// emits
defineEmits([...useDialogPluginComponent.emits]);

// setup quasar plugins
const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
const $q = useQuasar();

// i18n
const { t } = useI18n();

const step = ref(1);

// setup script dropdowns
const {
  script: failureAction,
  defaultArgs: failureArgs,
  defaultEnvVars: failureEnvVars,
  defaultTimeout: failureTimeout,
  serverScriptOptions,
  scriptOptions,
} = useScriptDropdown({ script: props.alertTemplate?.action, onMount: true });

const {
  script: resolvedAction,
  defaultArgs: resolvedArgs,
  defaultEnvVars: resolvedEnvVars,
  defaultTimeout: resolvedTimeout,
} = useScriptDropdown({
  script: props.alertTemplate?.resolved_action,
  onMount: true,
});

// setup custom field dropdown
const { restActionOptions } = useURLActionDropdown({ onMount: true });

// alert template form logic
const template: AlertTemplate = props.alertTemplate
  ? reactive(Object.assign({}, { ...props.alertTemplate }))
  : reactive({
      id: 0,
      name: "",
      is_active: true,
      action_type: "script",
      action: failureAction,
      action_rest: undefined,
      action_args: failureArgs,
      action_env_vars: failureEnvVars,
      action_timeout: failureTimeout,
      resolved_action_type: "script",
      resolved_action: resolvedAction,
      resolved_action_rest: undefined,
      resolved_action_args: resolvedArgs,
      resolved_action_env_vars: resolvedEnvVars,
      resolved_action_timeout: resolvedTimeout,
      email_recipients: [] as string[],
      email_from: "",
      text_recipients: [] as string[],
      agent_email_on_resolved: false,
      agent_text_on_resolved: false,
      agent_always_email: null,
      agent_always_text: null,
      agent_always_alert: null,
      agent_periodic_alert_days: 0,
      agent_script_actions: true,
      check_email_alert_severity: [] as AlertSeverity[],
      check_text_alert_severity: [] as AlertSeverity[],
      check_dashboard_alert_severity: [] as AlertSeverity[],
      check_email_on_resolved: false,
      check_text_on_resolved: false,
      check_always_email: null,
      check_always_text: null,
      check_always_alert: null,
      check_periodic_alert_days: 0,
      check_script_actions: true,
      task_email_alert_severity: [] as AlertSeverity[],
      task_text_alert_severity: [] as AlertSeverity[],
      task_dashboard_alert_severity: [] as AlertSeverity[],
      task_email_on_resolved: false,
      task_text_on_resolved: false,
      task_always_email: null,
      task_always_text: null,
      task_always_alert: null,
      task_periodic_alert_days: 0,
      task_script_actions: true,
    });

// reset selected script if action type is changed
watch(
  () => template.action_type,
  () => {
    template.action_rest = undefined;
    template.action = undefined;
    template.action_args = [];
    template.action_env_vars = [];
    template.action_timeout = 30;
  },
);

watch(
  () => template.resolved_action_type,
  () => {
    template.resolved_action_rest = undefined;
    template.resolved_action = undefined;
    template.resolved_action_args = [];
    template.resolved_action_env_vars = [];
    template.resolved_action_timeout = 30;
  },
);

// sync selected script to scriptdropdown
// only add watchers if editting template
if (props.alertTemplate) {
  watch(
    () => template.action,
    (newValue) => {
      if (newValue) {
        failureAction.value = newValue;

        // wait for the script change to happen
        nextTick(() => {
          template.action_args = failureArgs.value;
          template.action_env_vars = failureEnvVars.value;
          template.action_timeout = failureTimeout.value;
        });
      }
    },
  );

  watch(
    () => template.resolved_action,
    (newValue) => {
      if (newValue) {
        resolvedAction.value = newValue;

        // wait for the script change to happen
        nextTick(() => {
          template.resolved_action_args = resolvedArgs.value;
          template.resolved_action_env_vars = resolvedEnvVars.value;
          template.resolved_action_timeout = resolvedTimeout.value;
        });
      }
    },
  );
}

const severityOptions = computed(() => [
  { label: t("alertTemplate.sevError"), value: "error" },
  { label: t("alertTemplate.sevWarning"), value: "warning" },
  { label: t("alertTemplate.sevInfo"), value: "info" },
]);

const staticActionTypeOptions = computed(() => [
  { label: t("alertTemplate.actionRest"), value: "rest" },
  { label: t("alertTemplate.actionScript"), value: "script" },
  { label: t("alertTemplate.actionServer"), value: "server" },
]);

const actionTypeOptions = computed(() => {
  // don't show for hosted at all
  if (hosted.value) {
    return staticActionTypeOptions.value.filter(
      (option) => option.value !== "server",
    );
  }
  // disable the server script radio button if feature is disabled globally
  const modifiedOptions = staticActionTypeOptions.value.map((option) => {
    if (!server_scripts_enabled.value && option.value === "server") {
      return { ...option, disable: true };
    }
    return option;
  });

  return modifiedOptions;
});

const stepper = ref<QStepper | null>(null);
function toggleAddEmail() {
  $q.dialog({
    title: t("alertTemplate.addEmailTitle"),
    prompt: {
      model: "",
      isValid: (val) => isValidEmail(val),
      type: "email",
    },
    cancel: true,
    ok: { label: t("alertTemplate.addBtn"), color: "primary" },
    persistent: false,
  }).onOk((data) => {
    template.email_recipients.push(data);
  });
}

function toggleAddSMSNumber() {
  $q.dialog({
    title: t("alertTemplate.addNumberTitle"),
    message: t("alertTemplate.addNumberMessage"),
    prompt: {
      model: "",
    },
    html: true,
    cancel: true,
    ok: { label: t("alertTemplate.addBtn"), color: "primary" },
    persistent: false,
  }).onOk((data: string) => {
    template.text_recipients.push(data);
  });
}

function removeEmail(email: string) {
  const removed = template.email_recipients.filter((k) => k !== email);
  template.email_recipients = removed;
}

function removeSMSNumber(num: string) {
  const removed = template.text_recipients.filter((k) => k !== num);
  template.text_recipients = removed;
}

const loading = ref(false);

async function onSubmit() {
  // TODO rework this ghetto form validation
  if (!template.name) {
    notifyError(t("alertTemplate.nameRequired"));
    return;
  }

  loading.value = true;

  if (props.alertTemplate) {
    try {
      await saveAlertTemplate(template.id, template);
      notifySuccess(t("alertTemplate.notifyEdited"));
      onDialogOK();
    } catch {
    } finally {
      loading.value = false;
    }
  } else {
    try {
      await addAlertTemplate(template);
      notifySuccess(t("alertTemplate.notifyEdited"));
      onDialogOK();
    } catch {
    } finally {
      loading.value = false;
    }
  }
}
</script>
