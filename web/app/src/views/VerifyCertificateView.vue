<template>
  <!-- Portal PÚBLICO de verificación (053 · ola 4). Fuera de MainLayout: lo abre
       un tercero sin cuenta. Si el tenant lo tiene apagado, el backend responde
       404 y acá se muestra el NotFound genérico del producto: un mensaje propio
       del tipo «portal deshabilitado» confirmaría que la función existe. -->
  <NotFound v-if="portalApagado" />
  <div v-else class="q-pa-md">
    <div class="row justify-center">
      <div class="col-12 col-md-6">
        <q-card>
          <q-card-section>
            <div class="text-h6">{{ $t("erase.verify.title") }}</div>
            <div class="text-caption text-grey-7">
              {{ $t("erase.verify.subtitle") }}
            </div>
          </q-card-section>

          <q-card-section>
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
              color="primary"
              :label="$t('erase.verify.submit')"
              :loading="cargando"
              :disable="!identificador"
              @click="verificar"
            />
          </q-card-actions>

          <q-separator v-if="resultado || limitado" />

          <q-card-section v-if="limitado">
            <q-banner dense class="bg-orange-1">
              {{ $t("erase.verify.throttled") }}
            </q-banner>
          </q-card-section>

          <q-card-section v-else-if="resultado && !resultado.found">
            <q-banner dense class="bg-grey-3">
              {{ $t("erase.verify.notFound") }}
            </q-banner>
          </q-card-section>

          <q-card-section v-else-if="resultado">
            <div class="text-subtitle2 q-mb-sm">
              {{ resultado.certificate_id }}
            </div>
            <div class="text-caption text-grey-7 q-mb-md">
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

          <q-card-section class="text-caption text-grey-7">
            <!-- La vía offline no se reemplaza: prueba la AUTORÍA de la firma
                 sin preguntarle nada a este servidor. El portal agrega lo único
                 que un tercero no puede comprobar solo, el encadenamiento. -->
            {{ $t("erase.verify.offlineNotice") }}
            <a :href="signingKeyUrl" target="_blank" rel="noopener">{{
              $t("erase.verify.offlineLink")
            }}</a>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { getBaseUrl } from "@/boot/axios";
import NotFound from "@/views/NotFound.vue";

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
