<template>
  <q-dialog ref="dialog" @hide="onHide">
    <q-card class="q-dialog-plugin" style="width: 60vw">
      <q-bar>
        {{ title }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip class="bg-white text-primary">{{
            $t("policyModalsCommon.close")
          }}</q-tooltip>
        </q-btn>
      </q-bar>
      <q-form @submit="submit">
        <q-card-section v-if="copyPolicy">
          <i18n-t
            keypath="policyForm.copyIntro"
            scope="global"
            tag="div"
            class="text-subtitle1"
          >
            <template #name
              ><b>{{ copyPolicy.name }}</b></template
            >
          </i18n-t>
        </q-card-section>
        <q-card-section class="row">
          <div class="col-2">{{ $t("policyForm.name") }}</div>
          <div class="col-10">
            <q-input
              outlined
              dense
              v-model="localPolicy.name"
              :rules="[(val) => !!val || $t('policyForm.required')]"
            />
          </div>
        </q-card-section>
        <q-card-section class="row">
          <div class="col-2">{{ $t("policyForm.description") }}</div>
          <div class="col-10">
            <q-input outlined dense v-model="localPolicy.desc" />
          </div>
        </q-card-section>
        <q-card-section class="row">
          <div class="col-2">{{ $t("policyForm.active") }}</div>
          <div class="col-10">
            <q-toggle v-model="localPolicy.active" color="green" />
          </div>
        </q-card-section>
        <q-card-section class="row">
          <div class="col-2">{{ $t("policyForm.enforced") }}</div>
          <div class="col-10">
            <q-toggle v-model="localPolicy.enforced" color="green" />
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            dense
            flat
            :label="$t('policyModalsCommon.cancel')"
            v-close-popup
          />
          <q-btn
            flat
            :label="$t('policyModalsCommon.submit')"
            color="primary"
            type="submit"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script>
import mixins from "@/mixins/mixins";

export default {
  name: "PolicyForm",
  emits: ["hide", "ok", "cancel"],
  mixins: [mixins],
  props: { policy: Object, copyPolicy: Object },
  data() {
    return {
      localPolicy: {
        name: "",
        desc: "",
        enforced: false,
        active: false,
      },
    };
  },
  computed: {
    title() {
      return this.editing
        ? this.$t("policyForm.titleEdit")
        : this.$t("policyForm.titleAdd");
    },
    editing() {
      return !!this.policy;
    },
  },
  methods: {
    submit() {
      this.$q.loading.show();

      let data = {
        ...this.localPolicy,
      };

      if (this.editing) {
        this.$axios
          .put(`/automation/policies/${data.id}/`, data)
          .then(() => {
            this.$q.loading.hide();
            this.onOk();
            this.notifySuccess(this.$t("policyForm.notifyEdited"));
          })
          .catch(() => {
            this.$q.loading.hide();
          });
      } else {
        if (this.copyPolicy) {
          data.copyId = this.copyPolicy.id;
        }

        this.$axios
          .post("/automation/policies/", data)
          .then(() => {
            this.$q.loading.hide();
            this.onOk();
            this.notifySuccess(this.$t("policyForm.notifyAdded"));
          })
          .catch(() => {
            this.$q.loading.hide();
          });
      }
    },
    show() {
      this.$refs.dialog.show();
    },
    hide() {
      this.$refs.dialog.hide();
    },
    onHide() {
      this.$emit("hide");
    },
    onOk() {
      this.$emit("ok");
      this.hide();
    },
  },
  mounted() {
    // If pk prop is set that means we are editting
    if (this.policy) {
      this.localPolicy.id = this.policy.id;
      this.localPolicy.name = this.policy.name;
      this.localPolicy.desc = this.policy.desc;
      this.localPolicy.enforced = this.policy.enforced;
      this.localPolicy.active = this.policy.active;
    }
  },
};
</script>
