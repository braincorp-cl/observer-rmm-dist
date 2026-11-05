<template>
  <!--
    050 (V2-S06): la maqueta de acceso, `referencia/acceso.png`.

    Dos paneles. A la izquierda la franja de marca: la marca circular y
    «Observer RMM» arriba, y abajo el titular con su bajada. A la derecha el
    panel de formulario: encabezado propio, los campos con el rótulo ARRIBA —no
    de placeholder dentro, que es como lo hacía la v1— y un pie opcional.

    🪤 Por qué existe este componente y no cinco copias: V2-S06 salió 🔴 en su
    primera corrida porque T049 restiló la tarjeta de la v1 en tres pantallas y
    no tocó las otras dos (`SessionExpired.vue` tenía CERO commits). Con la
    maqueta en un solo sitio, una pantalla nueva del flujo de acceso no puede
    nacer fuera de ella.

    Todo el color sale de tokens --obs-* / --q-* (V2-G02): la franja va en
    `--obs-surface` y el panel en `--obs-page`, que es el escalón de la maqueta.
  -->
  <q-layout>
    <q-page-container>
      <q-page class="obs-ws obs-access">
        <aside class="obs-access__brand">
          <div class="obs-access__mark">
            <img
              :src="marca"
              class="obs-access__mark-img"
              width="32"
              height="32"
              alt=""
            />
            <span class="obs-access__wordmark">Observer RMM</span>
          </div>
          <!-- El titular es la promesa del producto, no un rótulo de pantalla:
               se queda igual en las cinco. -->
          <div class="obs-access__pitch">
            <p class="obs-access__headline">{{ $t("access.headline") }}</p>
            <p class="obs-access__sub">{{ $t("access.subhead") }}</p>
          </div>
        </aside>

        <!-- 🪤 Esto fue un <main> hasta que axe lo cazó: QPage YA renderiza <main>
             (QPage.js:58), así que había DOS y anidados. Daba tres violaciones de
             landmark a la vez: main-is-top-level, no-duplicate-main y unique. Un
             div no quita semántica —el main de la página sigue ahí— y las quita
             las tres. -->
        <div class="obs-access__panel">
          <div class="obs-access__form">
            <h1 v-if="heading" class="obs-access__heading">{{ heading }}</h1>
            <slot />
            <p v-if="footnote" class="obs-access__foot">{{ footnote }}</p>
            <slot name="foot" />
          </div>
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup>
import { onBeforeUnmount } from "vue";
import { useQuasar } from "quasar";
import marca from "@/assets/ormm_mark_128.png";

const props = defineProps({
  // Encabezado del panel derecho («Ingresar»). Vacío = sin encabezado.
  heading: { type: String, default: "" },
  // Línea de ayuda bajo el formulario (el aviso de los dos pasos en el login).
  footnote: { type: String, default: "" },
  // 050 (cableado T047): el acceso va oscuro, pero `$q.dark` es estado GLOBAL.
  // Las rutas SIN sesión no pasan por `getDashInfo`, así que entrar a /login y
  // seguir a /verificar dejaba el portal público oscuro. Acá el oscuro vale
  // mientras la pantalla está montada y al desmontarse se devuelve lo que
  // había. Solo lo piden las pantallas PREVIAS a la sesión (login, setup,
  // totp): en /expired y /404 el usuario ya tiene tema elegido y se respeta,
  // que además es lo que permite medir el ítem «en ambos temas».
  forceDark: { type: Boolean, default: false },
});

const $q = useQuasar();
if (props.forceDark) {
  const darkPrevio = $q.dark.isActive;
  $q.dark.set(true);
  onBeforeUnmount(() => {
    $q.dark.set(darkPrevio);
  });
}
</script>

<style lang="sass" scoped>
.obs-access
  display: flex
  min-height: 100vh
  background: var(--obs-page)
// Franja de marca. En la maqueta ocupa 617 de 1440 ≈ 43 %, y el titular se
// apoya abajo, no al centro.
.obs-access__brand
  flex: 0 0 43%
  display: flex
  flex-direction: column
  justify-content: space-between
  padding: 48px
  background: var(--obs-surface)
  border-right: 1px solid var(--obs-border)
.obs-access__mark
  display: flex
  align-items: center
  gap: 12px
.obs-access__mark-img
  display: block
  width: 32px
  height: 32px
.obs-access__wordmark
  font-size: 20px
  font-weight: 700
  color: var(--obs-text)
.obs-access__pitch
  max-width: 520px
  padding-bottom: 10vh
.obs-access__headline
  margin: 0 0 12px
  font-size: 34px
  line-height: 1.15
  font-weight: 700
  color: var(--obs-text)
.obs-access__sub
  margin: 0
  font-size: 14px
  line-height: 1.5
  color: var(--obs-text-2)
.obs-access__panel
  flex: 1 1 auto
  min-width: 0
  display: flex
  align-items: center
  justify-content: center
  padding: 48px 24px
.obs-access__form
  width: 100%
  max-width: 380px
.obs-access__heading
  margin: 0 0 20px
  font-size: 22px
  line-height: 1.25
  font-weight: 700
  color: var(--obs-text)
.obs-access__foot
  margin: 16px 0 0
  font-size: 12.5px
  line-height: 1.45
  color: var(--obs-text-2)
// Rótulos ARRIBA del campo, como la maqueta. La v1 los metía de placeholder
// dentro del control, que desaparece al escribir.
:deep(.obs-access__label)
  display: block
  margin-bottom: 6px
  font-size: 12.5px
  color: var(--obs-text-2)
:deep(.obs-access__field)
  margin-bottom: 16px
// Angosto: la franja no cabe en dos columnas, así que se vuelve una cabecera
// con la marca y el titular, y el formulario queda debajo. No se pierde nada
// de la maqueta, se apila.
@media (max-width: 900px)
  .obs-access
    flex-direction: column
    min-height: 100vh
  .obs-access__brand
    flex: none
    padding: 24px
    border-right: 0
    border-bottom: 1px solid var(--obs-border)
    gap: 20px
  .obs-access__pitch
    padding-bottom: 0
  .obs-access__headline
    font-size: 24px
  .obs-access__panel
    padding: 32px 24px
</style>
