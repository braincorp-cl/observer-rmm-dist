<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">{{ $t("erase.view.title") }}</div>
      <q-space />
      <q-btn
        dense
        flat
        icon="refresh"
        :loading="loading"
        :aria-label="$t('erase.view.refresh')"
        @click="reload"
      >
        <q-tooltip>{{ $t("erase.view.refresh") }}</q-tooltip>
      </q-btn>
    </div>

    <q-tabs
      v-model="tab"
      dense
      class="text-grey q-mb-md"
      active-color="primary"
      indicator-color="primary"
      align="left"
      narrow-indicator
      no-caps
    >
      <q-tab name="certificates" :label="$t('erase.view.tabCertificates')" />
      <q-tab name="intake" :label="$t('erase.view.tabIntake')" />
      <q-tab name="reconciliation" :label="$t('erase.reconciliation.title')" />
    </q-tabs>
    <q-separator class="q-mb-md" />

    <!-- Certificados (Bloque C) -->
    <div v-show="tab === 'certificates'">
      <div class="row q-col-gutter-md q-mb-md">
        <div class="col-12 col-sm-4">
          <q-select
            dense
            filled
            clearable
            emit-value
            map-options
            v-model="certKind"
            :options="kindOptions"
            :label="$t('erase.view.filterKind')"
          />
        </div>
        <div class="col-12 col-sm-4">
          <q-input
            dense
            filled
            clearable
            debounce="200"
            v-model="certSearch"
            :label="$t('erase.view.search')"
          >
            <template v-slot:prepend>
              <q-icon name="search" />
            </template>
          </q-input>
        </div>
      </div>

      <EraseCertificatesTable
        :rows="filteredCerts"
        :loading="loading"
        @view="openDetail"
      />
    </div>

    <!-- Ingresos de activos (Bloque D · custodia) -->
    <div v-show="tab === 'intake'">
      <div class="row items-center q-mb-md">
        <q-btn
          color="primary"
          icon="add"
          no-caps
          :label="$t('erase.view.newIntake')"
          @click="openIntakeForm"
        />
        <q-space />
      </div>

      <q-table
        dense
        flat
        bordered
        row-key="id"
        :rows="intakes"
        :columns="intakeColumns"
        :loading="loading"
        :rows-per-page-options="[25, 50, 0]"
        :no-data-label="$t('erase.view.noIntakes')"
        :loading-label="$t('erase.certificates.loading')"
      >
        <template v-slot:body-cell-client="props">
          <q-td :props="props">{{ clientName(props.row.client) }}</q-td>
        </template>

        <template v-slot:body-cell-state="props">
          <q-td :props="props">
            <q-badge :color="intakeStateColor(props.row.state)">
              {{ $t(`erase.intake.state.${props.row.state}`) }}
            </q-badge>
          </q-td>
        </template>

        <template v-slot:body-cell-routes="props">
          <q-td :props="props">
            <q-badge
              v-if="props.row.routes_to_physical_destruction"
              color="deep-orange"
            >
              {{ $t("erase.view.routesPhysical") }}
            </q-badge>
            <span v-else>{{ dash }}</span>
          </q-td>
        </template>

        <template v-slot:body-cell-created_at="props">
          <q-td :props="props">{{ formatDate(props.row.created_at) }}</q-td>
        </template>

        <template v-slot:body-cell-actions="props">
          <q-td :props="props" auto-width>
            <q-btn
              dense
              flat
              no-caps
              size="sm"
              icon="timeline"
              :label="$t('erase.custody.view')"
              @click="openCustody(props.row)"
            />
            <q-btn
              dense
              flat
              no-caps
              size="sm"
              color="deep-orange"
              icon="delete_forever"
              :label="$t('erase.view.certifyDestruction')"
              @click="askCertify(props.row)"
            />
          </q-td>
        </template>
      </q-table>
    </div>

    <!-- Reconciliación (RF-07) · qué entró, qué se certificó y qué falta -->
    <div v-show="tab === 'reconciliation'">
      <div class="text-caption text-grey-7 q-mb-sm">
        {{ $t("erase.reconciliation.subtitle") }}
      </div>

      <div class="row q-col-gutter-md q-mb-md items-end">
        <div class="col-12 col-sm-3">
          <q-select
            dense
            filled
            clearable
            emit-value
            map-options
            v-model="recFilters.client"
            :options="clientOptions"
            :label="$t('erase.reconciliation.client')"
          />
        </div>
        <div class="col-6 col-sm-2">
          <q-input
            dense
            filled
            type="date"
            v-model="recFilters.from"
            :label="$t('erase.reconciliation.from')"
          />
        </div>
        <div class="col-6 col-sm-2">
          <q-input
            dense
            filled
            type="date"
            v-model="recFilters.to"
            :label="$t('erase.reconciliation.to')"
          />
        </div>
        <div class="col-6 col-sm-3">
          <q-input
            dense
            filled
            type="number"
            v-model.number="recFilters.stalled_days"
            :label="$t('erase.reconciliation.stalledDays')"
            :hint="$t('erase.reconciliation.stalledHint')"
          />
        </div>
        <div class="col-6 col-sm-2">
          <q-btn
            color="primary"
            no-caps
            :loading="recLoading"
            :label="$t('erase.reconciliation.run')"
            @click="loadReconciliation"
          />
        </div>
      </div>

      <div class="row q-col-gutter-md q-mb-md">
        <div
          v-for="m in recMetrics"
          :key="m.key"
          class="col-6 col-sm-3"
        >
          <q-card flat bordered>
            <q-card-section class="text-center">
              <div class="text-h5" :class="m.clase">{{ m.valor }}</div>
              <div class="text-caption text-grey-7">{{ m.label }}</div>
            </q-card-section>
          </q-card>
        </div>
      </div>

      <q-table
        dense
        flat
        bordered
        class="q-mb-md"
        row-key="client_id"
        :title="$t('erase.reconciliation.byClient')"
        :rows="recReport.by_client || []"
        :columns="recClientColumns"
        :loading="recLoading"
        hide-pagination
        :rows-per-page-options="[0]"
      />

      <!-- 🔑 El listado es el producto: el número dice cuántos faltan, esta
           tabla dice DÓNDE se detuvo cada uno. -->
      <div class="text-caption text-grey-7 q-mb-xs">
        {{ $t("erase.reconciliation.missingDefinition") }}
      </div>
      <q-table
        dense
        flat
        bordered
        row-key="intake_id"
        :title="$t('erase.reconciliation.missingTitle')"
        :rows="recReport.missing_items || []"
        :columns="recMissingColumns"
        :loading="recLoading"
        :no-data-label="$t('erase.reconciliation.empty')"
        :rows-per-page-options="[25, 50, 100]"
        v-model:pagination="recPagination"
        @request="onRecRequest"
      >
        <template v-slot:body-cell-last_event="props">
          <q-td :props="props">
            <span v-if="props.row.last_event">
              {{ labelCustodyKind(props.row.last_event.kind) }}
              <span class="text-grey-7">
                {{ sep }} {{ formatDate(props.row.last_event.at) }}
              </span>
            </span>
            <span v-else class="text-grey-7">
              {{ $t("erase.reconciliation.noEvents") }}
            </span>
          </q-td>
        </template>

        <template v-slot:body-cell-stalled="props">
          <q-td :props="props">
            <q-badge v-if="props.row.stalled" color="deep-orange">
              {{ $t("erase.reconciliation.stalled") }}
            </q-badge>
            <span v-else>{{ dash }}</span>
          </q-td>
        </template>

        <template v-slot:body-cell-received_at="props">
          <q-td :props="props">{{ formatDate(props.row.received_at) }}</q-td>
        </template>

        <template v-slot:body-cell-actions="props">
          <q-td :props="props" auto-width>
            <q-btn
              dense
              flat
              no-caps
              size="sm"
              icon="timeline"
              :label="$t('erase.custody.view')"
              @click="openCustody({ id: props.row.intake_id })"
            />
          </q-td>
        </template>
      </q-table>
    </div>

    <!-- C7 · certificar destrucción física de un ingreso -->
    <q-dialog v-model="certifyDialog">
      <q-card style="min-width: 40vw">
        <q-bar>
          {{ $t("erase.certify.title") }}
          <q-space />
          <q-btn dense flat icon="close" v-close-popup />
        </q-bar>
        <q-card-section>
          <div class="text-body2 q-mb-md">
            {{
              $t("erase.certify.prompt", {
                serial: certifyTarget?.equipment_serial || dash,
                process: certifyTarget?.process_id || dash,
              })
            }}
          </div>
          <q-input
            dense
            filled
            class="q-mb-sm"
            v-model="certifyForm.method"
            :label="$t('erase.certify.method')"
          />
          <q-input
            dense
            filled
            class="q-mb-sm"
            v-model="certifyForm.operator"
            :label="$t('erase.certify.operator')"
            :hint="$t('erase.certify.operatorHint')"
          />

          <!-- Feature 053 · RF-05: lo que se acredita decide el veredicto. El
               aviso de abajo no es decorativo: sin metodo y sin testigo el
               certificado va a DECLARAR que no hubo verificacion. -->
          <q-select
            dense
            filled
            clearable
            emit-value
            map-options
            class="q-mb-sm"
            v-model="certifyForm.verification_method"
            :options="verificationMethodOptions"
            :label="$t('erase.certify.verificationMethod')"
          />
          <q-input
            dense
            filled
            class="q-mb-sm"
            v-model="certifyForm.verification_evidence"
            :label="$t('erase.certify.verificationEvidence')"
            :hint="$t('erase.certify.verificationEvidenceHint')"
          />
          <q-file
            dense
            filled
            clearable
            class="q-mb-sm"
            accept=".jpg,.jpeg,.png,.heic,.webp,.pdf"
            v-model="certifyForm.evidence_file"
            :label="$t('erase.certify.evidenceFile')"
            :hint="$t('erase.certify.evidenceFileHint')"
          >
            <template v-slot:prepend>
              <q-icon name="attach_file" />
            </template>
          </q-file>

          <div class="text-caption text-weight-medium q-mt-md">
            {{ $t("erase.certify.concurrenceSection") }}
          </div>
          <div class="row q-col-gutter-sm q-mb-sm">
            <q-input
              class="col-12 col-sm-4"
              dense
              filled
              v-model="certifyForm.concurrence_name"
              :label="$t('erase.certify.concurrenceName')"
              :error="witnessMissing"
              :error-message="$t('erase.certify.witnessRequired')"
            />
            <q-input
              class="col-12 col-sm-4"
              dense
              filled
              v-model="certifyForm.concurrence_role"
              :label="$t('erase.certify.concurrenceRole')"
            />
            <q-input
              class="col-12 col-sm-4"
              dense
              filled
              v-model="certifyForm.concurrence_contact"
              :label="$t('erase.certify.concurrenceContact')"
            />
          </div>

          <q-banner v-if="!accredited" dense class="bg-orange-1 text-orange-9">
            <template v-slot:avatar>
              <q-icon name="gpp_maybe" color="warning" />
            </template>
            {{ $t("erase.certify.noVerificationNotice") }}
          </q-banner>

          <q-input
            dense
            filled
            type="textarea"
            autogrow
            class="q-mt-sm"
            v-model="certifyForm.reason"
            :label="$t('erase.certify.reason')"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat :label="$t('erase.certify.cancel')" v-close-popup />
          <q-btn
            color="deep-orange"
            :loading="certifying"
            :disable="witnessMissing"
            :label="$t('erase.certify.emit')"
            @click="doCertify"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script>
// Feature 039 · Observer Erase · T030 — la consola de certificados (RF-C) y la
// custodia de activos (Bloque D). Dos pestañas: la reportería de certificados
// (sólo lectura, con descargas) y los ingresos de activos, desde donde se
// certifica la destrucción física (C7) —el flujo de valor que no necesita ni el
// Bloque A ni el Bloque B.
//
// Sin gating por permiso en el cliente: el alcance lo recorta `filter_by_role`
// en el servidor y el 403 lo traduce a un toast el interceptor de axios.

import { onMounted, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar } from "quasar";

import EraseCertificatesTable from "@/components/agents/EraseCertificatesTable.vue";
import EraseCertificateDetailDialog from "@/components/agents/EraseCertificateDetailDialog.vue";
import AssetIntakeForm from "@/components/agents/AssetIntakeForm.vue";
import AssetCustodyTimeline from "@/components/agents/AssetCustodyTimeline.vue";
import {
  fetchEraseCertificates,
  fetchAssetIntakes,
  certifyAssetDestruction,
  fetchReconciliation,
} from "@/api/erase";
import { fetchClients } from "@/api/clients";
import { labelDisposition, labelCustodyKind } from "@/utils/erase";
import { formatDate } from "@/utils/format";
import { notifySuccess, notifyError } from "@/utils/notify";

export default {
  name: "EraseCertificatesView",
  components: { EraseCertificatesTable },
  setup() {
    const { t } = useI18n();
    const $q = useQuasar();

    const dash = "—";
    // Separador de texto: va por variable y no literal en la plantilla, porque
    // el gate `lint:i18n` trata cualquier texto crudo como falta de traducción.
    const sep = "·";
    const tab = ref("certificates");
    const loading = ref(false);

    const certs = ref([]);
    const intakes = ref([]);
    const clientsById = ref({});

    // Filtros de la reportería: son de cliente (el listado no pagina ni filtra
    // por tipo en el servidor), así que se aplican sobre las filas cargadas.
    const certKind = ref(null);
    const certSearch = ref("");

    const kindOptions = [
      { value: "remote_destruction", label: t("erase.kind.remote_destruction") },
      {
        value: "physical_destruction",
        label: t("erase.kind.physical_destruction"),
      },
    ];

    const filteredCerts = computed(() => {
      let rows = certs.value;
      if (certKind.value) rows = rows.filter((c) => c.kind === certKind.value);
      const q = (certSearch.value || "").trim().toLowerCase();
      if (q) {
        rows = rows.filter((c) =>
          [c.certificate_id, c.tenant, c.asset_tag, c.operator]
            .filter(Boolean)
            .some((v) => String(v).toLowerCase().includes(q)),
        );
      }
      return rows;
    });

    const intakeColumns = [
      {
        name: "process_id",
        label: t("erase.view.colProcess"),
        field: "process_id",
        align: "left",
        sortable: true,
      },
      {
        name: "client",
        label: t("erase.view.colClient"),
        field: "client",
        align: "left",
      },
      {
        name: "equipment_serial",
        label: t("erase.view.colEquipmentSerial"),
        field: "equipment_serial",
        align: "left",
      },
      {
        name: "asset_tag",
        label: t("erase.view.colAssetTag"),
        field: "asset_tag",
        align: "left",
      },
      {
        name: "state",
        label: t("erase.view.colState"),
        field: "state",
        align: "left",
        sortable: true,
      },
      {
        // RF-03: el destino se ve en el listado, no solo dentro del acta — es
        // lo que permite revisar de un golpe qué activos ya tienen su destino
        // declarado y cuáles no.
        name: "media_disposition",
        label: t("erase.view.colDisposition"),
        field: "media_disposition",
        align: "left",
        sortable: true,
        format: (val) => labelDisposition(val) || dash,
      },
      {
        name: "routes",
        label: t("erase.view.colRoutes"),
        field: "routes_to_physical_destruction",
        align: "left",
      },
      {
        name: "created_at",
        label: t("erase.view.colCreatedAt"),
        field: "created_at",
        align: "left",
        sortable: true,
      },
      {
        name: "actions",
        label: t("erase.view.colActions"),
        field: "actions",
        align: "right",
      },
    ];

    function clientName(id) {
      return clientsById.value[id] ?? dash;
    }

    // --- Cadena de custodia (RF-06) -----------------------------------------

    function openCustody(row) {
      $q.dialog({
        component: AssetCustodyTimeline,
        componentProps: { intakeId: row.id },
      });
    }

    // --- Reconciliación (RF-07) ---------------------------------------------

    const recLoading = ref(false);
    const recReport = ref({});
    const recFilters = ref({
      client: null,
      from: "",
      to: "",
      stalled_days: null,
    });

    // 🔑 Paginación del SERVIDOR, no de la tabla: el informe puede tener miles
    // de faltantes y la respuesta trae sólo la página pedida. `rowsNumber` sale
    // de `missing_page.total`, que es lo que deja a la tabla saber que hay más.
    const recPagination = ref({
      page: 1,
      rowsPerPage: 25,
      rowsNumber: 0,
    });

    const clientOptions = computed(() =>
      Object.entries(clientsById.value).map(([value, label]) => ({
        value: Number(value),
        label,
      })),
    );

    const recMetrics = computed(() => {
      const t0 = recReport.value.totals ?? {};
      return [
        {
          key: "intakes",
          label: t("erase.reconciliation.intakes"),
          valor: t0.intakes ?? 0,
          clase: "",
        },
        {
          key: "certified",
          label: t("erase.reconciliation.certified"),
          valor: t0.certified ?? 0,
          clase: "text-positive",
        },
        {
          key: "missing",
          label: t("erase.reconciliation.missing"),
          valor: t0.missing ?? 0,
          clase: "text-deep-orange",
        },
        {
          key: "stalled",
          label: t("erase.reconciliation.stalled"),
          valor: t0.stalled ?? 0,
          clase: "text-negative",
        },
      ];
    });

    const recClientColumns = [
      {
        name: "client",
        label: t("erase.reconciliation.client"),
        field: "client",
        align: "left",
        sortable: true,
      },
      {
        name: "intakes",
        label: t("erase.reconciliation.intakes"),
        field: "intakes",
        align: "right",
        sortable: true,
      },
      {
        name: "certified",
        label: t("erase.reconciliation.certified"),
        field: "certified",
        align: "right",
        sortable: true,
      },
      {
        name: "missing",
        label: t("erase.reconciliation.missing"),
        field: "missing",
        align: "right",
        sortable: true,
      },
      {
        name: "stalled",
        label: t("erase.reconciliation.stalled"),
        field: "stalled",
        align: "right",
        sortable: true,
      },
    ];

    const recMissingColumns = [
      {
        name: "process_id",
        label: t("erase.reconciliation.processId"),
        field: "process_id",
        align: "left",
        sortable: true,
      },
      {
        name: "equipment_serial",
        label: t("erase.reconciliation.equipmentSerial"),
        field: "equipment_serial",
        align: "left",
      },
      {
        name: "received_at",
        label: t("erase.reconciliation.receivedAt"),
        field: "received_at",
        align: "left",
        sortable: true,
      },
      {
        name: "days_open",
        label: t("erase.reconciliation.daysOpen"),
        field: "days_open",
        align: "right",
        sortable: true,
      },
      {
        // 🔑 Esta columna es la que convierte el número en una acción.
        name: "last_event",
        label: t("erase.reconciliation.lastEvent"),
        field: "last_event",
        align: "left",
      },
      {
        name: "stalled",
        label: t("erase.reconciliation.stalled"),
        field: "stalled",
        align: "left",
      },
      { name: "actions", label: "", field: "actions", align: "right" },
    ];

    async function onRecRequest(props) {
      const { page, rowsPerPage } = props.pagination;
      recPagination.value.page = page;
      recPagination.value.rowsPerPage = rowsPerPage;
      await loadReconciliation();
    }

    async function loadReconciliation() {
      recLoading.value = true;
      try {
        // Sólo se mandan los filtros con valor: un `from` vacío daría 400.
        const params = {
          limit: recPagination.value.rowsPerPage,
          offset:
            (recPagination.value.page - 1) * recPagination.value.rowsPerPage,
        };
        if (recFilters.value.client) params.client = recFilters.value.client;
        if (recFilters.value.from) params.from = recFilters.value.from;
        if (recFilters.value.to) params.to = recFilters.value.to;
        if (recFilters.value.stalled_days) {
          params.stalled_days = recFilters.value.stalled_days;
        }
        recReport.value = await fetchReconciliation(params);
        recPagination.value.rowsNumber = recReport.value.missing_page?.total ?? 0;
      } catch (e) {
        notifyError(t("erase.reconciliation.loadError"));
      } finally {
        recLoading.value = false;
      }
    }

    function intakeStateColor(state) {
      if (state === "functional") return "primary";
      return "deep-orange";
    }

    async function loadCerts() {
      certs.value = (await fetchEraseCertificates()) ?? [];
    }

    async function loadIntakes() {
      intakes.value = (await fetchAssetIntakes()) ?? [];
    }

    async function loadClients() {
      const data = (await fetchClients()) ?? [];
      const map = {};
      data.forEach((c) => {
        map[c.id] = c.name;
      });
      clientsById.value = map;
    }

    async function reload() {
      loading.value = true;
      try {
        await Promise.all([loadCerts(), loadIntakes(), loadClients()]);
      } finally {
        loading.value = false;
      }
    }

    function openDetail(row) {
      $q.dialog({
        component: EraseCertificateDetailDialog,
        componentProps: { pk: row.id },
      });
    }

    function openIntakeForm() {
      $q.dialog({ component: AssetIntakeForm }).onOk(() => loadIntakes());
    }

    // --- C7 certificar destrucción ---
    const certifyDialog = ref(false);
    const certifying = ref(false);
    const certifyTarget = ref(null);
    function certifyFormVacio() {
      return {
      method: "",
      operator: "",
      reason: "",
      verification_method: "",
      verification_evidence: "",
      concurrence_name: "",
      concurrence_role: "",
      concurrence_contact: "",
      evidence_file: null,
    };
    }

    const certifyForm = ref(certifyFormVacio());

    // Mismo orden que `DestructionVerification` en el modelo. `none` entra como
    // opcion EXPLICITA: declarar que no se acredito nada es un acto consciente,
    // no un campo que se quedo sin llenar.
    const verificationMethodOptions = [
      "none",
      "witnessed",
      "photographic",
      "weighed",
      "vendor_certificate",
    ].map((value) => ({ value, label: t(`erase.verificationMethod.${value}`) }));

    // Lo mismo que decide el backend (T008): metodo distinto de "ninguno" Y
    // testigo nombrado. Se replica aca solo para avisar, no para autorizar: el
    // veredicto lo pone el servidor.
    const accredited = computed(() => {
      const m = certifyForm.value.verification_method;
      return !!(
        m && m !== "none" && (certifyForm.value.concurrence_name || "").trim()
      );
    });

    // La unica combinacion que el serializer rechaza con 400.
    const witnessMissing = computed(
      () =>
        certifyForm.value.verification_method === "witnessed" &&
        !(certifyForm.value.concurrence_name || "").trim(),
    );

    function askCertify(row) {
      certifyTarget.value = row;
      certifyForm.value = certifyFormVacio();
      certifyDialog.value = true;
    }

    async function doCertify() {
      certifying.value = true;
      try {
        const cert = await certifyAssetDestruction(
          certifyTarget.value.id,
          certifyForm.value,
        );
        notifySuccess(
          t("erase.certify.emitted", { id: cert.certificate_id }),
        );
        certifyDialog.value = false;
        await Promise.all([loadCerts(), loadIntakes()]);
      } catch (e) {
        console.error(e);
        notifyError(t("erase.certify.error"));
      } finally {
        certifying.value = false;
      }
    }

    onMounted(reload);

    return {
      dash,
      sep,
      tab,
      loading,
      certs,
      intakes,
      certKind,
      certSearch,
      kindOptions,
      filteredCerts,
      intakeColumns,
      verificationMethodOptions,
      accredited,
      witnessMissing,
      clientName,
      intakeStateColor,
      reload,
      openDetail,
      openIntakeForm,
      certifyDialog,
      certifying,
      certifyTarget,
      certifyForm,
      askCertify,
      doCertify,
      formatDate,
      openCustody,
      labelCustodyKind,
      recLoading,
      recReport,
      recFilters,
      recMetrics,
      recClientColumns,
      recMissingColumns,
      clientOptions,
      recPagination,
      onRecRequest,
      loadReconciliation,
    };
  },
};
</script>
