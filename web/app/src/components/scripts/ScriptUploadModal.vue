<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="width: 40vw">
      <q-bar>
        {{ $t("scriptUpload.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("scriptsCommon.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-form id="scriptUploadForm" @submit="submitForm">
        <q-card-section>
          <q-input
            :label="$t('scriptsCommon.name')"
            outlined
            dense
            v-model="script.name"
            :rules="[(val) => !!val || $t('scriptsCommon.required')]"
          />
        </q-card-section>

        <q-card-section>
          <q-input
            :label="$t('scriptsCommon.description')"
            outlined
            dense
            v-model="script.description"
          />
        </q-card-section>

        <q-card-section>
          <observer-dropdown
            v-model="script.category"
            :options="categories"
            :label="$t('scriptsCommon.category')"
            :hint="$t('scriptUpload.categoryHint')"
            outlined
            filterable
            clearable
            new-value-mode="add-unique"
          />
        </q-card-section>

        <q-card-section>
          <q-file
            :label="$t('scriptUpload.scriptUploadLabel')"
            v-model="file"
            filled
            dense
            counter
          >
            <template v-slot:prepend>
              <q-icon name="attach_file" />
            </template>
          </q-file>
        </q-card-section>

        <q-card-section>
          <observer-dropdown
            v-model="script.shell"
            :options="shellOptions"
            :label="$t('scriptUpload.type')"
            outlined
            mapOptions
          />
        </q-card-section>

        <q-card-section>
          <observer-dropdown
            v-model="script.supported_platforms"
            :options="agentPlatformOptions"
            :label="$t('scriptsCommon.supportedPlatforms')"
            clearable
            mapOptions
            filled
            multiple
          />
        </q-card-section>

        <q-card-section>
          <observer-dropdown
            v-model="script.args"
            :label="$t('scriptsCommon.scriptArguments')"
            :placeholder="$t('scriptUpload.argsPlaceholder')"
            filled
            use-input
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add"
          />
        </q-card-section>

        <q-card-section>
          <observer-dropdown
            v-model="script.env_vars"
            :label="$t('scriptsCommon.environmentVariables')"
            :placeholder="$t('scriptUpload.envVarsPlaceholder')"
            filled
            use-input
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add"
          />
        </q-card-section>

        <q-card-section>
          <q-input
            :label="$t('scriptUpload.defaultTimeout')"
            type="number"
            outlined
            dense
            v-model.number="script.default_timeout"
            :rules="[(val) => val >= 5 || $t('scriptsCommon.minTimeout')]"
          />
        </q-card-section>

        <q-card-actions>
          <q-space />
          <q-btn dense flat :label="$t('scriptsCommon.cancel')" v-close-popup />
          <q-btn
            :loading="loading"
            dense
            flat
            :label="$t('scriptsCommon.add')"
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
import { ref, watch } from "vue";
import { useDialogPluginComponent } from "quasar";
import { saveScript } from "@/api/scripts";
import { agentPlatformOptions } from "@/composables/agents";
import { notifySuccess } from "@/utils/notify";

// ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

// static data
import { shellOptions } from "@/composables/scripts";
export default {
  components: { ObserverDropdown },
  name: "ScriptModal",
  emits: [...useDialogPluginComponent.emits],
  props: {
    categories: !Array,
  },
  setup() {
    // setup quasar plugins
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();

    // script upload logic
    const script = ref({});
    const file = ref(null);
    const loading = ref(false);

    watch(file, (newValue) => {
      if (newValue) {
        // base64 encode the script and delete file
        const reader = new FileReader();
        reader.onloadend = () => {
          script.value.script_body = reader.result;
        };

        reader.readAsText(file.value);
      } else {
        script.value.script_body = "";
      }
    });

    async function submitForm() {
      loading.value = true;
      let result = "";
      try {
        result = await saveScript(script.value);
        onDialogOK();
        notifySuccess(result);
      } catch (e) {
        console.error(e);
      }

      loading.value = false;
    }

    return {
      // reactive data
      script,
      file,
      loading,

      // non-reactive data
      shellOptions,
      agentPlatformOptions,

      // methods
      submitForm,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
