<template>
  <!--
    050 (T034, V2-S04): con `embedded` es la página /preferences con la maqueta de
    ajustes (navegación lateral, migas y título, tarjeta de filas y barra fija con
    cambios sin guardar, Restablecer y Guardar). Sin `embedded` sigue siendo el
    diálogo. Los campos y el PATCH /accounts/users/ui/ son los mismos.
  -->
  <component
    :is="embedded ? 'div' : QDialog"
    ref="dialog"
    :class="{ 'obs-mgr obs-set': embedded }"
    @hide="onHide"
  >
    <ObsSectionNav
      v-if="embedded"
      wide
      :groups="navGroups"
      section="ui"
      :aria-label="$t('userPreferences.title')"
    />
    <component
      :is="embedded ? 'div' : QCard"
      :class="embedded ? 'obs-set__form' : 'q-dialog-plugin obs-set obs-prefs'"
      :style="embedded ? null : 'min-width: 60vw'"
    >
      <q-form class="obs-set__form" @submit.prevent="editUserPrefs">
        <q-card-section v-if="!embedded" class="row items-center">
          <div class="text-h6">{{ $t("userPreferences.title") }}</div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <div :class="embedded ? 'obs-set__scroll' : 'obs-prefs__body'">
          <div :class="{ 'obs-page obs-set__page': embedded }">
            <ObsPageHead
              v-if="embedded"
              :title="$t('userPreferences.title')"
              :crumbs="[$t('userPreferences.accountCrumb')]"
            />
            <section class="obs-set__panel">
              <h2 class="obs-set__card-title">
                {{ $t("userPreferences.userInterface") }}
              </h2>
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
                <q-input outlined dense v-model="dash_info_color" class="col-8">
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
            </section>
          </div>
        </div>

        <component
          :is="embedded ? 'div' : QCardSection"
          :class="embedded ? 'obs-set__bar' : 'row items-center justify-end'"
        >
          <template v-if="embedded">
            <span class="obs-set__dirty" aria-live="polite">{{
              dirtyCount
                ? $t("settingsPage.unsaved", { n: dirtyCount }, dirtyCount)
                : $t("settingsPage.noChanges")
            }}</span>
            <q-space />
            <q-btn
              outline
              no-caps
              class="obs-page__btn"
              :disable="!dirtyCount"
              :label="$t('settingsPage.reset')"
              @click="resetPrefs"
            />
          </template>
          <q-btn
            unelevated
            no-caps
            class="obs-page__btn"
            :label="$t('userPreferences.save')"
            color="primary"
            type="submit"
          />
        </component>
      </q-form>
    </component>
  </component>
</template>

<script>
import { openURL, QCard, QCardSection, QDialog } from "quasar";
import ObsSectionNav from "@/components/shell/ObsSectionNav.vue";
import ObsPageHead from "@/components/ui/ObsPageHead.vue";
import { loadingBarColors } from "@/mixins/data";
import mixins from "@/mixins/mixins";

export default {
  name: "UserPreferences",
  emits: ["hide", "ok", "cancel"],
  props: {
    embedded: { type: Boolean, default: false },
  },
  setup() {
    return { QCard, QCardSection, QDialog };
  },
  components: { ObsPageHead, ObsSectionNav },
  mixins: [mixins],
  data() {
    return {
      loadingBarColors,
      agentDblClickAction: "",
      defaultAgentTblTab: "",
      clientTreeSort: "",
      url_action: null,
      loading_bar_color: "",
      dash_info_color: "",
      dash_positive_color: "",
      dash_negative_color: "",
      dash_warning_color: "",
      urlActions: [],
      clear_search_when_switching: true,
      // Lo que devolvió el servidor: cuenta los cambios y permite restablecer.
      saved: null,
      date_format: "",
      quasar_color_url: "https://quasar.dev/style/color-palette",
    };
  },
  computed: {
    navGroups() {
      return [
        {
          key: "account",
          label: this.$t("userPreferences.accountCrumb"),
          items: [
            { key: "ui", label: this.$t("userPreferences.userInterface") },
          ],
        },
      ];
    },
    prefsData() {
      return {
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
    },
    dirtyCount() {
      if (!this.saved) return 0;
      return Object.keys(this.saved).filter(
        (k) => this.saved[k] !== this.prefsData[k],
      ).length;
    },
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
        this.saved = { ...this.prefsData };
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
      const data = { ...this.prefsData };
      this.$axios.patch("/accounts/users/ui/", data).then(() => {
        this.notifySuccess(this.$t("userPreferences.prefsSaved"));
        this.$store.dispatch("loadTree");
        if (this.embedded) {
          this.saved = { ...this.prefsData };
          this.$store.dispatch("getDashInfo");
        } else this.onOk();
      });
    },
    show() {
      this.$refs.dialog.show();
    },
    hide() {
      this.$refs.dialog.hide();
    },
    resetPrefs() {
      const s = this.saved;
      this.agentDblClickAction = s.agent_dblclick_action;
      this.url_action = s.url_action;
      this.defaultAgentTblTab = s.default_agent_tbl_tab;
      this.clientTreeSort = s.client_tree_sort;
      this.loading_bar_color = s.loading_bar_color;
      this.dash_info_color = s.dash_info_color;
      this.dash_positive_color = s.dash_positive_color;
      this.dash_negative_color = s.dash_negative_color;
      this.dash_warning_color = s.dash_warning_color;
      this.clear_search_when_switching = s.clear_search_when_switching;
      this.date_format = s.date_format;
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
