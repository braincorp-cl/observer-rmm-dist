<template>
  <q-dialog ref="dialog" @hide="onHide">
    <q-card style="width: 60vw">
      <q-bar>
        {{ $t("relationsView.title", { name: policy.name }) }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("relationsView.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-card-section
        class="row items-center"
        v-if="
          related.default_server_policy || related.default_workstation_policy
        "
      >
        <div v-if="related.default_server_policy" class="text-body">
          <q-icon name="error_outline" color="info" size="1.5em" />{{
            $t("relationsView.defaultServerPolicy")
          }}
        </div>
        <div v-if="related.default_workstation_policy" class="text-body">
          <q-icon name="error_outline" color="info" size="1.5em" />{{
            $t("relationsView.defaultWorkstationPolicy")
          }}
        </div>
      </q-card-section>
      <!-- 050 (T028): navegación lateral en vez de pestañas. -->
      <q-card-section class="row no-wrap q-pa-none">
        <ObsSectionNav
          :groups="navGroups"
          :section="tab"
          :aria-label="$t('relationsView.title', { name: policy.name })"
          @select="tab = $event"
        />
        <q-scroll-area
          :thumb-style="thumbStyle"
          class="col"
          style="height: 50vh"
        >
          <q-tab-panels v-model="tab" :animated="false">
            <q-tab-panel name="clients">
              <q-list separator padding>
                <q-item
                  v-for="item in related.server_clients"
                  :key="item.id + 'servers'"
                >
                  <q-item-section>
                    <q-item-label>{{ item.name }}</q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-item-label>
                      <i>{{ $t("relationsView.appliedToServers") }}</i>
                    </q-item-label>
                  </q-item-section>
                </q-item>
                <q-item
                  v-for="item in related.workstation_clients"
                  :key="item.id + 'workstations'"
                >
                  <q-item-section>
                    <q-item-label>{{ item.name }}</q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-item-label>
                      <i>{{ $t("relationsView.appliedToWorkstations") }}</i>
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-tab-panel>

            <q-tab-panel name="sites">
              <q-list separator padding>
                <q-item
                  v-for="item in related.server_sites"
                  :key="item.id + 'servers'"
                >
                  <q-item-section>
                    <q-item-label>{{ item.name }}</q-item-label>
                    <q-item-label caption>{{ item.client_name }}</q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-item-label>
                      <i>{{ $t("relationsView.appliedToServers") }}</i>
                    </q-item-label>
                  </q-item-section>
                </q-item>
                <q-item
                  v-for="item in related.workstation_sites"
                  :key="item.id + 'workstations'"
                >
                  <q-item-section>
                    <q-item-label>{{ item.name }}</q-item-label>
                    <q-item-label caption>{{ item.client_name }}</q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-item-label>
                      <i>{{ $t("relationsView.appliedToWorkstations") }}</i>
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-tab-panel>

            <q-tab-panel name="agents">
              <q-list separator padding>
                <q-item v-for="item in related.agents" :key="item.pk">
                  <q-item-section>
                    <q-item-label>{{ item.hostname }}</q-item-label>
                    <q-item-label caption>
                      <b>{{ item.client }}</b>
                      {{ item.site }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-tab-panel>
          </q-tab-panels>
        </q-scroll-area>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import ObsSectionNav from "@/components/shell/ObsSectionNav.vue";

export default {
  name: "RelationsView",
  components: { ObsSectionNav },
  emits: ["hide", "ok", "cancel"],
  props: {
    policy: {
      type: Object,
      required: true,
    },
  },
  computed: {
    navGroups() {
      return [
        {
          key: "relations",
          items: ["clients", "sites", "agents"].map((k) => ({
            key: k,
            label: this.$t(`relationsView.${k}`),
          })),
        },
      ];
    },
  },
  data() {
    return {
      tab: "clients",
      related: {},
      thumbStyle: {
        right: "2px",
        borderRadius: "5px",
        backgroundColor: "#027be3",
        width: "5px",
        opacity: 0.75,
      },
    };
  },
  methods: {
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
    this.$q.loading.show();

    this.$axios
      .get(`/automation/policies/${this.policy.id}/related/`)
      .then((r) => {
        this.$q.loading.hide();
        this.related = r.data;
      })
      .catch(() => {
        this.$q.loading.hide();
      });
  },
};
</script>
