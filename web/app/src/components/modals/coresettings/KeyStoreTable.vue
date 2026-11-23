<template>
  <div>
    <div class="row">
      <div class="text-subtitle2">{{ $t("keyStoreTable.title") }}</div>
      <q-space />
      <q-btn
        size="sm"
        outline
        no-caps
        icon="fas fa-plus"
        :label="$t('keyStoreTable.addKey')"
        @click="addKey"
      />
    </div>
    <q-separator />
    <q-table
      dense
      :rows="keystore"
      :columns="columns"
      v-model:pagination="pagination"
      row-key="id"
      binary-state-sort
      hide-pagination
      virtual-scroll
      :rows-per-page-options="[0]"
      :no-data-label="$t('keyStoreTable.noData')"
    >
      <!-- body slots -->
      <template v-slot:body="props">
        <q-tr
          :props="props"
          class="cursor-pointer"
          @dblclick="editKey(props.row)"
        >
          <!-- context menu -->
          <q-menu context-menu>
            <q-list dense style="min-width: 200px">
              <q-item clickable v-close-popup @click="editKey(props.row)">
                <q-item-section side>
                  <q-icon name="edit" />
                </q-item-section>
                <q-item-section>{{ $t("keyStoreTable.edit") }}</q-item-section>
              </q-item>
              <q-item clickable v-close-popup @click="deleteKey(props.row)">
                <q-item-section side>
                  <q-icon name="delete" />
                </q-item-section>
                <q-item-section>{{
                  $t("keyStoreTable.delete")
                }}</q-item-section>
              </q-item>

              <q-separator></q-separator>

              <q-item clickable v-close-popup>
                <q-item-section>{{ $t("keyStoreTable.close") }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
          <!-- name -->
          <q-td>
            {{ props.row.name }}
          </q-td>
          <!-- value -->
          <!-- RT-AUT-09 (llega por merge desde main): el servidor no entrega
               el valor de una clave secreta; la celda dice si hay algo
               guardado, nunca qué. Por eso se retiró el conmutador
               mostrar/ocultar de la v2: con el valor fuera del cable, un botón
               «Mostrar valores» prometía algo que ya no puede cumplir.
               🪤 Dos cambios sobre lo que trajo main, los dos de criterios de
               esta rama: `text-grey-7` es un color de la paleta de Quasar y no
               un token del proyecto (V2-G02), así que va `.obs-text-muted`; y
               el valor de una clave es ranura dedicada, así que la celda que SÍ
               lo muestra va en mono (V2-G01, clase 10). -->
          <q-td v-if="props.row.is_secret" class="obs-text-muted">
            <q-icon name="lock" size="xs" class="q-mr-xs" />
            {{
              props.row.value_set
                ? $t("keyStoreTable.secretSet")
                : $t("keyStoreTable.secretEmpty")
            }}
          </q-td>
          <!-- V2-G06 (tanda 2026-11-22): el td de q-table no salta de línea
               y un valor JSON de 924 caracteres dejaba la tabla en 7374 px con
               la columna fuera de alcance; salta en los espacios del valor. -->
          <q-td v-else class="mono obs-keystore__valor">
            {{ props.row.value }}
          </q-td>
        </q-tr>
      </template>
    </q-table>
  </div>
</template>

<script>
import KeyStoreForm from "@/components/modals/coresettings/KeyStoreForm.vue";
import mixins from "@/mixins/mixins";

export default {
  name: "KeyStoreTable",
  mixins: [mixins],
  data() {
    return {
      keystore: [],
      pagination: {
        rowsPerPage: 0,
        sortBy: "name",
        descending: true,
      },
    };
  },
  computed: {
    // columns computadas para reaccionar al cambio de idioma
    columns() {
      return [
        {
          name: "name",
          label: this.$t("keyStoreTable.colName"),
          field: "name",
          align: "left",
          sortable: true,
        },
        {
          name: "value",
          label: this.$t("keyStoreTable.colValue"),
          field: "value",
          align: "left",
          sortable: false,
        },
      ];
    },
  },
  methods: {
    getKeyStore() {
      this.$q.loading.show();

      this.$axios
        .get("/core/keystore/")
        .then((r) => {
          this.$q.loading.hide();
          this.keystore = r.data;
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    addKey() {
      this.$q
        .dialog({
          component: KeyStoreForm,
        })
        .onOk(() => {
          this.getKeyStore();
        });
    },
    editKey(key) {
      this.$q
        .dialog({
          component: KeyStoreForm,
          componentProps: {
            globalKey: key,
          },
        })
        .onOk(() => {
          this.getKeyStore();
        });
    },
    deleteKey(key) {
      this.$q
        .dialog({
          title: this.$t("keyStoreTable.deleteTitle", { name: key.name }),
          cancel: true,
          ok: { label: this.$t("keyStoreTable.delete"), color: "primary" },
        })
        .onOk(() => {
          this.$q.loading.show();
          this.$axios
            .delete(`/core/keystore/${key.id}/`)
            .then(() => {
              this.getKeyStore();
              this.$q.loading.hide();
              this.notifySuccess(
                this.$t("keyStoreTable.keyDeleted", { name: key.name }),
              );
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        });
    },
  },
  mounted() {
    this.getKeyStore();
  },
};
</script>
