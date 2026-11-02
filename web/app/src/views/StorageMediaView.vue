<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">{{ $t("storageMedia.title") }}</div>
      <q-space />
      <q-btn
        dense
        flat
        icon="refresh"
        :loading="loading"
        @click="load"
        :aria-label="$t('storageMedia.refresh')"
      >
        <q-tooltip>{{ $t("storageMedia.refresh") }}</q-tooltip>
      </q-btn>
    </div>

    <!-- Sólo Windows en esta fase: mostrar macOS/Linux en "sin dato" los
         pintaría como falsos desconocidos. El aviso lo dice para que nadie lea
         el panel como el estado de TODA la flota. -->
    <q-banner dense class="bg-grey-3 text-black q-mb-md">
      <template v-slot:avatar>
        <q-icon name="storage" color="primary" />
      </template>
      {{ $t("storageMedia.windowsOnlyNotice") }}
    </q-banner>

    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-sm-4">
        <q-select
          dense
          filled
          clearable
          emit-value
          map-options
          v-model="filters.verdict"
          :options="verdictOptions"
          :label="$t('storageMedia.filterVerdict')"
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
          :label="$t('storageMedia.filterClient')"
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
          :label="$t('storageMedia.filterSite')"
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
      :no-data-label="$t('storageMedia.noData')"
      :loading-label="$t('storageMedia.loading')"
    >
      <template v-slot:body-cell-verdict="props">
        <q-td :props="props">
          <q-badge :color="verdictColor(props.row.verdict)">
            {{ verdictLabel(props.row.verdict) }}
          </q-badge>
          <!-- La causa del "sin dato", si la hay. El error de consulta se ve al
               pasar el mouse sin ensuciar la columna, y el texto de ayuda
               explica qué significa cada veredicto: el panel informa
               decisiones de baja y no puede dejarlas a la interpretación. -->
          <q-tooltip>
            {{ props.row.query_error || verdictHelp(props.row.verdict) }}
          </q-tooltip>
        </q-td>
      </template>

      <template v-slot:body-cell-media="props">
        <q-td :props="props">
          {{ systemMedia(props.row) }}
        </q-td>
      </template>

      <template v-slot:body-cell-measured_at="props">
        <q-td :props="props">{{ formatDate(props.row.measured_at) }}</q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script>
// Feature 055 · el panel de categoría de sanitización alcanzable (RF-06).
//
// Una fila por equipo con el veredicto de su disco de sistema (RN-03). Los seis
// veredictos siguen siendo seis, y en particular "sin dato" NO es "sin
// categoría alcanzable" (RN-02): se pintan con colores distintos, y el que
// nunca reportó sale en gris y no en naranjo.
//
// Sin gating por permiso en el cliente, igual que el resto del producto: el
// alcance lo recorta `filter_by_role` en el servidor y el 403 ya se traduce a
// un toast por el interceptor de axios.
//
// Los códigos llegan crudos (RN-04): la traducción a texto vive acá y en
// `@/utils/storageMedia`, no en el backend.

import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { fetchStorageMediaFleet } from "@/api/storagemedia";
import { fetchClients } from "@/api/clients";
import { formatDate } from "@/utils/format";
import {
  capacityLabel,
  mediaTypeLabel,
  verdictColor,
} from "@/utils/storageMedia";

export default {
  name: "StorageMediaView",
  setup() {
    const { t } = useI18n();
    const router = useRouter();

    const rows = ref([]);
    const loading = ref(false);

    const filters = ref({ verdict: null, client: null, site: null });
    const clients = ref([]);
    const clientOptions = ref([]);
    const siteOptions = ref([]);

    // Los seis veredictos. El valor es el código que entiende el filtro del
    // backend; la etiqueta la redacta la consola.
    const verdictOptions = [
      { value: "purge_remote", label: t("storageMedia.verdict.purge_remote") },
      {
        value: "purge_live_image",
        label: t("storageMedia.verdict.purge_live_image"),
      },
      { value: "clear_remote", label: t("storageMedia.verdict.clear_remote") },
      { value: "virtual_media", label: t("storageMedia.verdict.virtual_media") },
      { value: "no_category", label: t("storageMedia.verdict.no_category") },
      { value: "no_data", label: t("storageMedia.verdict.no_data") },
    ];

    const columns = [
      {
        name: "hostname",
        label: t("storageMedia.colHostname"),
        field: "hostname",
        align: "left",
        sortable: true,
      },
      {
        name: "client_name",
        label: t("storageMedia.colClient"),
        field: "client_name",
        align: "left",
        sortable: true,
      },
      {
        name: "site_name",
        label: t("storageMedia.colSite"),
        field: "site_name",
        align: "left",
        sortable: true,
      },
      {
        name: "verdict",
        label: t("storageMedia.colVerdict"),
        field: "verdict",
        align: "left",
        sortable: true,
      },
      {
        name: "media",
        label: t("storageMedia.colMedia"),
        field: "system_disk",
        align: "left",
      },
      {
        name: "measured_at",
        label: t("storageMedia.colMeasuredAt"),
        field: "measured_at",
        align: "left",
        sortable: true,
      },
    ];

    function verdictLabel(veredicto) {
      return t(`storageMedia.verdict.${veredicto}`);
    }

    function verdictHelp(veredicto) {
      return t(`storageMedia.verdictHelp.${veredicto}`);
    }

    // El medio del disco de sistema, en una línea. Vacío cuando el equipo no
    // tiene disco de sistema reportado: los estados "sin dato".
    function systemMedia(row) {
      const disco = row.system_disk;
      if (!disco) return "";
      const partes = [
        disco.model,
        mediaTypeLabel(t, disco.media_type_code),
        capacityLabel(disco.size_bytes),
      ];
      return partes.filter((p) => p).join(" · ");
    }

    async function load() {
      loading.value = true;
      try {
        const params = {};
        if (filters.value.verdict) params.verdict = filters.value.verdict;
        if (filters.value.client) params.client = filters.value.client;
        if (filters.value.site) params.site = filters.value.site;
        rows.value = (await fetchStorageMediaFleet(params)) ?? [];
      } finally {
        loading.value = false;
      }
    }

    async function loadClients() {
      const data = (await fetchClients()) ?? [];
      clients.value = data;
      clientOptions.value = data.map((c) => ({ value: c.id, label: c.name }));
    }

    function onClientChange() {
      filters.value.site = null;
      const client = clients.value.find((c) => c.id === filters.value.client);
      siteOptions.value = (client?.sites ?? []).map((s) => ({
        value: s.id,
        label: s.name,
      }));
      load();
    }

    // El detalle vive en la pestaña del equipo: pinchar una fila abre ese
    // equipo, no un diálogo aparte.
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
      verdictOptions,
      clientOptions,
      siteOptions,
      verdictColor,
      verdictLabel,
      verdictHelp,
      systemMedia,
      load,
      onClientChange,
      openAgent,
      formatDate,
    };
  },
};
</script>
