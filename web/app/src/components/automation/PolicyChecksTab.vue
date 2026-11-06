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
        @click="getChecks"
        icon="refresh"
      />
      <q-btn-dropdown
        v-if="!!selectedPolicy && !embedded"
        icon="add"
        :label="$t('policyChecksTab.new')"
        no-caps
        dense
        flat
      >
        <q-list dense style="min-width: 200px">
          <q-item clickable v-close-popup @click="showCheckModal('diskspace')">
            <q-item-section side>
              <q-icon size="xs" name="far fa-hdd" />
            </q-item-section>
            <q-item-section>{{
              $t("policyChecksTab.diskSpaceCheck")
            }}</q-item-section>
          </q-item>
          <q-item clickable v-close-popup @click="showCheckModal('ping')">
            <q-item-section side>
              <q-icon size="xs" name="fas fa-network-wired" />
            </q-item-section>
            <q-item-section>{{
              $t("policyChecksTab.pingCheck")
            }}</q-item-section>
          </q-item>
          <q-item clickable v-close-popup @click="showCheckModal('cpuload')">
            <q-item-section side>
              <q-icon size="xs" name="fas fa-microchip" />
            </q-item-section>
            <q-item-section>{{
              $t("policyChecksTab.cpuLoadCheck")
            }}</q-item-section>
          </q-item>
          <q-item clickable v-close-popup @click="showCheckModal('memory')">
            <q-item-section side>
              <q-icon size="xs" name="fas fa-memory" />
            </q-item-section>
            <q-item-section>{{
              $t("policyChecksTab.memoryCheck")
            }}</q-item-section>
          </q-item>
          <q-item clickable v-close-popup @click="showCheckModal('winsvc')">
            <q-item-section side>
              <q-icon size="xs" name="fas fa-cogs" />
            </q-item-section>
            <q-item-section>{{
              $t("policyChecksTab.windowsServiceCheck")
            }}</q-item-section>
          </q-item>
          <q-item clickable v-close-popup @click="showCheckModal('script')">
            <q-item-section side>
              <q-icon size="xs" name="fas fa-terminal" />
            </q-item-section>
            <q-item-section>{{
              $t("policyChecksTab.scriptCheck")
            }}</q-item-section>
          </q-item>
          <q-item clickable v-close-popup @click="showCheckModal('eventlog')">
            <q-item-section side>
              <q-icon size="xs" name="fas fa-clipboard-list" />
            </q-item-section>
            <q-item-section>{{
              $t("policyChecksTab.eventLogCheck")
            }}</q-item-section>
          </q-item>
        </q-list>
      </q-btn-dropdown>

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
        :rows="checks"
        :columns="columns"
        v-model:pagination="pagination"
        :rows-per-page-options="[0]"
        row-key="id"
        binary-state-sort
        dense
        hide-pagination
        virtual-scroll
      >
        <!-- No data Slot -->
        <template v-slot:no-data>
          <div class="full-width row flex-center q-gutter-sm">
            <span v-if="!selectedPolicy">{{
              $t("policyChecksTab.clickPolicy")
            }}</span>
            <span v-else>{{ $t("policyChecksTab.noChecks") }}</span>
          </div>
        </template>
        <!-- header slots -->
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
        <template v-slot:header-cell-statusicon="props">
          <q-th auto-width :props="props"></q-th>
        </template>
        <!-- body slots -->
        <template v-slot:body="props">
          <q-tr
            :props="props"
            class="cursor-pointer"
            @dblclick="showCheckModal(props.row.check_type, props.row)"
          >
            <!-- context menu -->
            <q-menu context-menu>
              <q-list dense style="min-width: 200px">
                <q-item
                  clickable
                  v-close-popup
                  @click="showCheckModal(props.row.check_type, props.row)"
                >
                  <q-item-section side>
                    <q-icon name="edit" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("policyTabsCommon.edit")
                  }}</q-item-section>
                </q-item>
                <q-item clickable v-close-popup @click="deleteCheck(props.row)">
                  <q-item-section side>
                    <q-icon name="delete" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("policyTabsCommon.delete")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

                <q-item
                  clickable
                  v-close-popup
                  @click="showPolicyStatus(props.row)"
                >
                  <q-item-section side>
                    <q-icon name="sync" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("policyTabsCommon.policyStatus")
                  }}</q-item-section>
                </q-item>

                <q-separator></q-separator>

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
                  checkAlert(props.row.id, 'Text', props.row.text_alert)
                "
                v-model="props.row.text_alert"
              />
            </q-td>
            <q-td>
              <q-checkbox
              tabindex="-1"
                dense
                @update:model-value="
                  checkAlert(props.row.id, 'Email', props.row.email_alert)
                "
                v-model="props.row.email_alert"
              />
            </q-td>
            <q-td>
              <q-checkbox
              tabindex="-1"
                dense
                @update:model-value="
                  checkAlert(
                    props.row.id,
                    'Dashboard',
                    props.row.dashboard_alert,
                  )
                "
                v-model="props.row.dashboard_alert"
              />
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
                >{{ props.row.readable_desc }}</span
              >
            </q-td>
            <q-td>
              <span
                style="cursor: pointer; text-decoration: underline"
                @click="showPolicyStatus(props.row)"
                class="status-cell text-primary"
                >{{ $t("policyTabsCommon.seeStatus") }}</span
              >
            </q-td>
            <q-td v-if="props.row.assignedtasks.length > 1" class="mono">{{
              $t("policyChecksTab.tasksCount", {
                count: props.row.assignedtasks.length,
              })
            }}</q-td>
            <q-td v-else-if="props.row.assignedtasks.length === 1">{{
              props.row.assignedtasks[0].name
            }}</q-td>
            <q-td v-else></q-td>
          </q-tr>
        </template>
      </q-table>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";
import mixins from "@/mixins/mixins";
import PolicyStatus from "@/components/automation/modals/PolicyStatus.vue";
import DiskSpaceCheck from "@/components/checks/DiskSpaceCheck.vue";
import PingCheck from "@/components/checks/PingCheck.vue";
import CpuLoadCheck from "@/components/checks/CpuLoadCheck.vue";
import MemCheck from "@/components/checks/MemCheck.vue";
import WinSvcCheck from "@/components/checks/WinSvcCheck.vue";
import ScriptCheck from "@/components/checks/ScriptCheck.vue";
import EventLogCheck from "@/components/checks/EventLogCheck.vue";

import { mixinRejillaTabla } from "@/composables/rejillaTabla";

export default {
  name: "PolicyChecksTab",
  // 🪤 UNA sola clave `mixins`: una segunda PISA a la primera
  // y el mixin queda declarado y muerto, sin que el build ni el lint avisen.
  mixins: [mixins, mixinRejillaTabla],
  props: {
    selectedPolicy: !Number,
    embedded: { type: Boolean, default: false },
  },
  data() {
    return {
      checks: [],
      pagination: {
        rowsPerPage: 0,
        sortBy: "status",
        descending: true,
      },
    };
  },
  watch: {
    selectedPolicy: function (newValue, oldValue) {
      if (newValue !== oldValue) this.getChecks();
    },
  },
  computed: {
    rejillaFilas() {
      return this.checks;
    },
    rejillaRef() {
      return "tablaRejilla";
    },
    ...mapState(["dash_positive_color", "dash_warning_color"]),
    columns() {
      return [
        { name: "smsalert", field: "text_alert", align: "left" },
        { name: "emailalert", field: "email_alert", align: "left" },
        { name: "dashboardalert", field: "dashboard_alert", align: "left" },
        {
          name: "desc",
          field: "readable_desc",
          label: this.$t("policyChecksTab.colDescription"),
          align: "left",
          sortable: true,
        },
        {
          name: "status",
          label: this.$t("policyChecksTab.colStatus"),
          field: "status",
          align: "left",
        },
        {
          name: "assigned_task",
          label: this.$t("policyChecksTab.colAssignedTasks"),
          field: "assigned_task",
          align: "left",
          sortable: true,
        },
      ];
    },
  },
  methods: {
    getChecks() {
      this.$q.loading.show();
      this.$axios
        .get(`/automation/policies/${this.selectedPolicy}/checks/`)
        .then((r) => {
          this.checks = r.data;
          this.$q.loading.hide();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    checkAlert(id, alert_type, action) {
      this.$q.loading.show();
      const data = {};

      if (alert_type === "Email") {
        data.email_alert = !action;
      } else if (alert_type === "Text") {
        data.text_alert = !action;
      } else {
        data.dashboard_alert = !action;
      }

      data.check_alert = true;
      const typeMap = {
        Text: this.$t("policyChecksTab.catText"),
        Email: this.$t("policyChecksTab.catEmail"),
        Dashboard: this.$t("policyChecksTab.catDashboard"),
      };
      const actLabel = !action
        ? this.$t("policyChecksTab.actEnabled")
        : this.$t("policyChecksTab.actDisabled");
      const color = !action
        ? this.dash_positive_color
        : this.dash_warning_color;
      this.$axios
        .put(`/checks/${id}/`, data)
        .then(() => {
          this.$q.loading.hide();
          this.$q.notify({
            color: color,
            icon: "fas fa-check-circle",
            message: this.$t("policyChecksTab.alertToggled", {
              type: typeMap[alert_type],
              action: actLabel,
            }),
          });
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    deleteCheck(check) {
      this.$q
        .dialog({
          title: this.$t("policyChecksTab.deleteCheckTitle", {
            type: check.check_type,
          }),
          ok: { label: this.$t("policyTabsCommon.delete"), color: "primary" },
          cancel: true,
        })
        .onOk(() => {
          this.$q.loading.show();
          this.$axios
            .delete(`/checks/${check.id}/`)
            .then(() => {
              this.getChecks();
              this.$q.loading.hide();
              this.notifySuccess(this.$t("policyChecksTab.checkDeleted"));
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        });
    },
    showPolicyStatus(check) {
      this.$q.dialog({
        component: PolicyStatus,
        componentProps: {
          type: "check",
          item: check,
        },
      });
    },
    showCheckModal(type, check) {
      let component;

      if (type === "diskspace") component = DiskSpaceCheck;
      else if (type === "memory") component = MemCheck;
      else if (type === "cpuload") component = CpuLoadCheck;
      else if (type === "ping") component = PingCheck;
      else if (type === "winsvc") component = WinSvcCheck;
      else if (type === "eventlog") component = EventLogCheck;
      else if (type === "script") component = ScriptCheck;
      else return;

      this.$q
        .dialog({
          component: component,
          componentProps: {
            check: check,
            parent: !check ? { policy: this.selectedPolicy } : undefined,
          },
        })
        .onOk(this.getChecks);
    },
  },
  created() {
    this.getChecks();
  },
};
</script>
