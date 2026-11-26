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
            :class="{ mono: !esFechaSinHora(v) && !esNombre(k, v, j) }"
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
import { esIdentificador, esPalabra } from "@/utils/tipografia";

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

    // V2-G01 (2026-11-20): nombres, estados y palabras van en Archivo. Por
    // valor: lo hecho solo de palabras (esPalabra). Por clave: las propiedades
    // WMI que guardan un NOMBRE aunque traigan dígitos —el nombre de equipo
    // (enmienda 2026-11-14: el hostname no es valor dedicado), el usuario, la
    // organización, el nombre del SO con su versión, la arquitectura «64 bits»
    // y la lista de idiomas—.
    const CLAVES_NOMBRE = new Set([
      "CSName",
      "DNSHostName",
      "SystemName",
      "UserName",
      "RegisteredUser",
      "Organization",
      "OSArchitecture",
      "MUILanguages",
      "BuildType",
      "NetConnectionID",
      // Valor ENUMERADO («Ethernet 802.3»): interfaz (enmienda 2026-11-21 B).
      "AdapterType",
      // Nombre del dispositivo o del procesador gráfico (tanda 118dece): es
      // nombre, no modelo ⇒ Archivo en todas las instancias.
      "ProductName",
      "VideoProcessor",
    ]);
    // Claves cuyo valor es SIEMPRE un identificador generado (clase 10) o un
    // nombre de clase WMI: todos los hermanos van en mono, aunque alguno salga
    // hecho solo de letras («NdisWan» junto a «vmxnet3ndis6»).
    const CLAVES_DATO = new Set([
      "ServiceName",
      "PNPDeviceID",
      "DeviceID",
      "SettingID",
      "GUID",
      // Direcciones de red (tanda 118dece, I-339): valores dedicados aunque
      // lleguen como arreglo ⇒ mono.
      "IPAddress",
      "IPSubnet",
      "DefaultIPGateway",
      "DNSServerSearchOrder",
    ]);
    // V2-G01 (tanda 2026-11-22, enmienda B): valores ENUMERADOS por WMI —el
    // nombre de clase («Win32_Processor»), el rol («CPU»), el estado («OK»)—
    // son interfaz y van en Archivo; la clase 10 es solo para identificadores
    // GENERADOS.
    const CLAVES_ENUMERADAS = new Set([
      "CreationClassName",
      "CSCreationClassName",
      "SystemCreationClassName",
      "Role",
      "Status",
    ]);
    // V2-G01 (2026-11-21): en un dispositivo PnP (la instancia trae
    // PNPDeviceID) el Name, Caption, Description o Model es su MODELO de
    // hardware (clase 7) y va en mono aunque sea solo palabras: la tanda sobre
    // 6a1ef85 midió «WAN Miniport (SSTP)» en Archivo junto a «WAN Miniport
    // (IKEv2)» en mono, en la misma clave.
    // V2-G01 (lote G01, familia 3 aprobada 2026-11-24): el Name, Caption o
    // Description de un dispositivo PnP es su DESCRIPCIÓN («Disk drive», «WAN
    // Miniport (IKEv2)», «Standard USB … - 1.20 (Microsoft)»), con versión
    // embebida a veces ⇒ Archivo. Solo Model queda como modelo (clase 7).
    const CLAVES_MODELO = new Set(["Model"]);
    const CLAVES_DESCRIPCION_PNP = new Set(["Name", "Caption", "Description"]);
    // Tanda 118dece: una instancia es dispositivo si TRAE la clave PNPDeviceID
    // (aunque valga null, como Win32_Processor) o si su clase es de hardware.
    const CLASES_DISPOSITIVO = new Set([
      "Win32_Processor",
      "Win32_VideoController",
      "Win32_NetworkAdapter",
      "Win32_DiskDrive",
    ]);
    function esDispositivo(j) {
      return (
        !!j &&
        typeof j === "object" &&
        (Object.prototype.hasOwnProperty.call(j, "PNPDeviceID") ||
          CLASES_DISPOSITIVO.has(j.CreationClassName))
      );
    }
    function esNombre(k, v, j) {
      const clave = String(k);
      if (CLAVES_DATO.has(clave)) return false;
      if (CLAVES_NOMBRE.has(clave)) return true;
      if (CLAVES_ENUMERADAS.has(clave)) return true;
      if (typeof v === "string" && /^(CIM|Win32)_\w+$/.test(v)) return true;
      // I-336: Model es modelo de hardware (clase 7) traiga o no PNPDeviceID.
      if (CLAVES_MODELO.has(clave)) return false;
      // Ruta de dispositivo («\\.\PHYSICALDRIVE0»): clase 5 ⇒ mono, también
      // cuando WMI la repite como Name de un dispositivo.
      if (typeof v === "string" && v.startsWith("\\\\")) return false;
      if (esDispositivo(j) && CLAVES_DESCRIPCION_PNP.has(clave)) return true;
      // El mismo rótulo descriptivo del adaptador aparece fuera de PnP con su
      // índice delante («[00000003] WAN Miniport (IKEv2)», en
      // Win32_NetworkAdapterConfiguration): sigue siendo descripción ⇒ Archivo.
      if (CLAVES_DESCRIPCION_PNP.has(clave) && typeof v === "string" && /^\[\d+\]\s/.test(v)) return true;
      // Ruta, unidad o identificador compuesto: dato, aunque no traiga dígitos.
      if (esIdentificador(v)) return false;
      // El hostname es nombre (enmienda 2026-11-14) también cuando WMI lo
      // repite como Caption o Name de Win32_ComputerSystem.
      if (j && [j.CSName, j.DNSHostName, j.SystemName].includes(v)) return true;
      // El nombre del SO («Microsoft Windows 10 Pro») es un nombre con versión
      // embebida; el Caption de una CPU es especificación y sigue en mono.
      const so = typeof v === "string" && /^Microsoft Windows\b/.test(v);
      return esPalabra(v) || Array.isArray(v) || so;
    }

    return {
      esNombre,
      esFechaSinHora,
      tabHeight,
      uid,
      copyValueToClip,
    };
  },
};
</script>
