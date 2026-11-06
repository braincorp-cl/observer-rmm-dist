<template>
  <div class="row">
    <div class="col-12">
      <!-- 050 (T028): en la página /automation esta barra la pone la cabecera
           de la sección (prop embedded). -->
      <q-btn
        v-if="!!selectedPolicy && !embedded"
        class="q-mr-sm"
        dense
        flat
        push
        @click="getTasks"
        icon="refresh"
      />
      <q-btn
        v-if="!!selectedPolicy && !embedded"
        icon="add"
        :label="$t('policyTasksTab.addTask')"
        no-caps
        dense
        flat
        push
        @click="showAddTask"
      />
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
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        class="tabs-tbl-sticky"
        :rows="tasks"
        :columns="columns"
        :rows-per-page-options="[0]"
        v-model:pagination="pagination"
        dense
        row-key="id"
        binary-state-sort
        hide-pagination
        virtual-scroll
      >
        <!-- No data Slot -->
        <template v-slot:no-data>
          <div class="full-width row flex-center q-gutter-sm">
            <span v-if="!selectedPolicy">{{
              $t("policyTasksTab.clickPolicy")
            }}</span>
            <span v-else>{{ $t("policyTasksTab.noTasks") }}</span>
          </div>
        </template>
        <!-- header slots -->
        <template v-slot:header-cell-enabled="props">
          <q-th auto-width :props="props">
            <small>{{ $t("policyTasksTab.enabled") }}</small>
          </q-th>
        </template>

        <template v-slot:header-cell-smsalert="props">
          <q-th auto-width :props="props">
            <q-icon name="phone_android" size="1.5em">
              <q-tooltip>{{ $t("policyTabsCommon.smsAlert") }}</q-tooltip>
            </q-icon>
          </q-th>
        </template>

        <template v-slot:header-cell-emailalert="props">
          <q-th auto-width :props="props">
            <q-icon name="email" size="1.5em">
              <q-tooltip>{{ $t("policyTabsCommon.emailAlert") }}</q-tooltip>
            </q-icon>
          </q-th>
        </template>
        <template v-slot:header-cell-dashboardalert="props">
          <q-th auto-width :props="props">
            <q-icon name="notifications" size="1.5em">
              <q-tooltip>{{ $t("policyTabsCommon.dashboardAlert") }}</q-tooltip>
            </q-icon>
          </q-th>
        </template>

        <template v-slot:header-cell-collector="props">
          <q-th auto-width :props="props">
            <q-icon name="mdi-database-arrow-up" size="1.5em">
              <q-tooltip>{{ $t("policyTasksTab.collectorTask") }}</q-tooltip>
            </q-icon>
          </q-th>
        </template>

        <!-- body slots -->
        <template v-slot:body="props">
          <q-tr class="cursor-pointer" @dblclick="showEditTask(props.row)">
            <!-- context menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item clickable v-close-popup @click="runTask(props.row)">
                  <q-item-section side>
                    <q-icon name="play_arrow" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("policyTasksTab.runTaskNow")
                  }}</q-item-section>
                </q-item>
                <q-item
                  clickable
                  v-close-popup
                  @click="showEditTask(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="edit" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("policyTabsCommon.edit")
                  }}</q-item-section>
                </q-item>
                <q-item clickable v-close-popup @click="deleteTask(props.row)">
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("policyTabsCommon.delete")
                  }}</q-item-section>
                </q-item>
                <q-separator />
                <q-item clickable v-close-popup @click="showStatus(props.row)">
                  <q-item-section side>
                    <q-icon name="sync" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("policyTabsCommon.policyStatus")
                  }}</q-item-section>
                </q-item>
                <q-separator />
                <q-item clickable v-close-popup>
                  <q-item-section>{{
                    $t("policyTabsCommon.close")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
            <!-- tds -->
            <q-td>
              <q-checkbox
              tabindex="-1"
                dense
                @update:model-value="
                  editTask(props.row, { enabled: !props.row.enabled })
                "
                v-model="props.row.enabled"
              />
            </q-td>

            <q-td>
              <q-checkbox
              tabindex="-1"
                dense
                @update:model-value="
                  editTask(props.row, { text_alert: !props.row.text_alert })
                "
                v-model="props.row.text_alert"
              />
            </q-td>
            <!-- email alert -->
            <q-td>
              <q-checkbox
              tabindex="-1"
                dense
                @update:model-value="
                  editTask(props.row, { email_alert: !props.row.email_alert })
                "
                v-model="props.row.email_alert"
              />
            </q-td>
            <!-- dashboard alert -->
            <q-td>
              <q-checkbox
              tabindex="-1"
                dense
                @update:model-value="
                  editTask(props.row, {
                    dashboard_alert: !props.row.dashboard_alert,
                  })
                "
                v-model="props.row.dashboard_alert"
              />
            </q-td>
            <!-- is collector task -->
            <q-td>
              <q-icon
                v-if="!!props.row.custom_field"
                style="font-size: 1.3rem"
                name="check"
              >
                <q-tooltip>{{
                  $t("policyTasksTab.collectorTooltip")
                }}</q-tooltip>
              </q-icon>
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
                >{{ props.row.name }}</span
              >
            </q-td>
            <q-td>{{ props.row.schedule }}</q-td>
            <q-td>
              <span
                style="cursor: pointer; text-decoration: underline"
                @click="showStatus(props.row)"
                class="status-cell text-primary"
                >{{ $t("policyTabsCommon.seeStatus") }}</span
              >
            </q-td>
            <q-td>{{ props.row.check_name }}</q-td>
          </q-tr>
        </template>
      </q-table>
      </div>
    </div>
  </div>
</template>

<script>
import mixins from "@/mixins/mixins";
import AutomatedTaskForm from "@/components/tasks/AutomatedTaskForm.vue";
import PolicyStatus from "@/components/automation/modals/PolicyStatus.vue";

import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "PolicyAutomatedTasksTab",
  // 🪤 UNA sola clave `mixins`: una segunda PISA a la primera
  // y el mixin queda declarado y muerto, sin que el build ni el lint avisen.
  mixins: [mixins, mixinRejillaTabla],
  props: {
    selectedPolicy: !Number,
    embedded: { type: Boolean, default: false },
  },
  data() {
    return {
      tasks: [],
      pagination: {
        rowsPerPage: 0,
        sortBy: "name",
        descending: false,
      },
    };
  },
  watch: {
    selectedPolicy: function (newValue, oldValue) {
      if (newValue !== oldValue) this.getTasks();
    },
  },
  computed: {
    rejillaFilas() {
      return this.tasks;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
    columns() {
      return [
        { name: "enabled", align: "left", field: "enabled" },
        { name: "smsalert", field: "text_alert", align: "left" },
        { name: "emailalert", field: "email_alert", align: "left" },
        { name: "dashboardalert", field: "dashboard_alert", align: "left" },
        {
          name: "collector",
          label: this.$t("policyTasksTab.colCollector"),
          field: "custom_field",
          align: "left",
          sortable: true,
        },
        {
          name: "name",
          label: this.$t("policyTasksTab.colName"),
          field: "name",
          align: "left",
          sortable: true,
        },
        {
          name: "schedule",
          label: this.$t("policyTasksTab.colSchedule"),
          field: "schedule",
          align: "left",
          sortable: true,
        },
        {
          name: "status",
          label: this.$t("policyTasksTab.colMoreInfo"),
          field: "more_info",
          align: "left",
          sortable: true,
        },
        {
          name: "check_name",
          label: this.$t("policyTasksTab.colAssignedCheck"),
          field: "check_name",
          align: "left",
          sortable: true,
        },
      ];
    },
  },
  methods: {
    getTasks() {
      this.$q.loading.show();
      this.$axios
        .get(`/automation/policies/${this.selectedPolicy}/tasks/`)
        .then((r) => {
          this.tasks = r.data;
          this.$q.loading.hide();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    editTask(task, data) {
      this.$axios
        .put(`/tasks/${task.id}/`, data)
        .then((r) => {
          this.$q.loading.hide();
          this.notifySuccess(r.data);
          this.getTasks();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    showAddTask() {
      this.$q
        .dialog({
          component: AutomatedTaskForm,
          componentProps: {
            parent: { policy: this.selectedPolicy },
          },
        })
        .onOk(this.getTasks);
    },
    showEditTask(task) {
      this.$q
        .dialog({
          component: AutomatedTaskForm,
          componentProps: {
            task: task,
            parent: { policy: this.selectedPolicy },
          },
        })
        .onOk(this.getTasks);
    },
    showStatus(task) {
      this.$q.dialog({
        component: PolicyStatus,
        componentProps: {
          type: "task",
          item: task,
        },
      });
    },
    runTask(task) {
      if (!task.enabled) {
        this.notifyError(this.$t("policyTasksTab.taskDisabled"));
        return;
      }

      this.$q
        .dialog({
          title: this.$t("policyTasksTab.areYouSure"),
          message: this.$t("policyTasksTab.runTaskMsg", { name: task.name }),
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          this.$q.loading.show();
          this.$axios
            .post(`/automation/tasks/${task.id}/run/`)
            .then(() => {
              this.$q.loading.hide();
              this.notifySuccess(this.$t("policyTasksTab.taskInitiated"));
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        });
    },
    deleteTask(task) {
      this.$q
        .dialog({
          title: this.$t("policyTasksTab.areYouSure"),
          message: this.$t("policyTasksTab.deleteTaskMsg", { name: task.name }),
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          this.$q.loading.show();
          this.$axios
            .delete(`/tasks/${task.id}/`)
            .then(() => {
              this.getTasks();
              this.$q.loading.hide();
              this.notifySuccess(this.$t("policyTasksTab.taskDeleted"));
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        });
    },
  },
  created() {
    this.getTasks();
  },
};
</script>
