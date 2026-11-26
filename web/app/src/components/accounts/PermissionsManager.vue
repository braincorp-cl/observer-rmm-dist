<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="min-width: 60vw; height: 75vh">
      <q-bar>
        <q-btn @click="getRoles" class="q-mr-sm" dense flat icon="refresh" />
        <q-space />{{ $t("permissionsManager.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup />
      </q-bar>
      <!-- 050 (V2-G15): PATRÓN DE REJILLA (composables/rejillaTabla.js): una
           parada de TAB por tabla, flechas arriba/abajo por fila y
           izquierda/derecha hasta los botones de acción. -->
      <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
      <q-table
        dense
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        class="tabs-tbl-sticky"
        style="max-height: 70vh"
        binary-state-sort
        virtual-scroll
        @virtual-scroll="alDesplazarVirtual"
        ref="tablaRejilla"
        :rows="roles"
        :columns="columns"
        row-key="id"
        :pagination="{ rowsPerPage: 0, sortBy: 'name', descending: false }"
        :no-data-label="$t('permissionsManager.noRoles')"
        :rows-per-page-options="[0]"
      >
        <template v-slot:top>
          <q-btn
            color="primary"
            flat
            dense
            icon="add"
            :label="$t('permissionsManager.newRole')"
            @click="showAddRoleModal"
          />
        </template>
        <template v-slot:body="props">
          <q-tr
            :props="props"
            @dblclick="showEditRoleModal(props.row)"
            class="cursor-pointer"
          >
            <q-menu context-menu auto-close>
              <q-list dense style="min-width: 200px">
                <q-item clickable @click="showEditRoleModal(props.row)">
                  <q-item-section side>
                    <q-icon name="edit" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("permissionsManager.edit")
                  }}</q-item-section>
                </q-item>
                <q-item
                  clickable
                  @click="deleteRole(props.row)"
                  :disable="props.row.user_count > 0"
                >
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("permissionsManager.delete")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item clickable>
                  <q-item-section>{{
                    $t("permissionsManager.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
            <q-td key="name" :props="props"
              ><span
                class="obs-rej__host"
                :data-fila="props.rowIndex"
                :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                @focus="filaFoco = props.rowIndex"
                >{{ props.row.name }}</span
              ></q-td
            >
            <q-td key="is_superuser" :props="props">
              <q-icon
                v-if="props.row.is_superuser"
                name="done"
                size="sm"
              />
            </q-td>
            <q-td key="user_count" :props="props" class="mono">
              {{ props.row.user_count }}
            </q-td>
            <q-td key="actions" :props="props" class="obs-nowrap" @dblclick.stop>
              <q-btn
                flat
                dense
                round
                icon="edit"
                tabindex="-1"
                :aria-label="$t('permissionsManager.edit')"
                @click="showEditRoleModal(props.row)"
              />
              <q-btn
                flat
                dense
                round
                icon="delete"
                tabindex="-1"
                :aria-label="$t('permissionsManager.delete')"
                :disable="props.row.user_count > 0"
                @click="deleteRole(props.row)"
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
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent } from "quasar";
import { fetchRoles, removeRole } from "@/api/accounts";
import { notifySuccess } from "@/utils/notify";
import { usarRejillaTabla } from "@/composables/rejillaTabla";

// ui imports
import RolesForm from "@/components/accounts/RolesForm.vue";

export default {
  name: "PermissionsManager",
  emits: [...useDialogPluginComponent.emits],
  setup() {
    // setup quasar
    const $q = useQuasar();
    const { t } = useI18n();
    const { dialogRef, onDialogHide } = useDialogPluginComponent();

    // static data
    const columns = computed(() => [
      {
        name: "name",
        label: t("permissionsManager.colName"),
        field: "name",
        align: "left",
        sortable: true,
      },
      {
        name: "is_superuser",
        label: t("permissionsManager.colSuperuser"),
        field: "is_superuser",
        align: "left",
        sortable: true,
      },
      {
        name: "user_count",
        label: t("permissionsManager.colAssignedUsers"),
        field: "user_count",
        align: "left",
        sortable: true,
        // V2-G01: la vara dice «conteos y tamanos en su celda o badge» en mono.
        classes: "mono",
      },
      {
        name: "actions",
        label: "",
        field: "actions",
        align: "right",
      },
    ]);

    // permission manager logic
    const roles = ref([]);
    const loading = ref(false);

    // 050 (V2-G15): patrón de rejilla (ver composables/rejillaTabla.js).
    const tablaRejilla = ref();
    const { filaFoco, alEntrarFoco, alTeclaRejilla, alDesplazarVirtual } =
      usarRejillaTabla({
        refTabla: tablaRejilla,
        filas: () => roles.value,
      });

    function showEditRoleModal(role) {
      $q.dialog({
        component: RolesForm,
        componentProps: {
          role: role,
        },
      }).onOk(getRoles);
    }

    function showAddRoleModal() {
      $q.dialog({
        component: RolesForm,
      }).onOk(getRoles);
    }

    async function getRoles() {
      loading.value = true;
      roles.value = await fetchRoles();
      loading.value = false;
    }

    async function deleteRole(role) {
      $q.dialog({
        title: t("permissionsManager.confirmDelete", { name: role.name }),
        cancel: true,
        ok: { label: t("permissionsManager.delete"), color: "primary" },
      }).onOk(async () => {
        try {
          $q.loading.show();
          const result = await removeRole(role.id);
          notifySuccess(result);
          await getRoles();
        } catch (e) {
          console.error(e);
        }
        $q.loading.hide();
      });
    }

    // vue lifecycle hooks
    onMounted(getRoles);

    return {
      // reactive data
      roles,
      loading,
      tablaRejilla,
      filaFoco,

      // non-reactive data
      columns,

      // methods
      getRoles,
      deleteRole,
      showAddRoleModal,
      showEditRoleModal,
      alEntrarFoco,
      alTeclaRejilla,
      alDesplazarVirtual,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
