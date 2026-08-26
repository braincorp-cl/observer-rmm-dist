<template>
  <q-table
    dense
    flat
    bordered
    row-key="id"
    :rows="rows"
    :columns="columns"
    :loading="loading"
    :rows-per-page-options="[25, 50, 0]"
    :no-data-label="$t('erase.certificates.noData')"
    :loading-label="$t('erase.certificates.loading')"
    @row-click="onRowClick"
  >
    <template v-slot:body-cell-kind="props">
      <q-td :props="props">
        <q-badge :color="kindColor(props.row.kind)">
          {{ kindLabel(props.row.kind) }}
        </q-badge>
      </q-td>
    </template>

    <template v-slot:body-cell-verification_result="props">
      <q-td :props="props">
        <q-badge :color="resultColor(props.row.verification_result)">
          {{ resultLabel(props.row.verification_result) }}
        </q-badge>
      </q-td>
    </template>

    <template v-slot:body-cell-created_at="props">
      <q-td :props="props">{{ formatDate(props.row.created_at) }}</q-td>
    </template>

    <template v-slot:body-cell-actions="props">
      <q-td :props="props" auto-width @click.stop>
        <q-btn
          dense
          flat
          round
          size="sm"
          icon="visibility"
          :aria-label="$t('erase.certificates.view')"
          @click="$emit('view', props.row)"
        >
          <q-tooltip>{{ $t("erase.certificates.view") }}</q-tooltip>
        </q-btn>
        <q-btn
          dense
          flat
          round
          size="sm"
          icon="picture_as_pdf"
          :loading="downloading === props.row.id + ':pdf'"
          :aria-label="$t('erase.certificates.downloadPdf')"
          @click="download(props.row, 'pdf')"
        >
          <q-tooltip>{{ $t("erase.certificates.downloadPdf") }}</q-tooltip>
        </q-btn>
        <q-btn
          dense
          flat
          round
          size="sm"
          icon="data_object"
          :loading="downloading === props.row.id + ':json'"
          :aria-label="$t('erase.certificates.downloadJson')"
          @click="download(props.row, 'json')"
        >
          <q-tooltip>{{ $t("erase.certificates.downloadJson") }}</q-tooltip>
        </q-btn>
      </q-td>
    </template>
  </q-table>
</template>

<script>
// Feature 039 · Observer Erase · reportería de certificados (RF-C).
//
// Componente presentacional compartido por la vista de reportería (la flota) y
// por la pestaña de la ficha del activo (un equipo): las filas llegan por prop,
// el filtrado/carga lo hace cada anfitrión. Acá viven sólo la traducción de los
// códigos (kind, verificación) y las descargas —PDF y JSON van con el nombre
// que fijó el servidor, el mismo que quedó en la auditoría.

import { ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  fetchEraseCertificatePDF,
  fetchEraseCertificateJSON,
} from "@/api/erase";
import { formatDate } from "@/utils/format";
import { notifyError } from "@/utils/notify";

export default {
  name: "EraseCertificatesTable",
  props: {
    rows: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
  },
  emits: ["view"],
  setup(props, { emit }) {
    const { t } = useI18n();
    const downloading = ref(null);

    const columns = [
      {
        name: "certificate_id",
        label: t("erase.certificates.colId"),
        field: "certificate_id",
        align: "left",
        sortable: true,
      },
      {
        name: "kind",
        label: t("erase.certificates.colKind"),
        field: "kind",
        align: "left",
        sortable: true,
      },
      {
        name: "tenant",
        label: t("erase.certificates.colTenant"),
        field: "tenant",
        align: "left",
        sortable: true,
      },
      {
        name: "asset_tag",
        label: t("erase.certificates.colAssetTag"),
        field: "asset_tag",
        align: "left",
      },
      {
        name: "method_applied",
        label: t("erase.certificates.colMethod"),
        field: "method_applied",
        align: "left",
      },
      {
        name: "standard_ref",
        label: t("erase.certificates.colStandard"),
        field: "standard_ref",
        align: "left",
      },
      {
        name: "verification_result",
        label: t("erase.certificates.colResult"),
        field: "verification_result",
        align: "left",
        sortable: true,
      },
      {
        name: "operator",
        label: t("erase.certificates.colOperator"),
        field: "operator",
        align: "left",
      },
      {
        name: "created_at",
        label: t("erase.certificates.colCreatedAt"),
        field: "created_at",
        align: "left",
        sortable: true,
      },
      {
        name: "actions",
        label: t("erase.certificates.colActions"),
        field: "actions",
        align: "right",
      },
    ];

    // Dos clases de certificado: destrucción remota (Bloque A) y destrucción
    // física manual (C7). El color las separa; nunca se fusionan.
    function kindColor(kind) {
      return kind === "physical_destruction" ? "deep-orange" : "primary";
    }

    function kindLabel(kind) {
      return kind ? t(`erase.kind.${kind}`) : "—";
    }

    // "PASS" es el único verde; vacío o cualquier otro valor NO se pinta como
    // aprobado (el certificado dice lo que verificó, no lo que se asume).
    function resultColor(result) {
      return result === "PASS" ? "positive" : "grey";
    }

    function resultLabel(result) {
      return result || "—";
    }

    async function download(row, fmt) {
      downloading.value = `${row.id}:${fmt}`;
      try {
        const r =
          fmt === "pdf"
            ? await fetchEraseCertificatePDF(row.id)
            : await fetchEraseCertificateJSON(row.id);
        const type = fmt === "pdf" ? "application/pdf" : "application/json";
        const blob = new Blob([r.data], { type });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${row.certificate_id}.${fmt}`;
        link.click();
        // Se revoca el object URL: si no, el archivo queda vivo en memoria de la
        // pestaña hasta cerrarla.
        window.URL.revokeObjectURL(url);
      } catch (e) {
        console.error(e);
        notifyError(t("erase.certificates.downloadError"));
      } finally {
        downloading.value = null;
      }
    }

    // Pinchar la fila (fuera de los botones de acción, que frenan la
    // propagación) abre el detalle.
    function onRowClick(evt, row) {
      emit("view", row);
    }

    return {
      downloading,
      columns,
      kindColor,
      kindLabel,
      resultColor,
      resultLabel,
      download,
      onRowClick,
      formatDate,
    };
  },
};
</script>
