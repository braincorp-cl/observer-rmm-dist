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
          @click="getReportDataQueries"
        />{{ $t("reporting.dataQueryTable.title") }}
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip>{{ $t("reporting.common.close") }}</q-tooltip>
        </q-btn>
      </q-bar>
      <!-- 050 (V2-G15): PATRÓN DE REJILLA, ver composables/rejillaTabla.js. -->
      <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
      <q-table
        dense
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        :style="{ 'max-height': `${$q.screen.height - 24}px` }"
        class="tbl-sticky"
        :rows="reportDataQueries"
        :columns="columns"
        :loading="isLoading"
        :pagination="{ rowsPerPage: 0, sortBy: 'favorite', descending: true }"
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
          <q-btn
            class="q-ml-sm"
            icon="add"
            :label="$t('reporting.dataQueryTable.new')"
            no-caps
            dense
            flat
            @click="openNewDataQueryForm"
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

        <!-- 050 (V2-G15): la cabecera ordenable entra al recorrido del TAB y
             ordena con Enter o Espacio, igual que con el clic. -->
        <template #header-cell-name="props">
          <q-th
            :props="props"
            tabindex="0"
            @keydown.enter.prevent="props.sort(props.col)"
            @keydown.space.prevent="props.sort(props.col)"
            >{{ props.col.label }}</q-th
          >
        </template>

        <template #body="props">
          <q-tr
            :props="props"
            class="cursor-pointer"
            @dblclick="openEditDataQuery(props.row)"
          >
            <!-- Context Menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item v-close-popup clickable @click="cloneQuery(props.row)">
                  <q-item-section>{{
                    $t("reporting.dataQueryTable.clone")
                  }}</q-item-section>
                </q-item>

                <q-item
                  v-close-popup
                  clickable
                  @click="openEditDataQuery(props.row)"
                >
                  <q-item-section>{{
                    $t("reporting.common.edit")
                  }}</q-item-section>
                </q-item>

                <q-item
                  v-close-popup
                  clickable
                  @click="deleteDataQuery(props.row)"
                >
                  <q-item-section>{{
                    $t("reporting.common.delete")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item v-close-popup clickable>
                  <q-item-section>{{
                    $t("reporting.common.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>

            <!-- rows -->
            <!-- Host enfocable de la fila: única parada de tabulador de la
                 tabla; Enter abre Editar y la tecla Menú abre el menú
                 contextual de la fila, que antes era solo de ratón. -->
            <td>
              <span
                class="obs-rej__host"
                :data-fila="props.rowIndex"
                :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                @focus="filaFoco = props.rowIndex"
                @keydown.enter.prevent="openEditDataQuery(props.row)"
                >{{ props.row.name }}</span
              >
            </td>
          </q-tr>
        </template>
      </q-table>
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
// composition imports
import { usarRejillaTabla } from "@/composables/rejillaTabla";
import { ref, computed, onMounted } from "vue";
import { useQuasar, useDialogPluginComponent, type QTableColumn } from "quasar";
import { useI18n } from "vue-i18n";
import { useSharedReportDataQueries } from "../api/reporting";

// ui imports
import ReportDataQueryForm from "./ReportDataQueryForm.vue";

// type imports
import type { ReportDataQuery } from "../types/reporting";

// emits
defineEmits([...useDialogPluginComponent.emits]);

const { dialogRef, onDialogHide } = useDialogPluginComponent();
const $q = useQuasar();
const { t } = useI18n();

const columns = computed<QTableColumn[]>(() => [
  {
    name: "name",
    label: t("reporting.common.name"),
    field: "name",
    align: "left",
    sortable: true,
  },
]);

// reports manager logic
const {
  reportDataQueries,
  isLoading,
  getReportDataQueries,
  deleteReportDataQuery,
} = useSharedReportDataQueries;
const search = ref("");

// Patrón de rejilla: la tabla es UNA parada de tabulador y las flechas mueven la
// fila (el tope sale de `filteredSortedRows`, porque la tabla lleva `:filter`).
const tablaRejilla = ref();
const { filaFoco, alEntrarFoco, alTeclaRejilla, alDesplazarVirtual } =
  usarRejillaTabla({
    refTabla: tablaRejilla,
    filas: () => reportDataQueries.value,
  });

function openNewDataQueryForm() {
  $q.dialog({
    component: ReportDataQueryForm,
  });
}

function openEditDataQuery(dataQuery: ReportDataQuery) {
  $q.dialog({
    component: ReportDataQueryForm,
    componentProps: {
      dataQuery,
    },
  });
}

function deleteDataQuery(dataQuery: ReportDataQuery) {
  $q.dialog({
    title: t("reporting.dataQueryTable.deleteTitle", { name: dataQuery.name }),
    message: t("reporting.dataQueryTable.deleteMessage"),
    cancel: true,
    ok: { label: t("reporting.common.delete"), color: "primary" },
  }).onOk(() => {
    deleteReportDataQuery(dataQuery.id);
  });
}

async function cloneQuery(dataQuery: ReportDataQuery) {
  // TODO: fill out function
  console.log(dataQuery);
}

onMounted(getReportDataQueries);
</script>
