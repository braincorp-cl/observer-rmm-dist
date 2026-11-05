<template>
  <!-- 050 (T049): mismo andamiaje que LoginView — q-layout / q-page-container /
       q-page centrada — en vez del `row` con dos columnas vacías. La tarjeta
       toma el mismo ancho responsivo que el acceso, así que las tres pantallas
       del flujo comparten geometría. `obs-ws` es el ámbito de tokens de las
       vistas migradas: sin él, los grises internos de Quasar (rótulo y
       marginales del campo, borde del `outlined`, íconos) los pinta la hoja del
       framework con alfa sobre negro/blanco en vez de los tokens --obs-*
       (V2-G02). -->
  <q-layout>
    <q-page-container>
      <q-page class="flex flex-center obs-ws">
        <q-card
          v-bind:style="$q.screen.lt.sm ? { width: '80%' } : { width: '30%' }"
        >
          <q-card-actions align="center">
            <!-- 050 (T049): enlace a la documentación ⇒ botón secundario
                 (`outline` + `obs-page__btn`, el patrón de las vistas
                 migradas). Antes iba `color="info"`, que lo ponía a competir
                 con la acción principal de la tarjeta. -->
            <q-btn
              outline
              no-caps
              :label="$t('setup.gettingStarted')"
              class="obs-page__btn full-width"
              href="https://docs.observer.cl/guide_gettingstarted/"
              target="_blank"
            />
          </q-card-actions>
          <q-card-section class="row items-center">
            <h1 class="obs-page__title">{{ $t("setup.title") }}</h1>
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
                no-caps
                :label="$t('setup.finish')"
                color="primary"
                class="full-width"
                type="submit"
              />
            </q-card-actions>
          </q-form>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
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
