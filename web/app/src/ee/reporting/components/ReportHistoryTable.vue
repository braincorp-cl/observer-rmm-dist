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
          @click="getReportHistory"
        />{{ $t("reporting.historyTable.title") }}
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip>{{ $t("reporting.common.close") }}</q-tooltip>
        </q-btn>
      </q-bar>

      <!-- 🪤 050 (V2-G15): PATRÓN DE REJILLA, ver composables/rejillaTabla.js. -->
      <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
      <q-table
        dense
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        :style="{ 'max-height': `${$q.screen.height - 24}px` }"
        class="tbl-sticky"
        :rows="reportHistory"
        :columns="columns"
        :loading="isLoading"
        :pagination="{
          rowsPerPage: 0,
          sortBy: 'date_created',
          descending: true,
        }"
        :filter="search"
        row-key="id"
        binary-state-sort
        virtual-scroll
        @virtual-scroll="alDesplazarVirtual"
        :virtual-scroll-item-size="33"
        :virtual-scroll-sticky-size-start="28"
        :rows-per-page-options="[0]"
        ref="tablaRejilla"
      >
        <template #top>
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

        <template #header-cell-report_template_name="props">
          <q-th auto-width :props="props">{{ props.col.label }}</q-th>
        </template>

        <template #body="props">
          <q-tr :props="props" class="cursor-pointer">
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item
                  v-close-popup
                  clickable
                  :disabled="props.row.error_data"
                  @click="openReportHistory(props.row.id, 'pdf')"
                >
                  <q-item-section side>
                    <q-icon name="mdi-file-pdf-box" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("reporting.historyTable.openPdfReport")
                  }}</q-item-section>
                </q-item>

                <q-item
                  v-close-popup
                  clickable
                  :disabled="props.row.error_data"
                  @click="
                    openReportHistory(
                      props.row.id,
                      props.row.report_template_type !== 'plaintext'
                        ? 'html'
                        : 'plaintext',
                    )
                  "
                >
                  <q-item-section side>
                    <q-icon
                      :name="
                        props.row.report_template_type !== 'plaintext'
                          ? 'code'
                          : 'description'
                      "
                    />
                  </q-item-section>
                  <q-item-section>{{
                    $t("reporting.historyTable.openTypeReport", {
                      type:
                        props.row.report_template_type !== "plaintext"
                          ? "HTML"
                          : $t("reporting.historyTable.typeText"),
                    })
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <q-item
                  v-close-popup
                  clickable
                  :disabled="props.row.error_data"
                  @click="
                    downloadReportHistory(
                      props.row.id,
                      props.row.report_template_name,
                      'pdf',
                    )
                  "
                >
                  <q-item-section side>
                    <q-icon name="mdi-download" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("reporting.historyTable.downloadPdfReport")
                  }}</q-item-section>
                </q-item>

                <q-item
                  v-close-popup
                  clickable
                  :disabled="props.row.error_data"
                  @click="
                    downloadReportHistory(
                      props.row.id,
                      props.row.report_template_name,
                      props.row.report_template_type !== 'plaintext'
                        ? 'html'
                        : 'plaintext',
                    )
                  "
                >
                  <q-item-section side>
                    <q-icon name="mdi-download" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("reporting.historyTable.downloadTypeReport", {
                      type:
                        props.row.report_template_type !== "plaintext"
                          ? "HTML"
                          : $t("reporting.historyTable.typeText"),
                    })
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <q-item
                  v-close-popup
                  clickable
                  @click="deleteHistory(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
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
              <template v-if="col.name === 'error_data'">
                <!-- 050 (T046, G05): envolver el ícono en un botón `round`
                     no bastó — sin fondo, sin borde y sin rótulo, la única
                     superficie propia del control seguía siendo el triángulo
                     rojo, o sea un color de estado haciendo de rótulo. Ahora el
                     control lleva su rótulo de acción en teal. -->
                <!-- 🔴 050 (G05, 17.ª corrida): y la segunda mitad de ese
                     arreglo estaba mal. El rojo se dejó «en la insignia de
                     estado que va dentro, el mismo patrón del botón
                     Dependencias (T044)», pero no había ninguna insignia: era
                     un q-icon sin fondo ni borde propios cuyo texto entra en el
                     textContent del botón, o sea parte del RÓTULO, que el
                     criterio nombra expresamente como superficie propia del
                     control. Acá el rojo además no informaba nada: el botón
                     sólo existe con `v-if="props.row.error_data"`, así que su
                     presencia ya dice que hay error. El glifo se queda —sirve
                     para barrer la columna— y hereda el teal de la acción: la
                     FORMA lleva el significado, el COLOR lleva el rol. -->
                <!-- `tabindex="-1"`: se alcanza con la flecha derecha desde el
                     host de la fila (patrón de rejilla). -->
                <q-btn
                  v-if="props.row.error_data"
                  flat
                  dense
                  no-caps
                  color="primary"
                  tabindex="-1"
                  @click="openErrorMessage(props.row.error_data)"
                >
                  <q-icon name="warning" size="xs" class="q-mr-xs" />
                  {{ $t("reporting.historyTable.showError") }}
                </q-btn>
              </template>

              <!-- Host enfocable de la fila, en la PRIMERA columna del bucle
                   genérico: es la única parada de tabulador de la tabla, y desde
                   ella la tecla Menú abre el menú contextual de la fila —que
                   antes era sólo de ratón. -->
              <template v-else-if="col.name === props.cols[0].name">
                <span
                  class="obs-rej__host"
                  :data-fila="props.rowIndex"
                  :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                  @focus="filaFoco = props.rowIndex"
                  >{{ col.value }}</span
                >
              </template>

              <template v-else>
                {{ col.value }}
              </template>
            </q-td>
          </q-tr>
        </template>
      </q-table>
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { usarRejillaTabla } from "@/composables/rejillaTabla";
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent, type QTableColumn } from "quasar";
import { formatDate, capitalize } from "@/utils/format";
import { useSharedReportHistory } from "../api/reporting";
import type { ReportHistory } from "../types/reporting";

const { t } = useI18n();

// i18n-aware columns (computed for language reactivity)
const columns = computed<QTableColumn[]>(() => [
  {
    name: "report_template_name",
    label: t("reporting.historyTable.colTemplate"),
    field: "report_template_name",
    align: "left",
    sortable: true,
  },
  {
    name: "error_data",
    label: "",
    field: "error_data",
    align: "left",
    sortable: true,
  },
  {
    name: "report_template_type",
    label: t("reporting.historyTable.colTemplateType"),
    field: "report_template_type",
    align: "left",
    sortable: true,
    format: (val: string) => capitalize(val),
  },
  {
    name: "date_created",
    label: t("reporting.historyTable.colDateCreated"),
    field: "date_created",
    align: "left",
    sortable: true,
    format: (val: string) => formatDate(val),
  },
]);

// emits
defineEmits([...useDialogPluginComponent.emits]);

const { dialogRef, onDialogHide } = useDialogPluginComponent();
const $q = useQuasar();

const {
  reportHistory,
  isLoading,
  getReportHistory,
  deleteReportHistory,
  openReportHistory,
  downloadReportHistory,
} = useSharedReportHistory;

const search = ref("");

// Patrón de rejilla: la tabla es UNA parada de tabulador y las flechas mueven la
// fila. El tope real sale de `filteredSortedRows` de la propia tabla, que es lo
// que importa acá porque esta tabla lleva `:filter="search"`.
const tablaRejilla = ref();
const { filaFoco, alEntrarFoco, alTeclaRejilla, alDesplazarVirtual } =
  usarRejillaTabla({
    refTabla: tablaRejilla,
    filas: () => reportHistory.value,
  });

// Confirm and delete
function deleteHistory(entry: ReportHistory) {
  $q.dialog({
    title: t("reporting.historyTable.deleteTitle", {
      name: entry.report_template_name,
    }),
    message: t("reporting.historyTable.deleteMessage"),
    color: "primary",
    cancel: true,
    ok: { label: t("reporting.common.delete"), color: "primary" },
  }).onOk(() => {
    deleteReportHistory(entry.id);
  });
}

function openErrorMessage(msg: string) {
  $q.dialog({
    message: msg,
    color: "primary",
  });
}
onMounted(getReportHistory);
</script>
