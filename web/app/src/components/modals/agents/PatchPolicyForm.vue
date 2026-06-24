<template>
  <div class="q-pa-md">
    <!-- Auto Approval -->
    <div class="text-subtitle2">{{ $t("patchPolicy.autoApproval") }}</div>
    <q-separator />
    <q-card-section class="row">
      <div class="col-3">{{ $t("patchPolicy.severity") }}</div>
      <div class="col-4"></div>
      <div class="col-5">{{ $t("patchPolicy.action") }}</div>
    </q-card-section>
    <q-card-section class="row">
      <div class="col-3">{{ $t("patchPolicy.critical") }}</div>
      <div class="col-4"></div>
      <q-select
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.critical"
        :options="severityOptions"
        emit-value
        map-options
      />
    </q-card-section>
    <q-card-section class="row">
      <div class="col-3">{{ $t("patchPolicy.important") }}</div>
      <div class="col-4"></div>
      <q-select
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.important"
        :options="severityOptions"
        emit-value
        map-options
      />
    </q-card-section>
    <q-card-section class="row">
      <div class="col-3">{{ $t("patchPolicy.moderate") }}</div>
      <div class="col-4"></div>
      <q-select
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.moderate"
        :options="severityOptions"
        emit-value
        map-options
      />
    </q-card-section>
    <q-card-section class="row">
      <div class="col-3">{{ $t("patchPolicy.low") }}</div>
      <div class="col-4"></div>
      <q-select
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.low"
        :options="severityOptions"
        emit-value
        map-options
      />
    </q-card-section>
    <q-card-section class="row">
      <div class="col-3">{{ $t("patchPolicy.other") }}</div>
      <div class="col-4"></div>
      <q-select
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.other"
        :options="severityOptions"
        emit-value
        map-options
      />
    </q-card-section>
    <!-- Installation Schedule -->
    <div class="text-subtitle2">
      {{ $t("patchPolicy.installationSchedule") }}
    </div>
    <q-separator />
    <q-card-section class="row">
      <div class="col-3">{{ $t("patchPolicy.scheduleFrequency") }}</div>
      <div class="col-4"></div>
      <q-select
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.run_time_frequency"
        :options="frequencyOptions"
        emit-value
        map-options
      />
    </q-card-section>
    <q-card-section
      class="row"
      v-if="winupdatepolicy.run_time_frequency === 'monthly'"
    >
      <div class="col-3">{{ $t("patchPolicy.dayOfMonth") }}</div>
      <div class="col-4"></div>
      <q-select
        v-show="winupdatepolicy.run_time_frequency !== 'inherit'"
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.run_time_day"
        :options="monthDays"
        emit-value
        map-options
      />
    </q-card-section>
    <q-card-section
      class="row"
      v-show="winupdatepolicy.run_time_frequency !== 'inherit'"
    >
      <div class="col-3">{{ $t("patchPolicy.scheduledTime") }}</div>
      <div class="col-4"></div>
      <q-select
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.run_time_hour"
        :options="timeOptions"
        emit-value
        map-options
      />
    </q-card-section>
    <q-card-section
      v-if="winupdatepolicy.run_time_frequency === 'daily'"
      v-show="winupdatepolicy.run_time_frequency !== 'inherit'"
    >
      <div class="q-gutter-sm">
        <q-checkbox
          v-model="winupdatepolicy.run_time_days"
          :val="0"
          :label="$t('patchPolicy.monday')"
        />
        <q-checkbox
          v-model="winupdatepolicy.run_time_days"
          :val="1"
          :label="$t('patchPolicy.tuesday')"
        />
        <q-checkbox
          v-model="winupdatepolicy.run_time_days"
          :val="2"
          :label="$t('patchPolicy.wednesday')"
        />
        <q-checkbox
          v-model="winupdatepolicy.run_time_days"
          :val="3"
          :label="$t('patchPolicy.thursday')"
        />
        <q-checkbox
          v-model="winupdatepolicy.run_time_days"
          :val="4"
          :label="$t('patchPolicy.friday')"
        />
        <q-checkbox
          v-model="winupdatepolicy.run_time_days"
          :val="5"
          :label="$t('patchPolicy.saturday')"
        />
        <q-checkbox
          v-model="winupdatepolicy.run_time_days"
          :val="6"
          :label="$t('patchPolicy.sunday')"
        />
      </div>
    </q-card-section>
    <!-- Reboot After Installation -->
    <div class="text-subtitle2">{{ $t("patchPolicy.rebootAfterInstall") }}</div>
    <q-separator />
    <q-card-section class="row">
      <div class="col-3"></div>
      <div class="col-4"></div>
      <q-select
        dense
        class="col-5"
        outlined
        v-model="winupdatepolicy.reboot_after_install"
        :options="rebootOptions"
        emit-value
        map-options
      />
    </q-card-section>
    <!-- Failed Patches -->
    <div class="text-subtitle2">{{ $t("patchPolicy.failedPatches") }}</div>
    <q-separator />
    <q-card-section class="row" v-if="!policy">
      <div class="col-5">
        <q-checkbox
          v-model="winupdatepolicy.reprocess_failed_inherit"
          :label="$t('patchPolicy.inheritFailedSettings')"
        />
      </div>
    </q-card-section>
    <q-card-section
      class="row"
      v-show="!winupdatepolicy.reprocess_failed_inherit"
    >
      <div class="col-5">
        <q-checkbox
          v-model="winupdatepolicy.reprocess_failed"
          :label="$t('patchPolicy.reprocessFailed')"
        />
      </div>

      <div class="col-3">
        <q-input
          dense
          v-model.number="winupdatepolicy.reprocess_failed_times"
          type="number"
          filled
          :label="$t('patchPolicy.times')"
          :rules="[(val) => val > 0 || $t('patchPolicy.ruleGreaterThanZero')]"
        />
      </div>
      <div class="col-3"></div>
      <q-checkbox
        v-model="winupdatepolicy.email_if_fail"
        :label="$t('patchPolicy.emailOnFail')"
      />
    </q-card-section>
    <q-card-actions align="left" v-if="policy">
      <q-btn
        :label="$t('patchPolicy.submit')"
        color="primary"
        @click="submit"
      />
      <q-btn :label="$t('patchPolicy.cancel')" @click="$emit('hide')" />
      <q-space />
      <q-btn
        v-if="editing"
        :label="$t('patchPolicy.removePolicy')"
        color="negative"
        @click="deletePolicy(winupdatepolicy)"
      />
    </q-card-actions>
  </div>
</template>

<script>
import { scheduledTimes, monthDays } from "@/mixins/data";
import mixins from "@/mixins/mixins";

export default {
  name: "PatchPolicyForm",
  emits: ["close", "hide"],
  props: {
    policy: Object,
    agent: Object,
  },
  mixins: [mixins],
  data() {
    return {
      editing: true,
      winupdatepolicy: {},
      // Solo en contexto de agente se ofrece "Inherit" (heredar del global).
      showInherit: false,
      defaultWinUpdatePolicy: {
        critical: "ignore",
        important: "ignore",
        moderate: "ignore",
        low: "ignore",
        other: "ignore",
        run_time_hour: 3,
        run_time_frequency: "daily",
        run_time_days: [],
        run_time_day: 1,
        reboot_after_install: "never",
        reprocess_failed_inherit: false,
        reprocess_failed: false,
        reprocess_failed_times: 5,
        email_if_fail: false,
      },
      timeOptions: scheduledTimes,
      monthDays,
    };
  },
  computed: {
    // Las option arrays son computed (no data) para que las etiquetas traducidas
    // reaccionen al cambio de idioma en vivo (vue-i18n no es reactivo dentro de data()).
    severityOptions() {
      const opts = [
        { label: this.$t("patchPolicy.sevManual"), value: "manual" },
        { label: this.$t("patchPolicy.sevApprove"), value: "approve" },
        { label: this.$t("patchPolicy.sevIgnore"), value: "ignore" },
      ];
      if (this.showInherit)
        opts.push({ label: this.$t("patchPolicy.inherit"), value: "inherit" });
      return opts;
    },
    frequencyOptions() {
      const opts = [
        { label: this.$t("patchPolicy.freqDailyWeekly"), value: "daily" },
        { label: this.$t("patchPolicy.freqMonthly"), value: "monthly" },
      ];
      if (this.showInherit)
        opts.push({ label: this.$t("patchPolicy.inherit"), value: "inherit" });
      return opts;
    },
    rebootOptions() {
      const opts = [
        { label: this.$t("patchPolicy.rebootNever"), value: "never" },
        { label: this.$t("patchPolicy.rebootRequired"), value: "required" },
        { label: this.$t("patchPolicy.rebootAlways"), value: "always" },
      ];
      if (this.showInherit)
        opts.push({ label: this.$t("patchPolicy.inherit"), value: "inherit" });
      return opts;
    },
  },
  methods: {
    submit() {
      this.$q.loading.show();

      // modifying patch policy in automation manager
      if (this.policy) {
        // editing patch policy
        if (this.editing) {
          this.$axios
            .put(
              `/automation/patchpolicy/${this.winupdatepolicy.id}/`,
              this.winupdatepolicy,
            )
            .then(() => {
              this.$q.loading.hide();
              this.$emit("close");
              this.notifySuccess(this.$t("patchPolicy.editedSuccess"));
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        } else {
          // adding patch policy
          this.$axios
            .post("/automation/patchpolicy/", this.winupdatepolicy)
            .then(() => {
              this.$q.loading.hide();
              this.$emit("close");
              this.notifySuccess(this.$t("patchPolicy.createdSuccess"));
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        }
      }
    },
    deletePolicy(policy) {
      this.$q
        .dialog({
          title: this.$t("patchPolicy.deleteTitle"),
          cancel: true,
          ok: { label: this.$t("patchPolicy.delete"), color: "negative" },
        })
        .onOk(() => {
          this.$q.loading.show();
          this.$axios
            .delete(`/automation/patchpolicy/${policy.id}/`)
            .then(() => {
              this.$q.loading.hide();
              this.$emit("close");
              this.notifySuccess(this.$t("patchPolicy.deletedSuccess"));
            })
            .catch(() => {
              this.$q.loading.hide();
            });
        });
    },
  },
  mounted() {
    if (this.policy && this.policy.winupdatepolicy[0]) {
      this.winupdatepolicy = this.policy.winupdatepolicy[0];
      this.editing = true;
    } else if (this.policy) {
      this.winupdatepolicy = this.defaultWinUpdatePolicy;
      this.winupdatepolicy.policy = this.policy.id;
      this.editing = false;
    } else if (this.agent) {
      this.winupdatepolicy = this.agent.winupdatepolicy[0];

      // add agent inherit options (las option arrays computed lo agregan)
      this.showInherit = true;
    }
  },
};
</script>
