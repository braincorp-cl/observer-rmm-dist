<template>
  <!-- `@show` (no `@before-show`) es lo que garantiza que el div del mapa exista:
       q-dialog monta su contenido en un portal y lo emite cuando la transición
       terminó. Leaflet sobre un contenedor que todavía no está en el DOM no
       falla, simplemente no dibuja nada — otra pantalla en blanco sin mensaje. -->
  <q-dialog v-model="show" @hide="cleanup" @show="renderMap" full-width>
    <q-card>
      <q-bar>
        <q-icon name="travel_explore" />
        <div class="text-weight-bold">
          {{ $t("lostEquipment.timeline.title", { hostname: hostname }) }}
        </div>
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip>{{ $t("lostEquipment.timeline.close") }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-card-section
        v-if="loading"
        class="flex flex-center"
        style="height: 420px"
      >
        <q-circular-progress indeterminate size="50px" color="primary" />
      </q-card-section>

      <template v-else>
        <q-card-section v-if="state" class="q-pb-none">
          <div class="text-caption text-grey-7">
            {{
              $t("lostEquipment.timeline.caseMeta", {
                reason: state.reason,
                who: state.marked_by || "?",
                when: formatDate(state.marked_at),
              })
            }}
          </div>
        </q-card-section>

        <!-- La política del ambiente, a la vista. Que la evidencia se borra sola
             y si está cifrada es lo que ADR-025 exige que sea verdad; mostrarlo
             acá es lo que permite desmentirlo cuando NO lo es. -->
        <q-card-section v-if="retention" class="q-pt-sm q-pb-none">
          <q-chip dense square icon="auto_delete" class="text-caption">
            {{
              $t("lostEquipment.timeline.retention", {
                days: retention.prune_days,
                closed: retention.closed_case_days,
              })
            }}
          </q-chip>
          <q-chip
            v-if="encrypted !== null"
            dense
            square
            class="text-caption"
            :icon="encrypted ? 'lock' : 'lock_open'"
            :color="encrypted ? 'green-2' : 'orange-2'"
            text-color="black"
          >
            {{
              $t(
                encrypted
                  ? "lostEquipment.timeline.encrypted"
                  : "lostEquipment.timeline.notEncrypted",
              )
            }}
          </q-chip>
        </q-card-section>

        <q-card-section v-if="!cycles.length">
          <!-- Un caso recién abierto no tiene ciclos todavía: se dice, en vez de
               mostrar una lista vacía que se lee como "algo falló". -->
          <q-banner dense class="bg-grey-3 text-black">
            <template v-slot:avatar><q-icon name="hourglass_empty" /></template>
            {{ $t("lostEquipment.timeline.noCycles") }}
          </q-banner>
        </q-card-section>

        <q-card-section v-else class="row q-col-gutter-md">
          <!-- recorrido -->
          <div class="col-12 col-md-6">
            <div
              v-if="points.length"
              ref="mapEl"
              style="height: 420px; width: 100%; border-radius: 4px"
            ></div>
            <q-banner v-else dense class="bg-grey-3 text-black">
              <template v-slot:avatar><q-icon name="location_off" /></template>
              {{ $t("lostEquipment.timeline.noPoints") }}
            </q-banner>
          </div>

          <!-- ciclos -->
          <div class="col-12 col-md-6">
            <q-list separator style="max-height: 420px; overflow-y: auto">
              <q-item
                v-for="c in cycles"
                :key="c.cycle"
                clickable
                @click="focusCycle(c)"
              >
                <q-item-section avatar top>
                  <q-avatar
                    square
                    size="72px"
                    v-if="c.screen && c.screen.has_asset"
                    class="cursor-pointer"
                  >
                    <img
                      v-if="thumbs[c.screen.id]"
                      :src="thumbs[c.screen.id]"
                      :alt="$t('lostEquipment.timeline.screenAlt')"
                      @click.stop="openFull(c.screen.id)"
                    />
                    <q-icon v-else name="image" color="grey-6" />
                  </q-avatar>
                  <q-avatar square size="72px" v-else>
                    <q-icon name="visibility_off" color="grey-6" />
                  </q-avatar>

                  <!-- La foto de webcam va SEPARADA de la captura de pantalla y
                       no la reemplaza: son dos evidencias distintas del mismo
                       ciclo. Sólo aparece si el ciclo la trae, así que una flota
                       con la webcam apagada no ve nada de esto. -->
                  <q-avatar
                    v-if="c.webcam && c.webcam.has_asset"
                    square
                    size="72px"
                    class="cursor-pointer q-mt-xs"
                  >
                    <img
                      v-if="thumbs[c.webcam.id]"
                      :src="thumbs[c.webcam.id]"
                      :alt="$t('lostEquipment.timeline.webcamAlt')"
                      @click.stop="openFull(c.webcam.id)"
                    />
                    <q-icon v-else name="photo_camera" color="grey-6" />
                    <q-badge floating color="deep-orange" rounded>
                      <q-icon name="photo_camera" size="12px" />
                    </q-badge>
                  </q-avatar>
                </q-item-section>

                <q-item-section>
                  <q-item-label>
                    {{
                      $t("lostEquipment.timeline.cycleLabel", {
                        cycle: c.cycle,
                        when: formatDate(c.when),
                      })
                    }}
                  </q-item-label>

                  <q-item-label caption v-if="c.geo">
                    {{
                      $t("lostEquipment.timeline.geoMeta", {
                        source: $t(sourceKey(c.geo.source)),
                        accuracy: c.geo.accuracy_m ?? "?",
                      })
                    }}
                  </q-item-label>
                  <q-item-label caption v-else>
                    {{ $t("lostEquipment.timeline.noGeo") }}
                  </q-item-label>

                  <!-- El motivo por el que este ciclo no trae imagen. Se muestra
                       SIEMPRE que exista: distinguir "el equipo está apagado" de
                       "este equipo nunca va a dar capturas" es la razón de que la
                       fila se guarde aunque no haya archivo. -->
                  <q-item-label caption v-if="c.screen && c.screen.note">
                    <q-chip
                      dense
                      square
                      size="sm"
                      color="warning"
                      text-color="black"
                    >
                      {{ $t(reasonKey(c.screen.note)) }}
                    </q-chip>
                  </q-item-label>

                  <q-item-label caption v-if="c.sessionUser">
                    {{
                      $t("lostEquipment.timeline.sessionUser", {
                        user: c.sessionUser,
                      })
                    }}
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </div>
        </q-card-section>
      </template>

      <!-- imagen completa -->
      <q-dialog v-model="fullDialog">
        <q-card>
          <q-img :src="fullSrc" :alt="$t('lostEquipment.timeline.screenAlt')" />
        </q-card>
      </q-dialog>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 030 · Fase 1 · la línea de tiempo de un caso de equipo perdido (T012).
//
// Un ciclo es lo que el agente capturó de una vez: el punto de ubicación y la
// captura de pantalla del mismo momento. El servidor las guarda como filas
// separadas con el mismo número de ciclo, y acá se vuelven a juntar para
// mostrarlas como una sola línea — que es como lo piensa quien sigue el caso.
//
// DOS COSAS QUE NO SON OBVIAS:
//
//  1. Las miniaturas se bajan por axios como blob y se muestran con un object
//     URL. Un `<img src="/agents/.../file/">` no llevaría la cabecera de
//     autenticación —la evidencia está detrás de `can_view_lost_evidence`— y
//     además dejaría una URL que se puede pegar en cualquier parte. Los object
//     URL se revocan al cerrar el diálogo; si no, cada apertura filtraría unos
//     megas de memoria por caso.
//
//  2. Un ciclo SIN imagen se muestra igual, con su motivo traducido. Es la
//     misma razón por la que el servidor guarda la fila sin archivo: la lista
//     tiene que poder decir "acá no se pudo capturar, y por esto".
import { ref, computed, watch, nextTick, onBeforeUnmount } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { fetchLostEvidence, fetchLostEvidenceFile } from "@/api/lostmode";
import { formatDate } from "@/utils/format";

export default {
  name: "LostCaseTimelineDialog",
  props: {
    modelValue: { type: Boolean, default: false },
    agentId: { type: String, required: true },
    hostname: { type: String, default: "" },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const show = computed({
      get: () => props.modelValue,
      set: (v) => emit("update:modelValue", v),
    });

    const loading = ref(false);
    const state = ref(null);
    const evidence = ref([]);
    // Política de retención y cifrado del ambiente (030 · Fase 3). Vienen con el
    // caso y no de la Configuración global: quien mira la línea de tiempo tiene
    // que saber cuánto le queda a lo que está mirando, sin cambiar de pantalla.
    const retention = ref(null);
    const encrypted = ref(null);
    const thumbs = ref({});
    const fullDialog = ref(false);
    const fullSrc = ref("");
    const mapEl = ref(null);
    let map = null;

    // Los ciclos, del más reciente al más antiguo: lo último que se supo del
    // equipo es lo que importa cuando alguien abre el caso.
    const cycles = computed(() => {
      const porCiclo = new Map();

      for (const pieza of evidence.value) {
        if (!porCiclo.has(pieza.cycle)) {
          porCiclo.set(pieza.cycle, { cycle: pieza.cycle });
        }
        const c = porCiclo.get(pieza.cycle);

        if (pieza.kind === "geo") c.geo = pieza;
        if (pieza.kind === "screen") c.screen = pieza;
        if (pieza.kind === "webcam") c.webcam = pieza;

        // La hora del EQUIPO cuando existe; si no, la del servidor al recibir.
        // Entre las dos puede haber horas si el equipo estuvo sin red.
        if (!c.when) c.when = pieza.captured_at || pieza.created;
        if (!c.sessionUser && pieza.session_user)
          c.sessionUser = pieza.session_user;
      }

      return [...porCiclo.values()].sort((a, b) => b.cycle - a.cycle);
    });

    const points = computed(() =>
      cycles.value
        .filter((c) => c.geo && c.geo.lat != null && c.geo.lng != null)
        .map((c) => ({ ...c.geo, cycle: c.cycle })),
    );

    // Se reusan las traducciones de fuente del diálogo de ubicación (feature
    // 023): son las mismas cinco fuentes y tener dos redacciones para lo mismo
    // sería peor que la dependencia.
    function sourceKey(source) {
      return source
        ? `agentTabs.location.source_${source}`
        : "lostEquipment.timeline.noGeo";
    }

    function reasonKey(note) {
      return `lostEquipment.timeline.reason_${note}`;
    }

    async function load() {
      loading.value = true;
      state.value = null;
      evidence.value = [];
      retention.value = null;
      encrypted.value = null;
      try {
        const data = await fetchLostEvidence(props.agentId);
        state.value = data?.state ?? null;
        evidence.value = data?.evidence ?? [];
        retention.value = data?.retention ?? null;
        // `?? null` y no `?? false`: "el servidor no lo dijo" (una consola
        // nueva contra un backend viejo) no es lo mismo que "no cifra", y
        // pintar el aviso rojo en ese caso sería una alarma inventada.
        encrypted.value = data?.encryption?.enabled ?? null;
      } catch (e) {
        console.error(e);
      }
      loading.value = false;

      await nextTick();
      renderMap();
      loadThumbs();
    }

    // Las miniaturas se piden una por una y en segundo plano: un caso largo
    // puede tener decenas de capturas y bajarlas todas antes de dibujar dejaría
    // la lista en blanco sin explicación.
    async function loadThumbs() {
      for (const c of cycles.value) {
        // Pantalla y webcam son dos piezas distintas del mismo ciclo y se bajan
        // por separado. La cara va después de la pantalla a propósito: si el
        // operador no llega a ver todo, lo primero que aparece es la pantalla,
        // que es la evidencia menos sensible de las dos.
        await bajarMiniatura(c.screen);
        await bajarMiniatura(c.webcam);
      }
    }

    async function bajarMiniatura(pieza) {
      if (!pieza || !pieza.has_asset || thumbs.value[pieza.id]) return;
      try {
        const blob = await fetchLostEvidenceFile(props.agentId, pieza.id);
        thumbs.value[pieza.id] = URL.createObjectURL(blob);
      } catch (e) {
        // Un 403 acá es lo normal cuando el operador puede seguir el caso pero
        // no tiene `can_view_lost_evidence`: la lista se ve igual, sin las
        // imágenes. No es un error que valga interrumpir.
        console.debug("evidencia no disponible", e);
      }
    }

    function renderMap() {
      cleanupMap();
      if (!mapEl.value || !points.value.length) return;

      const ultimo = points.value[0];
      map = L.map(mapEl.value).setView([ultimo.lat, ultimo.lng], 14);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);

      // El recorrido va en orden cronológico (los ciclos vienen al revés).
      const enOrden = [...points.value].reverse();
      if (enOrden.length > 1) {
        L.polyline(
          enOrden.map((p) => [p.lat, p.lng]),
          { color: "#0E8FA8", weight: 3, opacity: 0.6, dashArray: "4 6" },
        ).addTo(map);
      }

      for (const p of enOrden) {
        const esUltimo = p.cycle === ultimo.cycle;
        if (p.accuracy_m) {
          L.circle([p.lat, p.lng], {
            radius: p.accuracy_m,
            color: "#0E8FA8",
            fillOpacity: esUltimo ? 0.12 : 0.05,
            weight: 1,
          }).addTo(map);
        }
        L.circleMarker([p.lat, p.lng], {
          radius: esUltimo ? 8 : 5,
          color: "#0E8FA8",
          fillColor: esUltimo ? "#0E8FA8" : "#ffffff",
          fillOpacity: 0.9,
          weight: 2,
        }).addTo(map);
      }

      if (enOrden.length > 1) {
        map.fitBounds(L.latLngBounds(enOrden.map((p) => [p.lat, p.lng])), {
          padding: [40, 40],
        });
      }

      setTimeout(() => map && map.invalidateSize(), 300);
    }

    function focusCycle(c) {
      if (!map || !c.geo || c.geo.lat == null) return;
      map.setView([c.geo.lat, c.geo.lng], 16);
    }

    function openFull(id) {
      fullSrc.value = thumbs.value[id] ?? "";
      if (fullSrc.value) fullDialog.value = true;
    }

    function cleanupMap() {
      if (map) {
        map.remove();
        map = null;
      }
    }

    function cleanup() {
      cleanupMap();
      // Sin esto cada apertura del caso deja los blobs de todas las capturas
      // colgando en memoria hasta que se recargue la consola.
      for (const url of Object.values(thumbs.value)) URL.revokeObjectURL(url);
      thumbs.value = {};
      fullDialog.value = false;
      fullSrc.value = "";
    }

    // `immediate` no es un detalle: la vista monta este componente con `v-if`
    // recién cuando hay un caso elegido, así que llega al DOM con `show` YA en
    // true y el watch normal no se dispararía nunca — el diálogo se abriría
    // vacío y para siempre. Es el tipo de error que no da ningún mensaje.
    watch(
      show,
      (v) => {
        if (v) load();
        else cleanup();
      },
      { immediate: true },
    );

    // Si la vista se destruye con el diálogo abierto (una navegación), el watch
    // no alcanza a limpiar y los object URL de las capturas quedan colgando.
    onBeforeUnmount(cleanup);

    return {
      show,
      loading,
      state,
      retention,
      encrypted,
      cycles,
      points,
      thumbs,
      mapEl,
      fullDialog,
      fullSrc,
      sourceKey,
      reasonKey,
      renderMap,
      focusCycle,
      openFull,
      cleanup,
      formatDate,
    };
  },
};
</script>
