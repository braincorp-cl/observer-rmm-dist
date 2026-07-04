<template>
  <div>
    <div class="row">
      <div class="text-subtitle2">{{ $t("scheduleTable.title") }}</div>
      <q-space />
      <q-btn
        size="sm"
        color="grey-5"
        icon="fas fa-plus"
        text-color="black"
        :label="$t('scheduleTable.addSchedule')"
        @click="openAddScheduleForm"
      />
    </div>
    <q-separator />

    <observer-table
      :rows="schedules"
      :columns="columns"
      row-key="id"
      binary-state-sort
      virtual-scroll
      :rows-per-page-options="[0]"
      :loading="isLoading"
      column-select
      dense
      storage-key="schedule-table"
    >
      <template #body="{ row, cols }">
        <q-tr class="cursor-pointer" @dblclick="openEditScheduleForm(row)">
          <q-menu context-menu>
            <q-list dense style="min-width: 200px">
              <q-item
                clickable
                v-close-popup
                @click="openEditScheduleForm(row)"
              >
                <q-item-section>
                  <q-item-label>{{ $t("scheduleCommon.edit") }}</q-item-label>
                </q-item-section>
              </q-item>

              <q-item clickable v-close-popup @click="removeSchedule(row)">
                <q-item-section>
                  <q-item-label>{{ $t("scheduleCommon.delete") }}</q-item-label>
                </q-item-section>
              </q-item>

              <q-separator />

              <q-item clickable v-close-popup>
                <q-item-section>
                  <q-item-label>{{ $t("scheduleCommon.close") }}</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-menu>

          <q-td v-for="col in cols" :key="col.id">
            {{ col.value }}
          </q-td>
        </q-tr>
      </template>
    </observer-table>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, computed } from "vue";
import { QTableColumn, useQuasar } from "quasar";
import { useI18n } from "vue-i18n";
import { useScheduleShared } from "../api";
import type { Schedule } from "../types";

// ui imports
import ScheduleForm from "./ScheduleForm.vue";
import ObserverTable from "src/core/dashboard/ui/ObserverTable.vue";
import { until } from "@vueuse/shared";

const { t } = useI18n();

const columns = computed<QTableColumn[]>(() => {
  const monthsAbbrev = [
    t("scheduleTable.monthAbbrJan"),
    t("scheduleTable.monthAbbrFeb"),
    t("scheduleTable.monthAbbrMar"),
    t("scheduleTable.monthAbbrApr"),
    t("scheduleTable.monthAbbrMay"),
    t("scheduleTable.monthAbbrJun"),
    t("scheduleTable.monthAbbrJul"),
    t("scheduleTable.monthAbbrAug"),
    t("scheduleTable.monthAbbrSep"),
    t("scheduleTable.monthAbbrOct"),
    t("scheduleTable.monthAbbrNov"),
    t("scheduleTable.monthAbbrDec"),
  ];

  const weekDaysAbbrev = [
    t("scheduleTable.weekdayAbbrSun"),
    t("scheduleTable.weekdayAbbrMon"),
    t("scheduleTable.weekdayAbbrTue"),
    t("scheduleTable.weekdayAbbrWed"),
    t("scheduleTable.weekdayAbbrThu"),
    t("scheduleTable.weekdayAbbrFri"),
    t("scheduleTable.weekdayAbbrSat"),
  ];

  const scheduleTypeLabels: Record<string, string> = {
    daily: t("scheduleCommon.daily"),
    weekly: t("scheduleCommon.weekly"),
    monthly: t("scheduleCommon.monthly"),
  };

  const weekOrdinals: Record<number, string> = {
    1: t("scheduleTable.ordFirst"),
    2: t("scheduleTable.ordSecond"),
    3: t("scheduleTable.ordThird"),
    4: t("scheduleTable.ordFourth"),
    5: t("scheduleTable.ordLast"),
  };

  return [
    {
      name: "name",
      label: t("scheduleCommon.name"),
      align: "left",
      field: "name",
      sortable: true,
      required: true,
    },
    {
      name: "schedule_type",
      label: t("scheduleTable.colScheduleType"),
      align: "left",
      field: "schedule_type",
      sortable: true,
      format: (val: string) => scheduleTypeLabels[val] ?? val,
    },
    {
      name: "run_time",
      label: t("scheduleTable.colRunTime"),
      align: "left",
      field: "run_time",
      sortable: true,
      format: (val: string) => {
        const parts = val.split(":");
        return `${parts[0]}:${parts[1]}`;
      },
    },
    {
      name: "run_time_weekdays",
      label: t("scheduleTable.colWeekdays"),
      align: "left",
      field: "run_time_weekdays",
      format: (val: number[]) => {
        if (val.length === 7) return t("scheduleTable.everyWeekday");
        else return val.map((weekday) => weekDaysAbbrev[weekday]).join(", ");
      },
    },
    {
      name: "monthly_months_of_year",
      label: t("scheduleTable.colMonths"),
      align: "left",
      field: "monthly_months_of_year",
      format: (val: number[]) => {
        if (val.length === 12) return t("scheduleTable.everyMonth");
        else {
          return val.map((month) => monthsAbbrev[month - 1]).join(", ");
        }
      },
    },
    {
      name: "monthly_days_of_month",
      label: t("scheduleTable.colDaysOfMonth"),
      align: "left",
      field: "monthly_days_of_month",
      format: (val: number[]) => {
        if (val.length >= 31) return t("scheduleTable.everyDay");
        else
          return val
            .map((day) => (day !== 32 ? day : t("scheduleTable.ordLast")))
            .join(", ");
      },
    },
    {
      name: "monthly_weeks_of_month",
      label: t("scheduleTable.colWeeksOfMonth"),
      align: "left",
      field: "monthly_weeks_of_month",
      format: (val: number[]) => {
        if (val.length === 5) return t("scheduleTable.everyWeek");
        return val.map((week) => weekOrdinals[week]).join(", ");
      },
    },
  ];
});

const $q = useQuasar();

const { schedules, getSchedules, deleteSchedule, isLoading, isError } =
  useScheduleShared;

function openEditScheduleForm(schedule: Schedule) {
  $q.dialog({
    component: ScheduleForm,
    componentProps: {
      schedule,
    },
  });
}

function openAddScheduleForm() {
  $q.dialog({
    component: ScheduleForm,
  });
}

function removeSchedule(schedule: Schedule) {
  $q.dialog({
    color: "primary",
    message: t("scheduleTable.deleteConfirm", { name: schedule.name }),
    ok: {
      color: "negative",
    },
    cancel: true,
  }).onOk(async () => {
    deleteSchedule(schedule.id);
    await until(isLoading).not.toBeTruthy();
    if (isError.value) return;
  });
}

onMounted(getSchedules);
</script>
