<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="width: 60vw">
      <q-bar>
        <q-btn
          @click="getSites"
          class="q-mr-sm"
          dense
          flat
          push
          icon="refresh"
        />{{ $t("sitesTable.titleFor", { name: client.name }) }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip>{{ $t("sitesTable.close") }}</q-tooltip>
        </q-btn>
      </q-bar>
      <!-- V2-G15: patrón de rejilla (composables/rejillaTabla.js). La tabla es UNA
           parada de tabulador (el host del nombre), las flechas mueven la fila,
           Enter/Espacio editan y la tecla Menú abre el menú contextual de la fila.
           Los oyentes de la raíz atajan el foco cuando el reciclaje lo sube al
           scroller. -->
      <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
      <q-table
        ref="tablaRejilla"
        @virtual-scroll="alDesplazarVirtual"
        dense
        :rows="sites"
        :columns="columns"
        :pagination="{ rowsPerPage: 0, sortBy: 'name', descending: false }"
        row-key="id"
        binary-state-sort
        virtual-scroll
        :rows-per-page-options="[0]"
        :no-data-label="$t('sitesTable.noData')"
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        class="settings-tbl-sticky"
        style="height: 65vh"
        :loading="loading"
      >
        <template v-slot:top>
          <q-btn
            :label="$t('sitesTable.new')"
            dense
            flat
            push
            unelevated
            no-caps
            icon="add"
            @click="showAddSite"
          />
        </template>

        <!-- loading slot -->
        <template v-slot:loading>
          <q-inner-loading showing class="obs-icon-neutral" />
        </template>

        <!-- body slots -->
        <template v-slot:body="props">
          <q-tr
            :props="props"
            class="cursor-pointer"
            @dblclick="showEditSite(props.row)"
          >
            <!-- context menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item
                  clickable
                  v-close-popup
                  @click="showEditSite(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="edit" />
                  </q-item-section>
                  <q-item-section>{{ $t("sitesTable.edit") }}</q-item-section>
                </q-item>
                <q-item
                  clickable
                  v-close-popup
                  @click="showSiteDeleteModal(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{ $t("sitesTable.delete") }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item clickable v-close-popup>
                  <q-item-section>{{ $t("sitesTable.close") }}</q-item-section>
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
                @keydown.enter.prevent="showEditSite(props.row)"
                @keydown.space.prevent="showEditSite(props.row)"
                >{{ props.row.name }}</span
              >
            </q-td>
            <!-- agent count -->
            <!-- 🪤 V2-G01 (2026-11-12): el `classes: "mono"` de la definicion de
                 columna es INERTE en esta tabla, porque la fila la dibuja el
                 slot `v-slot:body` y Quasar solo aplica `classes` cuando
                 renderiza la celda el mismo. Medido: «1» y «9» salian en
                 Archivo mientras la columna homonima de CLIENTES salia en mono
                 -esa tabla lleva la clase escrita a mano en su celda-. La clase
                 va AQUI. -->
            <q-td class="mono">{{ props.row.agent_count }}</q-td>
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
import { fetchClient, removeSite } from "@/api/clients";
import { notifySuccess } from "@/utils/notify";
import { usarRejillaTabla } from "@/composables/rejillaTabla";

// ui imports
import SitesForm from "@/components/clients/SitesForm.vue";
import DeleteClient from "@/components/clients/DeleteClient.vue";

export default {
  name: "SitesTable",
  emits: [...useDialogPluginComponent.emits],
  props: {
    client: !Object,
  },
  setup(props) {
    // setup quasar dialog
    const $q = useQuasar();
    const { t } = useI18n();
    const { dialogRef, onDialogHide } = useDialogPluginComponent();

    // i18n-aware columns (computed for language reactivity)
    const columns = computed(() => [
      {
        name: "name",
        label: t("sitesTable.colName"),
        field: "name",
        align: "left",
      },
      {
        name: "agent_count",
        label: t("sitesTable.colTotalAgents"),
        field: "agent_count",
        align: "left",
        // V2-G01: la vara dice «conteos y tamanos en su celda o badge» en mono.
        classes: "mono",
      },
    ]);

    // sites table logic
    const sites = ref([]);
    const loading = ref(false);

    // 050 (V2-G15): rejilla de teclado sobre la tabla virtual.
    const tablaRejilla = ref(null);
    const { filaFoco, alEntrarFoco, alTeclaRejilla, alDesplazarVirtual } =
      usarRejillaTabla({
        refTabla: tablaRejilla,
        filas: () => sites.value,
      });

    async function getSites() {
      loading.value = true;
      const client = await fetchClient(props.client.id);
      sites.value = client.sites;
      loading.value = false;
    }

    function showSiteDeleteModal(site) {
      // agents are still assigned to client. Need to open modal to select which site to move to
      if (site.agent_count > 0) {
        $q.dialog({
          component: DeleteClient,
          componentProps: {
            object: site,
            type: "site",
          },
        }).onOk(getSites);

        // can delete the client since there are no agents
      } else {
        $q.dialog({
          title: t("sitesTable.confirmTitle"),
          message: t("sitesTable.deleteMessage", { name: site.name }),
          cancel: true,
          ok: { label: t("sitesTable.delete"), color: "primary" },
        }).onOk(async () => {
          loading.value = true;
          try {
            const result = await removeSite(site.id);
            notifySuccess(result);
            await getSites();
          } catch (e) {
            console.error(e);
          }
          loading.value = false;
        });
      }
    }

    function showEditSite(site) {
      $q.dialog({
        component: SitesForm,
        componentProps: {
          site: site,
        },
      }).onOk(getSites);
    }

    function showAddSite() {
      $q.dialog({
        component: SitesForm,
        componentProps: {
          client: props.client.id,
        },
      }).onOk(getSites);
    }

    onMounted(getSites);

    return {
      // reactive data
      sites,
      loading,

      // i18n-aware columns
      columns,

      // rejilla de teclado (V2-G15)
      tablaRejilla,
      filaFoco,
      alEntrarFoco,
      alTeclaRejilla,
      alDesplazarVirtual,

      // methods
      getSites,
      showSiteDeleteModal,
      showEditSite,
      showAddSite,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
