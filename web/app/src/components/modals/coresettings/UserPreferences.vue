<template>
  <q-dialog ref="dialog" @hide="onHide">
    <q-card class="q-dialog-plugin" style="min-width: 60vw">
      <q-splitter v-model="splitterModel">
        <template v-slot:before>
          <q-tabs dense v-model="tab" vertical class="text-primary">
            <q-tab name="ui" :label="$t('userPreferences.userInterface')" />
          </q-tabs>
        </template>
        <template v-slot:after>
          <q-form @submit.prevent="editUserPrefs">
            <q-card-section class="row items-center">
              <div class="text-h6">{{ $t("userPreferences.title") }}</div>
              <q-space />
              <q-btn icon="close" flat round dense v-close-popup />
            </q-card-section>
            <q-tab-panels
              v-model="tab"
              animated
              transition-prev="jump-up"
              transition-next="jump-up"
            >
              <!-- UI -->
              <q-tab-panel name="ui">
                <div class="text-subtitle2">
                  {{ $t("userPreferences.userInterface") }}
                </div>
                <q-separator />
                <q-card-section class="row">
                  <div class="col-6">
                    {{ $t("userPreferences.agentDblClickAction") }}
                  </div>
                  <div class="col-2"></div>
                  <q-select
                    map-options
                    emit-value
                    outlined
                    dense
                    options-dense
                    v-model="agentDblClickAction"
                    :options="agentDblClickOptions"
                    class="col-4"
                    @update:model-value="url_action = null"
                  />
                </q-card-section>
                <q-card-section
                  class="row"
                  v-if="agentDblClickAction === 'urlaction'"
                >
                  <div class="col-6">{{ $t("userPreferences.urlAction") }}</div>
                  <div class="col-2"></div>
                  <q-select
                    map-options
                    emit-value
                    outlined
                    dense
                    options-dense
                    v-model="url_action"
                    :options="urlActions"
                    class="col-4"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-6">
                    {{ $t("userPreferences.agentTableDefaultTab") }}
                  </div>
                  <div class="col-2"></div>
                  <q-select
                    map-options
                    emit-value
                    outlined
                    dense
                    options-dense
                    v-model="defaultAgentTblTab"
                    :options="defaultAgentTblTabOptions"
                    class="col-4"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-4">
                    {{ $t("userPreferences.loadingBarColor") }}
                  </div>
                  <div class="col-4"></div>
                  <q-select
                    outlined
                    dense
                    options-dense
                    v-model="loading_bar_color"
                    :options="loadingBarColors"
                    class="col-4"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">
                    {{ $t("userPreferences.dashInfoColor") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    outlined
                    dense
                    v-model="dash_info_color"
                    class="col-8"
                  >
                    <template v-slot:after>
                      <q-btn
                        round
                        dense
                        flat
                        size="sm"
                        icon="info"
                        @click="openURL(quasar_color_url)"
                      >
                        <q-tooltip>{{
                          $t("userPreferences.colorOptionsTip")
                        }}</q-tooltip>
                      </q-btn>
                    </template>
                  </q-input>
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">
                    {{ $t("userPreferences.dashPositiveColor") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    outlined
                    dense
                    v-model="dash_positive_color"
                    class="col-8"
                  >
                    <template v-slot:after>
                      <q-btn
                        round
                        dense
                        flat
                        size="sm"
                        icon="info"
                        @click="openURL(quasar_color_url)"
                      >
                        <q-tooltip>{{
                          $t("userPreferences.colorOptionsTip")
                        }}</q-tooltip>
                      </q-btn>
                    </template>
                  </q-input>
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">
                    {{ $t("userPreferences.dashNegativeColor") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    outlined
                    dense
                    v-model="dash_negative_color"
                    class="col-8"
                  >
                    <template v-slot:after>
                      <q-btn
                        round
                        dense
                        flat
                        size="sm"
                        icon="info"
                        @click="openURL(quasar_color_url)"
                      >
                        <q-tooltip>{{
                          $t("userPreferences.colorOptionsTip")
                        }}</q-tooltip>
                      </q-btn>
                    </template>
                  </q-input>
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">
                    {{ $t("userPreferences.dashWarningColor") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input
                    outlined
                    dense
                    v-model="dash_warning_color"
                    class="col-8"
                  >
                    <template v-slot:after>
                      <q-btn
                        round
                        dense
                        flat
                        size="sm"
                        icon="info"
                        @click="openURL(quasar_color_url)"
                      >
                        <q-tooltip>{{
                          $t("userPreferences.colorOptionsTip")
                        }}</q-tooltip>
                      </q-btn>
                    </template>
                  </q-input>
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">
                    {{ $t("userPreferences.clientSort") }}
                  </div>
                  <div class="col-2"></div>
                  <q-select
                    map-options
                    emit-value
                    outlined
                    dense
                    options-dense
                    v-model="clientTreeSort"
                    :options="clientTreeSortOptions"
                    class="col-8"
                  />
                </q-card-section>
                <q-card-section class="row">
                  <div class="col-2">
                    {{ $t("userPreferences.dateFormat") }}
                  </div>
                  <div class="col-2"></div>
                  <q-input outlined dense v-model="date_format" class="col-8">
                    <template v-slot:after>
                      <q-btn
                        round
                        dense
                        flat
                        size="sm"
                        icon="info"
                        @click="
                          openURL(
                            'https://quasar.dev/quasar-utils/date-utils#format-for-display',
                          )
                        "
                      >
                        <q-tooltip>{{
                          $t("userPreferences.formatOptionsTip")
                        }}</q-tooltip>
                      </q-btn>
                    </template>
                  </q-input>
                </q-card-section>
                <q-card-section class="row">
                  <q-checkbox
                    v-model="clear_search_when_switching"
                    :label="$t('userPreferences.clearSearch')"
                  />
                </q-card-section>
              </q-tab-panel>
            </q-tab-panels>

            <q-card-section class="row items-center">
              <q-btn
                :label="$t('userPreferences.save')"
                color="primary"
                type="submit"
              />
            </q-card-section>
          </q-form>
        </template>
      </q-splitter>
    </q-card>
  </q-dialog>
</template>

<script>
import { openURL } from "quasar";
import { loadingBarColors } from "@/mixins/data";
import mixins from "@/mixins/mixins";

export default {
  name: "UserPreferences",
  emits: ["hide", "ok", "cancel"],
  mixins: [mixins],
  data() {
    return {
      loadingBarColors,
      agentDblClickAction: "",
      defaultAgentTblTab: "",
      clientTreeSort: "",
      url_action: null,
      tab: "ui",
      splitterModel: 20,
      loading_bar_color: "",
      dash_info_color: "",
      dash_positive_color: "",
      dash_negative_color: "",
      dash_warning_color: "",
      urlActions: [],
      clear_search_when_switching: true,
      date_format: "",
      quasar_color_url: "https://quasar.dev/style/color-palette",
    };
  },
  computed: {
    clientTreeSortOptions() {
      return [
        {
          label: this.$t("userPreferences.sortAlphaFail"),
          value: "alphafail",
        },
        {
          label: this.$t("userPreferences.sortAlpha"),
          value: "alpha",
        },
      ];
    },
    agentDblClickOptions() {
      return [
        {
          label: this.$t("userPreferences.optEditAgent"),
          value: "editagent",
        },
        {
          label: this.$t("userPreferences.optTakeControl"),
          value: "takecontrol",
        },
        {
          label: this.$t("userPreferences.optRemoteBg"),
          value: "remotebg",
        },
        {
          label: this.$t("userPreferences.optRunUrlAction"),
          value: "urlaction",
        },
      ];
    },
    defaultAgentTblTabOptions() {
      return [
        {
          label: this.$t("userPreferences.optServers"),
          value: "server",
        },
        {
          label: this.$t("userPreferences.optWorkstations"),
          value: "workstation",
        },
        {
          label: this.$t("userPreferences.optMixed"),
          value: "mixed",
        },
      ];
    },
  },
  watch: {
    agentDblClickAction(new_value) {
      if (new_value === "urlaction") {
        this.getURLActions();
      }
    },
  },
  methods: {
    openURL(url) {
      openURL(url);
    },
    getURLActions() {
      this.$axios.get("/core/urlaction/").then((r) => {
        this.urlActions = r.data
          .filter((action) => action.action_type === "web")
          .sort((a, b) => a.name.localeCompare(b.name))
          .map((action) => ({
            label: action.name,
            value: action.id,
          }));

        if (this.urlActions.length === 0) {
          this.notifyWarning(this.$t("userPreferences.noUrlActions"));
        }
      });
    },
    getUserPrefs() {
      this.$axios.get("/core/dashinfo/").then((r) => {
        this.agentDblClickAction = r.data.dbl_click_action;
        this.url_action = r.data.url_action;
        this.defaultAgentTblTab = r.data.default_agent_tbl_tab;
        this.clientTreeSort = r.data.client_tree_sort;
        this.loading_bar_color = r.data.loading_bar_color;
        this.dash_info_color = r.data.dash_info_color;
        this.dash_positive_color = r.data.dash_positive_color;
        this.dash_negative_color = r.data.dash_negative_color;
        this.dash_warning_color = r.data.dash_warning_color;
        this.clear_search_when_switching = r.data.clear_search_when_switching;
        this.date_format = r.data.date_format;
      });
    },
    editUserPrefs() {
      if (
        this.agentDblClickAction === "urlaction" &&
        this.url_action === null
      ) {
        this.notifyError(this.$t("userPreferences.selectUrlAction"));
        return;
      }
      const data = {
        agent_dblclick_action: this.agentDblClickAction,
        url_action: this.url_action,
        default_agent_tbl_tab: this.defaultAgentTblTab,
        client_tree_sort: this.clientTreeSort,
        loading_bar_color: this.loading_bar_color,
        dash_info_color: this.dash_info_color,
        dash_positive_color: this.dash_positive_color,
        dash_negative_color: this.dash_negative_color,
        dash_warning_color: this.dash_warning_color,
        clear_search_when_switching: this.clear_search_when_switching,
        date_format: this.date_format,
      };
      this.$axios.patch("/accounts/users/ui/", data).then(() => {
        this.notifySuccess(this.$t("userPreferences.prefsSaved"));
        this.$store.dispatch("loadTree");
        this.onOk();
      });
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
    onOk() {
      this.$emit("ok");
      this.hide();
    },
  },
  mounted() {
    this.getUserPrefs();
  },
};
</script>
