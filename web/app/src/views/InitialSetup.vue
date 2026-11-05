<template>
  <!--
    050 (V2-S06): la configuracion inicial en la maqueta de acceso.

    Antes era la misma `q-card` centrada que el login: la tarjeta de la v1 con
    otros tokens. El gauntlet la midio en 9,9-11,5 % de diferencia con la v1,
    pero con el bbox encerrado DENTRO de la tarjeta — o sea retoque, no maqueta.

    Ahora hereda `AccessLayout` y los rotulos van ARRIBA de cada campo, no como
    un `div` suelto encima del control.
  -->
  <AccessLayout force-dark :heading="$t('setup.title')">
    <q-form @submit.prevent="finish">
      <div class="obs-access__field">
        <label class="obs-access__label" for="obs-setup-client">
          {{ $t("setup.addClient") }}
        </label>
        <q-input
          id="obs-setup-client"
          dense
          outlined
          v-model="client.name"
          :rules="[(val) => !!val || $t('setup.required')]"
        >
          <template v-slot:prepend>
            <q-icon name="business" />
          </template>
        </q-input>
      </div>

      <div class="obs-access__field">
        <label class="obs-access__label" for="obs-setup-site">
          {{ $t("setup.addSite") }}
        </label>
        <q-input
          id="obs-setup-site"
          dense
          outlined
          v-model="site.name"
          :rules="[(val) => !!val || $t('setup.required')]"
        >
          <template v-slot:prepend>
            <q-icon name="apartment" />
          </template>
        </q-input>
      </div>

      <div class="obs-access__field">
        <label class="obs-access__label">
          {{ $t("setup.defaultTimezone") }}
        </label>
        <observer-dropdown
          filterable
          dense
          options-dense
          outlined
          v-model="timezone"
          :options="allTimezones"
        />
      </div>

      <div class="obs-access__field">
        <label class="obs-access__label" for="obs-setup-company">
          {{ $t("setup.companyName") }}
          <q-icon
            name="ion-information-circle-outline"
            size="xs"
            class="q-ml-xs cursor-pointer"
          >
            <q-tooltip class="text-caption">
              {{ $t("setup.companyNameTooltip") }}
            </q-tooltip>
          </q-icon>
        </label>
        <q-input id="obs-setup-company" dense outlined v-model="companyname" />
      </div>

      <q-btn
        unelevated
        no-caps
        :label="$t('setup.finish')"
        color="primary"
        class="obs-page__btn full-width"
        type="submit"
      />
    </q-form>

    <template #foot>
      <!-- El enlace a la documentacion es ayuda, no la accion de la pantalla:
           va al pie y de contorno, para no competir con «Finalizar». -->
      <q-btn
        outline
        no-caps
        :label="$t('setup.gettingStarted')"
        class="obs-page__btn full-width q-mt-md"
        href="https://docs.observer.cl/guide_gettingstarted/"
        target="_blank"
      />
    </template>
  </AccessLayout>
</template>

<script>
import mixins from "@/mixins/mixins";
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";
import AccessLayout from "@/components/access/AccessLayout.vue";

export default {
  name: "InitialSetup",
  components: { ObserverDropdown, AccessLayout },
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
