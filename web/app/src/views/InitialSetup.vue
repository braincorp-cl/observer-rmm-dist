<template>
  <div class="q-pa-md">
    <div class="row">
      <div class="col"></div>
      <div class="col">
        <q-card>
          <q-card-actions align="center">
            <q-btn
              :label="$t('setup.gettingStarted')"
              color="info"
              class="full-width"
              href="https://docs.observer.cl/guide_gettingstarted/"
              target="_blank"
            />
          </q-card-actions>
          <q-card-section class="row items-center">
            <div class="text-h5 text-weight-bold">{{ $t("setup.title") }}</div>
          </q-card-section>
          <q-form @submit.prevent="finish">
            <q-card-section>
              <div>{{ $t("setup.addClient") }}</div>
              <q-input
                dense
                outlined
                v-model="client.name"
                :rules="[(val) => !!val || $t('setup.required')]"
              >
                <template v-slot:prepend>
                  <q-icon name="business" />
                </template>
              </q-input>
            </q-card-section>
            <q-card-section>
              <div>{{ $t("setup.addSite") }}</div>
              <q-input
                dense
                outlined
                v-model="site.name"
                :rules="[(val) => !!val || $t('setup.required')]"
              >
                <template v-slot:prepend>
                  <q-icon name="apartment" />
                </template>
              </q-input>
            </q-card-section>
            <q-card-section>
              <div>{{ $t("setup.defaultTimezone") }}</div>
              <observer-dropdown
                filterable
                dense
                options-dense
                outlined
                v-model="timezone"
                :options="allTimezones"
              />
            </q-card-section>

            <q-card-section>
              <div>
                {{ $t("setup.companyName") }}
                <q-icon
                  name="ion-information-circle-outline"
                  size="sm"
                  class="q-ml-sm cursor-pointer"
                >
                  <q-tooltip class="text-caption">
                    {{ $t("setup.companyNameTooltip") }}
                  </q-tooltip>
                </q-icon>
              </div>

              <q-input dense outlined v-model="companyname"> </q-input>
            </q-card-section>

            <q-card-actions align="center">
              <q-btn
                :label="$t('setup.finish')"
                color="primary"
                class="full-width"
                type="submit"
              />
            </q-card-actions>
          </q-form>
        </q-card>
      </div>
      <div class="col"></div>
    </div>
  </div>
</template>

<script>
import mixins from "@/mixins/mixins";
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

export default {
  name: "InitialSetup",
  components: { ObserverDropdown },
  mixins: [mixins],
  data() {
    return {
      client: {
        name: "",
      },
      site: {
        name: "",
      },
      allTimezones: [],
      timezone: null,
      arch: "64",
      companyname: "",
    };
  },
  methods: {
    finish() {
      this.$q.loading.show();
      const data = {
        client: this.client,
        site: this.site,
        timezone: this.timezone,
        companyname: this.companyname,
        initialsetup: true,
      };
      this.$axios
        .post("/clients/", data)
        .then(() => {
          this.$q.loading.hide();
          this.$router.push({ name: "Dashboard" });
        })
        .catch(() => this.$q.loading.hide());
    },
    getSettings() {
      this.$axios.get("/core/settings/").then((r) => {
        this.allTimezones = Object.freeze(r.data.all_timezones);
        this.timezone = r.data.default_time_zone;
      });
    },
  },
  mounted() {
    this.getSettings();
  },
};
</script>
