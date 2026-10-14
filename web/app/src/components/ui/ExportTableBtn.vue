<template>
  <q-btn
    dense
    color="primary"
    icon-right="archive"
    :label="label"
    :aria-label="label || $t('exportTableBtn.tooltip')"
    @click="exportTable"
  >
    <q-tooltip>{{ $t("exportTableBtn.tooltip") }}</q-tooltip>
  </q-btn>
</template>

<script>
import { exportTableToCSV } from "@/utils/csv";

export default {
  name: "export-table-btn",
  props: {
    columns: !Array,
    data: !Array,
    // Texto visible opcional; sin él queda solo el ícono (como en v1).
    label: { type: String, default: undefined },
  },
  setup(props) {
    return {
      exportTable: () => exportTableToCSV(props.data, props.columns),
    };
  },
};
</script>
