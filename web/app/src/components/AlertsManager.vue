<template>
  <q-dialog ref="dialog" @hide="onHide">
    <div class="q-dialog-plugin" style="width: 90vw; max-width: 90vw">
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
  </q-dialog>
</template>

<script>
import mixins from "@/mixins/mixins";
import AlertTemplateForm from "@/components/modals/alerts/AlertTemplateForm.vue";
import AlertExclusions from "@/components/modals/alerts/AlertExclusions.vue";
import AlertTemplateRelated from "@/components/modals/alerts/AlertTemplateRelated.vue";

export default {
  name: "AlertsManager",
  mixins: [mixins],
  emits: ["hide", "ok", "cancel"],
  data() {
    return {
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
