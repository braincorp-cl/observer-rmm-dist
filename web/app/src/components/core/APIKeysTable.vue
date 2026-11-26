<template>
  <div>
    <div class="row">
      <div class="text-subtitle2">{{ $t("apiKeysTable.title") }}</div>
      <q-space />
      <q-btn
        size="sm"
        outline
        no-caps
        icon="fas fa-plus"
        :label="$t('apiKeysTable.addKey')"
        @click="addAPIKey"
      />
    </div>
    <q-separator />
    <!-- 050 (V2-G15): patrón de rejilla (composables/rejillaTabla.js). Editar,
         Eliminar y Copiar eran sólo de ratón; ahora el nombre es el host
         enfocable de la fila (una parada de TAB, flechas entre filas), Enter
         edita, la tecla Menú abre el menú contextual y la flecha derecha llega
         al botón de copiar. -->
    <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
    <q-table
      ref="tablaRejilla"
      @virtual-scroll="alDesplazarVirtual"
      :virtual-scroll-item-size="33"
      :virtual-scroll-sticky-size-start="28"
      dense
      :rows="keys"
      :columns="columns"
      v-model:pagination="pagination"
      row-key="id"
      binary-state-sort
      hide-pagination
      virtual-scroll
      :rows-per-page-options="[0]"
      :no-data-label="$t('apiKeysTable.noData')"
    >
      <!-- header slots -->
      <template v-slot:header-cell-actions="props">
        <q-th :props="props" auto-width> </q-th>
      </template>

      <!-- body slots -->
      <template v-slot:body="props">
        <q-tr
          :props="props"
          class="cursor-pointer"
          @dblclick="editAPIKey(props.row)"
        >
          <!-- context menu -->
          <q-menu context-menu>
            <q-list dense style="min-width: 200px">
              <q-item clickable v-close-popup @click="editAPIKey(props.row)">
                <q-item-section side>
                  <q-icon name="edit" />
                </q-item-section>
                <q-item-section>{{ $t("apiKeysTable.edit") }}</q-item-section>
              </q-item>
              <q-item clickable v-close-popup @click="deleteAPIKey(props.row)">
                <q-item-section side>
                  <q-icon name="delete" />
                </q-item-section>
                <q-item-section>{{ $t("apiKeysTable.delete") }}</q-item-section>
              </q-item>

              <q-separator></q-separator>

              <q-item clickable v-close-popup>
                <q-item-section>{{ $t("apiKeysTable.close") }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
          <!-- name -->
          <q-td>
            <span
              class="obs-rej__host"
              :data-fila="props.rowIndex"
              :tabindex="props.rowIndex === filaFoco ? 0 : -1"
              @focus="filaFoco = props.rowIndex"
              @keydown.enter.prevent="editAPIKey(props.row)"
              >{{ props.row.name }}</span
            >
          </q-td>
          <q-td>
            {{ props.row.username }}
          </q-td>
          <!-- expiration -->
          <q-td class="mono">
            {{ formatDate(props.row.expiration) }}
          </q-td>
          <!-- created time -->
          <q-td class="mono">
            {{ formatDate(props.row.created_time) }}
          </q-td>
          <q-td>
            <q-btn
              flat
              round
              dense
              size="sm"
              icon="content_copy"
              tabindex="-1"
              :aria-label="$t('apiKeysTable.copyTooltip')"
              @click="copyKeyToClipboard(props.row.key)"
            >
              <q-tooltip>{{ $t("apiKeysTable.copyTooltip") }}</q-tooltip>
            </q-btn>
          </q-td>
        </q-tr>
      </template>
    </q-table>
    </div>
  </div>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";
import { fetchAPIKeys, removeAPIKey } from "@/api/accounts";
import { useQuasar, copyToClipboard } from "quasar";
import { notifySuccess, notifyError } from "@/utils/notify";
import APIKeysForm from "@/components/core/APIKeysForm.vue";
import { usarRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "APIKeysTable",
  setup() {
    // i18n setup
    const { t } = useI18n();

    // columns (computed para reaccionar al cambio de idioma)
    const columns = computed(() => [
      {
        name: "name",
        label: t("apiKeysTable.colName"),
        field: "name",
        align: "left",
        sortable: true,
      },
      {
        name: "username",
        label: t("apiKeysTable.colUser"),
        field: "username",
        align: "left",
        sortable: true,
      },
      {
        name: "expiration",
        label: t("apiKeysTable.colExpiration"),
        field: "expiration",
        align: "left",
        sortable: true,
      },
      {
        name: "created_time",
        label: t("apiKeysTable.colCreated"),
        field: "created_time",
        align: "left",
        sortable: true,
      },
      {
        name: "actions",
        label: "",
        field: "actions",
      },
    ]);

    // setup quasar
    const $q = useQuasar();

    // setup vuex
    const store = useStore();
    const formatDate = computed(() => store.getters.formatDate);

    // setup api keys logic
    const keys = ref([]);
    const loading = ref(false);

    // 050 (V2-G15): rejilla de teclado sobre la tabla virtual.
    const tablaRejilla = ref(null);
    const {
      filaFoco,
      alEntrarFoco,
      alTeclaRejilla,
      alDesplazarVirtual,
    } = usarRejillaTabla({
      refTabla: tablaRejilla,
      filas: () => keys.value,
    });

    // setup table
    const pagination = ref({
      rowsPerPage: 0,
      sortBy: "name",
      descending: true,
    });

    function copyKeyToClipboard(apikey) {
      copyToClipboard(apikey)
        .then(() => {
          notifySuccess(t("apiKeysTable.keyCopied"));
        })
        .catch(() => {
          notifyError(t("apiKeysTable.copyError"));
        });
    }

    // api functions
    async function getAPIKeys() {
      loading.value = true;
      keys.value = await fetchAPIKeys();
      loading.value = false;
    }

    async function deleteAPIKey(key) {
      $q.dialog({
        title: t("apiKeysTable.deleteTitle", { name: key.name }),
        cancel: true,
        ok: { label: t("apiKeysTable.delete"), color: "primary" },
      }).onOk(async () => {
        loading.value = true;
        try {
          const result = await removeAPIKey(key.id);
          notifySuccess(result);
          getAPIKeys();
          loading.value = false;
        } catch (e) {
          console.error(e);
          loading.value = false;
        }
      });
    }

    // quasar dialog functions
    function editAPIKey(key) {
      $q.dialog({
        component: APIKeysForm,
        componentProps: {
          APIKey: key,
        },
      }).onOk(() => getAPIKeys());
    }

    function addAPIKey() {
      $q.dialog({
        component: APIKeysForm,
      }).onOk(() => getAPIKeys());
    }

    // component lifecycle hooks
    onMounted(getAPIKeys);
    return {
      // 050 (V2-G15): rejilla de teclado
      tablaRejilla,
      filaFoco,
      alEntrarFoco,
      alTeclaRejilla,
      alDesplazarVirtual,

      // reactive data
      keys,
      loading,
      pagination,

      // non-reactive data
      columns,

      //methods
      getAPIKeys,
      deleteAPIKey,
      copyKeyToClipboard,
      formatDate,

      //dialogs
      editAPIKey,
      addAPIKey,
    };
  },
};
</script>
