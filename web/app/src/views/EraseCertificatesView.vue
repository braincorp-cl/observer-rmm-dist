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
              color="deep-orange"
              icon="delete_forever"
              :label="$t('erase.view.certifyDestruction')"
              @click="askCertify(props.row)"
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
          <q-input
            dense
            filled
            type="textarea"
            autogrow
            v-model="certifyForm.reason"
            :label="$t('erase.certify.reason')"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat :label="$t('erase.certify.cancel')" v-close-popup />
          <q-btn
            color="deep-orange"
            :loading="certifying"
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
import {
  fetchEraseCertificates,
  fetchAssetIntakes,
  certifyAssetDestruction,
} from "@/api/erase";
import { fetchClients } from "@/api/clients";
import { formatDate } from "@/utils/format";
import { notifySuccess, notifyError } from "@/utils/notify";

export default {
  name: "EraseCertificatesView",
  components: { EraseCertificatesTable },
  setup() {
    const { t } = useI18n();
    const $q = useQuasar();

    const dash = "—";
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
    const certifyForm = ref({ method: "", operator: "", reason: "" });

    function askCertify(row) {
      certifyTarget.value = row;
      certifyForm.value = { method: "", operator: "", reason: "" };
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
      tab,
      loading,
      certs,
      intakes,
      certKind,
      certSearch,
      kindOptions,
      filteredCerts,
      intakeColumns,
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
    };
  },
};
</script>
