<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="min-width: 40vw">
      <q-bar>
        {{ $t("resetPatchPolicy.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("resetPatchPolicy.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-card-section class="text-subtitle3">
        {{ $t("resetPatchPolicy.description") }}
      </q-card-section>

      <q-card-section>
        <q-option-group
          v-model="target"
          :options="targetOptions"
          color="primary"
          inline
          dense
        />
      </q-card-section>

      <q-form @submit="submit">
        <q-card-section v-if="target == 'client'">
          <observer-dropdown
            :rules="[(val) => !!val || $t('resetPatchPolicy.required')]"
            :label="$t('resetPatchPolicy.clients')"
            mapOptions
            filterable
            clearable
            outlined
            v-model="state.client"
            :options="clientOptions"
          />
        </q-card-section>
        <q-card-section v-if="target == 'site'">
          <observer-dropdown
            :rules="[(val) => !!val || $t('resetPatchPolicy.required')]"
            :label="$t('resetPatchPolicy.sites')"
            mapOptions
            filterable
            clearable
            outlined
            v-model="state.site"
            :options="siteOptions"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            flat
            push
            dense
            :label="$t('resetPatchPolicy.cancel')"
            v-close-popup
          />
          <q-btn
            :loading="loading"
            flat
            dense
            push
            :label="
              target == 'all'
                ? $t('resetPatchPolicy.clearAll')
                : $t('resetPatchPolicy.clear')
            "
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
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import { useClientDropdown, useSiteDropdown } from "@/composables/clients";
import { sendPatchPolicyReset } from "@/api/automation";
import { notifySuccess } from "@/utils/notify";

//ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

export default {
  name: "ResetPatchPolicy",
  components: {
    ObserverDropdown,
  },
  emits: [...useDialogPluginComponent.emits],
  setup() {
    // setup quasar dialog plugin
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
    const { t } = useI18n();

    // static data
    const targetOptions = computed(() => [
      { label: t("resetPatchPolicy.optAll"), value: "all" },
      { label: t("resetPatchPolicy.optClient"), value: "client" },
      { label: t("resetPatchPolicy.optSite"), value: "site" },
    ]);

    // setup dropdowns
    const { client, clientOptions } = useClientDropdown(true);
    const { site, siteOptions } = useSiteDropdown(true);

    // reset patch policy logic
    const state = ref({
      client: client,
      site: site,
    });

    const target = ref("all");
    const loading = ref(false);

    watch(target, () => {
      state.value.client = null;
      state.value.site = null;
    });

    async function submit() {
      loading.value = true;
      try {
        const data = {};
        if (target.value === "client") data.client = state.value.client;
        else if (target.value === "site") data.site = state.value.site;

        const result = await sendPatchPolicyReset(data);
        notifySuccess(result);
        onDialogOK();
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
    }

    return {
      // reactive data
      state,
      target,
      loading,

      // non-reactive data
      targetOptions,
      clientOptions,
      siteOptions,

      // methods
      submit,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
