<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide" persistent>
    <q-card class="q-dialog-plugin" style="width: 90vw; max-width: 600px">
      <q-bar>
        {{ title }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup />
      </q-bar>

      <q-form @submit.prevent="submit">
        <q-card-section>
          <!-- start time input -->
          <q-input
            v-model="localSchedule.name"
            class="q-pa-sm"
            dense
            :label="$t('scheduleCommon.name')"
            filled
            :rules="[(val) => !!val || $t('scheduleCommon.required')]"
          />
        </q-card-section>

        <q-card-section>
          <q-option-group
            v-model="localSchedule.schedule_type"
            class="q-pa-sm"
            :label="$t('scheduleForm.taskRunType')"
            :options="taskTypeOptions"
            dense
            inline
          />
        </q-card-section>

        <q-card-section>
          <!-- start time input -->
          <q-input
            class="q-pa-sm"
            type="time"
            dense
            :label="$t('scheduleForm.hourMinute')"
            stack-label
            filled
            v-model="localSchedule.run_time"
            :rules="[(val) => !!val || $t('scheduleCommon.required')]"
          />
        </q-card-section>

        <!-- weekly options -->
        <q-card-section v-if="localSchedule.schedule_type === 'weekly'">
          <!-- day of week input -->
          {{ $t("scheduleForm.runOnDaysHeader") }}
          <span v-if="dayOfWeekValidationError" class="text-negative">{{
            $t("scheduleCommon.required")
          }}</span>
          <q-option-group
            inline
            dense
            :options="dayOfWeekOptions"
            type="checkbox"
            v-model="localSchedule.run_time_weekdays"
          />
        </q-card-section>

        <!-- monthly options -->
        <q-card-section
          v-if="localSchedule.schedule_type === 'monthly'"
          class="row"
        >
          <!-- type of monthly schedule -->
          <q-option-group
            class="col-12 q-pa-sm"
            v-model="localSchedule.monthly_type"
            inline
            :options="monthlyTypeOptions"
          />

          <!-- month select input -->
          <q-select
            :rules="[(val) => val.length > 0 || $t('scheduleCommon.required')]"
            class="col-4 q-pa-sm"
            filled
            dense
            options-dense
            v-model="localSchedule.monthly_months_of_year"
            :options="monthOptions"
            :label="$t('scheduleForm.runOnMonths')"
            multiple
            emit-value
            map-options
          >
            <template v-slot:before-options>
              <q-item>
                <q-item-section>
                  <q-item-label>{{
                    $t("scheduleForm.allMonths")
                  }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-checkbox
                    dense
                    v-model="allMonthsCheckbox"
                    @update:model-value="toggleMonths"
                  />
                </q-item-section>
              </q-item>
            </template>

            <template
              v-slot:option="{ itemProps, opt, selected, toggleOption }"
            >
              <q-item v-bind="itemProps">
                <q-item-section>
                  <q-item-label v-html="opt.label" />
                </q-item-section>
                <q-item-section side>
                  <q-checkbox
                    dense
                    :model-value="selected"
                    @update:model-value="
                      toggleOption(opt);
                      allMonthsCheckbox = false;
                    "
                  />
                </q-item-section>
              </q-item>
            </template>
          </q-select>

          <!-- days of month select input -->
          <q-select
            v-if="localSchedule.monthly_type === 'days'"
            :rules="[(val) => val.length > 0 || $t('scheduleCommon.required')]"
            class="col-4 q-pa-sm"
            filled
            dense
            options-dense
            v-model="localSchedule.monthly_days_of_month"
            :options="dayOfMonthOptions"
            :label="$t('scheduleForm.runOnDaysOfMonth')"
            multiple
            emit-value
            map-options
          >
            <template v-slot:before-options>
              <q-item>
                <q-item-section>
                  <q-item-label>{{ $t("scheduleForm.allDays") }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-checkbox
                    dense
                    v-model="allMonthDaysCheckbox"
                    @update:model-value="toggleMonthDays"
                  />
                </q-item-section>
              </q-item>
            </template>

            <template
              v-slot:option="{ itemProps, opt, selected, toggleOption }"
            >
              <q-item v-bind="itemProps">
                <q-item-section>
                  <q-item-label v-html="opt.label" />
                </q-item-section>
                <q-item-section side>
                  <q-checkbox
                    dense
                    :model-value="selected"
                    @update:model-value="
                      toggleOption(opt);
                      allMonthDaysCheckbox = false;
                    "
                  />
                </q-item-section>
              </q-item>
            </template>
          </q-select>

          <div v-if="localSchedule.monthly_type === 'days'" class="col-4"></div>

          <!-- week of month select input -->
          <q-select
            v-if="localSchedule.monthly_type === 'weeks'"
            :rules="[(val) => val.length > 0 || $t('scheduleCommon.required')]"
            class="col-4 q-pa-sm"
            filled
            dense
            options-dense
            v-model="localSchedule.monthly_weeks_of_month"
            :options="weekOptions"
            :label="$t('scheduleForm.runOnWeeks')"
            multiple
            emit-value
            map-options
          >
            <template
              v-slot:option="{ itemProps, opt, selected, toggleOption }"
            >
              <q-item v-bind="itemProps">
                <q-item-section>
                  <q-item-label v-html="opt.label" />
                </q-item-section>
                <q-item-section side>
                  <q-checkbox
                    dense
                    :model-value="selected"
                    @update:model-value="toggleOption(opt)"
                  />
                </q-item-section>
              </q-item>
            </template>
          </q-select>

          <!-- day of week select input -->
          <q-select
            v-if="localSchedule.monthly_type === 'weeks'"
            :rules="[(val) => val.length > 0 || $t('scheduleCommon.required')]"
            class="col-4 q-pa-sm"
            filled
            dense
            options-dense
            v-model="localSchedule.run_time_weekdays"
            :options="dayOfWeekOptions"
            :label="$t('scheduleForm.runOnWeekdays')"
            multiple
            emit-value
            map-options
          >
            <template v-slot:before-options>
              <q-item>
                <q-item-section>
                  <q-item-label>{{ $t("scheduleForm.allDays") }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-checkbox
                    dense
                    v-model="allWeekDaysCheckbox"
                    @update:model-value="toggleWeekDays"
                  />
                </q-item-section>
              </q-item>
            </template>

            <template
              v-slot:option="{ itemProps, opt, selected, toggleOption }"
            >
              <q-item v-bind="itemProps">
                <q-item-section>
                  <q-item-label v-html="opt.label" />
                </q-item-section>
                <q-item-section side>
                  <q-checkbox
                    dense
                    :model-value="selected"
                    @update:model-value="
                      toggleOption(opt);
                      allWeekDaysCheckbox = false;
                    "
                  />
                </q-item-section>
              </q-item>
            </template>
          </q-select>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn
            dense
            flat
            :label="$t('scheduleCommon.cancel')"
            v-close-popup
          />
          <q-btn
            :loading="isLoading"
            dense
            flat
            :label="$t('scheduleCommon.save')"
            color="primary"
            type="submit"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { until } from "@vueuse/shared";
import { useDialogPluginComponent, date } from "quasar";

import { useScheduleShared } from "../api";

import type { Schedule } from "../types";

const { t } = useI18n();

// static data (translated via computed so labels react to language change)
const taskTypeOptions = computed(() => [
  { label: t("scheduleCommon.daily"), value: "daily" },
  { label: t("scheduleCommon.weekly"), value: "weekly" },
  { label: t("scheduleCommon.monthly"), value: "monthly" },
]);

const monthlyTypeOptions = computed(() => [
  { label: t("scheduleForm.monthlyByDays"), value: "days" },
  { label: t("scheduleForm.monthlyByWeeks"), value: "weeks" },
]);

const dayOfWeekOptions = computed(() => [
  { label: t("scheduleForm.weekdayMonday"), value: 0 },
  { label: t("scheduleForm.weekdayTuesday"), value: 1 },
  { label: t("scheduleForm.weekdayWednesday"), value: 2 },
  { label: t("scheduleForm.weekdayThursday"), value: 3 },
  { label: t("scheduleForm.weekdayFriday"), value: 4 },
  { label: t("scheduleForm.weekdaySaturday"), value: 5 },
  { label: t("scheduleForm.weekdaySunday"), value: 6 },
]);

const dayOfMonthOptions = computed(() => {
  let result = [];
  let day = 1;
  for (let i = 1; i <= 31; i++) {
    result.push({ label: `${i}`, value: day });
    day = day + 1;
  }
  result.push({ label: t("scheduleForm.lastDay"), value: 32 });
  return result;
});

const monthOptions = computed(() => [
  { label: t("scheduleForm.monthJanuary"), value: 1 },
  { label: t("scheduleForm.monthFebruary"), value: 2 },
  { label: t("scheduleForm.monthMarch"), value: 3 },
  { label: t("scheduleForm.monthApril"), value: 4 },
  { label: t("scheduleForm.monthMay"), value: 5 },
  { label: t("scheduleForm.monthJune"), value: 6 },
  { label: t("scheduleForm.monthJuly"), value: 7 },
  { label: t("scheduleForm.monthAugust"), value: 8 },
  { label: t("scheduleForm.monthSeptember"), value: 9 },
  { label: t("scheduleForm.monthOctober"), value: 10 },
  { label: t("scheduleForm.monthNovember"), value: 11 },
  { label: t("scheduleForm.monthDecember"), value: 12 },
]);

const weekOptions = computed(() => [
  { label: t("scheduleForm.weekFirst"), value: 1 },
  { label: t("scheduleForm.weekSecond"), value: 2 },
  { label: t("scheduleForm.weekThird"), value: 3 },
  { label: t("scheduleForm.weekFourth"), value: 4 },
  { label: t("scheduleForm.weekLast"), value: 5 },
]);

const props = defineProps<{
  schedule?: Schedule;
}>();

const title = computed(() =>
  props.schedule ? t("scheduleForm.titleEdit") : t("scheduleForm.titleAdd"),
);

const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();
defineEmits([...useDialogPluginComponent.emits]);

const { addSchedule, editSchedule, isLoading, isError } = useScheduleShared;

const localSchedule = reactive<Schedule>(
  props.schedule
    ? Object.assign({}, props.schedule)
    : {
        id: 0,
        name: "",
        run_time: date.formatDate(Date.now(), "HH:mm"),
        run_time_weekdays: [] as number[],
        monthly_months_of_year: [] as number[],
        monthly_days_of_month: [] as number[],
        monthly_weeks_of_month: [] as number[],
        schedule_type: "daily",
        monthly_type: "days",
      },
);

// if all months is selected or cleared it will either clear the monthly_months_of_year array or add all options to it.
const allMonthsCheckbox = ref(false);
function toggleMonths() {
  localSchedule.monthly_months_of_year = allMonthsCheckbox.value
    ? monthOptions.value.map((month) => month.value)
    : [];
}

const allMonthDaysCheckbox = ref(false);
function toggleMonthDays() {
  localSchedule.monthly_days_of_month = allMonthDaysCheckbox.value
    ? dayOfMonthOptions.value.map((day) => day.value)
    : [];
}

const allWeekDaysCheckbox = ref(false);
function toggleWeekDays() {
  localSchedule.run_time_weekdays = allWeekDaysCheckbox.value
    ? dayOfWeekOptions.value.map((day) => day.value)
    : [];
}

const dayOfWeekValidationError = ref(false);
watch(
  () => localSchedule.run_time_weekdays,
  () => {
    dayOfWeekValidationError.value = false;
  },
);
async function submit() {
  // manually validate option-group since it doesn't have builtin rules
  if (
    localSchedule.schedule_type == "weekly" &&
    localSchedule.run_time_weekdays.length === 0
  ) {
    dayOfWeekValidationError.value = true;
    return;
  }

  props.schedule
    ? editSchedule(props.schedule.id, localSchedule)
    : addSchedule(localSchedule);

  await until(isLoading).not.toBeTruthy();
  if (isError.value) return;

  onDialogOK();
}

watch(
  () => localSchedule.schedule_type,
  () => {
    localSchedule.run_time_weekdays = [];
    localSchedule.monthly_months_of_year = [];
    localSchedule.monthly_days_of_month = [];
    localSchedule.monthly_weeks_of_month = [];
  },
);
</script>
