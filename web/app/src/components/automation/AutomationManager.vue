<template>
  <!-- 050 (T028): con `embedded` es la página /automation/:policy?/:section?
       (columna de políticas + navegación Chequeos/Tareas, sin pestañas). -->
  <component
    :is="embedded ? 'div' : QDialog"
    ref="dialog"
    :class="{ 'obs-mgr': embedded }"
    @hide="onHide"
  >
    <template v-if="embedded">
      <aside class="obs-mgr__policies">
        <div class="row items-center no-wrap obs-mgr__pol-head">
          <div class="col obs-mgr__pol-title">
            {{ $t("automationManager.policiesGroup") }}
          </div>
          <q-btn
            unelevated
            no-caps
            color="primary"
            class="obs-page__btn"
            :label="$t('automationManager.newShort')"
            @click="showAddPolicyForm"
          />
        </div>
        <q-btn
          outline
          no-caps
          class="obs-page__btn full-width q-mb-sm"
          :label="$t('automationManager.policyOverviewLong')"
          @click="showPolicyOverview"
        />
        <q-separator class="q-mb-sm" />
        <q-list dense>
          <q-item
            v-for="pol in sortedPolicies"
            :key="pol.id"
            clickable
            :active="selectedPolicy && selectedPolicy.id === pol.id"
            active-class="obs-mgr__pol--active"
            class="obs-mgr__pol"
            @click="selectPolicy(pol)"
            @dblclick="showEditPolicyForm(pol)"
          >
            <q-item-section>
              <q-item-label class="obs-mgr__pol-name ellipsis" :title="pol.name">{{
                pol.name
              }}</q-item-label>
              <q-item-label caption class="ellipsis" :title="pol.desc">{{
                pol.desc || "—"
              }}</q-item-label>
            </q-item-section>
            <q-item-section side top>
              <q-badge
                :color="pol.active ? 'positive' : 'grey'"
                :class="{ 'obs-chip-neutral': !pol.active }"
                >{{
                  pol.active
                    ? $t("automationManager.stateActive")
                    : $t("automationManager.stateInactive")
                }}</q-badge
              >
            </q-item-section>
          </q-item>
          <q-item v-if="!policies.length">
            <q-item-section class="obs-text-muted">{{
              $t("automationManager.noPolicies")
            }}</q-item-section>
          </q-item>
        </q-list>
      </aside>
      <ObsSectionNav
        v-if="selectedPolicy"
        :groups="sectionGroups"
        :section="subtab"
        :aria-label="$t('automationManager.policyGroup')"
        @select="selectSection"
      />
      <div class="obs-page obs-mgr__main">
        <template v-if="selectedPolicy">
          <ObsPageHead
            :title="selectedPolicy.name"
            :crumbs="[
              $t('automationManager.pageCrumb'),
              $t('automationManager.policiesCrumb'),
            ]"
          >
            <q-btn
              outline
              no-caps
              class="obs-page__btn"
              icon="refresh"
              :aria-label="$t('automationManager.refresh')"
              @click="refresh"
            />
          </ObsPageHead>
          <div class="row items-center q-gutter-sm obs-mgr__pol-meta">
            <q-badge
              :color="selectedPolicy.active ? 'positive' : 'grey'"
              :class="{ 'obs-chip-neutral': !selectedPolicy.active }"
              >{{
                selectedPolicy.active
                  ? $t("automationManager.stateActive")
                  : $t("automationManager.stateInactive")
              }}</q-badge
            >
            <q-badge v-if="selectedPolicy.enforced" color="grey" class="obs-chip-neutral">{{
              $t("automationManager.stateEnforced")
            }}</q-badge>
            <q-badge
              v-if="selectedPolicy.default_server_policy"
              color="grey"
              class="obs-chip-neutral"
              >{{ $t("automationManager.defaultServer") }}</q-badge
            >
            <q-badge
              v-if="selectedPolicy.default_workstation_policy"
              color="grey"
              class="obs-chip-neutral"
              >{{ $t("automationManager.defaultWorkstation") }}</q-badge
            >
            <span class="obs-text-muted">{{ selectedPolicy.desc }}</span>
          </div>
          <div class="obs-page__filters">
            <q-btn
              outline
              no-caps
              class="obs-page__btn"
              @click="showRelations(selectedPolicy)"
              >{{ $t("automationManager.relationsBtn") }}{{ sep }}<span class="mono">{{
                selectedPolicy.agents_count
              }}</span></q-btn
            >
            <q-btn
              outline
              no-caps
              class="obs-page__btn"
              @click="showPolicyExclusions(selectedPolicy)"
              >{{ $t("automationManager.exclusionsBtn") }}{{ sep }}<span class="mono">{{
                exclusionsCount(selectedPolicy)
              }}</span></q-btn
            >
            <q-btn
              outline
              no-caps
              class="obs-page__btn"
              :label="patchPolicyText(selectedPolicy)"
              @click="showPatchPolicyForm(selectedPolicy)"
            />
            <q-btn
              outline
              no-caps
              class="obs-page__btn"
              :label="alertTemplateText(selectedPolicy)"
              @click="showAlertTemplateAdd(selectedPolicy)"
            />
            <q-btn
              outline
              no-caps
              class="obs-page__btn"
              icon="more_horiz"
              :aria-label="$t('automationManager.moreActions')"
            >
              <q-menu>
                <q-list dense style="min-width: 220px">
                  <q-item
                    v-for="a in policyActions(selectedPolicy)"
                    :key="a.key"
                    clickable
                    v-close-popup
                    @click="a.run"
                  >
                    <q-item-section side><q-icon :name="a.icon" /></q-item-section>
                    <q-item-section>{{ a.label }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </div>
          <h2 class="obs-mgr__section-title">
            {{
              subtab === "tasks"
                ? $t("automationManager.tabTasks")
                : $t("automationManager.tabChecks")
            }}
          </h2>
          <PolicyChecksTab
            v-if="subtab === 'checks'"
            :key="`c${selectedPolicy.id}`"
            :selectedPolicy="selectedPolicy.id"
          />
          <PolicyAutomatedTasksTab
            v-else
            :key="`t${selectedPolicy.id}`"
            :selectedPolicy="selectedPolicy.id"
          />
        </template>
        <div v-else class="obs-text-muted q-pa-md">
          {{ $t("automationManager.pickPolicy") }}
        </div>
      </div>
    </template>
    <div v-else class="q-dialog-plugin" style="width: 90vw; max-width: 90vw">
      <q-card>
        <q-bar>
          <q-btn
            ref="refresh"
            @click="refresh"
            class="q-mr-sm"
            dense
            flat
            push
            icon="refresh"
          />{{ $t("automationManager.title") }}
          <q-space />
          <q-btn dense flat icon="close" v-close-popup>
            <q-tooltip class="bg-white text-primary">{{
              $t("automationManager.close")
            }}</q-tooltip>
          </q-btn>
        </q-bar>
        <q-card-section>
          <div class="q-gutter-sm">
            <q-btn
              :label="$t('automationManager.new')"
              dense
              flat
              push
              unelevated
              no-caps
              icon="add"
              @click="showAddPolicyForm"
            />
            <q-btn
              :label="$t('automationManager.policyOverview')"
              dense
              flat
              push
              unelevated
              no-caps
              icon="remove_red_eye"
              @click="showPolicyOverview"
            />
          </div>
          <div class="scroll" style="min-height: 35vh; max-height: 35vh">
            <q-table
              :table-class="{
                'table-bgcolor': !$q.dark.isActive,
                'table-bgcolor-dark': $q.dark.isActive,
              }"
              class="tabs-tbl-sticky"
              :rows="policies"
              :columns="columns"
              v-model:pagination="pagination"
              :rows-per-page-options="[0]"
              dense
              row-key="id"
              binary-state-sort
              hide-pagination
              virtual-scroll
              :no-data-label="$t('automationManager.noPolicies')"
            >
              <!-- header slots -->
              <template v-slot:header-cell-active="props">
                <q-th :props="props" auto-width>
                  <q-icon name="power_settings_new" size="1.5em">
                    <q-tooltip>{{
                      $t("automationManager.enablePolicyTip")
                    }}</q-tooltip>
                  </q-icon>
                </q-th>
              </template>

              <template v-slot:header-cell-enforced="props">
                <q-th :props="props" auto-width>
                  <q-icon name="security" size="1.5em">
                    <q-tooltip>{{
                      $t("automationManager.enforcePolicyTip")
                    }}</q-tooltip>
                  </q-icon>
                </q-th>
              </template>

              <!-- body slots -->
              <template v-slot:body="props">
                <q-tr
                  :props="props"
                  class="cursor-pointer"
                  :class="rowSelectedClass(props.row.id, selectedPolicy)"
                  @click="selectedPolicy = props.row"
                  @contextmenu="selectedPolicy = props.row"
                  @dblclick="showEditPolicyForm(props.row)"
                >
                  <!-- context menu -->
                  <q-menu context-menu>
                    <q-list dense style="min-width: 200px">
                      <q-item
                        clickable
                        v-close-popup
                        @click="showEditPolicyForm(props.row)"
                      >
                        <q-item-section side>
                          <q-icon name="edit" />
                        </q-item-section>
                        <q-item-section>{{
                          $t("automationManager.edit")
                        }}</q-item-section>
                      </q-item>

                      <q-item
                        clickable
                        v-close-popup
                        @click="showCopyPolicyForm(props.row)"
                      >
                        <q-item-section side>
                          <q-icon name="content_copy" />
                        </q-item-section>
                        <q-item-section>{{
                          $t("automationManager.copy")
                        }}</q-item-section>
                      </q-item>

                      <q-item
                        clickable
                        v-close-popup
                        @click="deletePolicy(props.row)"
                      >
                        <q-item-section side>
                          <q-icon name="delete" />
                        </q-item-section>
                        <q-item-section>{{
                          $t("automationManager.delete")
                        }}</q-item-section>
                      </q-item>

                      <q-separator></q-separator>

                      <q-item
                        clickable
                        v-close-popup
                        @click="showRelations(props.row)"
                      >
                        <q-item-section side>
                          <q-icon name="account_tree" />
                        </q-item-section>
                        <q-item-section>{{
                          $t("automationManager.showRelations")
                        }}</q-item-section>
                      </q-item>

                      <q-item
                        clickable
                        v-close-popup
                        @click="showPolicyExclusions(props.row)"
                      >
                        <q-item-section side>
                          <q-icon name="rule" />
                        </q-item-section>
                        <q-item-section>{{
                          $t("automationManager.policyExclusions")
                        }}</q-item-section>
                      </q-item>

                      <q-item
                        clickable
                        v-close-popup
                        @click="showPatchPolicyForm(props.row)"
                      >
                        <q-item-section side>
                          <q-icon name="system_update" />
                        </q-item-section>
                        <q-item-section>{{
                          patchPolicyText(props.row)
                        }}</q-item-section>
                      </q-item>

                      <q-item
                        clickable
                        v-close-popup
                        @click="showAlertTemplateAdd(props.row)"
                      >
                        <q-item-section side>
                          <q-icon name="warning" />
                        </q-item-section>
                        <q-item-section>{{
                          alertTemplateText(props.row)
                        }}</q-item-section>
                      </q-item>

                      <q-separator></q-separator>

                      <q-item clickable v-close-popup>
                        <q-item-section>{{
                          $t("automationManager.close")
                        }}</q-item-section>
                      </q-item>
                    </q-list>
                  </q-menu>
                  <!-- enabled checkbox -->
                  <q-td>
                    <q-checkbox
                      dense
                      @update:model-value="toggleCheckbox(props.row, 'Active')"
                      v-model="props.row.active"
                    />
                  </q-td>
                  <!-- enforced checkbox -->
                  <q-td>
                    <q-checkbox
                      dense
                      @update:model-value="
                        toggleCheckbox(props.row, 'Enforced')
                      "
                      v-model="props.row.enforced"
                    />
                  </q-td>
                  <q-td>
                    {{ props.row.name }}
                    <q-chip
                      v-if="props.row.default_server_policy"
                      color="primary"
                      text-color="white"
                      size="sm"
                      >{{ $t("automationManager.defaultServer") }}</q-chip
                    >
                    <q-chip
                      v-if="props.row.default_workstation_policy"
                      color="primary"
                      text-color="white"
                      size="sm"
                      >{{ $t("automationManager.defaultWorkstation") }}</q-chip
                    >
                  </q-td>
                  <q-td>{{ props.row.desc }}</q-td>
                  <q-td>
                    <span
                      style="cursor: pointer; text-decoration: underline"
                      class="text-primary"
                      @click="showRelations(props.row)"
                      >{{
                        $t("automationManager.showRelationsCount", {
                          count: props.row.agents_count,
                        })
                      }}</span
                    >
                  </q-td>
                  <q-td>
                    <span
                      style="cursor: pointer; text-decoration: underline"
                      class="text-primary"
                      @click="showPolicyExclusions(props.row)"
                      >{{
                        $t("automationManager.showPolicyExclusionsCount", {
                          count:
                            props.row.excluded_agents.length +
                            props.row.excluded_clients.length +
                            props.row.excluded_sites.length,
                        })
                      }}</span
                    >
                  </q-td>
                  <q-td>
                    <span
                      style="cursor: pointer; text-decoration: underline"
                      class="text-primary"
                      @click="showPatchPolicyForm(props.row)"
                      >{{ patchPolicyText(props.row) }}</span
                    >
                  </q-td>
                  <q-td>
                    <span
                      style="cursor: pointer; text-decoration: underline"
                      class="text-primary"
                      @click="showAlertTemplateAdd(props.row)"
                      >{{ alertTemplateText(props.row) }}</span
                    >
                  </q-td>
                  <q-td>
                    <q-icon
                      name="content_copy"
                      size="1.5em"
                      @click="showCopyPolicyForm(props.row)"
                    >
                      <q-tooltip>{{
                        $t("automationManager.copyTooltip")
                      }}</q-tooltip>
                    </q-icon>
                  </q-td>
                </q-tr>
              </template>
            </q-table>
          </div>
        </q-card-section>

        <q-card-section>
          <q-tabs
            v-model="subtab"
            dense
            inline-label
            class="text-grey"
            active-color="primary"
            indicator-color="primary"
            align="left"
            narrow-indicator
            no-caps
          >
            <q-tab
              name="checks"
              icon="fas fa-check-double"
              :label="$t('automationManager.tabChecks')"
            />
            <q-tab
              name="tasks"
              icon="fas fa-tasks"
              :label="$t('automationManager.tabTasks')"
            />
          </q-tabs>
          <q-separator />
          <q-tab-panels v-model="subtab" :animated="false">
            <q-tab-panel name="checks">
              <div class="scroll" style="min-height: 25vh; max-height: 25vh">
                <PolicyChecksTab
                  v-if="!!selectedPolicy"
                  :selectedPolicy="selectedPolicy.id"
                />
              </div>
            </q-tab-panel>
            <q-tab-panel name="tasks">
              <div class="scroll" style="min-height: 25vh; max-height: 25vh">
                <PolicyAutomatedTasksTab
                  v-if="!!selectedPolicy"
                  :selectedPolicy="selectedPolicy.id"
                />
              </div>
            </q-tab-panel>
          </q-tab-panels>
        </q-card-section>
      </q-card>
    </div>
  </component>
</template>

<script>
import { QDialog } from "quasar";
import mixins from "@/mixins/mixins";
import ObsSectionNav from "@/components/shell/ObsSectionNav.vue";
import ObsPageHead from "@/components/ui/ObsPageHead.vue";
import DialogWrapper from "@/components/ui/DialogWrapper.vue";
import PolicyForm from "@/components/automation/modals/PolicyForm.vue";
import PolicyOverview from "@/components/automation/PolicyOverview.vue";
import RelationsView from "@/components/automation/modals/RelationsView.vue";
import PatchPolicyForm from "@/components/modals/agents/PatchPolicyForm.vue";
import AlertTemplateAdd from "@/components/modals/alerts/AlertTemplateAdd.vue";
import PolicyExclusions from "@/components/automation/modals/PolicyExclusions.vue";
import PolicyChecksTab from "@/components/automation/PolicyChecksTab.vue";
import PolicyAutomatedTasksTab from "@/components/automation/PolicyAutomatedTasksTab.vue";

export default {
  name: "AutomationManager",
  emits: ["hide", "ok", "cancel"],
  components: {
    PolicyChecksTab,
    PolicyAutomatedTasksTab,
    ObsSectionNav,
    ObsPageHead,
  },
  mixins: [mixins],
  props: {
    // 050 (T028): página /automation/:policy?/:section? en vez de diálogo.
    embedded: { type: Boolean, default: false },
  },
  data() {
    return {
      QDialog,
      sep: " · ",
      sectionCounts: { checks: null, tasks: null },
      countsFor: null,
      subtab: "checks",
      policies: [],
      selectedPolicy: null,
      pagination: {
        rowsPerPage: 0,
        sortBy: "name",
        descending: true,
      },
    };
  },
  computed: {
    sortedPolicies() {
      return [...this.policies].sort((a, b) => a.name.localeCompare(b.name));
    },
    sectionGroups() {
      return [
        {
          key: "policy",
          label: this.$t("automationManager.policyGroup"),
          items: [
            { key: "checks", label: this.$t("automationManager.tabChecks"), count: this.sectionCounts.checks },
            { key: "tasks", label: this.$t("automationManager.tabTasks"), count: this.sectionCounts.tasks },
          ],
        },
      ];
    },
    columns() {
      return [
        {
          name: "active",
          label: this.$t("automationManager.colActive"),
          field: "active",
          align: "left",
        },
        {
          name: "enforced",
          label: this.$t("automationManager.colEnforced"),
          field: "enforced",
          align: "left",
        },
        {
          name: "name",
          label: this.$t("automationManager.colName"),
          field: "name",
          align: "left",
          sortable: true,
        },
        {
          name: "desc",
          label: this.$t("automationManager.colDescription"),
          field: "desc",
          align: "left",
        },
        {
          name: "relations",
          label: this.$t("automationManager.colRelations"),
          field: "relations",
          align: "left",
        },
        {
          name: "exclusions",
          label: this.$t("automationManager.colExclusions"),
          align: "left",
        },
        {
          name: "winupdatepolicy",
          label: this.$t("automationManager.colPatchPolicy"),
          field: "winupdatepolicy",
          align: "left",
        },
        {
          name: "alert_template",
          label: this.$t("automationManager.colAlertTemplate"),
          field: "alert_template",
          align: "left",
        },
        {
          name: "actions",
          label: this.$t("automationManager.colActions"),
          field: "actions",
          align: "left",
        },
      ];
    },
  },
  methods: {
    // 050 (T028): la política y la sección viven en la URL de la página.
    syncFromRoute() {
      if (!this.embedded) return;
      const id = Number(this.$route.params.policy);
      const sec = this.$route.params.section;
      this.subtab = sec === "tasks" ? "tasks" : "checks";
      this.selectedPolicy =
        this.policies.find((p) => p.id === id) || this.sortedPolicies[0] || null;
      // Desde el riel se llega a /automation: se completa la URL con la
      // política y la sección para que el enlace sea directo.
      if (this.selectedPolicy && (!id || !sec)) {
        this.goTo(this.selectedPolicy, this.subtab);
      }
      this.loadSectionCounts();
    },
    // Conteos de la navegación Chequeos/Tareas: las mismas lecturas de las
    // tablas de la política.
    loadSectionCounts() {
      const pol = this.selectedPolicy;
      if (!pol) return;
      if (this.countsFor === pol.id) return;
      this.countsFor = pol.id;
      this.sectionCounts = { checks: null, tasks: null };
      ["checks", "tasks"].forEach((k) =>
        this.$axios
          .get(`/automation/policies/${pol.id}/${k}/`)
          .then((r) => {
            if (this.countsFor === pol.id) this.sectionCounts[k] = r.data.length;
          })
          .catch(() => {}),
      );
    },
    goTo(policy, section) {
      this.$router.replace({
        name: "Automation",
        params: { policy: policy ? policy.id : undefined, section },
      });
    },
    selectPolicy(policy) {
      this.goTo(policy, this.subtab);
    },
    selectSection(section) {
      this.goTo(this.selectedPolicy, section);
    },
    exclusionsCount(policy) {
      return (
        policy.excluded_agents.length +
        policy.excluded_clients.length +
        policy.excluded_sites.length
      );
    },
    // Las acciones del menú contextual de la v1 que no están a la vista.
    policyActions(policy) {
      return [
        { key: "edit", icon: "edit", label: this.$t("automationManager.edit"), run: () => this.showEditPolicyForm(policy) },
        { key: "copy", icon: "content_copy", label: this.$t("automationManager.copy"), run: () => this.showCopyPolicyForm(policy) },
        {
          key: "active",
          icon: "power_settings_new",
          label: policy.active ? this.$t("automationManager.disablePolicy") : this.$t("automationManager.enablePolicy"),
          run: () => this.toggleCheckbox(policy, "Active"),
        },
        {
          key: "enforced",
          icon: "security",
          label: policy.enforced ? this.$t("automationManager.unenforcePolicy") : this.$t("automationManager.enforcePolicy"),
          run: () => this.toggleCheckbox(policy, "Enforced"),
        },
        { key: "delete", icon: "delete", label: this.$t("automationManager.delete"), run: () => this.deletePolicy(policy) },
      ];
    },
    getPolicies() {
      this.$q.loading.show();
      this.$axios
        .get("/automation/policies/")
        .then((r) => {
          this.policies = r.data;
          this.syncFromRoute();
          this.$q.loading.hide();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    clearRow() {
      if (!this.embedded) this.selectedPolicy = null;
    },
    refresh() {
      this.countsFor = null;
      this.getPolicies();
      this.clearRow();
    },
    deletePolicy(policy) {
      this.$q
        .dialog({
          title: this.$t("automationManager.deletePolicyTitle"),
          cancel: true,
          ok: { label: this.$t("automationManager.delete"), color: "negative" },
        })
        .onOk(() => {
          this.$q.loading.show();
          this.$axios
            .delete(`/automation/policies/${policy.id}/`)
            .then(() => {
              this.refresh();
              this.$q.loading.hide();
              this.notifySuccess(this.$t("automationManager.policyDeleted"));
              this.$store.dispatch("loadTree");
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        });
    },
    showRelations(policy) {
      this.$q.dialog({
        component: RelationsView,
        componentProps: {
          policy: policy,
        },
      });
    },
    showPolicyOverview() {
      this.$q.dialog({
        component: PolicyOverview,
      });
    },
    showAddPolicyForm() {
      this.$q
        .dialog({
          component: PolicyForm,
        })
        .onOk(() => {
          this.refresh();
        });
    },
    showCopyPolicyForm(policy) {
      this.$q
        .dialog({
          component: PolicyForm,
          componentProps: {
            copyPolicy: policy,
          },
        })
        .onOk(() => {
          this.refresh();
        });
    },
    showEditPolicyForm(policy) {
      this.$q
        .dialog({
          component: PolicyForm,
          componentProps: {
            policy: policy,
          },
        })
        .onOk(() => {
          this.refresh();
        });
    },
    showAlertTemplateAdd(policy) {
      this.$q
        .dialog({
          component: AlertTemplateAdd,
          componentProps: {
            type: "policy",
            object: policy,
          },
        })
        .onOk(() => {
          this.refresh();
        });
    },
    showPatchPolicyForm(policy) {
      this.$q
        .dialog({
          component: DialogWrapper,
          componentProps: {
            title:
              policy.winupdatepolicy.length > 0
                ? this.$t("automationManager.editPatchPolicy")
                : this.$t("automationManager.addPatchPolicy"),
            vuecomponent: PatchPolicyForm,
            componentProps: {
              policy: policy,
            },
          },
        })
        .onOk(() => {
          this.refresh();
        });
    },
    showPolicyExclusions(policy) {
      this.$q
        .dialog({
          component: PolicyExclusions,
          componentProps: {
            policy: policy,
          },
        })
        .onOk(() => {
          this.refresh();
        });
    },
    toggleCheckbox(policy, type) {
      this.$q.loading.show();
      let text = "";

      const data = {
        id: policy.id,
        name: policy.name,
        desc: policy.desc,
      };

      if (type === "Active") {
        text = !policy.active
          ? this.$t("automationManager.policyEnabled")
          : this.$t("automationManager.policyDisabled");
        data["active"] = !policy.active;
      } else if (type === "Enforced") {
        text = !policy.enforced
          ? this.$t("automationManager.policyEnforced")
          : this.$t("automationManager.policyEnforcementDisabled");
        data["enforced"] = !policy.enforced;
      }

      this.$axios
        .put(`/automation/policies/${data.id}/`, data)
        .then(() => {
          this.refresh();
          this.$q.loading.hide();
          this.notifySuccess(text);
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    patchPolicyText(policy) {
      return policy.winupdatepolicy.length > 0
        ? this.$t("automationManager.modifyPatchPolicy")
        : this.$t("automationManager.createPatchPolicy");
    },
    alertTemplateText(policy) {
      return policy.alert_template
        ? this.$t("automationManager.modifyAlertTemplate")
        : this.$t("automationManager.assignAlertTemplate");
    },
    rowSelectedClass(id, selectedPolicy) {
      if (selectedPolicy && selectedPolicy.id === id)
        return this.$q.dark.isActive ? "highlight-dark" : "highlight";
    },
    show() {
      this.$refs.dialog.show();
    },
    hide() {
      this.$refs.dialog.hide();
    },
    onHide() {
      this.$emit("hide");
    },
  },
  watch: {
    "$route.params"() {
      this.syncFromRoute();
    },
  },
  mounted() {
    this.getPolicies();
  },
};
</script>
