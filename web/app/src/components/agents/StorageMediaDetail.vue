<template>
  <div class="scroll" :style="{ 'max-height': tabHeight }">
    <div class="row items-center q-mb-sm">
      <div class="text-subtitle2">{{ $t("storageMedia.detail.title") }}</div>
      <q-space />
      <!-- V2-G01 clase 8: marca de tiempo dedicada. -->
      <span v-if="measuredAt" class="text-caption text-grey q-mr-sm mono">
        {{ formatDate(measuredAt) }}
      </span>
      <q-badge
        v-if="verdict"
        :color="verdictColor(verdict)"
        class="q-mr-sm"
        :class="{ 'obs-chip-neutral': verdictColor(verdict) === 'grey' }"
      >
        {{ $t(`storageMedia.verdict.${verdict}`) }}
      </q-badge>
    </div>

    <!-- Los "no sabemos" van con su propia redacción y NO fusionados: el
         operador tiene que distinguir "no pudimos leer" de "nunca reportó" de
         "no se sondearon las capacidades" (RN-02). Confundirlos haría que
         alguien decida una baja sobre un dato que no existe. -->
    <q-banner v-if="queryError" dense class="obs-notice q-mb-sm">
      <template v-slot:avatar>
        <q-icon name="warning" />
      </template>
      {{ $t("storageMedia.detail.queryError") }}
      <div class="text-caption q-mt-xs">{{ queryError }}</div>
    </q-banner>

    <q-banner
      v-else-if="!loading && media.length === 0"
      dense
      class="obs-notice q-mb-sm"
    >
      {{ $t("storageMedia.detail.noMedia") }}
    </q-banner>

    <q-banner
      v-else-if="capabilitiesProbed === false"
      dense
      class="obs-notice q-mb-sm"
    >
      <template v-slot:avatar>
        <q-icon name="info" />
      </template>
      {{ $t("storageMedia.detail.notProbed") }}
    </q-banner>

    <q-list bordered separator v-if="media.length">
      <q-item v-for="disco in media" :key="disco.pnp_device_id">
        <q-item-section>
          <!-- V2-G01 clase 7: modelo o especificación de hardware. -->
          <q-item-label class="mono">
            {{ disco.model || disco.pnp_device_id }}
            <q-badge
              v-if="disco.is_system_disk"
              color="primary"
              class="q-ml-sm"
            >
              {{ $t("storageMedia.detail.systemDisk") }}
            </q-badge>
          </q-item-label>
          <q-item-label caption>
            <div class="row q-col-gutter-x-md">
              <div>
                {{
                  par("mediaType", mediaTypeLabel($t, disco.media_type_code))
                }}
              </div>
              <div>{{ par("bus", busTypeLabel($t, disco.bus_type)) }}</div>
              <div v-if="disco.size_bytes">
                {{ par("capacity", capacityLabel(disco.size_bytes)) }}
              </div>
            </div>
            <div class="row q-col-gutter-x-md">
              <div v-if="disco.serial_number">
                {{ par("serial", disco.serial_number) }}
              </div>
              <div v-if="disco.firmware_revision">
                {{ par("firmware", disco.firmware_revision) }}
              </div>
              <div>
                {{
                  par(
                    "selfEncrypting",
                    selfEncryptingLabel($t, disco.self_encrypting),
                  )
                }}
              </div>
            </div>
          </q-item-label>
        </q-item-section>
      </q-item>
    </q-list>
  </div>
</template>

<script>
// Feature 055 · el inventario de medios de UN equipo (RF-01).
//
// Muestra TODOS los discos fijos, no sólo el de sistema: el veredicto del
// equipo sale del de sistema (RN-03), pero un segundo disco sin vía de
// sanitización es información que el operador quiere ver antes de prometer
// algo, y esconderla sería decidir por él.
//
// Los códigos llegan crudos (RN-04) y se traducen acá.

import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";

import { fetchStorageMediaDetail } from "@/api/storagemedia";
import { formatDate } from "@/utils/format";
import {
  busTypeLabel,
  capacityLabel,
  mediaTypeLabel,
  selfEncryptingLabel,
  verdictColor,
} from "@/utils/storageMedia";

export default {
  name: "StorageMediaDetail",
  props: {
    agentId: { type: String, required: true },
  },
  setup(props) {
    const { t } = useI18n();
    const loading = ref(false);
    const media = ref([]);
    const verdict = ref(null);
    const queryError = ref(null);
    const capabilitiesProbed = ref(null);
    const measuredAt = ref(null);

    const tabHeight = computed(() => "35vh");

    // «etiqueta: valor» compuesto por i18n y no concatenado en la plantilla.
    // No es sólo para contentar al gate: hay idiomas que no usan dos puntos ni
    // ese orden, y dejarlo en el archivo de idioma es lo que permite cambiarlo.
    function par(clave, valor) {
      return t("storageMedia.detail.pair", {
        label: t(`storageMedia.detail.${clave}`),
        value: valor,
      });
    }

    async function load() {
      loading.value = true;
      try {
        const data = await fetchStorageMediaDetail(props.agentId);
        media.value = data?.media ?? [];
        verdict.value = data?.verdict ?? null;
        queryError.value = data?.query_error ?? null;
        capabilitiesProbed.value = data?.capabilities_probed ?? null;
        measuredAt.value = data?.measured_at ?? null;
      } finally {
        loading.value = false;
      }
    }

    watch(() => props.agentId, load);
    onMounted(load);

    return {
      loading,
      media,
      verdict,
      queryError,
      capabilitiesProbed,
      measuredAt,
      tabHeight,
      par,
      formatDate,
      verdictColor,
      mediaTypeLabel,
      busTypeLabel,
      selfEncryptingLabel,
      capacityLabel,
    };
  },
};
</script>
