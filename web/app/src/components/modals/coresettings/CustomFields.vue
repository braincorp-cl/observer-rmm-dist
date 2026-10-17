<template>
  <div>
    <div class="row">
      <div class="text-subtitle2">{{ $t("customFields.title") }}</div>
      <q-space />
      <q-btn
        size="sm"
        outline
        no-caps
        icon="fas fa-plus"
        :label="$t('customFields.addField')"
        @click="addCustomField"
      />
    </div>
    <q-separator />
    <div>
      <!-- 050 (T034, V2-S04): sin pestañas; el modelo se elige con un grupo
           segmentado, como el tipo de equipo de la flota. -->
      <q-btn-toggle
        v-model="tab"
        no-caps
        unelevated
        toggle-color="primary"
        class="obs-page__toggle q-my-sm"
        :options="[
          { value: 'client', label: $t('customFields.tabClients') },
          { value: 'site', label: $t('customFields.tabSites') },
          { value: 'agent', label: $t('customFields.tabAgents') },
        ]"
      />
      <div style="max-height: 50vh; overflow-y: auto">
        <CustomFieldsTable
          v-if="tab === 'client'"
          @refresh="getCustomFields"
          :data="clientFields"
        />
        <CustomFieldsTable
          v-else-if="tab === 'site'"
          @refresh="getCustomFields"
          :data="siteFields"
        />
        <CustomFieldsTable
          v-else
          @refresh="getCustomFields"
          :data="agentFields"
        />
      </div>
    </div>
  </div>
</template>

<script>
import CustomFieldsTable from "@/components/modals/coresettings/CustomFieldsTable.vue";
import CustomFieldsForm from "@/components/modals/coresettings/CustomFieldsForm.vue";

export default {
  name: "CustomFields",
  components: {
    CustomFieldsTable,
  },
  data() {
    return {
      tab: "client",
      customFields: [],
    };
  },
  computed: {
    agentFields() {
      return this.customFields.filter((field) => field.model === "agent");
    },
    siteFields() {
      return this.customFields.filter((field) => field.model === "site");
    },
    clientFields() {
      return this.customFields.filter((field) => field.model === "client");
    },
  },
  methods: {
    getCustomFields() {
      this.$q.loading.show();

      this.$axios
        .get("/core/customfields/")
        .then((r) => {
          this.$q.loading.hide();
          this.customFields = r.data;
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    addCustomField() {
      this.$q
        .dialog({
          component: CustomFieldsForm,
          componentProps: {
            model: this.tab,
          },
        })
        .onOk(() => {
          this.getCustomFields();
        });
    },
  },
  mounted() {
    this.getCustomFields();
  },
};
</script>
