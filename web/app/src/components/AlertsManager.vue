<template>
  <!-- 050 (T029): con `embedded` es la página /alerts (sin q-bar ni cierre). -->
  <component
    :is="embedded ? 'div' : QDialog"
    ref="dialog"
    :class="{ 'obs-page': embedded }"
    @hide="onHide"
  >
    <div
      :class="{ 'q-dialog-plugin': !embedded }"
      :style="embedded ? null : 'width: 90vw; max-width: 90vw'"
    >
      <template v-if="embedded">
        <ObsPageHead
          :title="$t('alertsManager.pageTitle')"
          :crumbs="[$t('alertsManager.pageCrumb'), $t('alertsManager.pageTemplates')]"
        >
          <q-btn
            outline
            no-caps
            class="obs-page__btn"
            icon="refresh"
            :aria-label="$t('alertsManager.refresh')"
            @click="refresh"
          />
          <q-btn
            unelevated
            no-caps
            color="primary"
            class="obs-page__btn"
            :label="$t('alertsManager.newTemplate')"
            @click="showAddTemplateModal"
          />
        </ObsPageHead>
        <p class="obs-page__lead">{{ $t("alertsManager.pageLead") }}</p>
        <q-table
          flat
          bordered
          dense
          class="obs-mgr__table"
          :rows="templates"
          :columns="pageColumns"
          v-model:pagination="pagination"
          row-key="id"
          binary-state-sort
          hide-bottom
          :rows-per-page-options="[0]"
          :no-data-label="$t('alertsManager.noTemplates')"
        >
          <template v-slot:body="props">
            <q-tr
              :props="props"
              class="cursor-pointer"
              @dblclick="showEditTemplateModal(props.row)"
            >
              <q-menu context-menu>
                <q-list dense style="min-width: 200px">
                  <q-item
                    v-for="a in rowActions(props.row)"
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
              <q-td key="is_active" :props="props" auto-width @click.stop>
                <q-toggle
                  dense
                  color="primary"
                  :aria-label="$t('alertsManager.enableTemplate')"
                  @update:model-value="toggleEnabled(props.row)"
                  v-model="props.row.is_active"
                />
              </q-td>
              <q-td key="name" :props="props">
                <span class="obs-mgr__name">{{ props.row.name }}</span>
                <q-badge
                  v-if="props.row.default_template"
                  color="grey"
                  class="obs-chip-neutral q-ml-sm"
                  >{{ $t("alertsManager.defaultChip") }}</q-badge
                >
              </q-td>
              <q-td key="notifies" :props="props">{{ notifiesLabel(props.row) }}</q-td>
              <q-td key="applied_to" :props="props" @click.stop>
                <a
                  href="#"
                  class="obs-mgr__link"
                  @click.prevent="showTemplateApplied(props.row)"
                  >{{
                    $t("alertsManager.showAppliedCount", {
                      count: props.row.applied_count,
                    })
                  }}</a
                >
              </q-td>
              <q-td key="alert_exclusions" :props="props" @click.stop>
                <a
                  href="#"
                  class="obs-mgr__link"
                  @click.prevent="showAlertExclusions(props.row)"
                  >{{
                    $t("alertsManager.alertExclusionsCount", {
                      count:
                        props.row.excluded_agents.length +
                        props.row.excluded_clients.length +
                        props.row.excluded_sites.length,
                    })
                  }}</a
                >
              </q-td>
              <q-td key="action_name" :props="props">{{
                props.row.action_name || "—"
              }}</q-td>
              <q-td key="resolved_action_name" :props="props">{{
                props.row.resolved_action_name || "—"
              }}</q-td>
              <q-td key="actions" :props="props" auto-width @click.stop>
                <q-btn
                  flat
                  dense
                  round
                  icon="more_horiz"
                  :aria-label="$t('alertsManager.rowActions')"
                >
                  <q-menu>
                    <q-list dense style="min-width: 200px">
                      <q-item
                        v-for="a in rowActions(props.row)"
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
              </q-td>
            </q-tr>
          </template>
        </q-table>
      </template>
      <q-card v-else>
        <q-bar>
          <q-btn
            ref="refresh"
            @click="refresh"
            class="q-mr-sm"
            dense
            flat
            push
            icon="refresh"
          />{{ $t("alertsManager.title") }}
          <q-space />
          <q-btn dense flat icon="close" v-close-popup>
            <q-tooltip class="bg-white text-primary">{{
              $t("alertsManager.close")
            }}</q-tooltip>
          </q-btn>
        </q-bar>
        <div class="q-pa-sm" style="min-height: 65vh; max-height: 65vh">
          <div class="q-gutter-sm">
            <q-btn
              ref="new"
              :label="$t('alertsManager.new')"
              dense
              flat
              push
              unelevated
              no-caps
              icon="add"
              @click="showAddTemplateModal"
            />
          </div>
          <q-table
            dense
            :rows="templates"
            :columns="columns"
            v-model:pagination="pagination"
            row-key="id"
            binary-state-sort
            hide-pagination
            virtual-scroll
            :rows-per-page-options="[0]"
            :no-data-label="$t('alertsManager.noTemplates')"
          >
            <!-- header slots -->
            <template v-slot:header-cell-is_active="props">
              <q-th :props="props" auto-width>
                <q-icon name="power_settings_new" size="1.5em">
                  <q-tooltip>{{
                    $t("alertsManager.enableTemplate")
                  }}</q-tooltip>
                </q-icon>
              </q-th>
            </template>
            <template v-slot:header-cell-agent_settings="props">
              <q-th :props="props" auto-width>
                <q-icon name="devices" size="1.5em">
                  <q-tooltip>{{
                    $t("alertsManager.hasAgentSettings")
                  }}</q-tooltip>
                </q-icon>
              </q-th>
            </template>
            <template v-slot:header-cell-check_settings="props">
              <q-th :props="props" auto-width>
                <q-icon name="fas fa-check-double" size="1.5em">
                  <q-tooltip>{{
                    $t("alertsManager.hasCheckSettings")
                  }}</q-tooltip>
                </q-icon>
              </q-th>
            </template>
            <template v-slot:header-cell-task_settings="props">
              <q-th :props="props" auto-width>
                <q-icon name="fas fa-tasks" size="1.5em">
                  <q-tooltip>{{
                    $t("alertsManager.hasTaskSettings")
                  }}</q-tooltip>
                </q-icon>
              </q-th>
            </template>
            <!-- body slots -->
            <template v-slot:body="props">
              <q-tr
                :props="props"
                class="cursor-pointer"
                :class="rowSelectedClass(props.row.id, selectedTemplate)"
                @click="selectedTemplate = props.row"
                @contextmenu="selectedTemplate = props.row"
                @dblclick="showEditTemplateModal(props.row)"
              >
                <!-- context menu -->
                <q-menu context-menu>
                  <q-list dense style="min-width: 200px">
                    <q-item
                      clickable
                      v-close-popup
                      @click="showEditTemplateModal(props.row)"
                    >
                      <q-item-section side>
                        <q-icon name="edit" />
                      </q-item-section>
                      <q-item-section>{{
                        $t("alertsManager.edit")
                      }}</q-item-section>
                    </q-item>
                    <q-item
                      clickable
                      v-close-popup
                      @click="deleteTemplate(props.row)"
                    >
                      <q-item-section side>
                        <q-icon name="delete" />
                      </q-item-section>
                      <q-item-section>{{
                        $t("alertsManager.delete")
                      }}</q-item-section>
                    </q-item>

                    <q-separator></q-separator>

                    <q-item
                      clickable
                      v-close-popup
                      @click="showAlertExclusions(props.row)"
                    >
                      <q-item-section side>
                        <q-icon name="rule" />
                      </q-item-section>
                      <q-item-section>{{
                        $t("alertsManager.alertExclusions")
                      }}</q-item-section>
                    </q-item>

                    <q-separator></q-separator>

                    <q-item clickable v-close-popup>
                      <q-item-section>{{
                        $t("alertsManager.close")
                      }}</q-item-section>
                    </q-item>
                  </q-list>
                </q-menu>
                <!-- enabled checkbox -->
                <q-td>
                  <q-checkbox
                    dense
                    @update:model-value="toggleEnabled(props.row)"
                    v-model="props.row.is_active"
                  />
                </q-td>
                <!-- agent settings -->
                <q-td>
                  <q-icon
                    v-if="props.row.agent_settings"
                    color="primary"
                    name="done"
                    size="sm"
                  >
                    <q-tooltip>{{
                      $t("alertsManager.agentSettingsTip")
                    }}</q-tooltip>
                  </q-icon>
                </q-td>
                <!-- text settings -->
                <q-td>
                  <q-icon
                    v-if="props.row.check_settings"
                    color="primary"
                    name="done"
                    size="sm"
                  >
                    <q-tooltip>{{
                      $t("alertsManager.checkSettingsTip")
                    }}</q-tooltip>
                  </q-icon>
                </q-td>
                <!-- dashboard settings -->
                <q-td>
                  <q-icon
                    v-if="props.row.task_settings"
                    color="primary"
                    name="done"
                    size="sm"
                  >
                    <q-tooltip>{{
                      $t("alertsManager.taskSettingsTip")
                    }}</q-tooltip>
                  </q-icon>
                </q-td>
                <!-- name -->
                <q-td
                  >{{ props.row.name }}
                  <q-chip
                    v-if="props.row.default_template"
                    color="primary"
                    text-color="white"
                    size="sm"
                    >{{ $t("alertsManager.defaultChip") }}</q-chip
                  >
                </q-td>
                <!-- applied to -->
                <q-td>
                  <span
                    style="cursor: pointer; text-decoration: underline"
                    class="text-primary"
                    @click="showTemplateApplied(props.row)"
                    >{{
                      $t("alertsManager.showAppliedCount", {
                        count: props.row.applied_count,
                      })
                    }}</span
                  ></q-td
                >
                <!-- alert exclusions -->
                <q-td>
                  <span
                    style="cursor: pointer; text-decoration: underline"
                    class="text-primary"
                    @click="showAlertExclusions(props.row)"
                    >{{
                      $t("alertsManager.alertExclusionsCount", {
                        count:
                          props.row.excluded_agents.length +
                          props.row.excluded_clients.length +
                          props.row.excluded_sites.length,
                      })
                    }}</span
                  ></q-td
                >
                <!-- failure action -->
                <q-td>{{ props.row.action_name }}</q-td>
                <!-- resolve action -->
                <q-td>{{ props.row.resolved_action_name }}</q-td>
              </q-tr>
            </template>
          </q-table>
        </div>
      </q-card>
    </div>
  </component>
</template>

<script>
import { QDialog } from "quasar";
import mixins from "@/mixins/mixins";
import ObsPageHead from "@/components/ui/ObsPageHead.vue";
import AlertTemplateForm from "@/components/modals/alerts/AlertTemplateForm.vue";
import AlertExclusions from "@/components/modals/alerts/AlertExclusions.vue";
import AlertTemplateRelated from "@/components/modals/alerts/AlertTemplateRelated.vue";

export default {
  name: "AlertsManager",
  components: { ObsPageHead },
  mixins: [mixins],
  props: {
    // 050 (T029): página /alerts en vez de diálogo.
    embedded: { type: Boolean, default: false },
  },
  emits: ["hide", "ok", "cancel"],
  data() {
    return {
      QDialog,
      selectedTemplate: null,
      templates: [],
      pagination: {
        rowsPerPage: 0,
        sortBy: "name",
        descending: true,
      },
    };
  },
  computed: {
    pageColumns() {
      const c = (name, label, field) => ({ name, label, field, align: "left" });
      return [
        { ...c("is_active", this.$t("alertsManager.colActive"), "is_active"), sortable: true },
        { ...c("name", this.$t("alertsManager.colName"), "name"), sortable: true },
        c("notifies", this.$t("alertsManager.colNotifies"), "name"),
        c("applied_to", this.$t("alertsManager.colAppliedTo"), "applied_count"),
        c("alert_exclusions", this.$t("alertsManager.colAlertExclusions"), "id"),
        c("action_name", this.$t("alertsManager.colFailureAction"), "action_name"),
        c("resolved_action_name", this.$t("alertsManager.colResolvedAction"), "resolved_action_name"),
        { name: "actions", label: "", field: "id", align: "right" },
      ];
    },
    columns() {
      return [
        {
          name: "is_active",
          label: this.$t("alertsManager.colActive"),
          field: "is_active",
          align: "left",
        },
        {
          name: "agent_settings",
          label: this.$t("alertsManager.colAgentSettings"),
          field: "agent_settings",
        },
        {
          name: "check_settings",
          label: this.$t("alertsManager.colCheckSettings"),
          field: "check_settings",
        },
        {
          name: "task_settings",
          label: this.$t("alertsManager.colTaskSettings"),
          field: "task_settings",
        },
        {
          name: "name",
          label: this.$t("alertsManager.colName"),
          field: "name",
          align: "left",
        },
        {
          name: "applied_to",
          label: this.$t("alertsManager.colAppliedTo"),
          field: "applied_to",
          align: "left",
        },
        {
          name: "alert_exclusions",
          label: this.$t("alertsManager.colAlertExclusions"),
          field: "alert_exclusions",
          align: "left",
        },
        {
          name: "action_name",
          label: this.$t("alertsManager.colFailureAction"),
          field: "action_name",
          align: "left",
        },
        {
          name: "resolved_action_name",
          label: this.$t("alertsManager.colResolvedAction"),
          field: "resolved_action_name",
          align: "left",
        },
      ];
    },
  },
  methods: {
    // 050 (T029): «Avisa sobre» resume los tres indicadores de la v1.
    notifiesLabel(row) {
      const parts = [];
      if (row.check_settings) parts.push(this.$t("alertsManager.notifiesChecks"));
      if (row.task_settings) parts.push(this.$t("alertsManager.notifiesTasks"));
      if (row.agent_settings) parts.push(this.$t("alertsManager.notifiesAvailability"));
      return parts.length ? parts.join(", ") : "—";
    },
    // Las acciones del menú contextual de la v1, también en el botón ⋯.
    rowActions(row) {
      return [
        { key: "edit", icon: "edit", label: this.$t("alertsManager.edit"), run: () => this.showEditTemplateModal(row) },
        { key: "delete", icon: "delete", label: this.$t("alertsManager.delete"), run: () => this.deleteTemplate(row) },
        { key: "exclusions", icon: "rule", label: this.$t("alertsManager.alertExclusions"), run: () => this.showAlertExclusions(row) },
      ];
    },
    getTemplates() {
      this.$q.loading.show();
      this.$axios
        .get("alerts/templates/")
        .then((r) => {
          this.templates = r.data;
          this.$q.loading.hide();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    clearRow() {
      this.selectedTemplate = null;
    },
    refresh() {
      this.$store.dispatch("refreshDashboard");
      this.getTemplates();
      this.clearRow();
    },
    deleteTemplate(template) {
      this.$q
        .dialog({
          title: this.$t("alertsManager.deleteTitle", { name: template.name }),
          cancel: true,
          ok: { label: this.$t("alertsManager.delete"), color: "negative" },
        })
        .onOk(() => {
          this.$q.loading.show();
          this.$axios
            .delete(`alerts/templates/${template.id}/`)
            .then(() => {
              this.refresh();
              this.$q.loading.hide();
              this.notifySuccess(
                this.$t("alertsManager.templateDeleted", {
                  name: template.name,
                }),
              );
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        });
    },
    showEditTemplateModal(template) {
      this.$q
        .dialog({
          component: AlertTemplateForm,
          componentProps: {
            alertTemplate: template,
          },
        })
        .onOk(() => {
          this.refresh();
        });
    },
    showAddTemplateModal() {
      this.clearRow();
      this.$q
        .dialog({
          component: AlertTemplateForm,
        })
        .onOk(() => {
          this.refresh();
        });
    },
    showAlertExclusions(template) {
      this.$q
        .dialog({
          component: AlertExclusions,
          componentProps: {
            template: template,
          },
        })
        .onOk(() => {
          this.refresh();
        });
    },
    showTemplateApplied(template) {
      this.$q.dialog({
        component: AlertTemplateRelated,
        componentProps: {
          template: template,
        },
      });
    },
    toggleEnabled(template) {
      let text = !template.is_active
        ? this.$t("alertsManager.templateEnabled")
        : this.$t("alertsManager.templateDisabled");

      const data = {
        id: template.id,
        is_active: !template.is_active,
      };

      this.$axios.put(`alerts/templates/${template.id}/`, data).then(() => {
        this.notifySuccess(text);
        this.$store.dispatch("refreshDashboard");
      });
    },
    rowSelectedClass(id, selectedTemplate) {
      if (selectedTemplate && selectedTemplate.id === id)
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
  mounted() {
    this.getTemplates();
  },
};
</script>
