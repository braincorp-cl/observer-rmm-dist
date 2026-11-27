<template>
  <q-dialog ref="dialog" @hide="onHide">
    <q-card
      class="q-dialog-plugin obs-check-graph"
      :class="{ 'obs-check-graph--pct': isPercentCheck }"
      style="min-width: 80vw; min-height: 65vh; overflow-x: hidden"
    >
      <q-bar>
        <q-btn
          @click="getChartData"
          class="q-mr-sm"
          dense
          flat
          push
          icon="refresh"
        />
        {{ title }}
        <q-space />
        <!-- 050 (V2-G15): la barra propia de ApexCharts (div sin tabindex) se
             apaga; la descarga, que era su única acción sin otro control,
             pasa a un q-btn alcanzable con el tabulador. -->
        <q-btn
          v-if="showChart"
          dense
          flat
          icon="download"
          :aria-label="$t('checkGraph.downloadPng')"
          @click="downloadPng"
        >
          <q-tooltip>{{ $t("checkGraph.downloadPng") }}</q-tooltip>
        </q-btn>
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip>{{ $t("checkGraph.close") }}</q-tooltip>
        </q-btn>
      </q-bar>
      <div class="row">
        <span v-if="!showChart" class="q-pa-md">{{
          $t("checkGraph.noData")
        }}</span>
        <q-space />
        <q-select
          v-model="timeFilter"
          emit-value
          map-options
          style="width: 200px"
          :options="timeFilterOptions"
          outlined
          dense
          class="q-pr-md q-pt-md"
          @update:model-value="getChartData"
        />
      </div>
      <apexchart
        ref="chart"
        v-if="showChart"
        class="q-pt-md"
        type="line"
        height="70%"
        :options="chartOptions"
        :series="[{ name: seriesName, data: history }]"
      />
    </q-card>
  </q-dialog>
</template>
<script>
import VueApexCharts from "vue3-apexcharts";
import { getCssVar } from "quasar";

// 046 (UI-D02): los colores del gráfico salen de los tokens del tema y no de
// hex literales (el azul previo al rebranding y el rojo/ámbar de Quasar no
// seguían al tema). Mismo patrón que AgentLocationDialog/LostCaseTimelineDialog.
function obsToken(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim();
}

// 050 (V2-G01): el formatter del tooltip concatena HTML; los valores crudos
// del agente se escapan antes de insertarlos.
function escapeHtml(v) {
  return String(v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export default {
  name: "CheckGraph",
  emits: ["hide", "ok", "cancel"],
  components: {
    apexchart: VueApexCharts,
  },
  props: {
    check: !Object,
  },
  data() {
    return {
      history: [],
      results: [],
      timeFilter: 1,
      chartOptions: {
        tooltip: {
          x: {
            format: "dd MMM h:mm:sst",
          },
        },
        chart: {
          id: "chart2",
          type: "line",
          // 050 (V2-G01): sin esto ApexCharts escribe Helvetica/Arial en cada
          // texto; ejes y rótulos van en Archivo (la pila del body).
          fontFamily: getComputedStyle(document.body).fontFamily,
          // 050 (V2-G15): sin barra ni zoom por arrastre (sólo ratón).
          toolbar: {
            show: false,
          },
          zoom: {
            enabled: false,
          },
          animations: {
            enabled: false,
          },
        },
        // 050 (V2-G05): la serie es un dato, no una acción: token neutro.
        colors: [obsToken("--obs-text-2")],
        stroke: {
          width: 3,
        },
        dataLabels: {
          enabled: false,
        },
        fill: {
          opacity: 1,
        },
        markers: {
          size: 1,
        },
        xaxis: {
          type: "datetime",
          labels: {
            datetimeUTC: false,
          },
        },
        noData: {
          text: "",
        },
        theme: {
          mode: this.$q.dark.isActive ? "dark" : "light",
        },
      },
    };
  },
  computed: {
    title() {
      return this.$t("checkGraph.title", { desc: this.check.readable_desc });
    },
    timeFilterOptions() {
      return [
        { value: 1, label: this.$t("checkGraph.last24Hours") },
        { value: 7, label: this.$t("checkGraph.last7Days") },
        { value: 30, label: this.$t("checkGraph.last30Days") },
        { value: 0, label: this.$t("checkGraph.everything") },
      ];
    },
    isPercentCheck() {
      return ["cpuload", "memory", "diskspace"].includes(
        this.check.check_type,
      );
    },
    showChart() {
      return !this.$q.loading.isActive && this.history.length > 0;
    },
    seriesName() {
      if (this.check.check_type === "cpuload")
        return this.$t("checkGraph.seriesCpuLoad");
      else if (this.check.check_type === "memory")
        return this.$t("checkGraph.seriesMemory");
      else if (this.check.check_type === "diskspace")
        return this.$t("checkGraph.seriesDiskSpace");
      else if (this.check.check_type === "script")
        return this.$t("checkGraph.seriesScript");
      else if (this.check.check_type === "eventlog")
        return this.$t("checkGraph.seriesStatus");
      else if (this.check.check_type === "winsvc")
        return this.$t("checkGraph.seriesStatus");
      else if (this.check.check_type === "ping")
        return this.$t("checkGraph.seriesStatus");
      else return "";
    },
  },
  methods: {
    getChartData() {
      this.$q.loading.show();

      this.$axios
        .patch(`/checks/${this.check.check_result.id}/history/`, {
          timeFilter: this.timeFilter,
        })
        .then((r) => {
          this.history = Object.freeze(r.data);

          // save copy of data to reference results in chart tooltip
          if (
            this.check.check_type !== "cpuload" ||
            this.check.check_type !== "memory" ||
            this.check.check_type !== "diskspace"
          ) {
            this.results = Object.freeze(r.data);
          }

          this.$q.loading.hide();
        })
        .catch(() => {
          this.$q.loading.hide();
        });
    },
    downloadPng() {
      const chart = this.$refs.chart;
      if (!chart || !chart.dataURI) return;
      chart.dataURI().then(({ imgURI }) => {
        const a = document.createElement("a");
        a.href = imgURI;
        a.download = `${this.title}.png`;
        a.click();
      });
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
  },
  mounted() {
    this.chartOptions.noData.text = this.$t("checkGraph.noData");

    // create warning and error annotation on chart for certain check types
    if (
      this.check.check_type === "cpuload" ||
      this.check.check_type === "memory" ||
      this.check.check_type === "diskspace"
    ) {
      this.chartOptions["annotations"] = {
        position: "front",
        yaxis: [],
      };

      const cNegative = getCssVar("negative");
      const cWarning = getCssVar("warning");
      const cOnBrand = obsToken("--obs-on-brand");

      // add error threshold line if exists
      if (this.check.error_threshold) {
        this.chartOptions["annotations"]["yaxis"].push({
          y: this.check.error_threshold,
          strokeDashArray: 0,
          borderColor: cNegative,
          label: {
            position: "left",
            offsetX: 100,
            borderColor: cNegative,
            style: {
              color: cOnBrand,
              background: cNegative,
            },
            text: this.$t("checkGraph.errorThreshold"),
          },
        });
      }

      // add warning threshold line depending on check type
      if (this.check.warning_threshold) {
        this.chartOptions["annotations"]["yaxis"].push({
          y: this.check.warning_threshold,
          strokeDashArray: 0,
          borderColor: cWarning,
          label: {
            position: "left",
            offsetX: 100,
            borderColor: cWarning,
            style: {
              color: cOnBrand,
              background: cWarning,
            },
            text: this.$t("checkGraph.warningThreshold"),
          },
        });
      }

      // Set yaxis options
      this.chartOptions["yaxis"] = {
        min: 0,
        max: 100,
        labels: {
          formatter: (val) => {
            return val + "%";
          },
        },
      };

      if (this.check.check_type === "diskspace") {
        this.chartOptions["yaxis"]["reversed"] = true;
      }
    } else {
      // Set the y-axis labels to Failing and Passing
      this.chartOptions["yaxis"] = {
        min: -1,
        max: 2,
        tickAmount: 0,
        reversed: true,
        forceNiceScale: true,
        labels: {
          minWidth: 50,
          formatter: (val) => {
            if (val === 0) return this.$t("checkGraph.passing");
            else if (val === 1) return this.$t("checkGraph.failing");
            else return "";
          },
        },
      };

      // customize the yaxis tooltip to include more information
      this.chartOptions["tooltip"]["y"] = {
        title: {
          formatter: () => {
            return "";
          },
        },
        formatter: (value, { dataPointIndex }) => {
          let formatted = "";
          if (this.check.check_type === "script") {
            // 050 (V2-G01): retcode (clase 12) y stdout/stderr (clase 16) en
            // Mono, fuera del rótulo, que queda en Archivo.
            formatted +=
              this.$t("checkGraph.returnCode") +
              '<span class="mono">' +
              escapeHtml(this.results[dataPointIndex].results.retcode) +
              "</span><br/>";
            formatted +=
              this.$t("checkGraph.stdOut") +
              '<pre class="mono q-ma-none">' +
              escapeHtml(this.results[dataPointIndex].results.stdout) +
              "</pre>";
            formatted +=
              this.$t("checkGraph.errOut") +
              '<pre class="mono q-ma-none">' +
              escapeHtml(this.results[dataPointIndex].results.errout) +
              "</pre>";
            formatted +=
              this.$t("checkGraph.executionTime") +
              this.results[dataPointIndex].results.execution_time +
              "<br/>";
          } else if (this.check.check_type === "ping") {
            // 050 (V2-G01): la salida del ping es salida cruda (clase 16).
            formatted +=
              '<pre class="mono q-ma-none">' +
              escapeHtml(this.results[dataPointIndex].results) +
              "</pre>";
          } else {
            formatted += this.results[dataPointIndex].results;
          }

          return formatted;
        },
      };
    }

    this.getChartData();
  },
};
</script>
