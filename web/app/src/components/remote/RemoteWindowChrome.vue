<template>
  <!--
    050 (V2-P10): el chrome común de las ventanas remotas.

    Las cuatro superficies remotas —tomar control, VNC web, terminal web y
    administración en segundo plano— son ventanas propias: `api/agents.js` y
    `ActionBar.vue` las abren con `openURL` en 1600x900 y 1280x900, fuera de
    `MainLayout`. Por eso "shell" acá NO es la cabecera navy ni el `NavRail` de
    la consola (un riel global dentro de una ventana de sesión remota ofrece
    destinos a los que no se puede ir): es **tokens + cabecera propia**.

    Esto es una extracción literal de la cabecera que T048 escribió en
    `TakeControl.vue`, para que las otras ventanas la hereden en vez de copiarla.
    El marcado y el sass son los mismos; lo que cambia es que ahora hay un solo
    sitio donde viven.

    🔑 Y aquí vive el arranque de tema. `fetchDashboardInfo()` + `$q.dark.set()`
    es lo que hace que los tokens --obs-* resuelvan al tema del usuario. Sin esa
    llamada la ventana se queda en claro pase lo que pase, que es exactamente
    por qué `WebVNC` salía con `bg_body rgb(238,242,247)` y `dark=false` cuando
    las otras iban en `rgb(15,26,42)`. Ponerlo en el chrome y no en cada vista
    es lo que impide que la próxima ventana remota nazca con el mismo defecto.
  -->
  <div class="obs-page obs-remote">
    <header class="obs-remote__head row no-wrap items-center q-gutter-x-sm">
      <div class="col" style="min-width: 0">
        <div v-if="crumbs" class="obs-page__crumbs ellipsis" :title="crumbs">
          {{ crumbs }}
        </div>
        <div class="row items-center no-wrap q-gutter-x-sm">
          <h1 class="obs-remote__host ellipsis" :title="hostname || title">
            {{ hostname || title }}
          </h1>
          <!-- 046 (UI-D05) / V2-G05: el estado se dice con un punto de color de
               estado sobre píldora neutra, no pintando el texto ni el fondo. -->
          <span
            v-if="statusText"
            class="obs-remote__status"
            :class="`obs-remote__status--${status || 'unknown'}`"
          >
            <span class="obs-remote__dot" />
            {{ statusText }}
          </span>
        </div>
      </div>
      <div class="row no-wrap items-center q-gutter-sm obs-remote__btns">
        <slot name="actions" />
      </div>
    </header>
    <div class="obs-remote__canvas">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useQuasar } from "quasar";
import { fetchDashboardInfo } from "@/api/core";

defineProps({
  // Migas "cliente / sitio". Vacío en las ventanas que no cuelgan de un equipo.
  crumbs: { type: String, default: "" },
  // Nombre del equipo. Manda sobre `title` cuando ya llegó del backend.
  hostname: { type: String, default: "" },
  // Rótulo mientras no hay hostname, o en ventanas que no son de un equipo.
  title: { type: String, default: "" },
  // "online" | "offline" | null. Solo pinta el punto; el texto va en statusText.
  status: { type: String, default: null },
  // Sin texto no se dibuja la píldora: una ventana que no conoce el estado no
  // debe inventar uno "desconocido".
  statusText: { type: String, default: "" },
});

const $q = useQuasar();

onMounted(async () => {
  try {
    const { dark_mode, loading_bar_color } = await fetchDashboardInfo();
    $q.dark.set(dark_mode);
    $q.loadingBar.setDefaults({ color: loading_bar_color });
  } catch (e) {
    console.error(e);
  }
});
</script>

<style lang="sass" scoped>
// Ventana completa: cabecera fija arriba y el lienzo remoto se come el resto.
// `.obs-page` aporta el remapeo de grises de Quasar a tokens (app.sass); acá se
// le quita el relleno y el gap de página porque el lienzo va a sangre.
.obs-page.obs-remote
  height: 100vh
  padding: 0
  gap: 0
  overflow: hidden
  background: var(--obs-page)
.obs-remote__head
  flex: none
  padding: 10px 16px
  border-bottom: 1px solid var(--obs-border)
  background: var(--obs-page)
// El hostname es el título de la ventana, pero acá manda el lienzo: mismo papel
// que .obs-agenthdr__host con menos cuerpo para no comerse el escritorio remoto.
.obs-remote__host
  margin: 0
  font-size: 18px
  line-height: 1.25
  font-weight: 600
  min-width: 90px
  flex: 0 1 auto
  color: var(--obs-text)
.obs-remote__status
  display: inline-flex
  align-items: center
  gap: 6px
  flex: none
  font-size: 12.5px
  padding: 3px 10px
  border-radius: 99px
  background: var(--obs-raised)
  color: var(--obs-text-2)
  white-space: nowrap
.obs-remote__dot
  width: 7px
  height: 7px
  border-radius: 99px
  background: var(--obs-faint)
.obs-remote__status--online .obs-remote__dot
  background: var(--q-positive)
.obs-remote__status--offline .obs-remote__dot
  background: var(--q-warning)
.obs-remote__btns
  flex: none
.obs-remote__canvas
  flex: 1
  min-height: 0
  display: flex
  background: var(--obs-deep)
  // El lienzo lo pone quien usa el chrome: un iframe (mesh, noVNC) o el div de
  // xterm. Se estiran por flex y no por width/height al 100%, para no depender
  // de un selector de hijo directo dentro de :deep() — esbuild no lo parsea al
  // minificar y el aviso se confunde con los dos que el proyecto ya arrastra.
  :deep(iframe),
  :deep(.xterm-container)
    display: block
    flex: 1 1 auto
    min-width: 0
    border: 0
// Pantallas angostas: los botones bajan a su fila para que el hostname y el
// estado conserven el ancho (misma regla que .obs-agenthdr a 700 px).
@media (max-width: 700px)
  .obs-remote__head
    flex-wrap: wrap
  .obs-remote__btns
    width: 100%
    order: 2
    flex-wrap: wrap
</style>
