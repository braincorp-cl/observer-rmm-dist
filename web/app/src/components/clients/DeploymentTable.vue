<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="min-width: 70vw; height: 70vh">
      <q-bar>
        <q-btn
          @click="getDeployments"
          class="q-mr-sm"
          dense
          flat
          push
          icon="refresh"
        />
        {{ $t("deploymentTable.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip />
        </q-btn>
      </q-bar>
      <!-- 🪤 050 (V2-G15): PATRON DE REJILLA. Con una parada de tabulador por fila,
           el tabulador aterriza en las filas SOBRE-RENDERIZADAS que el
           desplazamiento virtual deja fuera del contenedor, donde el anillo no se
           dibuja a proposito porque el control esta entero fuera de pantalla
           (medido en el dialogo de instalar software: 13 paradas en y=785..1031 y
           en y=-321..-239 sobre un viewport de 757, en los dos temas). La tabla
           pasa a ser UNA parada y las flechas mueven la fila, con `scrollTo` POR
           INDICE. Los dos oyentes de la raiz son el seguro: cuando el reciclaje
           destruye el nodo enfocado, Chrome SUBE el foco al scroller
           (`tabindex=-1`) y desde ahi la rejilla quedaria muerta. -->
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
        class="audit-mgr-tbl-sticky"
        style="max-height: 65vh"
        binary-state-sort
        virtual-scroll
        :rows="deployments"
        :columns="columns"
        :rows-per-page-options="[0]"
        row-key="id"
        :pagination="{ rowsPerPage: 0, sortBy: 'id', descending: true }"
        :no-data-label="$t('deploymentTable.noData')"
        :loading="loading"
      >
        <template v-slot:top>
          <q-btn
            dense
            flat
            icon="add"
            :label="$t('deploymentTable.new')"
            @click="showAddDeployment"
          />
        </template>

        <template v-slot:body="props">
          <q-tr
            :props="props"
            class="cursor-pointer"
            @dblclick="copyLink(props.row)"
          >
            <q-menu context-menu auto-close>
              <q-list dense style="min-width: 200px">
                <q-item clickable @click="deleteDeployment(props.row)">
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("deploymentTable.delete")
                  }}</q-item-section>
                </q-item>
                <q-separator />
                <q-item clickable>
                  <q-item-section>{{
                    $t("deploymentTable.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
            <!-- Host enfocable de la fila: la ÚNICA parada de tabulador de la
                 tabla. Desde aquí la tecla Menú abre el menú contextual de la
                 fila —que antes era sólo de ratón— y las flechas
                 izquierda/derecha llegan a los demás controles de la fila. -->
            <q-td key="client" :props="props">
              <span
                class="obs-rej__host"
                :data-fila="props.rowIndex"
                :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                @focus="filaFoco = props.rowIndex"
                >{{ props.row.client_name }}</span
              >
            </q-td>
            <q-td key="site" :props="props">{{ props.row.site_name }}</q-td>
            <q-td key="mon_type" :props="props">{{ props.row.mon_type }}</q-td>
            <q-td key="goarch" :props="props" class="mono">{{ props.row.goarch }}</q-td>
            <q-td key="expiry" :props="props">{{
              formatDate(props.row.expiry)
            }}</q-td>
            <q-td key="created" :props="props">{{
              formatDate(props.row.created)
            }}</q-td>
            <q-td key="flags" :props="props"
              ><q-badge
                color="grey-8"
                :label="$t('deploymentTable.viewFlags')"
              />
              <q-tooltip style="font-size: 12px">{{
                props.row.install_flags
              }}</q-tooltip>
            </q-td>
            <q-td key="link" :props="props">
              <!-- `tabindex="-1"`: se alcanza con la flecha derecha desde el
                   host de la fila. -->
              <q-btn
                flat
                dense
                size="sm"
                color="primary"
                icon="content_copy"
                tabindex="-1"
                :label="$t('deploymentTable.copy')"
                @click="copyLink(props.row)"
              />
            </q-td>
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
import { useStore } from "vuex";
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent, copyToClipboard } from "quasar";
import { fetchDeployments, removeDeployment } from "@/api/clients";
import { notifySuccess } from "@/utils/notify";
import { getBaseUrl } from "@/boot/axios";

// ui imports
import NewDeployment from "@/components/clients/NewDeployment.vue";

import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "DeploymentTable",
  mixins: [mixinRejillaTabla],
  computed: {
    rejillaFilas() {
      return this.deployments;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
  },
  emits: [...useDialogPluginComponent.emits],
  setup() {
    // quasar dialog setup
    const { dialogRef, onDialogHide } = useDialogPluginComponent();
    const $q = useQuasar();
    const { t } = useI18n();

    // setup vuex
    const store = useStore();
    const formatDate = computed(() => store.getters.formatDate);

    // i18n-aware columns (computed for language reactivity)
    const columns = computed(() => [
      {
        name: "client",
        label: t("deploymentTable.colClient"),
        field: "client_name",
        align: "left",
        sortable: true,
      },
      {
        name: "site",
        label: t("deploymentTable.colSite"),
        field: "site_name",
        align: "left",
        sortable: true,
      },
      {
        name: "mon_type",
        label: t("deploymentTable.colType"),
        field: "mon_type",
        align: "left",
        sortable: true,
      },
      {
        name: "goarch",
        label: t("deploymentTable.colArch"),
        field: "goarch",
        align: "left",
        sortable: true,
      },
      {
        name: "expiry",
        label: t("deploymentTable.colExpiry"),
        field: "expiry",
        align: "left",
        sortable: true,
      },
      {
        name: "created",
        label: t("deploymentTable.colCreated"),
        field: "created",
        align: "left",
        sortable: true,
      },
      {
        name: "flags",
        label: t("deploymentTable.colFlags"),
        field: "install_flags",
        align: "left",
      },
      {
        name: "link",
        label: t("deploymentTable.colDownloadLink"),
        align: "left",
      },
    ]);

    // deployment logic
    const deployments = ref([]);
    const loading = ref(false);

    async function getDeployments() {
      loading.value = true;
      deployments.value = await fetchDeployments();
      loading.value = false;
    }

    function deleteDeployment(deployment) {
      $q.dialog({
        title: t("deploymentTable.deleteTitle"),
        cancel: true,
        ok: { label: t("deploymentTable.delete"), color: "primary" },
      }).onOk(async () => {
        loading.value = true;
        try {
          const result = await removeDeployment(deployment.id);
          notifySuccess(result);
          await getDeployments();
        } catch (e) {
          console.error(e);
        }
        loading.value = false;
      });
    }

    function copyLink(deployment) {
      const api = getBaseUrl();
      copyToClipboard(`${api}/clients/${deployment.uid}/deploy/`).then(() => {
        notifySuccess(t("deploymentTable.linkCopied"), 1500);
      });
    }

    function showAddDeployment() {
      $q.dialog({
        component: NewDeployment,
      }).onOk(getDeployments);
    }

    onMounted(getDeployments);

    return {
      // reactive data
      deployments,
      loading,

      // i18n-aware columns
      columns,

      // mehtods
      getDeployments,
      deleteDeployment,
      showAddDeployment,
      copyLink,
      formatDate,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
