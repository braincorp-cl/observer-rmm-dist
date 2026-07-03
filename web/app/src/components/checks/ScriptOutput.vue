<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="min-width: 70vw">
      <q-bar>
        {{ $t("scriptOutput.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("scriptOutput.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-card-section style="height: 70vh" class="scroll">
        <div>
          {{ $t("scriptOutput.lastRun") }}
          <code>{{ formatDate(scriptInfo.last_run) }}</code>
          <br />{{ $t("scriptOutput.runTime") }}
          <code>{{
            $t("scriptOutput.secondsValue", { n: scriptInfo.execution_time })
          }}</code>
          <br />{{ $t("scriptOutput.returnCode") }}
          <code>{{ scriptInfo.retcode }}</code>
          <br />
        </div>
        <br />
        <div v-if="scriptInfo.stdout">
          <script-output-copy-clip
            :label="$t('scriptOutput.standardOutput')"
            :data="scriptInfo.stdout"
          />
          <q-separator />
          <pre>{{ scriptInfo.stdout }}</pre>
        </div>
        <div v-if="scriptInfo.stderr">
          <script-output-copy-clip
            :label="$t('scriptOutput.standardError')"
            :data="scriptInfo.stderr"
          />
          <q-separator />
          <pre>{{ scriptInfo.stderr }}</pre>
        </div>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn
          flat
          dense
          push
          :label="$t('scriptOutput.cancel')"
          v-close-popup
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
// composition imports
import { computed } from "vue";
import { useStore } from "vuex";
import { useDialogPluginComponent } from "quasar";

import ScriptOutputCopyClip from "@/components/scripts/ScriptOutputCopyClip.vue";

export default {
  name: "ScriptOutput",
  components: {
    ScriptOutputCopyClip,
  },
  emits: [...useDialogPluginComponent.emits],
  props: { scriptInfo: !Object },
  setup() {
    // setup vuex
    const store = useStore();
    const formatDate = computed(() => store.getters.formatDate);

    // quasar dialog setup
    const { dialogRef, onDialogHide } = useDialogPluginComponent();

    return {
      // methods
      formatDate,

      // quasar dialog
      dialogRef,
      onDialogHide,
    };
  },
};
</script>
