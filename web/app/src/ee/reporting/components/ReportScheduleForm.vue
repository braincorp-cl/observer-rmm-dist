<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide" persistent>
    <q-card class="q-dialog-plugin" style="width: 90vw; max-width: 600px">
      <q-bar>
        <template v-if="!emailOnly">
          {{
            schedule && !clone
              ? $t("reporting.scheduleForm.editTitle")
              : $t("reporting.scheduleForm.addTitle")
          }}
        </template>
        <template v-else> {{ $t("reporting.scheduleForm.emailReportTitle") }} </template>
        <q-space />
        <q-btn dense flat icon="close" v-close-popup />
      </q-bar>

      <q-form @submit.prevent="submit">
        <q-card-section class="q-pa-md">
          <q-input
            v-if="!emailOnly"
            v-model="localSchedule.name"
            :label="$t('reporting.common.name')"
            dense
            filled
            :rules="[(val: string) => !!val || $t('reporting.scheduleForm.requiredField')]"
          />

          <q-toggle
            v-if="!emailOnly"
            v-model="localSchedule.enabled"
            :label="$t('reporting.scheduleForm.enabledLabel')"
            dense
            dense-toggle
            class="q-mb-sm"
          />

          <observer-dropdown
            v-model="localSchedule.report_template"
            :options="reportTemplateOptions"
            :label="$t('reporting.scheduleForm.reportTemplateLabel')"
            dense
            filled
            map-options
            emit-value
            options-dense
            filterable
            :rules="[(val: number) => !!val || $t('reporting.scheduleForm.requiredField')]"
          >
            <template #after v-if="hasDependencies">
              <!-- 🔴 050 (G05, 17.ª y 18.ª corridas): acá hubo DOS arreglos y el
                   primero no sirvió, así que queda la historia entera.
                   · 17.ª: el «warning» ámbar vivía DENTRO del q-btn
                     «Dependencias» y un comentario mío —de T044— lo llamaba «la
                     insignia de estado dentro del control». No era una insignia:
                     sin fondo ni borde propios, y el textContent del botón era
                     literalmente «warning Dependencias», o sea el glifo era
                     parte del RÓTULO, que el criterio nombra como superficie
                     propia del control.
                   · 18.ª: lo saqué del botón y lo puse como «hermano suyo,
                     FUERA de él». 🔴 Falso: el slot #after se rinde DENTRO del
                     `label.q-field` del q-select, que es otro control. Medido a
                     dos niveles: icono rect 879,247,18,18 contenido en el del
                     campo 437,236,566,60, `fondo_propio=False`,
                     `borde_propio=False`, `position=relative`. Lo mismo que la
                     17.ª, un control más arriba. Cinco de los seis críticos lo
                     cazaron.
                   🔑 Lo que aprendí recién: mover un color de estado de un
                   control a su contenedor no lo saca de la clase, porque la
                   clase no es «estar dentro de ESTE botón», es «caer sobre la
                   superficie propia de ALGÚN control». Y mi propia sonda lo
                   publicó como cero porque su lista de controles no incluía
                   `.q-field`: el hueco estaba en el instrumento, no en el dato.
                   Ahora el estado lo lleva el TEXTO del rótulo de la acción, en
                   teal, sin ningún color de estado en juego: la palabra dice
                   qué pasa y el color dice que es una acción. El dato
                   (`areDependenciesMet`) sigue siendo el que decide qué se
                   lee. -->
              <q-btn
                flat
                dense
                no-caps
                color="primary"
                @click="openDependenciesForm"
              >
                {{
                  areDependenciesMet
                    ? $t("reporting.scheduleForm.dependenciesLabel")
                    : $t("reporting.scheduleForm.dependenciesMissing")
                }}
              </q-btn>
            </template>
          </observer-dropdown>

          <q-option-group
            v-model="localSchedule.format"
            :options="formatOptions"
            :label="$t('reporting.scheduleForm.formatLabel')"
            inline
            dense
            class="q-mb-sm"
            :rules="[(val: number) => !!val || $t('reporting.scheduleForm.requiredField')]"
          />

          <observer-dropdown
            v-if="!emailOnly"
            v-model="localSchedule.schedule"
            :options="scheduleOptions"
            :label="$t('reporting.scheduleForm.scheduleLabel')"
            map-options
            emit-value
            options-dense
            dense
            filled
            filterable
            :rules="[(val: string) => !!val || $t('reporting.scheduleForm.requiredField')]"
          >
            <template #after>
              <q-btn
                @click="openCoreScheduleForm"
                icon="fas fa-plus"
                color="primary"
                flat
                no-caps
                dense
                :label="$t('reporting.scheduleForm.createNewScheduleLabel')"
              />
            </template>
          </observer-dropdown>

          <!-- 050 (T044, G01): el identificador IANA de la zona horaria es un
               valor dedicado ⇒ JetBrains Mono, igual que en Ajustes. -->
          <observer-dropdown
            v-if="!emailOnly"
            v-model="localSchedule.timezone"
            :options="settings?.all_timezones || []"
            :label="$t('reporting.scheduleForm.timezoneLabel')"
            class="obs-mono-values"
            options-dense
            dense
            filled
            filterable
            clearable
            :hint="
              $t('reporting.scheduleForm.timezoneHint', {
                tz: settings?.default_time_zone,
              })
            "
          />

          <div class="row q-pt-sm">
            <div class="col-9 text-weight-medium">
              {{ $t("reporting.scheduleForm.emailRecipientsLabel") }}
              <q-icon name="info" size="xs" class="cursor-pointer">
                <q-tooltip max-width="300px">{{
                  settings?.email_alert_recipients &&
                  settings.email_alert_recipients.length > 0
                    ? $t("reporting.scheduleForm.defaultEmailRecipients", {
                        recipients:
                          settings.email_alert_recipients.join(", "),
                      })
                    : $t("reporting.scheduleForm.noEmailRecipients")
                }}</q-tooltip>
              </q-icon>
            </div>
            <div class="col-3">
              <q-btn
                no-caps
                dense
                flat
                icon="fas fa-plus"
                color="primary"
                :label="$t('reporting.scheduleForm.addEmailLabel')"
                @click="toggleAddEmail"
              />
            </div>
            <div class="col-12">
              <q-list dense v-if="localSchedule.email_recipients.length !== 0">
                <q-item
                  v-for="email in localSchedule.email_recipients"
                  :key="email"
                  dense
                >
                  <q-item-section>
                    <!-- 050 (T046, G01): un correo es un NOMBRE ⇒ Archivo. -->
                    <q-item-label>{{ email }}</q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-icon
                      class="cursor-pointer"
                      name="delete"
                      @click="removeEmail(email)"
                    />
                  </q-item-section>
                </q-item>
              </q-list>
              <q-list v-else>
                <q-item-section>
                  <q-item-label>{{
                    $t("reporting.scheduleForm.noRecipientsHint")
                  }}</q-item-label>
                </q-item-section>
              </q-list>
            </div>
          </div>
          <q-checkbox
            v-if="!emailOnly"
            v-model="localSchedule.send_report_email"
            :label="$t('reporting.scheduleForm.sendReportEmailLabel')"
            class="q-pt-md"
            dense
          />
        </q-card-section>
        <q-card-section>
          <q-btn
            no-caps
            dense
            flat
            color="primary"
            :label="$t('reporting.scheduleForm.customizeEmailContentLabel')"
            @click="openEmailSettings"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat :label="$t('reporting.common.cancel')" v-close-popup dense />
          <q-btn
            flat
            :label="
              !emailOnly
                ? $t('reporting.common.save')
                : $t('reporting.scheduleForm.sendLabel')
            "
            color="primary"
            :loading="isLoading"
            class="q-ml-sm"
            type="submit"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script lang="ts" setup>
import { ref, watch, unref, reactive, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent, extend } from "quasar";
import { until } from "@vueuse/shared";
import {
  useSharedReportSchedules,
  useSharedReportTemplates,
} from "../api/reporting";
import { useReportTemplateDropdown } from "../composables";
import { useScheduleDropdown } from "@/core/settings/composables";
import { isValidEmail } from "@/utils/validation";
import { notifyWarning } from "@/utils/notify";

// ui imports
import ReportDependencyPrompt from "./ReportDependencyPrompt.vue";
import ScheduleForm from "@/core/settings/components/ScheduleForm.vue";
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

import type {
  ReportSchedule,
  ReportFormat,
  ReportTemplate,
  ReportDependencies,
  EmailSettings,
} from "../types/reporting";
import ReportEmailSettingsForm from "./ReportEmailSettingsForm.vue";
import { fetchCoreSettings } from "@/api/core";
import { CoreSetting } from "@/types/core/settings";

const props = defineProps<{
  schedule?: ReportSchedule;
  reportTemplate?: number;
  clone?: boolean;
  emailOnly?: boolean;
}>();

const { t } = useI18n();

const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
defineEmits(useDialogPluginComponent.emits);

const { addReportSchedule, editReportSchedule, isLoading, isError } =
  useSharedReportSchedules;

const { reportTemplates, emailReport } = useSharedReportTemplates;

const $q = useQuasar();

const { reportTemplateOptions } = useReportTemplateDropdown();
const { scheduleOptions } = useScheduleDropdown();

const formatOptions = computed<{ label: string; value: ReportFormat }[]>(() => [
  { label: "HTML", value: "html" },
  { label: "PDF", value: "pdf" },
  { label: t("reporting.scheduleForm.formatPlaintext"), value: "plaintext" },
]);

const localSchedule = reactive<ReportSchedule>(
  props.schedule
    ? extend(true, {}, props.schedule)
    : {
        id: 0,
        name: "",
        enabled: true,
        report_template: props.reportTemplate,
        format: "html",
        schedule: undefined,
        email_recipients: [],
        send_report_email: true,
        dependencies: {},
        email_settings: {
          subject: "",
          body: "",
          attachment_name: "",
          attachment_extension: "",
          include_report_link: false,
        },
        timezone: null,
      },
);

const selectedTemplate = ref<ReportTemplate | null>(null);

const areDependenciesMet = computed(() => {
  const required = selectedTemplate.value?.depends_on;

  if (!required || required.length === 0) {
    return true;
  }

  return required.every((key) => localSchedule.dependencies[key] != null);
});

// set selected template if editing the form or r
if (
  props.reportTemplate ||
  (props.schedule && props.schedule.report_template)
) {
  const template = reportTemplates.value.find(
    (t) => t.id === localSchedule?.report_template,
  );
  if (template?.depends_on && template.depends_on.length > 0) {
    selectedTemplate.value = template;
  }
}

const hasDependencies = computed(() => {
  if (selectedTemplate.value && selectedTemplate.value.depends_on) {
    return selectedTemplate.value.depends_on.length > 0;
  }
  return false;
});

watch(
  () => localSchedule.report_template,
  (newValue) => {
    localSchedule.dependencies = {};
    selectedTemplate.value = null;

    if (newValue) {
      const template = reportTemplates.value.find((t) => t.id === newValue);
      if (template?.depends_on && template.depends_on.length > 0) {
        selectedTemplate.value = template;
      }
    }
  },
);

function openDependenciesForm() {
  $q.dialog({
    component: ReportDependencyPrompt,
    componentProps: {
      dependsOn: selectedTemplate.value?.depends_on,
      values: localSchedule.dependencies,
    },
  }).onOk((data: ReportDependencies) => {
    localSchedule.dependencies = unref(data);
  });
}

function openCoreScheduleForm() {
  $q.dialog({
    component: ScheduleForm,
  });
}

function openEmailSettings() {
  $q.dialog({
    component: ReportEmailSettingsForm,
    componentProps: {
      emailSettings: localSchedule.email_settings,
      format: localSchedule.format,
    },
  }).onOk((data: EmailSettings) => (localSchedule.email_settings = data));
}

function toggleAddEmail() {
  $q.dialog({
    title: t("reporting.scheduleForm.addEmailLabel"),
    prompt: {
      model: "",
      isValid: (val) => isValidEmail(val),
      type: "email",
    },
    color: "primary",
    cancel: true,
    ok: { label: t("reporting.common.add"), color: "primary" },
    persistent: false,
  }).onOk((data) => {
    localSchedule.email_recipients.push(data);
  });
}

function removeEmail(email: string) {
  const removed = localSchedule.email_recipients.filter((k) => k !== email);
  localSchedule.email_recipients = removed;
}

async function submit() {
  // make sure dependencies are set
  if (!areDependenciesMet.value) {
    notifyWarning(
      !props.emailOnly
        ? t("reporting.scheduleForm.depsRequiredSave")
        : t("reporting.scheduleForm.depsRequiredSend"),
    );
    return;
  }

  if (props.emailOnly && props.reportTemplate) {
    if (props.reportTemplate)
      emailReport(props.reportTemplate, {
        format: localSchedule.format,
        email_recipients: localSchedule.email_recipients,
        dependencies: localSchedule.dependencies,
        email_settings: localSchedule.email_settings,
      });
  } else if (!props.clone && props.schedule) {
    editReportSchedule(props.schedule.id, localSchedule);
  } else {
    addReportSchedule(localSchedule);
  }
  await until(isLoading).not.toBeTruthy();
  if (isError.value) return;

  onDialogOK();
}

const settings = ref<CoreSetting | null>(null);

async function getCoreSettings() {
  settings.value = await fetchCoreSettings();
}

onMounted(getCoreSettings);
</script>
