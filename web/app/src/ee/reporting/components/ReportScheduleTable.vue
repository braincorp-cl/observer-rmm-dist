<template>
  <q-dialog ref="dialogRef" maximized @hide="onDialogHide">
    <q-card>
      <q-bar>
        <q-btn
          class="q-mr-sm"
          dense
          flat
          push
          icon="refresh"
          @click="getReportSchedules"
        />{{ $t("reporting.scheduleTable.title") }}
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip>{{ $t("reporting.common.close") }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-table
        dense
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        :style="{ 'max-height': `${$q.screen.height - 24}px` }"
        class="tbl-sticky"
        :rows="reportSchedules"
        :columns="columns"
        :loading="isLoading"
        :pagination="{
          rowsPerPage: 0,
          sortBy: 'report_template',
          descending: false,
        }"
        :filter="search"
        row-key="id"
        binary-state-sort
        virtual-scroll
        :rows-per-page-options="[0]"
      >
        <template #top>
          <q-btn
            class="q-ml-sm"
            icon="add"
            :label="$t('reporting.scheduleTable.newLabel')"
            no-caps
            dense
            flat
            @click="openNewScheduleForm"
          />
          <q-space />
          <q-input
            v-model="search"
            style="width: 300px"
            :label="$t('reporting.common.search')"
            dense
            outlined
            clearable
            class="q-pr-md q-pb-xs"
          >
            <template #prepend>
              <q-icon name="search" />
            </template>
          </q-input>
        </template>

        <template #body="props">
          <q-tr
            :props="props"
            class="cursor-pointer"
            @dblclick="openEditSchedule(props.row)"
          >
            <!-- Context Menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item v-close-popup clickable @click="runSchedule(props.row)">
                  <q-item-section>{{
                    $t("reporting.scheduleTable.runScheduledReport")
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <q-item
                  v-close-popup
                  clickable
                  @click="openEditSchedule(props.row)"
                >
                  <q-item-section>{{
                    $t("reporting.common.edit")
                  }}</q-item-section>
                </q-item>

                <q-item
                  v-close-popup
                  clickable
                  @click="openCloneSchedule(props.row)"
                >
                  <q-item-section>{{
                    $t("reporting.scheduleTable.cloneLabel")
                  }}</q-item-section>
                </q-item>

                <q-item
                  v-close-popup
                  clickable
                  @click="deleteSchedule(props.row)"
                >
                  <q-item-section>{{
                    $t("reporting.common.delete")
                  }}</q-item-section>
                </q-item>

                <q-separator />
                <q-item v-close-popup clickable>
                  <q-item-section>{{
                    $t("reporting.common.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>

            <q-td v-for="col in props.cols" :key="col.name" :props="props">
              {{ col.value }}
            </q-td>
          </q-tr>
        </template>
      </q-table>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent, type QTableColumn } from "quasar";
import { formatDate, capitalize } from "@/utils/format";
import { useSharedReportSchedules } from "../api/reporting";
import ReportScheduleForm from "./ReportScheduleForm.vue";
import type { ReportSchedule } from "../types/reporting";

const { t } = useI18n();

const columns = computed<QTableColumn[]>(() => [
  {
    name: "name",
    label: t("reporting.common.name"),
    field: "name",
    align: "left",
    sortable: true,
  },
  {
    name: "enabled",
    label: t("reporting.scheduleTable.enabledCol"),
    field: "enabled",
    align: "left",
    sortable: true,
    format: (val: boolean) =>
      val ? t("reporting.common.yes") : t("reporting.common.no"),
  },
  {
    name: "report_template_name",
    label: t("reporting.scheduleTable.templateCol"),
    field: "report_template_name",
    align: "left",
    sortable: true,
  },
  {
    name: "format",
    label: t("reporting.scheduleTable.formatCol"),
    field: "format",
    align: "left",
    sortable: true,
    format: (val: string) => capitalize(val),
  },
  {
    name: "schedule_name",
    label: t("reporting.scheduleTable.scheduleCol"),
    field: "schedule_name",
    align: "left",
    sortable: true,
  },
  {
    // 050 (T046, G01): un correo es un NOMBRE ⇒ Archivo (la clasificación
    // cerrada de la vara solo nombra IP, MAC, versión en su columna, conteos,
    // tamaños, rutas, comandos y especificaciones). Se mantiene el corte por
    // palabra, que es de ancho, no de tipografía.
    name: "email_recipients",
    label: t("reporting.scheduleTable.recipientsCol"),
    field: "email_recipients",
    align: "left",
    sortable: false,
    classes: "obs-wrap-words",
    format: (val: string[]) => val.join(", "),
    // V2-G07: token sin espacios que fijaría el ancho de la columna.
    classes: "obs-break-anywhere",
  },
  {
    name: "send_report_email",
    label: t("reporting.scheduleTable.sendEmailCol"),
    field: "send_report_email",
    align: "center",
    sortable: true,
    format: (val: boolean) =>
      val ? t("reporting.common.yes") : t("reporting.common.no"),
  },
  {
    name: "last_run",
    label: t("reporting.scheduleTable.lastRunCol"),
    field: "last_run",
    align: "center",
    sortable: true,
    // V2-G01: mono SÓLO cuando rinde marca de tiempo; el rótulo «Nunca» es
    // interfaz y se queda en Archivo.
    classes: (row: { last_run?: string }) => (row.last_run ? "mono" : ""),
    format: (val: string) =>
      val ? formatDate(val) : t("reporting.scheduleTable.neverLabel"),
  },
]);

// emits
defineEmits([...useDialogPluginComponent.emits]);

const { dialogRef, onDialogHide } = useDialogPluginComponent();
const $q = useQuasar();

const {
  reportSchedules,
  isLoading,
  getReportSchedules,
  runReportSchedule,
  deleteReportSchedule,
} = useSharedReportSchedules;

const search = ref("");

function openNewScheduleForm() {
  $q.dialog({
    component: ReportScheduleForm,
  });
}

function openEditSchedule(schedule: ReportSchedule) {
  $q.dialog({
    component: ReportScheduleForm,
    componentProps: { schedule },
  });
}

function openCloneSchedule(schedule: ReportSchedule) {
  $q.dialog({
    component: ReportScheduleForm,
    componentProps: {
      schedule: {
        ...schedule,
        name: `${schedule.name} ${t("reporting.scheduleTable.copySuffix")}`,
      },
      clone: true,
    },
  });
}

function runSchedule(schedule: ReportSchedule) {
  runReportSchedule(schedule.id);
}

function deleteSchedule(schedule: ReportSchedule) {
  $q.dialog({
    title: t("reporting.scheduleTable.deleteTitle", { name: schedule.name }),
    message: t("reporting.scheduleTable.deleteMessage"),
    cancel: true,
    color: "primary",
    ok: { label: t("reporting.common.delete"), color: "primary" },
  }).onOk(() => {
    deleteReportSchedule(schedule.id);
  });
}

onMounted(getReportSchedules);
</script>
