<template>
  <!-- wipe (feature 043 · A2): borrado selectivo por rutas. Se ordena desde el
       caso perdido abierto (RF-G06), después de recuperar (orden invariante
       RN-03, no bloqueante). Crear la orden NO borra: exige una segunda persona
       (RF-G02) y la ventana de arrepentimiento, y el despacho sigue GATED
       (ADR-029). El permiso `can_wipe_device` lo gatea el servidor. -->
  <q-dialog v-model="show" @show="load" full-width>
    <q-card>
      <q-bar class="bg-negative text-white">
        <q-icon name="delete_sweep" />
        <div class="text-weight-bold">
          {{ $t("erase.wipe.title", { hostname: hostname }) }}
        </div>
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip>{{ $t("erase.wipe.close") }}</q-tooltip>
        </q-btn>
      </q-bar>

      <!-- Aviso no bloqueante "borrar sin recuperar" (D-06 / RN-03): sólo si no
           consta una recuperación completada para este equipo. No impide crear. -->
      <q-banner
        v-if="!fileretrievalDone"
        dense
        class="bg-orange-1 text-orange-9 q-ma-md"
      >
        <template v-slot:avatar>
          <q-icon name="warning" color="warning" />
        </template>
        {{ $t("erase.wipe.retrievalWarning") }}
      </q-banner>

      <q-card-section class="q-gutter-sm">
        <q-select
          v-model="selectedTemplate"
          dense
          filled
          clearable
          emit-value
          map-options
          :options="templateOptions"
          :label="$t('erase.wipe.templateLabel')"
          :hint="$t('erase.wipe.templateHint')"
          :loading="loadingTemplates"
        />
        <q-input
          v-model="pathsAddText"
          type="textarea"
          autogrow
          outlined
          :label="$t('erase.wipe.pathsAddLabel')"
          :hint="$t('erase.wipe.pathsAddHint')"
        />
        <q-input
          v-model="pathsRemoveText"
          type="textarea"
          autogrow
          outlined
          :label="$t('erase.wipe.pathsRemoveLabel')"
          :hint="$t('erase.wipe.pathsRemoveHint')"
        />

        <!-- Vista previa de las rutas resueltas (plantilla + añadidas − quitadas).
             Es orientativa: el servidor las materializa y valida el tope (RF-07). -->
        <div class="text-caption text-grey-7">
          {{ $t("erase.wipe.resolvedTitle", { count: resolvedPaths.length }) }}
        </div>
        <q-list
          v-if="resolvedPaths.length"
          bordered
          separator
          dense
          class="oe-preview"
        >
          <q-item v-for="p in resolvedPaths" :key="p">
            <q-item-section>
              <q-item-label class="oe-path">{{ p }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
        <div v-else class="text-caption text-grey-6">
          {{ $t("erase.wipe.resolvedEmpty") }}
        </div>

        <q-input
          v-model="reason"
          dense
          filled
          :label="$t('erase.wipe.reasonLabel')"
          :hint="$t('erase.wipe.reasonHint')"
        />
        <div class="row items-center q-gutter-md">
          <q-toggle
            v-model="dryRun"
            :label="$t('erase.wipe.dryRun')"
          />
          <q-space />
          <q-btn
            color="negative"
            icon="send"
            :label="$t('erase.wipe.launch')"
            :loading="launching"
            @click="launch"
          />
        </div>
      </q-card-section>

      <q-separator />

      <q-card-section>
        <q-table
          dense
          flat
          bordered
          row-key="id"
          :rows="orders"
          :columns="columns"
          :loading="loading"
          :no-data-label="$t('erase.wipe.noOrders')"
        >
          <template v-slot:body-cell-status="props">
            <q-td :props="props">
              <q-badge :color="statusColor(props.row.status)">
                {{ $t("erase.status." + props.row.status) }}
              </q-badge>
            </q-td>
          </template>
          <template v-slot:body-cell-dry_run="props">
            <q-td :props="props">
              <q-icon
                :name="props.row.dry_run ? 'science' : 'delete_forever'"
                :color="props.row.dry_run ? 'orange' : 'negative'"
              />
            </q-td>
          </template>
          <template v-slot:body-cell-actions="props">
            <q-td :props="props">
              <q-btn
                dense
                flat
                icon="visibility"
                :aria-label="$t('erase.wipe.view')"
                @click="openOrder(props.row.id)"
              >
                <q-tooltip>{{ $t("erase.wipe.view") }}</q-tooltip>
              </q-btn>
              <q-btn
                v-if="props.row.status === 'pending_confirmation'"
                dense
                flat
                icon="how_to_reg"
                color="negative"
                :aria-label="$t('erase.wipe.confirm')"
                @click="confirm(props.row)"
              >
                <q-tooltip>{{ $t("erase.wipe.confirm") }}</q-tooltip>
              </q-btn>
              <q-btn
                v-if="cancelable(props.row.status)"
                dense
                flat
                icon="cancel"
                color="warning"
                :aria-label="$t('erase.wipe.cancel')"
                @click="cancel(props.row.id)"
              >
                <q-tooltip>{{ $t("erase.wipe.cancel") }}</q-tooltip>
              </q-btn>
            </q-td>
          </template>
        </q-table>
      </q-card-section>

      <!-- Detalle de una orden: resultado por-ruta + verificación por relectura
           (RN-08) + descarga del certificado C si la orden verificó (T019). -->
      <q-card-section v-if="detail">
        <div class="row items-center q-gutter-sm q-mb-sm">
          <div class="text-subtitle2">
            {{ $t("erase.wipe.detailTitle", { id: detail.id }) }}
          </div>
          <q-badge :color="verifiedColor(detail.verified)">
            {{ verifiedLabel(detail.verified) }}
          </q-badge>
          <q-space />
          <q-btn
            v-if="detail.certificate"
            dense
            flat
            no-caps
            color="primary"
            icon="verified"
            :label="$t('erase.wipe.viewCertificate')"
            @click="openCertificate(detail.certificate)"
          />
        </div>
        <div v-if="detail.method_applied" class="text-caption q-mb-sm">
          {{ $t("erase.wipe.method", { method: detail.method_applied }) }}
        </div>
        <q-markup-table v-if="resultRows.length" dense flat bordered>
          <thead>
            <tr>
              <th class="text-left">{{ $t("erase.wipe.colPath") }}</th>
              <th class="text-left">{{ $t("erase.wipe.colPathStatus") }}</th>
              <th class="text-right">{{ $t("erase.wipe.colBytes") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in resultRows" :key="r.path">
              <td class="text-left oe-path">{{ r.path }}</td>
              <td class="text-left">{{ r.status }}</td>
              <td class="text-right">{{ r.bytes }}</td>
            </tr>
          </tbody>
        </q-markup-table>
        <div v-else class="text-caption text-grey-7">
          {{ $t("erase.wipe.resultEmpty") }}
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar } from "quasar";

import ConfirmWipeOrderDialog from "@/components/agents/ConfirmWipeOrderDialog.vue";
import EraseCertificateDetailDialog from "@/components/agents/EraseCertificateDetailDialog.vue";
import {
  createWipeOrder,
  fetchWipeOrders,
  fetchWipeOrder,
  cancelWipeOrder,
  fetchWipePathTemplates,
  fetchFileRetrievalOrders,
} from "@/api/erase";
import { notifySuccess, notifyError } from "@/utils/notify";

// Estados en los que una orden aún se puede cancelar desde la consola (antes de
// despacharse). Después es terminal.
const CANCELABLE = ["pending_confirmation", "confirmed", "recovery_window"];

const STATUS_COLOR = {
  draft: "grey",
  pending_confirmation: "orange",
  confirmed: "amber",
  recovery_window: "warning",
  dispatched: "blue",
  executed: "negative",
  incomplete: "deep-orange",
  cancelled: "positive",
  failed: "deep-orange",
};

export default {
  name: "WipeOrderDialog",
  props: {
    modelValue: { type: Boolean, default: false },
    agentId: { type: String, required: true },
    hostname: { type: String, default: "" },
    lostModeCycle: { type: Number, default: null },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const { t } = useI18n();
    const $q = useQuasar();

    const show = computed({
      get: () => props.modelValue,
      set: (v) => emit("update:modelValue", v),
    });

    const templates = ref([]);
    const selectedTemplate = ref(null);
    const loadingTemplates = ref(false);
    const pathsAddText = ref("");
    const pathsRemoveText = ref("");
    const reason = ref("");
    // Destructivo: el simulacro (dry_run) es el default seguro (RF-G05).
    const dryRun = ref(true);
    const launching = ref(false);
    const loading = ref(false);
    const orders = ref([]);
    const detail = ref(null);
    // Sin evidencia en contra se asume que NO se recuperó, y se muestra el aviso.
    const fileretrievalDone = ref(false);

    const templateOptions = computed(() =>
      templates.value.map((tpl) => ({
        value: tpl.id,
        label: `${tpl.name} (${tpl.os_scope})`,
      })),
    );

    const columns = [
      {
        name: "status",
        label: t("erase.wipe.colStatus"),
        field: "status",
        align: "left",
      },
      {
        name: "dry_run",
        label: t("erase.wipe.colDryRun"),
        field: "dry_run",
        align: "center",
      },
      {
        name: "ordered_by",
        label: t("erase.wipe.colOrderedBy"),
        field: "ordered_by",
        align: "left",
      },
      {
        name: "ordered_at",
        label: t("erase.wipe.colOrderedAt"),
        field: "ordered_at",
        align: "left",
      },
      {
        name: "actions",
        label: t("erase.wipe.colActions"),
        field: "actions",
        align: "right",
      },
    ];

    function splitLines(text) {
      return text
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
    }

    const pathsAdd = computed(() => splitLines(pathsAddText.value));
    const pathsRemove = computed(() => splitLines(pathsRemoveText.value));

    // Previsualización client-side: plantilla + añadidas − quitadas, sin repetir.
    // El servidor hace la materialización real y valida el tope.
    const resolvedPaths = computed(() => {
      const tpl = templates.value.find((x) => x.id === selectedTemplate.value);
      const base = tpl && Array.isArray(tpl.paths) ? tpl.paths : [];
      const removed = new Set(pathsRemove.value);
      const out = [];
      const seen = new Set();
      for (const p of [...base, ...pathsAdd.value]) {
        if (removed.has(p) || seen.has(p)) continue;
        seen.add(p);
        out.push(p);
      }
      return out;
    });

    // Filas del resultado por-ruta del reporte del agente. `order.result` es un
    // dict {ruta: {status, bytes}} con una clave meta "_" que se descarta.
    const resultRows = computed(() => {
      const res = detail.value && detail.value.result;
      if (!res || typeof res !== "object") return [];
      return Object.entries(res)
        .filter(([k]) => k !== "_")
        .map(([path, v]) => ({
          path,
          status: v && typeof v === "object" ? v.status ?? "—" : String(v),
          bytes: v && typeof v === "object" && v.bytes != null ? v.bytes : "—",
        }));
    });

    function statusColor(status) {
      return STATUS_COLOR[status] ?? "grey";
    }

    function cancelable(status) {
      return CANCELABLE.includes(status);
    }

    // La verificación por relectura (RN-08) tiene tres estados: confirmada,
    // no-confirmada (incompleta) y aún desconocida (null, sin reporte todavía).
    function verifiedColor(v) {
      if (v === true) return "positive";
      if (v === false) return "negative";
      return "grey";
    }
    function verifiedLabel(v) {
      if (v === true) return t("erase.wipe.verifiedYes");
      if (v === false) return t("erase.wipe.verifiedNo");
      return t("erase.wipe.verifiedUnknown");
    }

    async function loadTemplates() {
      loadingTemplates.value = true;
      try {
        templates.value = (await fetchWipePathTemplates(props.agentId)) ?? [];
      } catch (e) {
        console.error(e);
      } finally {
        loadingTemplates.value = false;
      }
    }

    async function loadOrders() {
      loading.value = true;
      try {
        const all = (await fetchWipeOrders()) ?? [];
        // El listado global no filtra por equipo en el servidor; se recorta al
        // equipo abierto por hostname (la orden lo congela al crearse).
        orders.value = props.hostname
          ? all.filter((o) => o.agent_hostname === props.hostname)
          : all;
      } catch (e) {
        console.error(e);
      } finally {
        loading.value = false;
      }
    }

    async function loadRetrievalState() {
      try {
        const ro = (await fetchFileRetrievalOrders(props.agentId)) ?? [];
        // "Recuperado" = existe al menos una orden de recuperación completada.
        fileretrievalDone.value = ro.some((o) => o.status === "done");
      } catch (e) {
        console.error(e);
        fileretrievalDone.value = false;
      }
    }

    async function load() {
      await Promise.all([loadTemplates(), loadOrders(), loadRetrievalState()]);
    }

    async function launch() {
      if (!reason.value.trim()) {
        notifyError(t("erase.wipe.needReason"));
        return;
      }
      launching.value = true;
      try {
        await createWipeOrder(props.agentId, {
          action: "wipe",
          template: selectedTemplate.value,
          paths_add: pathsAdd.value,
          paths_remove: pathsRemove.value,
          dry_run: dryRun.value,
          reason: reason.value.trim(),
          lost_mode_cycle: props.lostModeCycle,
        });
        notifySuccess(t("erase.wipe.launched"));
        pathsAddText.value = "";
        pathsRemoveText.value = "";
        reason.value = "";
        selectedTemplate.value = null;
        await loadOrders();
      } catch (e) {
        console.error(e);
        // El 422 (tope) y el 403 los traduce el interceptor a un toast; aquí
        // sólo queda un aviso genérico si fue otra cosa.
        notifyError(t("erase.wipe.launchError"));
      } finally {
        launching.value = false;
      }
    }

    async function openOrder(pk) {
      try {
        detail.value = await fetchWipeOrder(pk);
      } catch (e) {
        console.error(e);
      }
    }

    function confirm(order) {
      // Segunda confirmación (RF-G02) + ventana de arrepentimiento: la conduce
      // el diálogo de 039, que exige una persona distinta a la que ordenó.
      $q.dialog({
        component: ConfirmWipeOrderDialog,
        componentProps: { order },
      }).onOk(() => loadOrders());
    }

    async function cancel(pk) {
      try {
        await cancelWipeOrder(pk, {});
        await loadOrders();
        if (detail.value && detail.value.id === pk) {
          await openOrder(pk);
        }
      } catch (e) {
        console.error(e);
      }
    }

    function openCertificate(pk) {
      $q.dialog({
        component: EraseCertificateDetailDialog,
        componentProps: { pk },
      });
    }

    return {
      show,
      selectedTemplate,
      templateOptions,
      loadingTemplates,
      pathsAddText,
      pathsRemoveText,
      reason,
      dryRun,
      launching,
      loading,
      orders,
      detail,
      fileretrievalDone,
      resolvedPaths,
      resultRows,
      columns,
      statusColor,
      cancelable,
      verifiedColor,
      verifiedLabel,
      load,
      launch,
      openOrder,
      confirm,
      cancel,
      openCertificate,
    };
  },
};
</script>

<style scoped>
.oe-preview {
  max-height: 180px;
  overflow-y: auto;
}
.oe-path {
  font-family: monospace;
  word-break: break-all;
}
</style>
