<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">{{ $t("erase.orders.title") }}</div>
      <q-space />
      <q-btn
        dense
        flat
        icon="refresh"
        :loading="loading"
        :aria-label="$t('erase.orders.refresh')"
        @click="load"
      >
        <q-tooltip>{{ $t("erase.orders.refresh") }}</q-tooltip>
      </q-btn>
    </div>

    <!-- Gobernanza B0: esta vista NO crea órdenes destructivas (crearlas es el
         Bloque A, GATED por ADR-029). Sólo gobierna las existentes: segunda
         confirmación y ventana de arrepentimiento. El despacho real al equipo
         sigue deshabilitado en el servidor. -->
    <q-banner dense class="bg-grey-3 text-black q-mb-md">
      <template v-slot:avatar>
        <q-icon name="gavel" color="primary" />
      </template>
      {{ $t("erase.orders.governanceNotice") }}
    </q-banner>

    <q-table
      dense
      flat
      bordered
      row-key="id"
      :rows="rows"
      :columns="columns"
      :loading="loading"
      :rows-per-page-options="[25, 50, 0]"
      :no-data-label="$t('erase.orders.noData')"
      :loading-label="$t('erase.certificates.loading')"
    >
      <template v-slot:body-cell-action="props">
        <q-td :props="props">{{ actionLabel(props.row.action) }}</q-td>
      </template>

      <template v-slot:body-cell-status="props">
        <q-td :props="props">
          <q-badge :color="statusColor(props.row.status)">
            {{ $t(`erase.status.${props.row.status}`) }}
          </q-badge>
        </q-td>
      </template>

      <template v-slot:body-cell-dry_run="props">
        <q-td :props="props">
          <q-badge :color="props.row.dry_run ? 'grey' : 'negative'">
            {{
              props.row.dry_run
                ? $t("erase.confirmOrder.dryRunYes")
                : $t("erase.confirmOrder.dryRunNo")
            }}
          </q-badge>
        </q-td>
      </template>

      <template v-slot:body-cell-ordered_at="props">
        <q-td :props="props">{{ formatDate(props.row.ordered_at) }}</q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props" auto-width>
          <q-btn
            v-if="props.row.status === 'pending_confirmation'"
            dense
            flat
            no-caps
            size="sm"
            color="negative"
            icon="how_to_reg"
            :label="$t('erase.orders.confirmAction')"
            @click="openConfirm(props.row)"
          />
          <q-btn
            v-else-if="props.row.status === 'recovery_window'"
            dense
            flat
            no-caps
            size="sm"
            color="warning"
            icon="hourglass_bottom"
            :label="$t('erase.orders.windowAction')"
            @click="openWindow(props.row)"
          />
          <span v-else>{{ dash }}</span>
        </q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script>
// Feature 039 · Observer Erase · T033 (anfitrión) — gobernanza de las órdenes de
// borrado (B0). Lista `/erase/orders/` y ofrece, por estado, la segunda
// confirmación (RF-G02) y la ventana de arrepentimiento (RF-G03). No hay botón
// de crear: eso es el Bloque A destructivo y está GATED.

import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar } from "quasar";

import ConfirmWipeOrderDialog from "@/components/agents/ConfirmWipeOrderDialog.vue";
import RecoveryWindowDialog from "@/components/agents/RecoveryWindowDialog.vue";
import { fetchWipeOrders } from "@/api/erase";
import { formatDate } from "@/utils/format";

export default {
  name: "WipeOrdersView",
  setup() {
    const { t } = useI18n();
    const $q = useQuasar();

    const dash = "—";
    const rows = ref([]);
    const loading = ref(false);

    const columns = [
      {
        name: "id",
        label: t("erase.orders.colId"),
        field: "id",
        align: "left",
        sortable: true,
      },
      {
        name: "action",
        label: t("erase.orders.colAction"),
        field: "action",
        align: "left",
      },
      {
        name: "agent_hostname",
        label: t("erase.orders.colHostname"),
        field: "agent_hostname",
        align: "left",
        sortable: true,
      },
      {
        name: "status",
        label: t("erase.orders.colStatus"),
        field: "status",
        align: "left",
        sortable: true,
      },
      {
        name: "ordered_by",
        label: t("erase.orders.colOrderedBy"),
        field: "ordered_by",
        align: "left",
      },
      {
        name: "ordered_at",
        label: t("erase.orders.colOrderedAt"),
        field: "ordered_at",
        align: "left",
        sortable: true,
      },
      {
        name: "dry_run",
        label: t("erase.orders.colDryRun"),
        field: "dry_run",
        align: "left",
      },
      {
        name: "actions",
        label: t("erase.orders.colActions"),
        field: "actions",
        align: "right",
      },
    ];

    // El color separa lo que aún se puede gobernar (pendiente/ventana) de lo
    // terminal (cancelada/ejecutada/fallida). No fusiona estados.
    const statusColorMap = {
      draft: "grey",
      pending_confirmation: "orange",
      confirmed: "amber",
      recovery_window: "warning",
      dispatched: "blue",
      executed: "negative",
      cancelled: "positive",
      failed: "deep-orange",
    };

    function statusColor(status) {
      return statusColorMap[status] ?? "grey";
    }

    function actionLabel(action) {
      return action ? t(`erase.action.${action}`) : dash;
    }

    async function load() {
      loading.value = true;
      try {
        rows.value = (await fetchWipeOrders()) ?? [];
      } finally {
        loading.value = false;
      }
    }

    function openConfirm(order) {
      $q.dialog({
        component: ConfirmWipeOrderDialog,
        componentProps: { order },
      }).onOk(() => load());
    }

    function openWindow(order) {
      $q.dialog({
        component: RecoveryWindowDialog,
        componentProps: { order },
      }).onOk(() => load());
    }

    onMounted(load);

    return {
      dash,
      rows,
      columns,
      loading,
      statusColor,
      actionLabel,
      load,
      openConfirm,
      openWindow,
      formatDate,
    };
  },
};
</script>
