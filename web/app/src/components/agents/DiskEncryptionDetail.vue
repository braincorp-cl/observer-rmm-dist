<template>
  <div class="scroll" :style="{ 'max-height': tabHeight }">
    <div class="row items-center q-mb-sm">
      <div class="text-subtitle2">{{ $t("diskEncryption.detailTitle") }}</div>
      <q-space />
      <span v-if="measuredAt" class="text-caption text-grey q-mr-sm">
        {{ $t("diskEncryption.lastMeasured", { when: formatDate(measuredAt) }) }}
      </span>
      <q-btn
        dense
        flat
        no-caps
        icon="refresh"
        color="primary"
        :loading="refreshing || loading"
        :label="$t('diskEncryption.refreshAgent')"
        @click="refresh"
      >
        <q-tooltip>{{ $t("diskEncryption.refreshAgentTooltip") }}</q-tooltip>
      </q-btn>
    </div>

    <!-- Los tres "no sabemos" van con su propia redacción, no fusionados: el
         operador tiene que distinguir "no lo soporta" de "no pudimos leer" de
         "nunca reportó" (RN-A03, RF-07). -->
    <q-banner
      v-if="supported === false"
      dense
      class="bg-grey-3 text-black q-mb-sm"
    >
      <template v-slot:avatar>
        <q-icon name="info" color="grey-7" />
      </template>
      {{ $t("diskEncryption.notSupported") }}
    </q-banner>

    <q-banner v-else-if="queryError" dense class="bg-orange-1 text-orange-9 q-mb-sm">
      <template v-slot:avatar>
        <q-icon name="warning" color="warning" />
      </template>
      {{ $t("diskEncryption.queryError", { error: queryError }) }}
    </q-banner>

    <q-banner
      v-else-if="supported === null"
      dense
      class="bg-grey-3 text-black q-mb-sm"
    >
      <template v-slot:avatar>
        <q-icon name="help_outline" color="grey-7" />
      </template>
      {{ $t("diskEncryption.neverReported") }}
    </q-banner>

    <q-table
      v-if="volumes.length"
      dense
      flat
      bordered
      hide-pagination
      row-key="device_id"
      :rows="volumes"
      :columns="volumeColumns"
      :rows-per-page-options="[0]"
      :loading="loading"
      class="q-mb-md"
    >
      <template v-slot:body-cell-is_system_volume="props">
        <q-td :props="props">
          <q-badge v-if="props.row.is_system_volume" color="primary">
            {{ $t("diskEncryption.systemVolumeYes") }}
          </q-badge>
          <span v-else>{{ dash }}</span>
        </q-td>
      </template>

      <template v-slot:body-cell-protection_status="props">
        <q-td :props="props">
          <q-badge :color="protectionColor(props.row.protection_status)">
            {{ protectionLabel(props.row.protection_status) }}
          </q-badge>
        </q-td>
      </template>

      <template v-slot:body-cell-conversion_status="props">
        <q-td :props="props">
          {{ conversionLabel(props.row.conversion_status) }}
        </q-td>
      </template>

      <template v-slot:body-cell-encryption_method="props">
        <q-td :props="props">{{ methodLabel(props.row.encryption_method) }}</q-td>
      </template>

      <template v-slot:body-cell-encryption_percentage="props">
        <q-td :props="props">
          {{ percentText(props.row.encryption_percentage) }}
        </q-td>
      </template>

      <template v-slot:body-cell-volume_type="props">
        <q-td :props="props">{{ volumeTypeText(props.row.volume_type) }}</q-td>
      </template>

      <template v-slot:body-cell-key_protector_types="props">
        <q-td :props="props">{{ protectorTypesText(props.row) }}</q-td>
      </template>

      <template v-slot:body-cell-measured_at="props">
        <q-td :props="props">{{ formatDate(props.row.measured_at) }}</q-td>
      </template>
    </q-table>

    <div v-else-if="!loading" class="text-caption text-grey q-mb-md">
      {{ $t("diskEncryption.noVolumes") }}
    </div>

    <!-- El registro de cambios (RF-09): es lo que convierte "está sin cifrar" en
         "está sin cifrar desde el martes". -->
    <div v-if="history.length">
      <div class="text-subtitle2 q-mb-xs">
        {{ $t("diskEncryption.historyTitle") }}
      </div>
      <q-table
        dense
        flat
        bordered
        hide-pagination
        row-key="changed_at"
        :rows="history"
        :columns="historyColumns"
        :rows-per-page-options="[0]"
      >
        <template v-slot:body-cell-previous_status="props">
          <q-td :props="props">
            {{ protectionLabel(props.row.previous_status) }}
          </q-td>
        </template>
        <template v-slot:body-cell-new_status="props">
          <q-td :props="props">{{ protectionLabel(props.row.new_status) }}</q-td>
        </template>
        <template v-slot:body-cell-changed_at="props">
          <q-td :props="props">{{ formatDate(props.row.changed_at) }}</q-td>
        </template>
      </q-table>
    </div>
  </div>
</template>

<script>
// Feature 037 · Fase 3 · T015 — el detalle de cifrado de un equipo (RF-05/RF-09).
//
// Vive junto a WmiDetail (dentro de AssetsTab, Windows-only) porque el cifrado
// es un activo del equipo como el resto. Muestra TODOS los volúmenes —no sólo el
// de sistema— porque un volumen de datos sin cifrar es información que el
// operador quiere ver, y el registro de cambios para leer desde cuándo.
//
// El botón de refresco (RF-06) reusa el mismo `sysinfo` que puebla los demás
// activos (endpoint WMI del backend). Si el equipo está fuera de línea NO se
// envía el comando: se avisa y punto. El dato no se actualiza en el acto —el
// agente reporta por NATS y la latencia normal es de ~1 hora—, así que el aviso
// dice que el refresco quedó pedido, no que ya está.

import { onMounted, ref, watch, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";

import { fetchDiskEncryptionDetail } from "@/api/diskencryption";
import { refreshAgentWMI } from "@/api/agents";
import { formatDate } from "@/utils/format";
import {
  protectionStatusLabel,
  conversionStatusLabel,
  encryptionMethodLabel,
  volumeTypeLabel,
} from "@/utils/diskEncryption";
import { notifySuccess, notifyWarning } from "@/utils/notify";

export default {
  name: "DiskEncryptionDetail",
  props: {
    agentId: { type: String, required: true },
    // Estado de última señal del agente (online/offline/overdue). Es la misma
    // fuente que usa el resto de la consola para el semáforo; con `offline` no se
    // manda el comando de refresco.
    status: { type: String, default: "" },
  },
  setup(props) {
    const { t } = useI18n();
    const store = useStore();
    const tabHeight = computed(() => store.state.tabHeight);

    // Guion largo del "sin valor". Va como constante y se pinta por binding, no
    // como texto crudo en la plantilla, porque el gate i18n (no-raw-text) marca
    // cualquier literal suelto en el template.
    const dash = "—";

    const loading = ref(false);
    const refreshing = ref(false);
    const volumes = ref([]);
    const history = ref([]);
    const supported = ref(null);
    const queryError = ref(null);
    const measuredAt = ref(null);

    const volumeColumns = [
      {
        name: "drive_letter",
        label: t("diskEncryption.volDrive"),
        field: "drive_letter",
        align: "left",
      },
      {
        name: "is_system_volume",
        label: t("diskEncryption.volSystem"),
        field: "is_system_volume",
        align: "left",
      },
      {
        name: "protection_status",
        label: t("diskEncryption.volProtection"),
        field: "protection_status",
        align: "left",
      },
      {
        name: "conversion_status",
        label: t("diskEncryption.volConversion"),
        field: "conversion_status",
        align: "left",
      },
      {
        name: "encryption_method",
        label: t("diskEncryption.volMethod"),
        field: "encryption_method",
        align: "left",
      },
      {
        name: "encryption_percentage",
        label: t("diskEncryption.volPercent"),
        field: "encryption_percentage",
        align: "right",
      },
      {
        name: "volume_type",
        label: t("diskEncryption.volType"),
        field: "volume_type",
        align: "left",
      },
      {
        name: "key_protector_count",
        label: t("diskEncryption.volProtectors"),
        field: "key_protector_count",
        align: "right",
      },
      {
        name: "key_protector_types",
        label: t("diskEncryption.volProtectorTypes"),
        field: "key_protector_types",
        align: "left",
      },
      {
        name: "measured_at",
        label: t("diskEncryption.volMeasuredAt"),
        field: "measured_at",
        align: "left",
      },
    ];

    const historyColumns = [
      {
        name: "device_id",
        label: t("diskEncryption.histColDevice"),
        field: "device_id",
        align: "left",
      },
      {
        name: "previous_status",
        label: t("diskEncryption.histColFrom"),
        field: "previous_status",
        align: "left",
      },
      {
        name: "new_status",
        label: t("diskEncryption.histColTo"),
        field: "new_status",
        align: "left",
      },
      {
        name: "changed_at",
        label: t("diskEncryption.histColWhen"),
        field: "changed_at",
        align: "left",
      },
    ];

    function protectionColor(code) {
      if (code === 1) return "positive";
      if (code === 0) return "negative";
      return "grey";
    }

    const protectionLabel = (code) => protectionStatusLabel(t, code);
    const conversionLabel = (code) => conversionStatusLabel(t, code);
    const methodLabel = (code) => encryptionMethodLabel(t, code);
    const volumeTypeText = (code) => volumeTypeLabel(t, code);

    // El porcentaje admite nulo en el cable (no se aplana a 0: "0 % cifrado" es
    // un dato distinto de "no lo sabemos").
    function percentText(pct) {
      return pct == null ? "—" : `${pct}%`;
    }

    // Sólo la CANTIDAD y el TIPO de protectores salen del agente, nunca material
    // de clave (RN-A06). Los tipos llegan como lista de códigos crudos.
    function protectorTypesText(row) {
      const types = row.key_protector_types;
      if (!types || !types.length) return "—";
      return types.join(", ");
    }

    async function load() {
      loading.value = true;
      try {
        const data = await fetchDiskEncryptionDetail(props.agentId);
        volumes.value = data?.volumes ?? [];
        history.value = data?.history ?? [];
        supported.value = data?.supported ?? null;
        queryError.value = data?.query_error ?? null;
        measuredAt.value = data?.measured_at ?? null;
      } finally {
        loading.value = false;
      }
    }

    async function refresh() {
      // RF-06: si el equipo está fuera de línea no se manda el comando. El
      // servidor igual devolvería "no se pudo contactar", pero avisarlo acá
      // ahorra el viaje y deja claro que no quedó nada pedido.
      if (props.status === "offline") {
        notifyWarning(t("diskEncryption.agentOffline"));
        return;
      }
      refreshing.value = true;
      try {
        await refreshAgentWMI(props.agentId);
        // El dato no cambia en el acto: el agente vuelve a medir y reporta por
        // NATS con su latencia. El aviso lo dice para no prometer un refresco
        // instantáneo que no existe.
        notifySuccess(t("diskEncryption.refreshRequested"));
      } catch (e) {
        console.error(e);
      } finally {
        refreshing.value = false;
      }
    }

    watch(
      () => props.agentId,
      (value) => {
        if (value) load();
      },
    );

    onMounted(() => {
      if (props.agentId) load();
    });

    return {
      dash,
      tabHeight,
      loading,
      refreshing,
      volumes,
      history,
      supported,
      queryError,
      measuredAt,
      volumeColumns,
      historyColumns,
      protectionColor,
      protectionLabel,
      conversionLabel,
      methodLabel,
      volumeTypeText,
      percentText,
      protectorTypesText,
      refresh,
      formatDate,
    };
  },
};
</script>
