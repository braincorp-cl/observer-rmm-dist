<template>
  <div class="scroll" :style="{ 'max-height': tabHeight - 10 }">
    <div v-for="i in info" :key="i + uid()">
      <div v-for="j in i" :key="j + uid()">
        <div v-for="(v, k) in j" :key="v + uid()">
          <span class="text-overline">{{
            $t("wmiDetail.keyLabel", { k })
          }}</span>
          <!-- 046 (UI-D05): el valor de inventario es un dato, no una acción: chip neutro y monoespaciado.
               V2-G01 (enmienda 2026-11-11): antes era `!esFecha(v)`, o sea la
               fecha se iba a Archivo. La enmienda invirtió ese caso: una MARCA
               DE TIEMPO compacta es un valor y va entera en mono, y nombra
               «su insignia» como sitio dedicado. Lo que sigue en Archivo es la
               fecha SOLA, sin hora, que es interfaz. De ahí `esFechaSinHora`. -->
          <q-badge
            class="q-ml-sm text-caption obs-chip-neutral"
            :class="{ mono: !esFechaSinHora(v) }"
            >{{ v }}</q-badge
          >
          <q-btn
            v-if="!!v"
            size="sm"
            class="q-ml-xs"
            flat
            round
            icon="content_copy"
            @click="copyValueToClip(v)"
          >
            <q-tooltip>{{ $t("wmiDetail.copyToClipboard") }}</q-tooltip>
          </q-btn>
        </div>
      </div>
      <q-separator v-if="info.length > 1" />
    </div>
  </div>
</template>

<script>
import { copyToClipboard } from "quasar";
import { notifySuccess } from "@/utils/notify";
// composition imports
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useStore } from "vuex";
import { uid } from "quasar";

export default {
  name: "WmiDetail",
  props: { info: !Object },
  setup() {
    // setup vuex
    const store = useStore();
    const { t } = useI18n();
    const tabHeight = computed(() => store.state.tabHeight);

    function copyValueToClip(val) {
      copyToClipboard(val).then(() => {
        notifySuccess(t("wmiDetail.copiedToClipboard"));
      });
    }

    // 046 (UI-D01): las fechas quedan en Archivo; el resto de valores es dato (mono).
    // V2-G01: sólo la fecha SOLA es interfaz. Si trae hora es una marca de
    // tiempo, y la enmienda del 2026-11-11 la manda entera a JetBrains Mono.
    // Medido: 63 insignias del inventario WMI salían en Archivo con ISO crudo
    // (`0001-01-01T00:00:00Z`, `2026-09-23T14:29:21.5-03:00`), mientras 1066
    // insignias no-ISO de la MISMA clase salían en mono.
    function esFechaSinHora(v) {
      return typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
    }

    return {
      esFechaSinHora,
      tabHeight,
      uid,
      copyValueToClip,
    };
  },
};
</script>
