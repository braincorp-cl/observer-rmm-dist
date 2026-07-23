<template>
  <q-dialog v-model="show" @hide="cleanup">
    <q-card style="width: 720px; max-width: 90vw">
      <q-bar>
        <q-icon name="place" />
        <div class="text-weight-bold">
          {{ $t("agentTabs.location.title", { hostname: hostname }) }}
        </div>
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip>{{ $t("agentTabs.location.close") }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section v-if="loading" class="flex flex-center" style="height: 420px">
        <q-circular-progress indeterminate size="50px" color="primary" />
      </q-card-section>

      <!-- interruptor global apagado -->
      <q-card-section v-else-if="location && !location.enabled" style="height: 420px">
        <q-banner class="bg-grey-3 text-grey-9">
          <template #avatar><q-icon name="location_off" /></template>
          {{ $t("agentTabs.location.disabled") }}
        </q-banner>
      </q-card-section>

      <!-- habilitado pero sin ubicación registrada -->
      <q-card-section
        v-else-if="location && location.lat == null"
        style="height: 420px"
      >
        <q-banner class="bg-grey-3 text-grey-9">
          <template #avatar><q-icon name="help_outline" /></template>
          {{ $t("agentTabs.location.noFix") }}
        </q-banner>
      </q-card-section>

      <!-- mapa -->
      <template v-else-if="location">
        <q-card-section class="q-pb-none">
          <div class="text-caption text-grey-7">
            {{
              $t("agentTabs.location.meta", {
                source: sourceLabel ? $t(sourceLabel) : "?",
                accuracy: location.accuracy_m ?? "?",
                when: store.getters.formatDate(location.captured_at),
              })
            }}
          </div>
        </q-card-section>
        <q-card-section>
          <div ref="mapEl" style="height: 380px; width: 100%; border-radius: 4px"></div>
        </q-card-section>
      </template>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 023: diálogo de ubicación del agente. Usa Leaflet (MIT) + tiles OSM
// (self-hostable). La posición actual y la trayectoria vienen del backend, que
// las deriva de CheckHistory. Se usan circleMarker/polyline en vez de iconos de
// imagen para no depender de assets externos y evitar el clásico problema de
// rutas de iconos de Leaflet con bundlers.
import { ref, computed, watch, nextTick } from "vue";
import { useStore } from "vuex";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { fetchAgentLocation, fetchAgentLocationHistory } from "@/api/agents";

export default {
  name: "AgentLocationDialog",
  props: {
    modelValue: { type: Boolean, default: false },
    agentId: { type: String, required: true },
    hostname: { type: String, default: "" },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const store = useStore();
    const show = computed({
      get: () => props.modelValue,
      set: (v) => emit("update:modelValue", v),
    });

    const loading = ref(false);
    const location = ref(null);
    const points = ref([]);
    const mapEl = ref(null);
    let map = null;

    const sourceLabel = computed(() => {
      const src = location.value?.source;
      const key = `agentTabs.location.source_${src}`;
      // fallback al código crudo si no hay traducción
      return src ? key : "";
    });

    async function load() {
      loading.value = true;
      location.value = null;
      points.value = [];
      try {
        location.value = await fetchAgentLocation(props.agentId);
        if (location.value?.enabled && location.value.lat != null) {
          const hist = await fetchAgentLocationHistory(props.agentId, {
            limit: 500,
          });
          points.value = (hist?.points || []).filter(
            (p) => p.lat != null && p.long != null,
          );
        }
      } catch (e) {
        console.error(e);
      }
      loading.value = false;
      if (location.value?.enabled && location.value.lat != null) {
        await nextTick();
        renderMap();
      }
    }

    function renderMap() {
      cleanup();
      if (!mapEl.value || !location.value || location.value.lat == null) return;

      const lat = location.value.lat;
      const long = location.value.long;
      map = L.map(mapEl.value).setView([lat, long], 14);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);

      // trayectoria (T023): secuencia de puntos por timestamp
      if (points.value.length > 1) {
        const latlngs = points.value.map((p) => [p.lat, p.long]);
        L.polyline(latlngs, { color: "#0E8FA8", weight: 3, opacity: 0.7 }).addTo(
          map,
        );
      }

      // círculo de precisión
      if (location.value.accuracy_m) {
        L.circle([lat, long], {
          radius: location.value.accuracy_m,
          color: "#0E8FA8",
          fillOpacity: 0.1,
        }).addTo(map);
      }

      // posición actual
      L.circleMarker([lat, long], {
        radius: 8,
        color: "#0E8FA8",
        fillColor: "#0E8FA8",
        fillOpacity: 0.9,
      }).addTo(map);

      // el diálogo anima su tamaño; recalcular el mapa cuando termina
      setTimeout(() => map && map.invalidateSize(), 300);
    }

    function cleanup() {
      if (map) {
        map.remove();
        map = null;
      }
    }

    watch(show, (v) => {
      if (v) load();
      else cleanup();
    });

    return {
      store,
      show,
      loading,
      location,
      sourceLabel,
      mapEl,
      cleanup,
    };
  },
};
</script>
