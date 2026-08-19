<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">{{ $t("diskEncryption.title") }}</div>
      <q-space />
      <q-btn
        dense
        flat
        icon="refresh"
        :loading="loading"
        @click="load"
        :aria-label="$t('diskEncryption.refresh')"
      >
        <q-tooltip>{{ $t("diskEncryption.refresh") }}</q-tooltip>
      </q-btn>
    </div>

    <!-- Sólo Windows en esta fase (RN-A07): mostrar macOS/Linux en "sin dato"
         los pintaría como falsos incumplidores. El aviso lo dice para que nadie
         lea el panel como el estado de TODA la flota. -->
    <q-banner dense class="bg-grey-3 text-black q-mb-md">
      <template v-slot:avatar>
        <q-icon name="lock" color="primary" />
      </template>
      {{ $t("diskEncryption.windowsOnlyNotice") }}
    </q-banner>

    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-sm-4">
        <q-select
          dense
          filled
          clearable
          emit-value
          map-options
          v-model="filters.state"
          :options="stateOptions"
          :label="$t('diskEncryption.filterState')"
          @update:model-value="load"
        />
      </div>
      <div class="col-12 col-sm-4">
        <q-select
          dense
          filled
          clearable
          emit-value
          map-options
          v-model="filters.client"
          :options="clientOptions"
          :label="$t('diskEncryption.filterClient')"
          @update:model-value="onClientChange"
        />
      </div>
      <div class="col-12 col-sm-4">
        <q-select
          dense
          filled
          clearable
          emit-value
          map-options
          v-model="filters.site"
          :options="siteOptions"
          :label="$t('diskEncryption.filterSite')"
          :disable="!filters.client"
          @update:model-value="load"
        />
      </div>
    </div>

    <q-table
      dense
      flat
      bordered
      row-key="agent_id"
      @row-click="openAgent"
      :rows="rows"
      :columns="columns"
      :loading="loading"
      :rows-per-page-options="[25, 50, 0]"
      :no-data-label="$t('diskEncryption.noData')"
      :loading-label="$t('diskEncryption.loading')"
    >
      <template v-slot:body-cell-state="props">
        <q-td :props="props">
          <q-badge :color="stateColor(props.row.state)">
            {{ stateLabel(props.row.state) }}
          </q-badge>
          <!-- "sin dato" con causa: si la consulta falló, el motivo se ve al
               pasar el mouse (RF-07), sin ensuciar la columna. -->
          <q-tooltip v-if="props.row.query_error">
            {{ props.row.query_error }}
          </q-tooltip>
        </q-td>
      </template>

      <template v-slot:body-cell-method="props">
        <q-td :props="props">
          {{ systemMethod(props.row) }}
        </q-td>
      </template>

      <template v-slot:body-cell-measured_at="props">
        <q-td :props="props">{{ formatDate(props.row.measured_at) }}</q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script>
// Feature 037 · Fase 3 · T014 — el panel de cumplimiento de cifrado (RF-04).
//
// Una fila por equipo con el veredicto de su volumen de sistema (RN-A02). Los
// cuatro estados siguen siendo cuatro: "sin dato" NO es "sin cifrar" (RN-A03),
// así que se pintan con colores distintos y el que nunca reportó no aparece como
// incumplidor.
//
// Sin gating por permiso en el cliente, igual que el resto del producto: el
// alcance lo recorta `filter_by_role` en el servidor (RN-A08) y el 403 ya se
// traduce a un toast por el interceptor de axios.
//
// Los códigos de WMI llegan crudos (RN-A05): la traducción a texto vive acá, en
// `systemMethod` y en los mapas de estado, no en el backend.

import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { fetchDiskEncryptionFleet } from "@/api/diskencryption";
import { fetchClients } from "@/api/clients";
import { formatDate } from "@/utils/format";
import { encryptionMethodLabel } from "@/utils/diskEncryption";

export default {
  name: "DiskEncryptionView",
  setup() {
    const { t } = useI18n();
    const router = useRouter();

    const rows = ref([]);
    const loading = ref(false);

    const filters = ref({ state: null, client: null, site: null });
    const clients = ref([]);
    const clientOptions = ref([]);
    const siteOptions = ref([]);

    // Los cuatro estados de RF-04. El valor es el código que entiende el filtro
    // del backend; la etiqueta la redacta la consola.
    const stateOptions = [
      { value: "encrypted", label: t("diskEncryption.state.encrypted") },
      { value: "unencrypted", label: t("diskEncryption.state.unencrypted") },
      { value: "unsupported", label: t("diskEncryption.state.unsupported") },
      { value: "no_data", label: t("diskEncryption.state.no_data") },
    ];

    const columns = [
      {
        name: "hostname",
        label: t("diskEncryption.colHostname"),
        field: "hostname",
        align: "left",
        sortable: true,
      },
      {
        name: "client_name",
        label: t("diskEncryption.colClient"),
        field: "client_name",
        align: "left",
        sortable: true,
      },
      {
        name: "site_name",
        label: t("diskEncryption.colSite"),
        field: "site_name",
        align: "left",
        sortable: true,
      },
      {
        name: "state",
        label: t("diskEncryption.colState"),
        field: "state",
        align: "left",
        sortable: true,
      },
      {
        name: "method",
        label: t("diskEncryption.colMethod"),
        field: "method",
        align: "left",
      },
      {
        name: "measured_at",
        label: t("diskEncryption.colMeasuredAt"),
        field: "measured_at",
        align: "left",
        sortable: true,
      },
    ];

    // El color separa el incumplimiento (rojo) del "no sabemos" (naranjo) del
    // "no aplica" (gris). Fusionarlos en un solo color sería el ok falso de
    // RN-A03 pintado en pantalla.
    const stateColorMap = {
      encrypted: "positive",
      unencrypted: "negative",
      unsupported: "grey",
      no_data: "warning",
    };

    function stateColor(state) {
      return stateColorMap[state] ?? "grey";
    }

    function stateLabel(state) {
      return t(`diskEncryption.state.${state}`);
    }

    // El método de cifrado del volumen de sistema, traducido. Vacío si el equipo
    // no tiene volumen de sistema (los estados "sin dato"/"no soportado").
    function systemMethod(row) {
      const vol = row.system_volume;
      if (!vol || vol.encryption_method == null) return "";
      return encryptionMethodLabel(t, vol.encryption_method);
    }

    async function load() {
      loading.value = true;
      try {
        const params = {};
        if (filters.value.state) params.state = filters.value.state;
        if (filters.value.client) params.client = filters.value.client;
        if (filters.value.site) params.site = filters.value.site;
        rows.value = (await fetchDiskEncryptionFleet(params)) ?? [];
      } finally {
        loading.value = false;
      }
    }

    async function loadClients() {
      const data = (await fetchClients()) ?? [];
      clients.value = data;
      clientOptions.value = data.map((c) => ({ value: c.id, label: c.name }));
    }

    // Al cambiar de cliente, el sitio elegido deja de ser válido: se limpia y se
    // repuebla la lista con los sitios de ese cliente.
    function onClientChange() {
      filters.value.site = null;
      const client = clients.value.find((c) => c.id === filters.value.client);
      siteOptions.value = (client?.sites ?? []).map((s) => ({
        value: s.id,
        label: s.name,
      }));
      load();
    }

    // El detalle del cifrado vive en la pestaña del equipo (T015): pinchar una
    // fila abre ese equipo, no un diálogo aparte.
    function openAgent(evt, row) {
      router.push({ name: "Agent", params: { agent_id: row.agent_id } });
    }

    onMounted(() => {
      loadClients();
      load();
    });

    return {
      rows,
      columns,
      loading,
      filters,
      stateOptions,
      clientOptions,
      siteOptions,
      stateColor,
      stateLabel,
      systemMethod,
      load,
      onClientChange,
      openAgent,
      formatDate,
    };
  },
};
</script>
