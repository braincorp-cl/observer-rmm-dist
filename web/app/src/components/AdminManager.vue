<template>
  <q-card style="width: 65vw; max-width: 70vw; min-height: 50vh">
    <q-bar>
      <q-btn
        ref="refresh"
        @click="getUsers"
        class="q-mr-sm"
        dense
        flat
        push
        icon="refresh"
      />{{ $t("adminManager.title") }}
      <q-space />
      <q-btn dense flat icon="close" v-close-popup>
        <q-tooltip>{{ $t("adminManager.close") }}</q-tooltip>
      </q-btn>
    </q-bar>
    <div class="q-pa-md">
      <div class="q-gutter-sm">
        <q-btn
          ref="new"
          :label="$t('adminManager.new')"
          dense
          flat
          push
          unelevated
          no-caps
          icon="add"
          @click="showAddUserModal"
        />
      </div>
      <!-- 🪤 050 (V2-G15): PATRON DE REJILLA. Con una parada de tabulador por fila,
           el tabulador aterriza en las filas SOBRE-RENDERIZADAS que el
           desplazamiento virtual deja fuera del contenedor, donde el anillo no se
           dibuja a proposito porque el control esta entero fuera de pantalla
           (medido: 13 paradas en y=785..1031 y en y=-321..-239 sobre un viewport de
           757, en los dos temas). La tabla pasa a ser UNA parada y las flechas
           mueven la fila, con `scrollTo` POR INDICE. Los dos oyentes de la raiz son
           el seguro: cuando el reciclaje destruye el nodo enfocado, Chrome SUBE el
           foco al scroller (`tabindex=-1`) y desde ahi la rejilla quedaria
           muerta. -->
      <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
      <q-table
        ref="tablaRejilla"
        @virtual-scroll="alDesplazarVirtual"
        :virtual-scroll-item-size="33"
        :virtual-scroll-sticky-size-start="28"
        dense
        :rows="users"
        :columns="columns"
        v-model:pagination="pagination"
        row-key="id"
        binary-state-sort
        hide-pagination
        virtual-scroll
      >
        <!-- header slots -->
        <template v-slot:header-cell-is_active="props">
          <q-th :props="props" auto-width>
            <q-icon name="power_settings_new" size="1.5em">
              <q-tooltip>{{ $t("adminManager.enableUser") }}</q-tooltip>
            </q-icon>
          </q-th>
        </template>

        <template v-slot:header-cell-sso="props">
          <q-th :props="props" auto-width></q-th>
        </template>

        <!-- No data Slot -->
        <template v-slot:no-data>
          <div class="full-width row flex-center q-gutter-sm">
            <span v-if="users.length === 0">{{
              $t("adminManager.noUsers")
            }}</span>
          </div>
        </template>

        <!-- body slots -->
        <template v-slot:body="props">
          <q-tr
            :props="props"
            class="cursor-pointer"
            @dblclick="showEditUserModal(props.row)"
          >
            <!-- context menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item
                  clickable
                  v-close-popup
                  @click="showEditUserModal(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="edit" />
                  </q-item-section>
                  <q-item-section>{{ $t("adminManager.edit") }}</q-item-section>
                </q-item>
                <q-item
                  clickable
                  v-close-popup
                  @click="deleteUser(props.row)"
                  :disable="props.row.username === logged_in_user"
                >
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("adminManager.delete")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item
                  clickable
                  v-close-popup
                  @click="ResetPassword(props.row)"
                  id="context-reset"
                  :disable="props.row.social_accounts.length !== 0"
                >
                  <q-item-section side>
                    <q-icon name="autorenew" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("adminManager.resetPassword")
                  }}</q-item-section>
                </q-item>

                <q-item
                  clickable
                  v-close-popup
                  @click="reset2FA(props.row)"
                  id="context-reset"
                  :disable="props.row.social_accounts.length !== 0"
                >
                  <q-item-section side>
                    <q-icon name="autorenew" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("adminManager.resetTwoFactor")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item
                  clickable
                  v-close-popup
                  @click="showSessions(props.row)"
                  id="context-reset"
                >
                  <q-item-section side>
                    <q-icon name="groups" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("adminManager.showActiveSessions")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item clickable v-close-popup>
                  <q-item-section>{{
                    $t("adminManager.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
            <!-- enabled checkbox -->
            <q-td>
              <q-checkbox
              tabindex="-1"
                dense
                @update:model-value="toggleEnabled(props.row)"
                v-model="props.row.is_active"
                :disable="props.row.username === logged_in_user"
              />
            </q-td>
            <q-td>
              <q-chip
                v-if="props.row.social_accounts.length > 0"
                color="primary"
                dense
                >{{ $t("adminManager.sso") }}</q-chip
              >
            </q-td>
            <!-- Host enfocable de la fila: la ÚNICA parada de tabulador de la tabla.
                 Desde aquí la tecla Menú abre el menú contextual de la fila —que antes
                 era sólo de ratón— y las flechas izquierda/derecha llegan a los demás
                 controles de la fila. -->
            <q-td>
              <span
                class="obs-rej__host"
                :data-fila="props.rowIndex"
                :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                @focus="filaFoco = props.rowIndex"
                >{{ props.row.username }}</span
              >
            </q-td>
            <q-td>{{ props.row.first_name }} {{ props.row.last_name }}</q-td>
            <q-td>{{ props.row.email }}</q-td>
            <q-td v-if="props.row.last_login">{{
              formatDate(props.row.last_login)
            }}</q-td>
            <q-td v-else>{{ $t("adminManager.never") }}</q-td>
            <q-td class="mono">{{ props.row.last_login_ip }}</q-td>
          </q-tr>
        </template>
      </q-table>
      </div>
    </div>
  </q-card>
</template>

<script>
import mixins from "@/mixins/mixins";
import { computed } from "vue";
import { useStore } from "vuex";
import { useQuasar } from "quasar";

import { mapState as piniaMapState } from "pinia";
import { useAuthStore } from "@/stores/auth";
import UserForm from "@/components/modals/admin/UserForm.vue";
import UserResetPasswordForm from "@/components/modals/admin/UserResetPasswordForm.vue";
// SSO descartado (ADR-010, 2026-06-17): import de SSOAccountsTable eliminado (módulo ee/sso vaciado).
import UserSessionsTable from "@/components/accounts/UserSessionsTable.vue";

import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "AdminManager",
  // 🪤 UNA sola clave `mixins`: una segunda PISA a la primera
  // y el mixin queda declarado y muerto, sin que el build ni el lint avisen.
  mixins: [mixins, mixinRejillaTabla],
  setup() {
    // setup vuex
    const store = useStore();
    const formatDate = computed(() => store.getters.formatDate);

    const $q = useQuasar();

    async function showSessions(user) {
      $q.dialog({
        component: UserSessionsTable,
        componentProps: {
          user,
        },
      });
    }

    return {
      formatDate,
      showSessions,
    };
  },
  data() {
    return {
      users: [],
      pagination: {
        rowsPerPage: 0,
        sortBy: "username",
        descending: true,
      },
    };
  },
  methods: {
    getUsers() {
      this.$q.loading.show();
      this.$axios
        .get("/accounts/users/")
        .then((r) => {
          this.users = r.data;
          this.$q.loading.hide();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    deleteUser(user) {
      this.$q
        .dialog({
          title: this.$t("adminManager.deleteUserTitle", {
            username: user.username,
          }),
          cancel: true,
          ok: { label: this.$t("adminManager.delete"), color: "primary" },
        })
        .onOk(() => {
          this.$axios.delete(`/accounts/${user.id}/users/`).then(() => {
            this.getUsers();
            this.notifySuccess(
              this.$t("adminManager.userDeleted", { username: user.username }),
            );
          });
        });
    },
    showEditUserModal(user) {
      this.$q
        .dialog({
          component: UserForm,
          componentProps: {
            user: user,
          },
        })
        .onOk(() => {
          this.getUsers();
        });
    },
    showAddUserModal() {
      this.$q
        .dialog({
          component: UserForm,
        })
        .onOk(() => {
          this.getUsers();
        });
    },
    toggleEnabled(user) {
      if (user.username === this.logged_in_user) {
        return;
      }
      let text = !user.is_active
        ? this.$t("adminManager.userEnabled")
        : this.$t("adminManager.userDisabled");

      const data = {
        id: user.id,
        is_active: !user.is_active,
      };

      this.$axios.put(`/accounts/${data.id}/users/`, data).then(() => {
        this.notifySuccess(text);
      });
    },
    ResetPassword(user) {
      this.$q
        .dialog({
          component: UserResetPasswordForm,
          componentProps: {
            user: user,
          },
        })
        .onOk(() => {
          this.getUsers();
        });
    },
    reset2FA(user) {
      const data = {
        id: user.id,
      };

      this.$q
        .dialog({
          title: this.$t("adminManager.reset2faTitle", {
            username: user.username,
          }),
          cancel: true,
          ok: { label: this.$t("adminManager.reset"), color: "positive" },
        })
        .onOk(() => {
          this.$axios
            .put("/accounts/users/reset_totp/", data)
            .then((response) => {
              this.notifySuccess(response.data, 4000);
            });
        });
    },
  },
  computed: {
    rejillaFilas() {
      return this.users;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
    ...piniaMapState(useAuthStore, {
      logged_in_user: (state) => state.username,
    }),
    // columns computadas para reaccionar al cambio de idioma
    columns() {
      return [
        {
          name: "is_active",
          label: this.$t("adminManager.colActive"),
          field: "is_active",
          align: "left",
        },
        {
          name: "sso",
          label: "",
          field: "sso",
          align: "left",
          sortable: true,
        },
        {
          name: "username",
          label: this.$t("adminManager.colUsername"),
          field: "username",
          align: "left",
          sortable: true,
        },
        {
          name: "name",
          label: this.$t("adminManager.colName"),
          field: "name",
          align: "left",
          sortable: true,
        },
        {
          name: "email",
          label: this.$t("adminManager.colEmail"),
          field: "email",
          align: "left",
          sortable: true,
        },
        {
          name: "last_login",
          label: this.$t("adminManager.colLastLogin"),
          field: "last_login",
          align: "left",
          sortable: true,
        },
        {
          name: "last_login_ip",
          label: this.$t("adminManager.colLastLoginFrom"),
          field: "last_login_ip",
          align: "left",
          sortable: true,
        },
      ];
    },
  },
  mounted() {
    this.getUsers();
  },
};
</script>
