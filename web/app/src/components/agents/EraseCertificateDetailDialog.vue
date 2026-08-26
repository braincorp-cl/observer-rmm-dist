<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="min-width: 60vw; max-width: 90vw">
      <q-bar>
        {{ $t("erase.detail.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip>{{ $t("erase.detail.close") }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section v-if="loading" class="row justify-center q-pa-lg">
        <q-spinner size="2em" color="primary" />
      </q-card-section>

      <template v-else-if="cert">
        <!-- El veredicto de integridad va primero: es lo que hace verificable a
             un certificado, no un adorno. Documento, firma y cadena por
             separado — que la firma no esté presente NO invalida el documento. -->
        <q-card-section>
          <div class="row items-center q-gutter-sm">
            <q-badge
              :color="verification.valid ? 'positive' : 'negative'"
              class="text-body2 q-pa-sm"
            >
              <q-icon
                :name="verification.valid ? 'verified' : 'gpp_bad'"
                class="q-mr-xs"
              />
              {{
                verification.valid
                  ? $t("erase.detail.valid")
                  : $t("erase.detail.invalid")
              }}
            </q-badge>
            <q-chip dense :color="chipColor(verification.document_intact)" text-color="white">
              {{ $t("erase.detail.documentIntact") }}
            </q-chip>
            <q-chip
              dense
              :color="signatureChipColor"
              text-color="white"
            >
              {{ signatureChipLabel }}
            </q-chip>
            <q-chip dense :color="chipColor(verification.chain_intact)" text-color="white">
              {{ $t("erase.detail.chainIntact") }}
            </q-chip>
          </div>
        </q-card-section>

        <q-separator />

        <q-card-section class="scroll" style="max-height: 55vh">
          <table class="oe-detail-table">
            <tbody>
              <tr v-for="field in fields" :key="field.key">
                <th>{{ field.label }}</th>
                <td>{{ field.value }}</td>
              </tr>
            </tbody>
          </table>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn
            flat
            icon="picture_as_pdf"
            :label="$t('erase.certificates.downloadPdf')"
            :loading="downloading === 'pdf'"
            @click="download('pdf')"
          />
          <q-btn
            flat
            icon="data_object"
            :label="$t('erase.certificates.downloadJson')"
            :loading="downloading === 'json'"
            @click="download('json')"
          />
          <q-btn
            flat
            color="primary"
            :label="$t('erase.detail.close')"
            v-close-popup
          />
        </q-card-actions>
      </template>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 039 · Observer Erase · detalle de un certificado.
//
// Lee el certificado completo y el resultado de verificarlo (documento, firma,
// cadena) —que el servidor recalcula en cada lectura— y ofrece las descargas.
// Sólo lectura: un certificado emitido es append-only, no hay nada que editar.

import { onMounted, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";

import {
  fetchEraseCertificate,
  fetchEraseCertificatePDF,
  fetchEraseCertificateJSON,
} from "@/api/erase";
import { formatDate } from "@/utils/format";
import { notifyError } from "@/utils/notify";

export default {
  name: "EraseCertificateDetailDialog",
  props: {
    pk: { type: Number, required: true },
  },
  emits: [...useDialogPluginComponent.emits],
  setup(props) {
    const { t } = useI18n();
    const { dialogRef, onDialogHide } = useDialogPluginComponent();

    const loading = ref(true);
    const cert = ref(null);
    const verification = ref({});
    const downloading = ref(null);

    // Guion largo del "sin valor", por binding y no como literal en el template
    // (el gate i18n no-raw-text marca cualquier texto suelto).
    const dash = "—";

    // Los campos se arman como lista label/valor para pintarlos por binding: el
    // gate i18n (no-raw-text) marca cualquier literal suelto en el template.
    const fields = computed(() => {
      const c = cert.value;
      if (!c) return [];
      return [
        { key: "certificate_id", label: t("erase.detail.certificateId"), value: c.certificate_id || dash },
        { key: "kind", label: t("erase.detail.kind"), value: c.kind ? t(`erase.kind.${c.kind}`) : dash },
        { key: "tenant", label: t("erase.detail.tenant"), value: c.tenant || dash },
        { key: "asset_tag", label: t("erase.detail.assetTag"), value: c.asset_tag || dash },
        { key: "method_applied", label: t("erase.detail.method"), value: c.method_applied || dash },
        { key: "standard_ref", label: t("erase.detail.standard"), value: c.standard_ref || dash },
        { key: "verification_result", label: t("erase.detail.result"), value: c.verification_result || dash },
        { key: "operator", label: t("erase.detail.operator"), value: c.operator || dash },
        { key: "started_at", label: t("erase.detail.startedAt"), value: c.started_at ? formatDate(c.started_at) : dash },
        { key: "finished_at", label: t("erase.detail.finishedAt"), value: c.finished_at ? formatDate(c.finished_at) : dash },
        { key: "software_version", label: t("erase.detail.softwareVersion"), value: c.software_version || dash },
        { key: "created_at", label: t("erase.detail.createdAt"), value: c.created_at ? formatDate(c.created_at) : dash },
        { key: "document_hash", label: t("erase.detail.documentHash"), value: c.document_hash || dash },
        { key: "signature_alg", label: t("erase.detail.signatureAlg"), value: c.signature_alg || dash },
        { key: "signing_key_id", label: t("erase.detail.signingKeyId"), value: c.signing_key_id || dash },
      ];
    });

    function chipColor(ok) {
      return ok ? "positive" : "negative";
    }

    // La firma tiene tres estados, no dos: válida, inválida, o ausente (el
    // certificado sin B firma el documento pero puede no llevar FEA). "Ausente"
    // NO es "inválida", así que se pinta distinto.
    const signatureChipColor = computed(() => {
      if (!verification.value.signature_present) return "grey";
      return verification.value.signature_valid ? "positive" : "negative";
    });

    const signatureChipLabel = computed(() => {
      if (!verification.value.signature_present) {
        return t("erase.detail.signatureAbsent");
      }
      return verification.value.signature_valid
        ? t("erase.detail.signatureValid")
        : t("erase.detail.signatureInvalid");
    });

    async function load() {
      loading.value = true;
      try {
        const data = await fetchEraseCertificate(props.pk);
        cert.value = data;
        verification.value = data?.verification ?? {};
      } catch (e) {
        console.error(e);
        notifyError(t("erase.detail.loadError"));
      } finally {
        loading.value = false;
      }
    }

    async function download(fmt) {
      downloading.value = fmt;
      try {
        const r =
          fmt === "pdf"
            ? await fetchEraseCertificatePDF(props.pk)
            : await fetchEraseCertificateJSON(props.pk);
        const type = fmt === "pdf" ? "application/pdf" : "application/json";
        const blob = new Blob([r.data], { type });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${cert.value.certificate_id}.${fmt}`;
        link.click();
        window.URL.revokeObjectURL(url);
      } catch (e) {
        console.error(e);
        notifyError(t("erase.certificates.downloadError"));
      } finally {
        downloading.value = null;
      }
    }

    onMounted(load);

    return {
      dialogRef,
      onDialogHide,
      loading,
      cert,
      verification,
      fields,
      downloading,
      chipColor,
      signatureChipColor,
      signatureChipLabel,
      download,
    };
  },
};
</script>

<style scoped>
.oe-detail-table {
  width: 100%;
  border-collapse: collapse;
}
.oe-detail-table th,
.oe-detail-table td {
  text-align: left;
  padding: 5px 8px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.2);
  vertical-align: top;
  font-size: 13px;
}
.oe-detail-table th {
  width: 30%;
  font-weight: 600;
  opacity: 0.75;
}
.oe-detail-table td {
  word-break: break-all;
}
</style>
