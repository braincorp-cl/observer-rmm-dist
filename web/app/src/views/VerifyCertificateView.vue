<template>
  <!--
    Portal PÚBLICO de verificación (053 · ola 4). Fuera de MainLayout: lo abre
    un tercero sin cuenta —un cliente, un auditor, un tribunal—.

    050 (cableado T047): llegaba del merge con el chrome de la v1 (un `div
    q-pa-md` con grilla, `text-h6` y banners `bg-orange-1`/`bg-grey-3`). Pasa al
    patrón de las pantallas de acceso (T049), que es el único de la v2 que vive
    fuera de MainLayout: q-layout / q-page-container / q-page centrada con
    `obs-ws` como ámbito de tokens —sin él los grises internos de Quasar no
    siguen al tema (V2-G02)— y el título en `obs-page__title` dentro de una
    q-card centrada.

    Marca de PRODUCTO y nada más: logo, nombre del producto y una línea que dice
    qué es esta página. NO va el nombre del tenant ni del cliente —el portal lo
    abre un tercero y el certificado ya dice de quién es— y NO va chrome de
    navegación: desde una página pública no hay a dónde ir.
  -->
  <q-layout>
    <q-page-container>
      <q-page class="flex flex-center obs-ws">
        <!-- Si el tenant lo tiene apagado, el backend responde 404 y acá se
             muestra el NotFound genérico del producto: un mensaje propio del
             tipo «portal deshabilitado» confirmaría que la función existe. En
             contexto público va SIN el botón «Volver» (no hay a dónde). -->
        <NotFound v-if="portalApagado" public-context />
        <q-card
          v-else
          v-bind:style="$q.screen.lt.sm ? { width: '80%' } : { width: '30%' }"
        >
          <q-card-section class="text-center q-pt-lg">
            <img
              :src="productMark"
              alt=""
              width="56"
              height="56"
              class="obs-verify__mark"
            />
            <h1 class="obs-page__title ellipsis">Observer RMM</h1>
            <div class="obs-verify__lead">{{ $t("erase.verify.title") }}</div>
          </q-card-section>

          <q-card-section>
            <div class="text-caption obs-text-muted q-mb-md">
              {{ $t("erase.verify.subtitle") }}
            </div>
            <q-input
              v-model="identificador"
              outlined
              dense
              autofocus
              :label="$t('erase.verify.inputLabel')"
              :hint="$t('erase.verify.inputHint')"
              @keyup.enter="verificar"
            />
          </q-card-section>

          <q-card-actions align="right">
            <q-btn
              unelevated
              no-caps
              color="primary"
              class="obs-page__btn full-width"
              :label="$t('erase.verify.submit')"
              :loading="cargando"
              :disable="!identificador"
              @click="verificar"
            />
          </q-card-actions>

          <q-separator v-if="resultado || limitado" />

          <q-card-section v-if="limitado">
            <q-banner dense class="obs-notice">
              <template v-slot:avatar>
                <q-icon name="hourglass_top" />
              </template>
              {{ $t("erase.verify.throttled") }}
            </q-banner>
          </q-card-section>

          <q-card-section v-else-if="resultado && !resultado.found">
            <q-banner dense class="obs-notice">
              <template v-slot:avatar>
                <q-icon name="search_off" />
              </template>
              {{ $t("erase.verify.notFound") }}
            </q-banner>
          </q-card-section>

          <q-card-section v-else-if="resultado">
            <div class="text-subtitle2 mono q-mb-sm">
              {{ resultado.certificate_id }}
            </div>
            <div class="text-caption obs-text-muted q-mb-md">
              {{
                $t("erase.verify.issuedAtLine", {
                  value: formatearFecha(resultado.issued_at),
                })
              }}
              <br />
              {{ $t("erase.verify.kindLine", { value: resultado.kind }) }}
            </div>
            <q-chip
              v-for="v in veredictos"
              :key="v.clave"
              :color="resultado[v.clave] ? 'positive' : 'negative'"
              text-color="white"
              :icon="resultado[v.clave] ? 'check' : 'close'"
            >
              {{ $t(v.etiqueta) }}
            </q-chip>
            <div class="q-mt-md text-weight-medium">
              {{
                resultado.valid
                  ? $t("erase.verify.verdictValid")
                  : $t("erase.verify.verdictInvalid")
              }}
            </div>
          </q-card-section>

          <q-separator />

          <q-card-section class="text-caption obs-text-muted">
            <!-- La vía offline no se reemplaza: prueba la AUTORÍA de la firma
                 sin preguntarle nada a este servidor. El portal agrega lo único
                 que un tercero no puede comprobar solo, el encadenamiento. -->
            {{ $t("erase.verify.offlineNotice") }}
            <a :href="signingKeyUrl" target="_blank" rel="noopener">{{
              $t("erase.verify.offlineLink")
            }}</a>
          </q-card-section>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { getBaseUrl } from "@/boot/axios";
import NotFound from "@/views/NotFound.vue";
import productMark from "@/assets/ormm_mark_128.png";

const route = useRoute();

const identificador = ref("");
const resultado = ref(null);
const cargando = ref(false);
const limitado = ref(false);
const portalApagado = ref(false);

const signingKeyUrl = `${getBaseUrl()}/erase/signing-key/`;

const veredictos = [
  { clave: "document_intact", etiqueta: "erase.verify.documentIntact" },
  { clave: "signature_valid", etiqueta: "erase.verify.signatureValid" },
  { clave: "chain_intact", etiqueta: "erase.verify.chainIntact" },
];

function formatearFecha(valor) {
  if (!valor) return "—";
  return new Date(valor).toLocaleString();
}

// fetch y no axios: el interceptor global muestra un toast en cada 4xx y
// redirige en 401, y acá un 404 o un 429 son respuestas ESPERADAS que la página
// explica por sí misma.
async function verificar() {
  if (!identificador.value) return;
  cargando.value = true;
  resultado.value = null;
  limitado.value = false;
  try {
    const r = await fetch(
      `${getBaseUrl()}/erase/verify/${encodeURIComponent(identificador.value.trim())}/`,
    );
    if (r.status === 404) {
      portalApagado.value = true;
      return;
    }
    if (r.status === 429) {
      limitado.value = true;
      return;
    }
    resultado.value = await r.json();
  } catch (e) {
    limitado.value = false;
    resultado.value = null;
  } finally {
    cargando.value = false;
  }
}

onMounted(() => {
  // Permite compartir el enlace ya con el identificador puesto, que es como se
  // imprime en un acta. No hay búsqueda ni listado: un buscador por serie o
  // cliente convertiría el portal en el oráculo que L-02 prohíbe.
  if (route.params.certificate_id) {
    identificador.value = route.params.certificate_id;
    verificar();
  }
});
</script>

<style lang="sass" scoped>
// Marca de producto del portal público: el logo y la línea que dice qué es la
// página. Sin tenant y sin navegación (decisión de producto): el único gesto de
// identidad acá es el del producto.
.obs-verify__mark
  display: block
  margin: 0 auto 10px
.obs-verify__lead
  margin-top: 6px
  font-size: 14px
  color: var(--obs-text-2)
</style>
