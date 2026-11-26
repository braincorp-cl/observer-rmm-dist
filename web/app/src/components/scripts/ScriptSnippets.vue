<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card
      class="q-dialog-plugin"
      :style="{
        width: `${$q.screen.width - 300}px`,
        'max-width': `${$q.screen.width - 300}px`,
        height: `${$q.screen.height - 300}px`,
        'max-height': `${$q.screen.height - 300}px`,
      }"
    >
      <q-bar>
        <q-btn
          @click="getSnippets"
          class="q-mr-sm"
          dense
          flat
          push
          icon="refresh"
        />{{ $t("scriptSnippets.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip>{{ $t("scriptsCommon.close") }}</q-tooltip>
        </q-btn>
      </q-bar>
      <!-- V2-G15: patrón de rejilla (composables/rejillaTabla.js); la tabla
           es una sola parada de tabulador y Enter/tecla Menú actúan sobre la
           fila enfocada. -->
      <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
      <q-table
        ref="tablaRejilla"
        @virtual-scroll="alDesplazarVirtual"
        :virtual-scroll-item-size="33"
        :virtual-scroll-sticky-size-start="28"
        dense
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        :style="{ 'max-height': `${$q.screen.height - 300 - 32}px` }"
        class="tbl-sticky"
        :rows="snippets"
        :columns="columns"
        :loading="loading"
        :pagination="{ rowsPerPage: 0, sortBy: 'name', descending: true }"
        row-key="id"
        binary-state-sort
        virtual-scroll
        :rows-per-page-options="[0]"
      >
        <template v-slot:top>
          <q-btn
            dense
            flat
            no-caps
            icon="add"
            :label="$t('scriptsCommon.newBtn')"
            @click="newSnippetModal"
          />
        </template>
        <template v-slot:header-cell-shell="props">
          <q-th
            :props="props"
            auto-width
            tabindex="0"
            @keydown.enter.prevent.stop="props.sort(props.col)"
            @keydown.space.prevent.stop="props.sort(props.col)"
          >
            {{ $t("scriptSnippets.columnShell") }}
          </q-th>
        </template>
        <template v-slot:header-cell-name="props">
          <q-th
            :props="props"
            tabindex="0"
            @keydown.enter.prevent.stop="props.sort(props.col)"
            @keydown.space.prevent.stop="props.sort(props.col)"
          >
            {{ props.col.label }}
          </q-th>
        </template>

        <template v-slot:body="props">
          <!-- Table View -->
          <q-tr
            :props="props"
            @dblclick="editSnippetModal(props.row)"
            class="cursor-pointer"
          >
            <!-- Context Menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item
                  clickable
                  v-close-popup
                  @click="editSnippetModal(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="edit" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptsCommon.edit")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="deleteSnippet(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("scriptsCommon.delete")
                  }}</q-item-section>
                </q-item>

                <q-item clickable v-close-popup>
                  <q-item-section>{{
                    $t("scriptsCommon.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
            <q-td>
              <q-icon
                v-if="props.row.shell === 'powershell'"
                name="mdi-powershell"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellPowershell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'python'"
                name="mdi-language-python"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellPython") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'cmd'"
                name="mdi-microsoft-windows"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellBatch") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'shell'"
                name="mdi-bash"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellShell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'nushell'"
                name="mdi-nushell"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellNushell") }}</q-tooltip>
              </q-icon>
              <q-icon
                v-else-if="props.row.shell === 'deno'"
                name="mdi-typescript"
                size="sm"
              >
                <q-tooltip>{{ $t("scriptsCommon.shellDeno") }}</q-tooltip>
              </q-icon>
            </q-td>
            <!-- name -->
            <q-td>
              <span
                class="obs-rej__host"
                :data-fila="props.rowIndex"
                :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                @focus="filaFoco = props.rowIndex"
                @keydown.enter="editSnippetModal(props.row)"
                >{{ props.row.name }}</span
              >
            </q-td>
            <q-td>{{ props.row.desc }}</q-td>
          </q-tr>
        </template>
      </q-table>
      </div>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent } from "quasar";
import { fetchScriptSnippets, removeScriptSnippet } from "@/api/scripts";
import { notifySuccess } from "@/utils/notify";
import { usarRejillaTabla } from "@/composables/rejillaTabla";

// ui imports
import ScriptSnippetFormModal from "@/components/scripts/ScriptSnippetFormModal.vue";

export default {
  name: "ScriptSnippetManager",
  emits: [...useDialogPluginComponent.emits],
  setup() {
    // setup quasar plugins
    const { dialogRef, onDialogHide } = useDialogPluginComponent();
    const $q = useQuasar();

    // i18n
    const { t } = useI18n();

    // table columns (computed for language reactivity)
    const columns = computed(() => [
      {
        name: "shell",
        label: t("scriptSnippets.columnShell"),
        field: "shell",
        align: "left",
        sortable: true,
      },
      {
        name: "name",
        label: t("scriptsCommon.name"),
        field: "name",
        align: "left",
        sortable: true,
      },
      {
        name: "desc",
        label: t("scriptsCommon.description"),
        field: "description",
        align: "left",
        sortable: false,
      },
    ]);

    // script snippet manager logic
    const snippets = ref([]);

    async function getSnippets() {
      loading.value = true;
      try {
        snippets.value = await fetchScriptSnippets();
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    function deleteSnippet(snippet) {
      $q.dialog({
        title: t("scriptSnippets.deleteTitle", { name: snippet.name }),
        cancel: true,
        ok: { label: t("scriptsCommon.delete"), color: "primary" },
      }).onOk(async () => {
        loading.value = true;
        try {
          const data = await removeScriptSnippet(snippet.id);
          notifySuccess(data);
          getSnippets();
        } catch (e) {}

        loading.value = false;
      });
    }

    // table setup
    const loading = ref(false);

    // V2-G15: rejilla de teclado sobre la tabla virtual.
    const tablaRejilla = ref();
    const { filaFoco, alEntrarFoco, alTeclaRejilla, alDesplazarVirtual } =
      usarRejillaTabla({
        refTabla: tablaRejilla,
        filas: () => snippets.value,
      });

    function newSnippetModal() {
      $q.dialog({
        component: ScriptSnippetFormModal,
      }).onOk(() => {
        getSnippets();
      });
    }

    function editSnippetModal(snippet) {
      $q.dialog({
        component: ScriptSnippetFormModal,
        componentProps: {
          snippet,
        },
      }).onOk(getSnippets);
    }

    // component life cycle hooks
    onMounted(getSnippets);

    return {
      // reactive data
      snippets,
      loading,
      tablaRejilla,
      filaFoco,
      alEntrarFoco,
      alTeclaRejilla,
      alDesplazarVirtual,

      // non-reactive data
      columns,

      // api methods
      getSnippets,
      deleteSnippet,

      // dialog methods
      newSnippetModal,
      editSnippetModal,

      // quasar dialog plugin
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
