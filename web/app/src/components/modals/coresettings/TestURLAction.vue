<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="width: 80vw">
      <q-bar>
        {{ $t("testUrlAction.title", { name: urlAction.name }) }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("testUrlAction.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section>
        <q-option-group
          v-model="runAgainst"
          :options="runAgainstOptions"
          inline
          dense
        />
      </q-card-section>

      <q-card-section v-if="runAgainst === 'agent'">
        <observer-dropdown
          v-model="agent"
          :options="agentOptions"
          :label="$t('testUrlAction.agents')"
          mapOptions
          filterable
          dense
          filled
        />
      </q-card-section>

      <q-card-section v-else-if="runAgainst === 'site'">
        <observer-dropdown
          v-model="site"
          :options="siteOptions"
          :label="$t('testUrlAction.sites')"
          mapOptions
          filterable
          dense
          filled
        />
      </q-card-section>

      <q-card-section v-else-if="runAgainst === 'client'">
        <observer-dropdown
          v-model="client"
          :options="clientOptions"
          :label="$t('testUrlAction.client')"
          mapOptions
          filterable
          dense
          filled
        />
      </q-card-section>

      <q-card-section style="height: 60vh" class="scroll">
        <div>
          {{ $t("testUrlAction.url") }}
          <code>{{ return_url }}</code>
        </div>
        <br />
        <div>
          {{ $t("testUrlAction.body") }}
          <q-separator />
          <code>{{ return_request }}</code>
        </div>
        <br />
        <div>
          {{ $t("testUrlAction.response") }}
          <q-separator />
          <code>{{ return_result }}</code>
        </div>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat :label="$t('testUrlAction.close')" v-close-popup />
        <q-btn
          :loading="loading"
          flat
          :label="$t('testUrlAction.run')"
          color="primary"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
// composition imports
import { ref, reactive, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import { useAgentDropdown } from "@/composables/agents";
import { useSiteDropdown, useClientDropdown } from "@/composables/clients";
import { runTestURLAction } from "@/api/core";
import { URLAction } from "@/types/core/urlactions";

// ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

// define emits
defineEmits([...useDialogPluginComponent.emits]);

// define props
const props = defineProps<{ urlAction: URLAction }>();

// setup quasar
const { dialogRef, onDialogHide } = useDialogPluginComponent();
const { t } = useI18n();

// setup dropdowns
const { agent, agentOptions } = useAgentDropdown({ onMount: true });
const { client, clientOptions } = useClientDropdown(true);
const { site, siteOptions } = useSiteDropdown(true);

const runAgainst = ref<"agent" | "site" | "client" | "none">("none");

const runAgainstOptions = computed(() => [
  { label: t("testUrlAction.optAgent"), value: "agent" },
  { label: t("testUrlAction.optSite"), value: "site" },
  { label: t("testUrlAction.optClient"), value: "client" },
  { label: t("testUrlAction.optNone"), value: "none" },
]);
const loading = ref(false);

const runAgainstID = computed(() => {
  if (runAgainst.value === "agent") return agent.value;
  else if (runAgainst.value === "site") return site.value;
  else if (runAgainst.value === "client") return client.value;
  else return 0;
});
const state = reactive({
  pattern: props.urlAction.pattern,
  rest_body: props.urlAction.rest_body,
  rest_headers: props.urlAction.rest_headers,
  rest_method: props.urlAction.rest_method,
  run_instance_type: runAgainst,
  run_instance_id: runAgainstID,
});

const return_url = ref("");
const return_result = ref("");
const return_request = ref("");

async function submit() {
  loading.value = true;

  try {
    const { url, result, body } = await runTestURLAction(state);

    return_result.value = result;
    return_url.value = url;
    return_request.value = body;
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}
</script>
