<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">{{ $t("activityLive.title") }}</div>
      <q-space />
      <q-btn
        dense
        color="primary"
        icon="refresh"
        :label="$t('activityLive.refreshAll')"
        :loading="actualizandoTodo"
        :disable="!pagina.length"
        @click="actualizarPagina"
      />
    </div>
    <p class="text-caption text-grey q-mb-md">{{ $t("activityLive.notice") }}</p>

    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-sm-4">
        <q-select
          dense
          filled
          clearable
          emit-value
          map-options
          v-model="cliente"
          :options="clientOptions"
          :label="$t('activityLive.client')"
          @update:model-value="cargar"
        />
      </div>
    </div>

    <div v-if="cargando" class="q-pa-md"><q-spinner size="md" /></div>
    <div v-else-if="!equipos.length" class="text-grey q-pa-md">
      {{ $t("activityLive.empty") }}
    </div>
    <div v-else>
      <div class="row q-col-gutter-md">
        <div v-for="e in pagina" :key="e.agent_id" class="col-12 col-sm-6 col-md-4 col-lg-3">
          <q-card flat bordered>
            <q-card-section class="q-py-xs row items-center no-wrap">
              <div class="ellipsis text-weight-medium">{{ e.hostname }}</div>
              <q-space />
              <q-btn
                dense
                flat
                round
                size="sm"
                icon="refresh"
                :loading="e.pidiendo"
                :disable="e.status !== 'online' || !e.screenshots"
                @click="actualizar(e)"
              >
                <q-tooltip>{{ $t("activityLive.refresh") }}</q-tooltip>
              </q-btn>
            </q-card-section>
            <div class="cursor-pointer" @click="ver(e)">
              <q-img v-if="e.img" :src="e.img" :ratio="16 / 9" fit="cover" />
              <div v-else class="sin-imagen flex flex-center text-grey">
                {{ $t("activityLive.noImage") }}
              </div>
            </div>
            <q-card-section class="q-py-xs text-caption">
              <div class="ellipsis text-grey">{{ `${e.client} · ${e.site}` }}</div>
              <div class="ellipsis">{{ detalle(e) }}</div>
              <div v-if="e.ultima && e.ultima.url" class="ellipsis text-grey">{{ e.ultima.url }}</div>
              <q-chip
                v-if="e.estado && e.estado !== 'ok'"
                dense
                size="sm"
                color="orange"
                text-color="white"
                class="q-ml-none"
              >
                {{ $t(`activityLive.state_${e.estado}`) }}
              </q-chip>
              <q-chip v-else-if="e.status !== 'online'" dense size="sm" color="grey-7" text-color="white" class="q-ml-none">
                {{ $t("activityLive.offline") }}
              </q-chip>
            </q-card-section>
          </q-card>
        </div>
      </div>
      <div v-if="paginas > 1" class="row justify-center q-mt-md">
        <q-pagination v-model="pag" :max="paginas" direction-links @update:model-value="actualizarPagina" />
      </div>
    </div>

    <q-dialog v-model="abierta">
      <q-card v-if="sel" style="max-width: 95vw; width: 1200px">
        <q-bar>
          {{ `${sel.hostname} · ${detalle(sel)}` }}
          <q-space />
          <q-btn dense flat icon="refresh" :loading="sel.pidiendo" @click="actualizar(sel)" />
          <q-btn dense flat icon="close" v-close-popup />
        </q-bar>
        <q-img v-if="sel.img" :src="sel.img" fit="contain" />
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { fetchClients } from "@/api/clients";
import { fetchActivityLive, fetchActivityScreenshotBlob, forceActivityScreenshot } from "@/api/agents";

// Feature 049-E · monitoreo en vivo SIN video: cada tarjeta muestra la última
// captura del equipo y, al abrir la página o con «Actualizar», pide una del
// momento. Respeta lo mismo que la captura periódica (sesión bloqueada, sin
// usuario, capturas apagadas) y cada pedido queda en Auditoría.
const POR_PAGINA = 12;

const cliente = ref(null);
const clientOptions = ref([]);
const equipos = ref([]);
const cargando = ref(false);
const actualizandoTodo = ref(false);
const pag = ref(1);
const sel = ref(null);
const abierta = ref(false);

const paginas = computed(() => Math.ceil(equipos.value.length / POR_PAGINA));
const pagina = computed(() => equipos.value.slice((pag.value - 1) * POR_PAGINA, pag.value * POR_PAGINA));

function hora(iso) {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function detalle(e) {
  const u = e.ultima;
  if (!u) return "—";
  return [hora(u.captured_at), u.username, u.process].filter(Boolean).join(" · ");
}

function liberar(e) {
  if (e.img) URL.revokeObjectURL(e.img);
  e.img = "";
}

async function cargarImagen(e) {
  if (!e.ultima || !e.ultima.id) return;
  try {
    const blob = await fetchActivityScreenshotBlob(e.agent_id, e.ultima.id);
    liberar(e);
    e.img = URL.createObjectURL(blob);
  } catch (err) {
    // sin imagen legible: la tarjeta queda con el texto
  }
}

async function actualizar(e) {
  if (e.pidiendo || e.status !== "online" || !e.screenshots) return;
  e.pidiendo = true;
  try {
    const r = await forceActivityScreenshot(e.agent_id);
    e.estado = r.estado;
    if (r.estado === "ok" && r.ultima) {
      // La lista trae los metadatos completos de la última captura.
      const lista = await fetchActivityLive(cliente.value ? { client: cliente.value } : {});
      const nuevo = lista.find((x) => x.agent_id === e.agent_id);
      e.ultima = (nuevo && nuevo.ultima) || r.ultima;
      await cargarImagen(e);
    }
  } catch (err) {
    e.estado = "error";
  } finally {
    e.pidiendo = false;
  }
}

async function actualizarPagina() {
  actualizandoTodo.value = true;
  const cola = pagina.value.filter((e) => e.status === "online" && e.screenshots);
  async function trabajador() {
    while (cola.length) await actualizar(cola.shift());
  }
  await Promise.all([trabajador(), trabajador(), trabajador()]);
  actualizandoTodo.value = false;
}

async function cargar() {
  cargando.value = true;
  equipos.value.forEach(liberar);
  pag.value = 1;
  try {
    const lista = await fetchActivityLive(cliente.value ? { client: cliente.value } : {});
    equipos.value = lista.map((x) => ({ ...x, img: "", estado: "", pidiendo: false }));
  } catch (err) {
    equipos.value = [];
  }
  cargando.value = false;
  await Promise.all(pagina.value.map(cargarImagen));
  actualizarPagina();
}

function ver(e) {
  if (!e.img) return;
  sel.value = e;
  abierta.value = true;
}

onMounted(async () => {
  try {
    const data = (await fetchClients()) ?? [];
    clientOptions.value = data.map((c) => ({ value: c.id, label: c.name }));
  } catch (err) {
    clientOptions.value = [];
  }
  cargar();
});
onBeforeUnmount(() => equipos.value.forEach(liberar));
</script>

<style scoped>
.sin-imagen {
  aspect-ratio: 16 / 9;
  background: rgba(128, 128, 128, 0.12);
}
</style>
