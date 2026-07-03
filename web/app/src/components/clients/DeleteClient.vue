<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin">
      <q-bar>
        {{ $t("deleteClient.title", { name: object.name }) }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("deleteClient.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-form @submit="submit">
        <q-card-section v-if="siteOptions.length === 0">
          {{ $t("deleteClient.noValidSites") }}
        </q-card-section>
        <q-card-section v-if="siteOptions.length > 0">
          <observer-dropdown
            :label="$t('deleteClient.siteToMove')"
            outlined
            v-model="site"
            :options="siteOptions"
            mapOptions
            :rules="[(val) => !!val || $t('deleteClient.selectSite')]"
            :hint="$t('deleteClient.moveHint')"
            filterable
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            dense
            flat
            push
            :label="$t('deleteClient.cancel')"
            v-close-popup
          />
          <q-btn
            :loading="loading"
            :disable="siteOptions.length === 0"
            dense
            flat
            push
            :label="$t('deleteClient.move')"
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
import { useI18n } from "vue-i18n";
import { useQuasar, useDialogPluginComponent } from "quasar";
import { notifySuccess } from "@/utils/notify";
import { fetchClients, removeClient, removeSite } from "@/api/clients";
import { formatSiteOptions } from "@/utils/format";

// ui imports
import ObserverDropdown from "@/components/ui/ObserverDropdown.vue";

export default {
  name: "DeleteClient",
  emits: [...useDialogPluginComponent.emits],
  components: {
    ObserverDropdown,
  },
  props: {
    object: !Object,
    type: !String,
  },
  setup(props) {
    // setup quasar dialog
    const $q = useQuasar();
    const { t } = useI18n();
    const { dialogRef, onDialogOK, onDialogHide } = useDialogPluginComponent();

    // delete client logic
    const loading = ref(false);
    const site = ref(null);
    const siteOptions = ref([]);

    function submit() {
      $q.dialog({
        title: t("deleteClient.areYouSure"),
        message: t("deleteClient.deletingMsg", {
          type: props.type,
          name: props.object.name,
          count: props.object.agent_count,
        }),
        cancel: true,
        ok: { label: t("deleteClient.delete"), color: "negative" },
      }).onOk(async () => {
        loading.value = true;
        try {
          const result =
            props.type === "client"
              ? await removeClient(props.object.id, {
                  move_to_site: site.value,
                })
              : await removeSite(props.object.id, { move_to_site: site.value });
          notifySuccess(result);
          onDialogOK();
        } catch (e) {
          console.error(e);
        }
        loading.value = false;
      });
    }

    async function getSiteOptions() {
      $q.loading.show();
      const clients = await fetchClients();
      $q.loading.hide();

      if (props.type === "client") {
        // filter out client that is being deleted
        siteOptions.value = Object.freeze(
          formatSiteOptions(
            clients.filter((client) => client.id !== props.object.id),
          ),
        );
      } else {
        // filter out site that is being dleted
        clients.forEach(
          (client) =>
            (client.sites = client.sites.filter(
              (site) => site.id !== props.object.id,
            )),
        );
        siteOptions.value = Object.freeze(formatSiteOptions(clients));
      }
    }

    onMounted(getSiteOptions);

    return {
      site,
      loading,
      siteOptions,

      // methods
      submit,

      // quasar dialog
      dialogRef,
      onDialogHide,
      onDialogOK,
    };
  },
};
</script>
