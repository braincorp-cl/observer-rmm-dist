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
          @click="getReportTemplates()"
        />{{ $t("reporting.manager.title") }}
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip class="bg-white text-primary">{{
            $t("reporting.common.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-table
        dense
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        :style="{ 'max-height': `${$q.screen.height - 32}px` }"
        class="tbl-sticky"
        :rows="reportTemplates"
        :columns="columns"
        :loading="isLoading"
        :pagination="{ rowsPerPage: 0, sortBy: 'name', descending: false }"
        :filter="search"
        row-key="id"
        binary-state-sort
        virtual-scroll
        :rows-per-page-options="[0]"
      >
        <template #top>
          <!--
            Feature 007 · BrainCorp deshabilita la CREACIÓN/importación de
            reportes por el usuario final (dropdown "Agregar/Importar" removido).
            Los reportes los arma BrainCorp y se suman al Gestor. Se conservan
            Plantillas base, Recursos, Consultas, Programaciones e Historial.
          -->
          <q-btn
            class="q-ml-sm"
            :label="$t('reporting.manager.baseTemplates')"
            no-caps
            dense
            flat
            @click="openHTMLTemplates"
          />
          <q-btn
            class="q-ml-sm"
            :label="$t('reporting.manager.reportAssets')"
            no-caps
            dense
            flat
            @click="openReportAssets"
          />
          <q-btn
            class="q-ml-sm"
            :label="$t('reporting.manager.dataQueries')"
            no-caps
            dense
            flat
            @click="openDataQueries"
          />
          <q-btn
            @click="openReportSchedules"
            class="q-ml-sm"
            :label="$t('reporting.manager.reportSchedules')"
            no-caps
            dense
            flat
          />
          <q-btn
            @click="openReportHistory"
            class="q-ml-sm"
            :label="$t('reporting.manager.reportRunHistory')"
            no-caps
            dense
            flat
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
              <q-icon name="search" color="primary" />
            </template>
          </q-input>
        </template>

        <template #body="props">
          <q-tr
            :props="props"
            class="cursor-pointer"
            @dblclick="
              openReport(
                props.row.id,
                props.row.type !== 'plaintext' ? 'html' : 'plaintext',
                props.row.depends_on,
                {},
              )
            "
          >
            <!-- Context Menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <!--
                  Feature 007 · BrainCorp deshabilita la autoría de reportes por
                  el usuario final (Editar / Clonar / Exportar). Los reportes se
                  solicitan a BrainCorp y se suman al Gestor. Ver también el
                  @dblclick de la fila (arriba) que también abría Editar.
                -->
                <q-item
                  v-close-popup
                  clickable
                  @click="
                    openReport(props.row.id, 'pdf', props.row.depends_on, {})
                  "
                >
                  <q-item-section>{{
                    $t("reporting.manager.openPdfReport")
                  }}</q-item-section>
                </q-item>

                <q-item
                  v-close-popup
                  clickable
                  @click="
                    openReport(
                      props.row.id,
                      props.row.type !== 'plaintext' ? 'html' : 'plaintext',
                      props.row.depends_on,
                      {},
                    )
                  "
                >
                  <q-item-section>{{
                    $t("reporting.manager.openReport", {
                      type:
                        props.row.type !== "plaintext"
                          ? "HTML"
                          : $t("reporting.manager.formatText"),
                    })
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <q-item
                  v-close-popup
                  clickable
                  @click="downloadReport(props.row, 'pdf', {})"
                >
                  <q-item-section>{{
                    $t("reporting.manager.downloadPdfReport")
                  }}</q-item-section>
                </q-item>

                <q-item
                  v-close-popup
                  clickable
                  @click="
                    downloadReport(
                      props.row,
                      props.row.type !== 'plaintext' ? 'html' : 'plaintext',
                      {},
                    )
                  "
                >
                  <q-item-section>{{
                    $t("reporting.manager.downloadReport", {
                      type:
                        props.row.type !== "plaintext"
                          ? "HTML"
                          : $t("reporting.manager.formatText"),
                    })
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <q-item
                  v-close-popup
                  clickable
                  @click="scheduleReport(props.row)"
                >
                  <q-item-section>{{
                    $t("reporting.manager.scheduleReport")
                  }}</q-item-section>
                </q-item>

                <q-item v-close-popup clickable @click="emailReport(props.row)">
                  <q-item-section>{{
                    $t("reporting.manager.emailReport")
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <q-item
                  v-close-popup
                  clickable
                  @click="deleteTemplate(props.row)"
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

            <!-- rows -->
            <td>{{ props.row.name }}</td>
            <td>{{ capitalize(props.row.type) }}</td>
            <td>
              {{
                props.row.depends_on.length > 0
                  ? props.row.depends_on.join(", ")
                  : ""
              }}
            </td>
          </q-tr>
        </template>
      </q-table>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent, type QTableColumn } from "quasar";
import { useSharedReportTemplates } from "../api/reporting";
import { capitalize } from "@/utils/format";

// ui imports
import ReportAssets from "./ReportAssets.vue";
import ReportHTMLTemplateTable from "./ReportHTMLTemplateTable.vue";
import ReportDataQueryTable from "./ReportDataQueryTable.vue";
import ReportScheduleTable from "./ReportScheduleTable.vue";
import ReportHistoryTable from "./ReportHistoryTable.vue";
import ReportScheduleForm from "./ReportScheduleForm.vue";

// type imports
import type { ReportTemplate } from "../types/reporting";

const { t } = useI18n();

// i18n-aware columns (computed for language reactivity)
const columns = computed<QTableColumn[]>(() => [
  {
    name: "name",
    label: t("reporting.common.name"),
    field: "name",
    align: "left",
    sortable: true,
  },
  {
    name: "type",
    label: t("reporting.manager.colType"),
    field: "type",
    align: "left",
    sortable: true,
  },
  {
    name: "depends_on",
    label: t("reporting.manager.colDependencies"),
    field: "depends_on",
    align: "left",
    sortable: true,
  },
]);

// emits
defineEmits([...useDialogPluginComponent.emits]);

const { dialogRef, onDialogHide } = useDialogPluginComponent();
const $q = useQuasar();

// reports manager logic
const {
  reportTemplates,
  isLoading,
  getReportTemplates,
  deleteReportTemplate,
  openReport,
  downloadReport,
} = useSharedReportTemplates;

onMounted(getReportTemplates);
const search = ref("");

function openReportAssets() {
  $q.dialog({
    component: ReportAssets,
  });
}

function openDataQueries() {
  $q.dialog({
    component: ReportDataQueryTable,
  });
}

function openHTMLTemplates() {
  $q.dialog({
    component: ReportHTMLTemplateTable,
  });
}

function openReportSchedules() {
  $q.dialog({
    component: ReportScheduleTable,
  });
}

function openReportHistory() {
  $q.dialog({
    component: ReportHistoryTable,
  });
}

function scheduleReport(template: ReportTemplate) {
  $q.dialog({
    component: ReportScheduleForm,
    componentProps: {
      reportTemplate: template.id,
    },
  });
}

function emailReport(template: ReportTemplate) {
  $q.dialog({
    component: ReportScheduleForm,
    componentProps: {
      reportTemplate: template.id,
      emailOnly: true,
    },
  });
}

function deleteTemplate(template: ReportTemplate) {
  $q.dialog({
    title: t("reporting.manager.deleteTitle", { name: template.name }),
    cancel: true,
    ok: { label: t("reporting.common.delete"), color: "negative" },
  }).onOk(() => {
    deleteReportTemplate(template.id);
  });
}

</script>
