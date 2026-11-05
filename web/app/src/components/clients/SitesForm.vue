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
          <q-tooltip>{{ $t("sitesForm.close") }}</q-tooltip>
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
                inputmode="decimal"
                class="obs-mono-values"
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
                inputmode="decimal"
                class="obs-mono-values"
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
import { parseCoord, coordError } from "@/utils/coords";

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

    // Coordenadas del sitio (feature 026). Feature 051: se aceptan coma o punto
    // decimal y un texto que no es número es error, nunca «sin coordenada»
    // (antes, con coma en los dos campos, el sitio se guardaba sin ubicación).
    function coordRule(own, other, max, errorKey) {
      const error = coordError(own, other, max);
      if (error === null) return true;
      return t(
        error === "nullIsland" ? "sitesForm.nullIslandInvalid" : errorKey,
      );
    }

    const latitudeRule = (val) =>
      coordRule(val, state.value.longitude, 90, "sitesForm.latitudeInvalid");
    const longitudeRule = (val) =>
      coordRule(val, state.value.latitude, 180, "sitesForm.longitudeInvalid");

    async function submit() {
      loading.value = true;
      state.value.latitude = parseCoord(state.value.latitude);
      state.value.longitude = parseCoord(state.value.longitude);
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
