<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="width: 40vw; max-width: 50vw">
      <q-bar>
        {{ $t("installSoftware.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip>{{
            $t("installSoftware.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <!-- 🪤 050 (V2-G15): PATRÓN DE REJILLA. Esta tabla fue donde se MIDIÓ el
           defecto: con una parada de tabulador por fila, el tabulador aterrizaba
           en las filas SOBRE-RENDERIZADAS que el desplazamiento virtual deja
           fuera del contenedor —13 paradas con los botones `add` en y=785..1031
           y en y=-321..-239 sobre un viewport de 757, en los dos temas—, donde
           el anillo no se dibuja a propósito porque el control está entero
           fuera de pantalla. Los dos oyentes de la raíz son el seguro: cuando el
           reciclaje destruye el nodo enfocado, Chrome SUBE el foco al scroller
           (`tabindex=-1`) y desde ahí la rejilla quedaría muerta. -->
      <q-card-section @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
        <q-table
          ref="tablaRejilla"
          class="remote-bg-tbl-sticky"
          :table-class="{
            'table-bgcolor': !$q.dark.isActive,
            'table-bgcolor-dark': $q.dark.isActive,
          }"
          dense
          :rows="chocos"
          :columns="columns"
          v-model:pagination="pagination"
          :filter="filter"
          binary-state-sort
          hide-bottom
          virtual-scroll
          @virtual-scroll="alDesplazarVirtual"
          :virtual-scroll-item-size="33"
          :virtual-scroll-sticky-size-start="28"
          :rows-per-page-options="[0]"
          row-key="name"
        >
          <template v-slot:top-left>
            <q-input
              v-model="filter"
              outlined
              :label="$t('installSoftware.search')"
              dense
              clearable
            >
              <template v-slot:prepend>
                <q-icon name="search" />
              </template>
            </q-input>
          </template>
          <template v-slot:body="props">
            <q-tr :props="props">
              <q-td auto-width>
                <!-- `tabindex="-1"`: la tabla es UNA parada de tabulador y a
                     este botón se llega con la flecha derecha desde el nombre.
                     Sigue siendo clicable igual que antes. -->
                <q-btn
                  dense
                  flat
                  push
                  icon="add"
                  tabindex="-1"
                  :aria-label="
                    $t('installSoftware.installAria', { name: props.row.name })
                  "
                  @click="installSoftware(props.row.name)"
                />
              </q-td>
              <q-td>
                <!-- 🪤 Antes el `@click` vivía en el `q-td` y el nombre era un
                     `span` subrayado SIN tabindex: abrir la descripción era
                     imposible sin ratón. Ahora el nombre es el host enfocable de
                     la fila —la única parada de tabulador de la tabla— y lleva
                     el mismo molde que la flota: `role="button"`, Enter y
                     Espacio. El clic en el nombre hace lo mismo que hacía el
                     clic en la celda. -->
                <span
                  class="mono obs-rej__host"
                  role="button"
                  :data-fila="props.rowIndex"
                  :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                  :aria-label="
                    $t('installSoftware.descriptionAria', {
                      name: props.row.name,
                    })
                  "
                  style="cursor: pointer; text-decoration: underline"
                  @focus="filaFoco = props.rowIndex"
                  @keydown.space.prevent
                  @keyup.enter="showDescription(props.row.name)"
                  @keyup.space="showDescription(props.row.name)"
                  @click="showDescription(props.row.name)"
                  >{{ props.row.name }}</span
                >
              </q-td>
            </q-tr>
          </template>
        </q-table>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent, useQuasar } from "quasar";
import { fetchChocosSoftware, installAgentSoftware } from "@/api/software";
import { notifySuccess } from "@/utils/notify";
import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "InstallSoftware",
  mixins: [mixinRejillaTabla],
  // El patrón de rejilla necesita saber qué filas tiene la tabla y cuál es su
  // `ref`; el tope real lo toma de `filteredSortedRows`, porque esta tabla
  // lleva filtro.
  computed: {
    rejillaFilas() {
      return this.chocos;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
  },
  emits: [...useDialogPluginComponent.emits],
  props: {
    agent_id: !String,
  },
  setup(props) {
    // quasar setup
    const { dialogRef, onDialogHide } = useDialogPluginComponent();
    const $q = useQuasar();
    const { t } = useI18n();

    // static data
    const columns = computed(() => [
      {
        name: "install",
        align: "left",
        label: t("installSoftware.colInstall"),
        sortable: false,
      },
      {
        name: "name",
        align: "left",
        label: t("installSoftware.colName"),
        field: "name",
        sortable: true,
      },
    ]);

    // install software logic
    const chocos = ref([]);
    const filter = ref("");
    const pagination = ref({
      rowsPerPage: 0,
      sortBy: "name",
      descending: false,
    });

    async function getChocos() {
      chocos.value = Object.freeze(await fetchChocosSoftware());
    }

    function showDescription(name) {
      window.open(`https://chocolatey.org/packages/${name}`, "_blank");
    }

    function installSoftware(name) {
      const data = { name: name };
      $q.dialog({
        title: t("installSoftware.confirmInstall", { name }),
        persistent: true,
        ok: { label: t("installSoftware.install") },
        cancel: true,
      }).onOk(async () => {
        $q.loading.show();
        try {
          const result = await installAgentSoftware(props.agent_id, data);
          onDialogHide();
          notifySuccess(result, 5000);
        } catch (e) {
          console.error(e);
        }
        $q.loading.hide();
      });
    }

    onMounted(getChocos);

    return {
      // reactive data
      chocos,
      filter,
      pagination,

      // non-reactive data
      columns,

      // methods
      getChocos,
      showDescription,
      installSoftware,

      // quasar dialog
      onDialogHide,
      dialogRef,
    };
  },
};
</script>
