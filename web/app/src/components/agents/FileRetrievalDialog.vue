<template>
  <!-- fileretrieval (feature 042): recuperar archivos ANTES de borrar. Se abre
       desde el caso perdido (RF-G06); no es destructivo. El permiso
       can_retrieve_files lo gatea el servidor. -->
  <q-dialog v-model="show" @show="load" full-width>
    <q-card>
      <q-bar>
        <q-icon name="download_for_offline" />
        <div class="text-weight-bold">
          {{ $t("erase.fileretrieval.title", { hostname: hostname }) }}
        </div>
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip>{{ $t("erase.fileretrieval.close") }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section class="q-gutter-sm">
        <q-input
          v-model="pathsText"
          type="textarea"
          autogrow
          outlined
          :label="$t('erase.fileretrieval.pathsLabel')"
          :hint="$t('erase.fileretrieval.pathsHint')"
        />
        <div class="row items-center q-gutter-md">
          <q-toggle
            v-model="dryRun"
            :label="$t('erase.fileretrieval.dryRun')"
          />
          <q-btn
            color="primary"
            icon="send"
            :label="$t('erase.fileretrieval.launch')"
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
          :no-data-label="$t('erase.fileretrieval.noOrders')"
        >
          <template v-slot:body-cell-status="props">
            <q-td :props="props">
              {{ $t("erase.fileretrieval.status." + props.row.status) }}
            </q-td>
          </template>
          <template v-slot:body-cell-dry_run="props">
            <q-td :props="props">
              <q-icon
                :name="props.row.dry_run ? 'science' : 'download'"
                :color="props.row.dry_run ? 'orange' : 'primary'"
              />
            </q-td>
          </template>
          <template v-slot:body-cell-actions="props">
            <q-td :props="props">
              <q-btn
                dense
                flat
                icon="folder_open"
                :aria-label="$t('erase.fileretrieval.view')"
                @click="openOrder(props.row.id)"
              >
                <q-tooltip>{{ $t("erase.fileretrieval.view") }}</q-tooltip>
              </q-btn>
              <q-btn
                v-if="cancelable(props.row.status)"
                dense
                flat
                icon="cancel"
                color="negative"
                :aria-label="$t('erase.fileretrieval.cancel')"
                @click="cancel(props.row.id)"
              >
                <q-tooltip>{{ $t("erase.fileretrieval.cancel") }}</q-tooltip>
              </q-btn>
            </q-td>
          </template>
        </q-table>
      </q-card-section>

      <!-- Detalle de una orden: archivos recuperados y su descarga. -->
      <q-card-section v-if="detail">
        <div class="text-subtitle2 q-mb-sm">
          {{ $t("erase.fileretrieval.filesTitle") }}
        </div>
        <div v-if="detail.result && detail.result.plan" class="text-caption q-mb-sm">
          {{ $t("erase.fileretrieval.plan", { plan: detail.result.plan }) }}
        </div>
        <q-list bordered separator v-if="detail.files && detail.files.length">
          <q-item v-for="f in detail.files" :key="f.id">
            <q-item-section>
              <q-item-label>{{ f.source_path }}</q-item-label>
              <q-item-label caption>{{ f.size }} B</q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-btn
                dense
                flat
                icon="download"
                :aria-label="$t('erase.fileretrieval.download')"
                @click="download(detail.id, f)"
              />
            </q-item-section>
          </q-item>
        </q-list>
        <div v-else class="text-caption text-grey-7">
          {{ $t("erase.fileretrieval.noFiles") }}
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";

import {
  createFileRetrievalOrder,
  fetchFileRetrievalOrders,
  fetchFileRetrievalOrder,
  cancelFileRetrievalOrder,
  downloadRetrievedFile,
} from "@/api/erase";
import { notifySuccess, notifyError } from "@/utils/notify";

const CANCELABLE = ["pending", "dispatched", "uploading"];

export default {
  name: "FileRetrievalDialog",
  props: {
    modelValue: { type: Boolean, default: false },
    agentId: { type: String, required: true },
    hostname: { type: String, default: "" },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const { t } = useI18n();

    const show = computed({
      get: () => props.modelValue,
      set: (v) => emit("update:modelValue", v),
    });

    const pathsText = ref("");
    const dryRun = ref(false);
    const launching = ref(false);
    const loading = ref(false);
    const orders = ref([]);
    const detail = ref(null);

    const columns = [
      {
        name: "status",
        label: t("erase.fileretrieval.colStatus"),
        field: "status",
        align: "left",
      },
      {
        name: "dry_run",
        label: t("erase.fileretrieval.colDryRun"),
        field: "dry_run",
        align: "center",
      },
      {
        name: "file_count",
        label: t("erase.fileretrieval.colFiles"),
        field: "file_count",
        align: "right",
      },
      {
        name: "requested_at",
        label: t("erase.fileretrieval.colCreated"),
        field: "requested_at",
        align: "left",
      },
      {
        name: "actions",
        label: t("erase.fileretrieval.colActions"),
        field: "actions",
        align: "right",
      },
    ];

    function cancelable(status) {
      return CANCELABLE.includes(status);
    }

    async function load() {
      loading.value = true;
      try {
        orders.value = await fetchFileRetrievalOrders(props.agentId);
      } catch (e) {
        console.error(e);
      } finally {
        loading.value = false;
      }
    }

    function parsePaths() {
      return pathsText.value
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
    }

    async function launch() {
      const paths = parsePaths();
      if (paths.length === 0) {
        notifyError(t("erase.fileretrieval.needPaths"));
        return;
      }
      launching.value = true;
      try {
        await createFileRetrievalOrder(props.agentId, {
          paths,
          dry_run: dryRun.value,
        });
        notifySuccess(t("erase.fileretrieval.launched"));
        pathsText.value = "";
        await load();
      } catch (e) {
        console.error(e);
        notifyError(t("erase.fileretrieval.launchError"));
      } finally {
        launching.value = false;
      }
    }

    async function openOrder(pk) {
      try {
        detail.value = await fetchFileRetrievalOrder(pk);
      } catch (e) {
        console.error(e);
      }
    }

    async function cancel(pk) {
      try {
        await cancelFileRetrievalOrder(pk);
        await load();
        if (detail.value && detail.value.id === pk) {
          await openOrder(pk);
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function download(pk, file) {
      try {
        const r = await downloadRetrievedFile(pk, file.id);
        const blob = new Blob([r.data]);
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        // Nombre de archivo desde la ruta de origen (basename).
        const base = file.source_path.split(/[\\/]/).pop() || "archivo";
        link.download = base;
        link.click();
        window.URL.revokeObjectURL(url);
      } catch (e) {
        console.error(e);
        notifyError(t("erase.fileretrieval.downloadError"));
      }
    }

    return {
      show,
      pathsText,
      dryRun,
      launching,
      loading,
      orders,
      detail,
      columns,
      cancelable,
      load,
      launch,
      openOrder,
      cancel,
      download,
    };
  },
};
</script>
