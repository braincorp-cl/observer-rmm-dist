<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="width: 60vw">
      <q-bar>
        {{
          !!site
            ? $t("sitesForm.editing", { name: site.name })
            : $t("sitesForm.titleAdd")
        }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("sitesForm.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-form @submit="submit">
        <q-card-section>
          <observer-dropdown
            v-model="state.client"
            :label="$t('sitesForm.client')"
            :options="clientOptions"
            outlined
            mapOptions
            :rules="[(val) => !!val || $t('sitesForm.clientRequired')]"
            filterable
          />
        </q-card-section>
        <q-card-section>
          <q-input
            :rules="[(val) => !!val || $t('sitesForm.nameRequired')]"
            outlined
            dense
            v-model="state.name"
            :label="$t('sitesForm.name')"
          />
        </q-card-section>

        <!-- Ubicación física del sitio (feature 026). OPCIONAL: se puede dejar
             vacía al crear y completarla después. -->
        <q-card-section class="q-pt-none">
          <div class="text-caption text-grey-7 q-mb-sm">
            {{ $t("sitesForm.locationHint") }}
          </div>
          <div class="row q-col-gutter-sm">
            <div class="col">
              <q-input
                outlined
                dense
                clearable
                type="number"
                step="any"
                v-model="state.latitude"
                :label="$t('sitesForm.latitude')"
                :rules="[latitudeRule]"
              />
            </div>
            <div class="col">
              <q-input
                outlined
                dense
                clearable
                type="number"
                step="any"
                v-model="state.longitude"
                :label="$t('sitesForm.longitude')"
                :rules="[longitudeRule]"
              />
            </div>
          </div>
        </q-card-section>

        <div class="q-pl-sm text-h6" v-if="customFields.length > 0">
          {{ $t("sitesForm.customFields") }}
        </div>
        <q-card-section v-for="field in customFields" :key="field.id">
          <CustomField v-model="custom_fields[field.name]" :field="field" />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn
            dense
            flat
            push
            :label="$t('sitesForm.cancel')"
            v-close-popup
          />
          <q-btn
            :loading="loading"
            dense
            flat
            push
            :label="$t('sitesForm.save')"
            color="primary"
            type="submit"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import { ref, onMounted } from "vue";
import { useQuasar, useDialogPluginComponent } from "quasar";
import { useI18n } from "vue-i18n";
import { useClientDropdown } from "@/composables/clients";
import { fetchSite, saveSite, editSite } from "@/api/clients";
import { fetchCustomFields } from "@/api/core";
import { formatCustomFields } from "@/utils/format";
import { notifySuccess } from "@/utils/notify";

// ui imports
import CustomField from "@/components/ui/CustomField.vue";
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

export default {
  name: "SitesForm",
  emits: [...useDialogPluginComponent.emits],
  components: {
    CustomField,
    ObserverDropdown,
  },
  props: {
    site: Object,
    client: Number,
  },
  setup(props) {
    // setup quasar dialog
    const $q = useQuasar();
    const { dialogRef, onDialogOK, onDialogHide } = useDialogPluginComponent();
    const { t } = useI18n();

    // setup dropdowns
    const { clientOptions } = useClientDropdown(true);

    // sites for logic
    const state = !!props.site
      ? ref(Object.assign({}, props.site))
      : ref({ client: props.client, name: "" });
    const custom_fields = ref({});
    const customFields = ref([]);
    const loading = ref(false);

    // Coordenadas del sitio (feature 026). q-input entrega strings, y al limpiar
    // el campo entrega "" o null; el backend espera number o null, así que se
    // normaliza acá en vez de mandar "" y comerse un 400.
    function coord(value) {
      if (value === null || value === undefined || value === "") return null;
      const n = Number(value);
      return Number.isFinite(n) ? n : null;
    }

    // Ambas o ninguna, y dentro de rango: media coordenada no ubica nada y el
    // backend la rechaza igual, así que se avisa antes de mandar el formulario.
    function coordRule(own, other, max, errorKey) {
      const a = coord(own);
      const b = coord(other);
      if (a === null && b === null) return true;
      if (a === null || Math.abs(a) > max) return t(errorKey);
      // (0, 0) es el "null island" del Atlántico: siempre es un campo a medio
      // llenar, nunca una oficina.
      if (a === 0 && b === 0) return t("sitesForm.nullIslandInvalid");
      return true;
    }

    const latitudeRule = (val) =>
      coordRule(val, state.value.longitude, 90, "sitesForm.latitudeInvalid");
    const longitudeRule = (val) =>
      coordRule(val, state.value.latitude, 180, "sitesForm.longitudeInvalid");

    async function submit() {
      loading.value = true;
      state.value.latitude = coord(state.value.latitude);
      state.value.longitude = coord(state.value.longitude);
      const data = {
        site: state.value,
        custom_fields: formatCustomFields(
          customFields.value,
          custom_fields.value,
        ),
      };
      try {
        const result = !!props.site
          ? await editSite(props.site.id, data)
          : await saveSite(data);
        notifySuccess(result);
        onDialogOK();
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    async function getSiteCustomFieldValues() {
      loading.value = true;
      const data = await fetchSite(props.site.id);

      for (let field of customFields.value) {
        const value = data.custom_fields.find(
          (value) => value.field === field.id,
        );

        if (field.type === "multiple") {
          if (value) custom_fields.value[field.name] = value.value;
          else custom_fields.value[field.name] = [];
        } else if (field.type === "checkbox") {
          if (value) custom_fields.value[field.name] = value.value;
          else custom_fields.value[field.name] = false;
        } else {
          if (value) custom_fields.value[field.name] = value.value;
          else custom_fields.value[field.name] = "";
        }
      }
      loading.value = false;
    }

    onMounted(async () => {
      $q.loading.show();
      try {
        const fields = await fetchCustomFields({ model: "site" });
        customFields.value = fields.filter((field) => !field.hide_in_ui);
        if (props.site) getSiteCustomFieldValues();
      } catch (e) {
        console.error(e);
      }
      $q.loading.hide();
    });

    return {
      // reactive data
      state,
      loading,
      custom_fields,
      customFields,
      clientOptions,

      // methods
      submit,
      latitudeRule,
      longitudeRule,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
