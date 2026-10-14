<template>
  <!--
    050 ola 2 · Flota en dirección 1c (maqueta referencia/flota.png): columna de
    clientes y sitios, 5 indicadores de urgencia calculados sobre la lista de
    /agents/ que ya se pide, tipo de equipo como grupo de botones (sin q-tabs) y la
    tabla de equipos. El menú contextual del árbol y los filtros son los de v1.
  -->
  <q-page class="obs-fleet">
    <aside class="obs-fleet__ctx" :aria-label="$t('fleet.clientsAndSites')">
      <div class="obs-fleet__ctx-head">
        <div class="row items-center no-wrap">
          <div class="obs-fleet__eyebrow col">{{ $t("fleet.clientsAndSites") }}</div>
          <q-btn
            dense
            outline
            icon="add"
            class="obs-fleet__add"
            :aria-label="$t('fleet.addClientOrSite')"
          >
            <q-tooltip>{{ $t("fleet.addClientOrSite") }}</q-tooltip>
            <q-menu auto-close>
              <q-list dense style="min-width: 160px">
                <q-item clickable @click="showAddClient">
                  <q-item-section>{{ $t("nav.client") }}</q-item-section>
                </q-item>
                <q-item clickable @click="showAddSiteFromHeader">
                  <q-item-section>{{ $t("nav.site") }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </div>
        <q-input
          v-model="treeFilter"
          dense
          outlined
          clearable
          class="q-mt-sm"
          :placeholder="$t('fleet.filterClients')"
          :aria-label="$t('fleet.filterClients')"
        >
          <template v-slot:prepend><q-icon name="search" size="16px" /></template>
        </q-input>
      </div>
      <div v-if="!treeReady" class="q-pa-md text-center">
        <q-spinner size="32px" color="primary" />
      </div>
      <div v-else class="obs-fleet__tree scroll">
        <q-item
          clickable
          dense
          :active="allClientsActive"
          active-class="obs-fleet__node--active"
          class="obs-fleet__all"
          @click="clearTreeSelected"
        >
          <q-item-section>{{ $t("dashboard.allClients") }}</q-item-section>
          <q-item-section side>
            <span class="mono obs-fleet__count">{{ totalAgents }}</span>
          </q-item-section>
        </q-item>
        <q-tree
          ref="tree"
          :nodes="clientsTree"
          node-key="raw"
          :filter="treeFilter || ''"
          :no-nodes-label="$t('dashboard.noClients')"
          :no-results-label="$t('fleet.noClientMatch')"
          selected-color="primary"
          v-model:selected="selectedTree"
          @update:selected="$store.dispatch('refreshDashboard')"
        >
          <template v-slot:default-header="props">
            <div class="row items-center no-wrap full-width obs-fleet__node">
              <span
                class="ellipsis col"
                :class="props.node.children ? 'obs-fleet__client' : 'obs-fleet__site'"
                :title="props.node.label"
                >{{ props.node.label }}</span
              >
              <q-icon
                v-for="st in nodeStates(props.node)"
                :key="st"
                :name="stateIcon(st)"
                :class="`obs-fleet__state obs-fleet__state--${st}`"
                size="14px"
                :aria-label="stateLabel(st)"
              >
                <q-tooltip>{{ stateLabel(st) }}</q-tooltip>
              </q-icon>
              <span class="mono obs-fleet__count">{{
                props.node.children
                  ? props.node.client.agent_count
                  : props.node.site.agent_count
              }}</span>
          <q-menu context-menu>
            <q-list dense style="min-width: 200px">
              <q-item
                clickable
                v-close-popup
                @click="showEditModal(props.node)"
              >
                <q-item-section side>
                  <q-icon name="edit" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.edit")
                }}</q-item-section>
              </q-item>
              <q-item
                clickable
                v-close-popup
                @click="showDeleteModal(props.node)"
              >
                <q-item-section side>
                  <q-icon name="delete" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.delete")
                }}</q-item-section>
              </q-item>

              <q-separator></q-separator>

              <q-item
                v-if="props.node.children"
                clickable
                v-close-popup
                @click="showAddSiteModal(props.node)"
              >
                <q-item-section side>
                  <q-icon name="add" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.addSite")
                }}</q-item-section>
              </q-item>

              <q-item
                clickable
                v-close-popup
                @click="showToggleMaintenance(props.node)"
              >
                <q-item-section side>
                  <q-icon name="construction" />
                </q-item-section>
                <q-item-section>{{
                  props.node.color === "green"
                    ? $t("dashboard.disableMaintenance")
                    : $t("dashboard.enableMaintenance")
                }}</q-item-section>
              </q-item>

              <!-- Feature 049-B2: monitoreo de actividad por cliente/sitio -->
              <q-item
                clickable
                v-close-popup
                @click="showActivityMonitoring(props.node)"
              >
                <q-item-section side>
                  <q-icon name="timeline" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.activityMonitoring")
                }}</q-item-section>
              </q-item>

              <q-item
                v-if="props.node.children === undefined"
                clickable
                v-close-popup
                @click="showInstallAgent(props.node)"
              >
                <q-item-section side>
                  <q-icon name="cloud_download" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.installAgent")
                }}</q-item-section>
              </q-item>

              <q-item
                clickable
                v-close-popup
                @click="showPolicyAdd(props.node)"
              >
                <q-item-section side>
                  <q-icon name="policy" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.assignAutomationPolicy")
                }}</q-item-section>
              </q-item>

              <q-item
                clickable
                v-close-popup
                @click="showAlertTemplateAdd(props.node)"
              >
                <q-item-section side>
                  <q-icon name="error" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.assignAlertTemplate")
                }}</q-item-section>
              </q-item>

              <q-item clickable v-ripple @click="getURLActions">
                <q-item-section side>
                  <q-icon name="open_in_new" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.runUrlAction")
                }}</q-item-section>
                <q-item-section side>
                  <q-icon name="keyboard_arrow_right" />
                </q-item-section>
                <q-menu auto-close anchor="top end" self="top start">
                  <q-list>
                    <q-item
                      v-for="action in urlActions"
                      :key="action.id"
                      dense
                      clickable
                      v-close-popup
                      @click="
                        runURLAction(
                          props.node.id,
                          action.id,
                          props.node.children ? 'client' : 'site',
                        )
                      "
                    >
                      {{ action.name }}
                    </q-item>
                  </q-list>
                </q-menu>
              </q-item>

              <!-- Bulk Run Checks -->
              <q-item
                clickable
                v-close-popup
                @click="runChecks(props.node)"
              >
                <q-item-section side>
                  <q-icon name="fas fa-check-double" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.runChecks")
                }}</q-item-section>
              </q-item>

              <q-item
                clickable
                v-if="
                  (props.node.children &&
                    $integrations?.clientMenuIntegrations?.length >
                      0) ||
                  (!props.node.children &&
                    $integrations?.siteMenuIntegrations.length > 0)
                "
              >
                <q-item-section side>
                  <q-icon name="analytics" />
                </q-item-section>
                <q-item-section>{{
                  $t("dashboard.reporting")
                }}</q-item-section>
                <q-item-section side>
                  <q-icon name="keyboard_arrow_right" />
                </q-item-section>
                <integrations-context-menu
                  :type="props.node.children ? 'client' : 'site'"
                  :id="props.node.id"
                />
              </q-item>

              <q-separator></q-separator>

              <q-item clickable v-close-popup>
                <q-item-section>{{
                  $t("dashboard.close")
                }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
            </div>
          </template>
        </q-tree>
      </div>
    </aside>

    <main class="obs-fleet__main">
      <div class="row items-end q-gutter-y-sm obs-fleet__head">
        <div class="col">
          <div class="obs-fleet__crumbs">
            <template v-if="crumbs.length">
              <span v-for="(c, i) in crumbs" :key="i"
                ><span v-if="i" class="obs-fleet__crumb-sep"></span
                ><span :class="{ 'obs-fleet__crumb-last': i === crumbs.length - 1 }">{{
                  c
                }}</span></span
              >
            </template>
            <span v-else>{{ $t("dashboard.allClients") }}</span>
          </div>
          <h1 class="obs-fleet__title">{{ $t("fleet.title") }}</h1>
        </div>
        <div class="row q-gutter-sm">
          <q-btn outline no-caps class="obs-fleet__btn" :label="$t('fleet.bulkActions')">
            <q-menu auto-close>
              <q-list dense style="min-width: 220px">
                <q-item v-for="b in bulkModes" :key="b.mode" clickable @click="showBulkAction(b.mode)">
                  <q-item-section>{{ $t(b.label) }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
          <q-btn
            unelevated
            no-caps
            color="primary"
            class="obs-fleet__btn"
            :label="$t('nav.installAgent')"
            @click="showInstallAgentFromHeader"
          />
        </div>
      </div>

      <!-- Indicadores de urgencia: clic = filtro de la tabla (mismos filtros is:* de v1) -->
      <div class="obs-fleet__kpis">
        <button
          v-for="k in kpis"
          :key="k.key"
          type="button"
          class="obs-fleet__kpi"
          :class="{ 'obs-fleet__kpi--alert': k.alert }"
          :aria-pressed="k.active ? 'true' : 'false'"
          @click="kpiFilter(k.key)"
        >
          <span class="obs-fleet__kpi-label">{{ $t(k.label) }}</span>
          <span class="obs-fleet__kpi-value">
            <span class="mono obs-fleet__kpi-num" :class="k.numClass">{{ k.value }}</span>
            <span class="mono obs-fleet__kpi-of">{{ k.of }}</span>
          </span>
        </button>
      </div>

      <!-- Filtros: el tipo de equipo es un grupo de botones (v1: q-tabs server/workstation/mixed) -->
      <div class="row items-center obs-fleet__filters">
        <q-btn-toggle
          v-model="tab"
          no-caps
          unelevated
          dense
          class="obs-fleet__type"
          toggle-color="primary"
          role="radiogroup"
          :aria-label="$t('fleet.agentType')"
          :options="typeOptions"
        />
        <q-btn
          v-for="c in chips"
          :key="c.key"
          no-caps
          dense
          rounded
          :outline="!c.on"
          :unelevated="c.on"
          :color="c.on ? 'primary' : undefined"
          class="obs-fleet__chip"
          :aria-pressed="c.on ? 'true' : 'false'"
          :label="$t(c.label)"
          @click="toggleChip(c.key)"
        />
        <q-btn
          dense
          no-caps
          outline
          class="obs-fleet__chip"
          icon="filter_alt"
          :label="$t('fleet.moreFilters')"
        >
          <q-menu>
          <q-list dense>
            <q-item-label header>{{
              $t("dashboard.filterAgentTable")
            }}</q-item-label>

            <q-item>
              <q-item-section side>
                <q-checkbox v-model="filterChecksFailing" />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.checksFailing")
                }}</q-item-label>
              </q-item-section>
            </q-item>

            <q-item>
              <q-item-section side>
                <q-checkbox v-model="filterPatchesPending" />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.patchesPending")
                }}</q-item-label>
              </q-item-section>
            </q-item>

            <q-item>
              <q-item-section side>
                <q-checkbox v-model="filterActionsPending" />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.actionsPending")
                }}</q-item-label>
              </q-item-section>
            </q-item>

            <q-item>
              <q-item-section side>
                <q-checkbox v-model="filterRebootNeeded" />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.rebootNeeded")
                }}</q-item-label>
              </q-item-section>
            </q-item>

            <q-item-label header>{{
              $t("dashboard.availability")
            }}</q-item-label>

            <q-item>
              <q-item-section side>
                <q-radio val="all" v-model="filterAvailability" />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.showAllAgents")
                }}</q-item-label>
              </q-item-section>
            </q-item>

            <q-item>
              <q-item-section side>
                <q-radio val="online" v-model="filterAvailability" />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.showOnlineOnly")
                }}</q-item-label>
              </q-item-section>
            </q-item>

            <q-item>
              <q-item-section side>
                <q-radio val="offline" v-model="filterAvailability" />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.showOfflineOnly")
                }}</q-item-label>
              </q-item-section>
            </q-item>

            <q-item>
              <q-item-section side>
                <q-radio val="overdue" v-model="filterAvailability" />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.showOverdueOnly")
                }}</q-item-label>
              </q-item-section>
            </q-item>

            <q-item>
              <q-item-section side>
                <q-radio
                  val="offline_30days"
                  v-model="filterAvailability"
                />
              </q-item-section>

              <q-item-section>
                <q-item-label>{{
                  $t("dashboard.showOffline30days")
                }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>

          <div class="row no-wrap q-pa-md">
            <div class="column">
              <q-btn
                v-close-popup
                :label="$t('dashboard.apply')"
                color="primary"
                @click="applyFilter"
              />
            </div>
            <q-space />
            <div class="column">
              <q-btn
                :label="$t('dashboard.clear')"
                @click="clearFilter"
              />
            </div>
          </div>
        </q-menu>
        </q-btn>
        <q-space />
        <q-input
          v-model="search"
          dense
          outlined
          clearable
          class="obs-fleet__search"
          :placeholder="$t('dashboard.search')"
          :aria-label="$t('dashboard.search')"
          @clear="clearFilter"
        >
          <template v-slot:prepend><q-icon name="search" size="16px" /></template>
        </q-input>
        <q-btn dense no-caps outline class="obs-fleet__chip" icon="view_column" :label="$t('fleet.columns')">
          <q-menu>
            <q-list dense style="min-width: 220px">
              <q-item v-for="c in optionalColumns" :key="c.name" tag="label">
                <q-item-section side><q-checkbox v-model="visibleColumns" :val="c.name" /></q-item-section>
                <q-item-section>{{ $t(c.label) }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
        <export-table-btn :data="filteredAgents" :columns="exportColumns" :label="$t('fleet.exportCsv')" />
      </div>

      <AgentTable
        :agents="filteredAgents"
        :columns="columns"
        :search="search"
        :visibleColumns="visibleColumns"
      />
    </main>

    <!-- install agent modal -->
    <q-dialog v-model="showInstallAgentModal" @hide="closeInstallAgent">
      <InstallAgent
        @close="closeInstallAgent"
        :sitepk="sitePk ? parseInt(sitePk) : undefined"
      />
    </q-dialog>
  </q-page>
</template>

<script>
import mixins from "@/mixins/mixins";
import { openURL } from "quasar";
import { mapState } from "vuex";
import AgentTable from "@/components/AgentTable.vue";
import PolicyAdd from "@/components/automation/modals/PolicyAdd.vue";
import ClientsForm from "@/components/clients/ClientsForm.vue";
import SitesForm from "@/components/clients/SitesForm.vue";
import ActivityMonitoringDialog from "@/components/agents/ActivityMonitoringDialog.vue";
import DeleteClient from "@/components/clients/DeleteClient.vue";
import InstallAgent from "@/components/modals/agents/InstallAgent.vue";
import AlertTemplateAdd from "@/components/modals/alerts/AlertTemplateAdd.vue";
import IntegrationsContextMenu from "@/components/ui/IntegrationsContextMenu.vue";
import ExportTableBtn from "@/components/ui/ExportTableBtn.vue";
import BulkAction from "@/components/modals/agents/BulkAction.vue";

import { removeClient, removeSite } from "@/api/clients";

export default {
  name: "DashboardView",
  components: {
    AgentTable,
    InstallAgent,
    IntegrationsContextMenu,
    ExportTableBtn,
  },
  // allow child components to refresh table
  provide() {
    return {
      refreshDashboard: (clearTreeSelected, clearSubTable) => {
        if (clearSubTable) this.$store.commit("destroySubTable");

        this.$store.dispatch("refreshDashboard", clearTreeSelected);
      },
    };
  },
  mixins: [mixins],
  data() {
    return {
      showInstallAgentModal: false,
      sitePk: null,
      innerModel: (this.$q.screen.height - 82) / 2,
      search: this.$route.query.search ? this.$route.query.search : "",
      filterTextLength: 0,
      filterAvailability: "all",
      filterPatchesPending: false,
      filterActionsPending: false,
      filterChecksFailing: false,
      filterRebootNeeded: false,
      urlActions: [],
      treeFilter: "",
      // 050: atajos del encabezado de la flota a las mismas acciones masivas del riel
      bulkModes: [
        { mode: "command", label: "nav.bulkCommand" },
        { mode: "script", label: "nav.bulkScript" },
        { mode: "patch", label: "nav.bulkPatchManagement" },
        { mode: "alert", label: "nav.bulkSendAlert" },
        { mode: "lock", label: "nav.bulkLock" },
        { mode: "alarm", label: "nav.bulkAlarm" },
        { mode: "stopalarm", label: "nav.bulkStopAlarm" },
      ],
      // 050: por omisión, equipo+descripción y cliente+sitio en una celda; las alertas
      // por equipo (SMS, correo, panel), el sitio y la descripción sueltos y el arranque
      // quedan elegibles en «Columnas» para que la tabla quepa a 1280 px.
      visibleColumns: [
        "plat",
        "mon-type",
        "checks-status",
        "client_name",
        "hostname",
        "user",
        "patchespending",
        "pendingactions",
        "agentstatus",
        "needs_reboot",
        "last_seen",
      ],
    };
  },
  watch: {
    search(newVal) {
      if (newVal === "") this.clearFilter();
      else if (newVal.length < this.filterTextLength) this.clearFilter();
    },
    // El botón "Ver listado" del banner de mantenimiento (feature 036) navega acá
    // con ?search=is:maintenance. `data()` sólo lee la query al montar, así que sin
    // este watcher el botón no haría nada si el usuario YA estaba en el dashboard —
    // que es el caso normal, porque el banner vive en el header.
    "$route.query.search"(newVal) {
      if (newVal && newVal !== this.search) {
        this.filterTextLength = 0;
        this.search = newVal;
      }
    },
    selectedTree() {
      if (this.clearSearchWhenSwitching) this.clearFilter();
    },
    tab() {
      this.$store.dispatch("loadAgents");
    },
  },
  methods: {
    // 050 · flota
    // Estados del nodo: chequeos (error, si no advertencia) y, aparte, mantenimiento. node.color
    // (store, v1) elige uno solo con mantenimiento primero y tapa los chequeos con error.
    nodeStates(node) {
      const d = node.client || node.site;
      if (!d) return node.color ? [node.color] : [];
      const out = [];
      if (d.failing_checks?.error) out.push("negative");
      else if (d.failing_checks?.warning) out.push("warning");
      if (d.maintenance_mode) out.push("green");
      return out;
    },
    stateIcon(st) {
      return st === "green" ? "construction" : st === "negative" ? "error" : "warning";
    },
    stateLabel(st) {
      if (st === "green") return this.$t("fleet.stateMaintenance");
      if (st === "negative") return this.$t("fleet.stateError");
      return this.$t("fleet.stateWarning");
    },
    // Un indicador aplica solo su filtro (los mismos is:* de v1); un segundo clic lo quita.
    kpiFilter(key) {
      const activo = this.kpis.find((k) => k.key === key)?.active;
      this.clearFilter();
      if (activo) return;
      if (key === "online") this.filterAvailability = "online";
      if (key === "checks") this.filterChecksFailing = true;
      if (key === "patches") this.filterPatchesPending = true;
      if (key === "reboot") this.filterRebootNeeded = true;
      if (key === "actions") this.filterActionsPending = true;
      this.applyFilter();
    },
    toggleChip(key) {
      if (key === "checks") this.filterChecksFailing = !this.filterChecksFailing;
      if (key === "online")
        this.filterAvailability = this.filterAvailability === "online" ? "all" : "online";
      if (key === "reboot") this.filterRebootNeeded = !this.filterRebootNeeded;
      if (this.isFilteringTable) this.applyFilter();
      else this.clearFilter();
    },
    showAddClient() {
      this.$q.dialog({ component: ClientsForm }).onOk(() => this.$store.dispatch("loadTree"));
    },
    showAddSiteFromHeader() {
      const sel = this.selectedTree || "";
      this.$q
        .dialog({
          component: SitesForm,
          componentProps: sel.startsWith("Client|") ? { client: parseInt(sel.split("|")[1]) } : {},
        })
        .onOk(() => this.$store.dispatch("loadTree"));
    },
    showInstallAgentFromHeader() {
      const sel = this.selectedTree || "";
      this.sitePk = sel.startsWith("Site|") ? sel.split("|")[1] : null;
      this.showInstallAgentModal = true;
    },
    showBulkAction(mode) {
      this.$q.dialog({ component: BulkAction, componentProps: { mode } });
    },
    getTree() {
      this.$store.dispatch("loadTree");
    },
    clearTreeSelected() {
      if (this.clearSearchWhenSwitching) this.clearFilter();
      this.$store.dispatch("refreshDashboard", true);
    },
    showPolicyAdd(node) {
      this.$q
        .dialog({
          component: PolicyAdd,
          componentProps: {
            type: node.children ? "client" : "site",
            object: node.children ? node.client : node.site,
          },
        })
        .onOk(() => this.$store.dispatch("loadTree"));
    },
    showAddSiteModal(node) {
      this.$q
        .dialog({
          component: SitesForm,
          componentProps: {
            client: node.id,
          },
        })
        .onOk(() => this.$store.dispatch("loadTree"));
    },
    showEditModal(node) {
      let props = {};
      if (node.children) {
        props.client = { id: node.id, name: node.label };
      } else {
        props.site = { id: node.id, name: node.label, client: node.client };
      }

      this.$q
        .dialog({
          component: node.children ? ClientsForm : SitesForm,
          componentProps: node.children
            ? { client: node.client }
            : { site: node.site },
        })
        .onOk(() => this.$store.dispatch("loadTree"));
    },
    showDeleteModal(node) {
      if (
        (node.children && node.client.agent_count > 0) ||
        (!node.children && node.site.agent_count > 0)
      ) {
        this.$q
          .dialog({
            component: DeleteClient,
            componentProps: {
              object: node.children ? node.client : node.site,
              type: node.children ? "client" : "site",
            },
          })
          .onOk(this.clearTreeSelected);
      } else {
        this.$q
          .dialog({
            title: this.$t("dashboard.confirmTitle"),
            message: this.$t("dashboard.deleteMessage", {
              type: node.children
                ? this.$t("dashboard.typeClient")
                : this.$t("dashboard.typeSite"),
              label: node.label,
            }),
            cancel: true,
            ok: { label: this.$t("dashboard.delete"), color: "negative" },
          })
          .onOk(async () => {
            this.$q.loading.show();
            try {
              const result = node.children
                ? await removeClient(node.id)
                : await removeSite(node.id);
              this.notifySuccess(result);
              this.clearTreeSelected();
            } catch (e) {
              console.error(e);
            }
            this.$q.loading.hide();
          });
      }
    },
    showInstallAgent(node) {
      this.sitePk = node.id;
      this.showInstallAgentModal = true;
    },
    closeInstallAgent() {
      this.showInstallAgentModal = false;
      this.sitePk = null;
    },
    showAlertTemplateAdd(node) {
      this.$q
        .dialog({
          component: AlertTemplateAdd,
          componentProps: {
            type: node.children ? "client" : "site",
            object: node.children ? node.client : node.site,
          },
        })
        .onOk(() => this.$store.dispatch("refreshDashboard"));
    },
    runChecks(node) {
      const target = node.children ? "client" : "site";
      this.$axios
        .post(`/checks/${target}/${node.id}/csbulkrun/`)
        .then((r) => {
          this.notifySuccess(r.data);
        })
        .catch((e) => {
          console.error(e);
        });
    },
    showActivityMonitoring(node) {
      this.$q.dialog({
        component: ActivityMonitoringDialog,
        componentProps: {
          level: node.children ? "client" : "site",
          id: node.id,
          name: node.label,
        },
      });
    },
    showToggleMaintenance(node) {
      let data = {
        id: node.id,
        type: node.raw.split("|")[0],
        action: node.color === "green" ? false : true,
      };

      this.$axios
        .post("/agents/maintenance/bulk/", data)
        .then((r) => {
          this.notifySuccess(r.data);
          this.$store.dispatch("refreshDashboard");
          this.$store.commit("setRefreshSummaryTab", true);
        })
        .catch((e) => {
          console.error(e);
        });
    },
    clearFilter() {
      this.filterTextLength = 0;
      this.filterPatchesPending = false;
      this.filterRebootNeeded = false;
      this.filterChecksFailing = false;
      this.filterActionsPending = false;
      this.filterAvailability = "all";
      this.search = "";
    },
    applyFilter() {
      // clear search if availability changes to all
      if (
        this.filterAvailability === "all" &&
        (this.search.includes("is:online") ||
          this.search.includes("is:offline") ||
          this.search.includes("is:expired") ||
          this.search.includes("is:overdue"))
      )
        this.clearFilter();

      // don't apply filter if nothing is being filtered
      if (!this.isFilteringTable) return;

      let filterText = "";

      if (this.filterPatchesPending) {
        filterText += "is:patchespending ";
      }

      if (this.filterActionsPending) {
        filterText += "is:actionspending ";
      }

      if (this.filterChecksFailing) {
        filterText += "is:checksfailing ";
      }

      if (this.filterRebootNeeded) {
        filterText += "is:rebootneeded ";
      }

      if (this.filterAvailability !== "all") {
        if (this.filterAvailability === "online") {
          filterText += "is:online ";
        } else if (this.filterAvailability === "offline") {
          filterText += "is:offline ";
        } else if (this.filterAvailability === "offline_30days") {
          filterText += "is:expired ";
        } else if (this.filterAvailability === "overdue") {
          filterText += "is:overdue ";
        }
      }

      this.search = filterText;
      this.filterTextLength = filterText.length - 1;
    },
    getURLActions() {
      this.$axios.get("/core/urlaction/").then((r) => {
        this.urlActions = r.data
          .filter((action) => action.action_type === "web")
          .sort((a, b) => a.name.localeCompare(b.name));
        if (this.urlActions.length === 0) {
          this.notifyWarning(this.$t("dashboard.noUrlActions"));
        }
      });
    },
    runURLAction(id, action, model) {
      const data = {
        [model]: id,
        action: action,
      };
      this.$axios.patch("/core/urlaction/run/", data).then((r) => {
        openURL(r.data);
      });
    },
  },
  computed: {
    totalAgents() {
      return (this.clientsTree || []).reduce((n, c) => n + (c.client?.agent_count || 0), 0);
    },
    crumbs() {
      const sel = this.selectedTree || "";
      if (!sel) return [];
      for (const c of this.clientsTree || []) {
        if (c.raw === sel) return [c.label];
        const s = (c.children || []).find((x) => x.raw === sel);
        if (s) return [c.label, s.label];
      }
      return [];
    },
    // Indicadores calculados sobre la misma lista de /agents/ que pinta la tabla (sin endpoint nuevo).
    kpis() {
      const a = this.filteredAgents || [];
      const n = (f) => a.filter(f).length;
      const s = this.search || "";
      const online = n((x) => x.status === "online");
      // Mismo criterio que el filtro is:checksfailing de AgentTable (error o advertencia).
      const checks = n((x) => x.checks && x.checks.has_failing_checks);
      const patches = n((x) => x.has_patches_pending);
      const reboot = n((x) => x.needs_reboot);
      const actions = a.reduce((t, x) => t + (parseInt(x.pending_actions_count) || 0), 0);
      const tone = (v, cls) => (v > 0 ? cls : "");
      return [
        { key: "online", label: "fleet.kpiOnline", value: online, of: this.$t("fleet.ofTotal", { n: a.length }), active: s.includes("is:online") },
        { key: "checks", label: "fleet.kpiChecks", value: checks, of: this.$t("fleet.agentsUnit"), numClass: tone(checks, "obs-fleet__kpi-num--neg"), alert: checks > 0, active: s.includes("is:checksfailing") },
        { key: "patches", label: "fleet.kpiPatches", value: patches, of: this.$t("fleet.agentsUnit"), numClass: tone(patches, "obs-fleet__kpi-num--warn"), active: s.includes("is:patchespending") },
        { key: "reboot", label: "fleet.kpiReboot", value: reboot, of: this.$t("fleet.agentsUnit"), numClass: tone(reboot, "obs-fleet__kpi-num--warn"), active: s.includes("is:rebootneeded") },
        { key: "actions", label: "fleet.kpiActions", value: actions, of: this.$t("fleet.queuedUnit"), active: s.includes("is:actionspending") },
      ];
    },
    // Tipo de equipo como grupo de radio (role/aria-checked por opción).
    typeOptions() {
      return [
        { label: this.$t("fleet.typeAll"), value: "mixed" },
        { label: this.$t("dashboard.tabServers"), value: "server" },
        { label: this.$t("dashboard.tabWorkstations"), value: "workstation" },
      ].map((o) => ({ ...o, attrs: { role: "radio", "aria-checked": String(this.tab === o.value) } }));
    },
    chips() {
      return [
        { key: "checks", label: "dashboard.checksFailing", on: this.filterChecksFailing },
        { key: "online", label: "fleet.chipOnline", on: this.filterAvailability === "online" },
        { key: "reboot", label: "fleet.chipReboot", on: this.filterRebootNeeded },
      ];
    },
    // Columnas que el usuario puede ocultar o mostrar (todas visibles por omisión, como en v1).
    optionalColumns() {
      return [
        { name: "smsalert", label: "fleet.colSmsAlert" },
        { name: "emailalert", label: "fleet.colEmailAlert" },
        { name: "dashboardalert", label: "fleet.colDashboardAlert" },
        { name: "site_name", label: "dashboard.colSite" },
        { name: "description", label: "dashboard.colDescription" },
        { name: "user", label: "dashboard.colUser" },
        { name: "last_seen", label: "dashboard.colLastResponse" },
        { name: "boot_time", label: "dashboard.colBootTime" },
      ];
    },
    exportColumns() {
      return this.columns.filter((c) => c.label && this.visibleColumns.includes(c.name));
    },
    // columns es computed (no data) para que los headers traducidos reaccionen
    // al cambio de idioma en vivo (vue-i18n no es reactivo dentro de data()).
    columns() {
      return [
        { name: "smsalert", align: "left" },
        { name: "emailalert", align: "left" },
        { name: "dashboardalert", align: "left" },
        {
          name: "plat",
          label: "",
          field: "plat",
          sortable: true,
          align: "left",
        },
        {
          name: "mon-type",
          label: "",
          field: "monitoring_type",
          sortable: true,
          align: "left",
        },
        {
          name: "checks-status",
          align: "left",
          field: "checks",
          sortable: true,
          sort: (a, b) =>
            parseInt(b.failing) - parseInt(a.failing) ||
            parseInt(b.warning) - parseInt(a.warning) ||
            parseInt(b.info) - parseInt(a.info),
        },
        {
          name: "client_name",
          label: this.$t("dashboard.colClient"),
          field: "client_name",
          sortable: true,
          align: "left",
        },
        {
          name: "site_name",
          label: this.$t("dashboard.colSite"),
          field: "site_name",
          sortable: true,
          align: "left",
        },
        {
          name: "hostname",
          label: this.$t("dashboard.colHostname"),
          field: "hostname",
          sortable: true,
          align: "left",
        },
        {
          name: "description",
          label: this.$t("dashboard.colDescription"),
          field: "description",
          sortable: true,
          align: "left",
        },
        {
          name: "user",
          label: this.$t("dashboard.colUser"),
          field: "logged_username",
          sortable: true,
          align: "left",
        },
        { name: "italic", field: "italic" },
        {
          name: "patchespending",
          field: "has_patches_pending",
          align: "left",
          sortable: true,
        },
        {
          name: "pendingactions",
          field: "pending_actions_count",
          align: "left",
          sortable: true,
        },
        {
          name: "needs_reboot",
          field: "needs_reboot",
          align: "left",
          sortable: true,
        },
        {
          name: "agentstatus",
          field: "status",
          align: "left",
          sort: (a, b) => {
            const statusRank = {
              online: 0,
              offline: 1,
              overdue: 2,
            };
            return (statusRank[a] ?? 3) - (statusRank[b] ?? 3);
          },
          sortable: true,
        },
        {
          name: "last_seen",
          label: this.$t("dashboard.colLastResponse"),
          field: "last_seen",
          sortable: true,
          align: "left",
        },
        {
          name: "boot_time",
          label: this.$t("dashboard.colBootTime"),
          field: "boot_time",
          sortable: true,
          align: "left",
        },
      ];
    },
    ...mapState({
      clientsTree: (state) => state.tree,
      treeReady: (state) => state.treeReady,
      clearSearchWhenSwitching: (state) => state.clearSearchWhenSwitching,
      agents: (state) => state.agents,
    }),
    clientTreeSplitter: {
      get() {
        return this.$store.state.clientTreeSplitter;
      },
      set(newVal) {
        this.$store.dispatch("setClientTreeSplitter", newVal);
      },
    },
    tab: {
      get() {
        return this.$store.state.defaultAgentTblTab;
      },
      set(newVal) {
        this.$store.commit("SET_DEFAULT_AGENT_TBL_TAB", newVal);
        this.$store.commit("destroySubTable");
      },
    },
    selectedTree: {
      get() {
        return this.$store.state.selectedTree;
      },
      set(newVal) {
        this.$store.commit("setSelectedTree", newVal);
        this.$store.commit("destroySubTable");
      },
    },
    allClientsActive() {
      return this.selectedTree === "";
    },
    filteredAgents() {
      if (this.tab === "mixed") return this.agents;
      else return this.agents.filter((k) => k.monitoring_type === this.tab);
    },
    isFilteringTable() {
      return (
        this.filterPatchesPending ||
        this.filterActionsPending ||
        this.filterChecksFailing ||
        this.filterRebootNeeded ||
        this.filterAvailability !== "all"
      );
    },
  },
  mounted() {
    this.getTree();
    // 046 F1: al volver al dashboard desde /agents/:id (botón de inicio del riel)
    // la tabla quedaba vacía hasta otro refresco: mounted solo cargaba el árbol.
    // En la PRIMERA carga la pestaña (defaultAgentTblTab) aún es null y la carga la
    // hace el watcher de `tab` cuando llegan las preferencias; cargar acá con null
    // pedía ?monitoring_type=null (400, lo encontró el gauntlet en UI-N03).
    if (this.$store.state.defaultAgentTblTab)
      this.$store.dispatch("loadAgents");

    // 046 F4: sin panel inferior, la tabla usa todo el alto (SET_SPLITTER(0)).
    // 050: la cabecera de la flota (título, indicadores y filtros) ocupa ~200 px sobre la tabla.
    this.$store.commit("SET_SPLITTER", 200);
  },
};
</script>

<style>
.my-menu-link {
  color: var(--obs-text);
  background: var(--obs-selected);
}
</style>

<style lang="sass" scoped>
// 050 ola 2 · flota en dirección 1c (referencia/flota.png). Solo tokens --obs-* / --q-*.
.obs-fleet
  display: flex
  align-items: stretch
  min-height: calc(100vh - 50px)
  background: var(--obs-page)
.obs-fleet__ctx
  width: 280px
  flex: none
  display: flex
  flex-direction: column
  background: var(--obs-surface)
  border-right: 1px solid var(--obs-border)
.obs-fleet__ctx-head
  padding: 16px 16px 10px
.obs-fleet__eyebrow
  font-size: 12px
  font-weight: 600
  letter-spacing: .08em
  text-transform: uppercase
  color: var(--obs-faint)
.obs-fleet__add
  color: var(--obs-text-2)
.obs-fleet__tree
  flex: 1
  padding: 0 8px 16px
  overflow-y: auto
.obs-fleet__all
  border-radius: 8px
  font-weight: 600
  color: var(--obs-text-2)
.obs-fleet__node--active
  background: var(--obs-selected)
  color: var(--q-accent)
.obs-fleet__node
  gap: 8px
  min-width: 0
.obs-fleet__client
  font-weight: 600
  color: var(--obs-text)
.obs-fleet__site
  color: var(--obs-text-2)
.obs-fleet__count
  font-size: 12px
  color: var(--obs-muted)
.obs-fleet__state--negative
  color: var(--q-negative)
.obs-fleet__state--warning
  color: var(--q-warning)
.obs-fleet__state--green
  color: var(--obs-muted)
.obs-fleet__tree :deep(.q-tree__arrow)
  color: var(--obs-muted)
.obs-fleet__tree :deep(.q-tree__node-header)
  border-radius: 8px
  padding: 6px 8px
.obs-fleet__tree :deep(.q-tree__node--selected)
  background: var(--obs-selected)
.obs-fleet__tree :deep(.q-tree__node--selected .obs-fleet__site),
.obs-fleet__tree :deep(.q-tree__node--selected .obs-fleet__client)
  color: var(--q-accent)
.obs-fleet__main
  flex: 999 1 560px
  min-width: 0
  display: flex
  flex-direction: column
  gap: 14px
  padding: 18px 24px 16px
.obs-fleet__crumbs
  font-size: 13px
  color: var(--obs-muted)
.obs-fleet__crumb-sep::before
  content: " / "
.obs-fleet__crumb-last
  color: var(--obs-text-2)
.obs-fleet__title
  margin: 4px 0 0
  font-size: 26px
  line-height: 1.2
  font-weight: 700
  letter-spacing: -.01em
  color: var(--obs-text)
.obs-fleet__btn
  min-height: 36px
  border-radius: 8px
.obs-fleet__kpis
  display: grid
  grid-template-columns: repeat(5, minmax(0, 1fr))
  gap: 12px
@media (max-width: 1100px)
  .obs-fleet__kpis
    grid-template-columns: repeat(3, minmax(0, 1fr))
.obs-fleet__kpi
  display: flex
  flex-direction: column
  gap: 6px
  padding: 12px 16px
  text-align: left
  font: inherit
  color: inherit
  background: var(--obs-surface)
  border: 1px solid var(--obs-border)
  border-radius: 12px
  cursor: pointer
  &:hover
    background: var(--obs-hover)
  &[aria-pressed="true"]
    border-color: var(--q-primary)
    background: var(--obs-selected)
.obs-fleet__kpi--alert
  border-color: var(--q-negative)
.obs-fleet__kpi-label
  font-size: 12px
  color: var(--obs-muted)
.obs-fleet__kpi-value
  display: flex
  align-items: baseline
  gap: 6px
.obs-fleet__kpi-num
  font-size: 26px
  font-weight: 500
  color: var(--obs-text)
.obs-fleet__kpi-num--neg
  color: var(--q-negative)
.obs-fleet__kpi-num--warn
  color: var(--q-warning)
.obs-fleet__kpi-of
  font-size: 12px
  color: var(--obs-muted)
.obs-fleet__filters
  gap: 8px
  flex-wrap: wrap
.obs-fleet__type
  border: 1px solid var(--obs-border)
  border-radius: 9px
  background: var(--obs-surface)
.obs-fleet__chip
  border-radius: 16px
  min-height: 30px
  padding: 0 4px
  font-size: 13px
  color: var(--obs-text-2)
.obs-fleet__chip.q-btn--outline:before
  border-color: var(--obs-hdr-ctl-border)
.obs-fleet__btn.q-btn--outline:before
  border-color: var(--obs-hdr-ctl-border)
.obs-fleet__type :deep(.q-btn)
  font-size: 13px
  padding: 0 10px
.obs-fleet__search
  width: 260px
</style>
