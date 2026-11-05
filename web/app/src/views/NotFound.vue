<template>
  <!--
    050 (V2-S06): el 404 en la maqueta de acceso.

    🪤 Esta vista tenía UN commit en la rama v2 y era sólo la prop
    `publicContext` del cableado de T047: nada visual. El gauntlet lo midió —
    0,17 % de diferencia con la v1 en los dos temas, acotado al texto y al
    botón.

    🔑 Pero el 404 tiene una vuelta que las otras cuatro no: se reusa EMBEBIDO
    dentro del portal público (`VerifyCertificateView` lo monta con
    `public-context` cuando el tenant tiene el portal apagado). Ahí no puede
    imponer el chrome de acceso: sería una franja de marca y una pantalla
    completa dentro de otra página, con dos marcas en pantalla. En contexto
    público se rinde como el fragmento que ya era, y es el anfitrión quien pone
    el marco.
  -->
  <div v-if="publicContext" class="obs-nf obs-nf--embebido">
    <p class="obs-nf__msg">
      {{ $t("notFound.message") }}
      <strong>{{ $t("notFound.code") }}</strong>
    </p>
  </div>

  <AccessLayout v-else :heading="$t('notFound.heading')">
    <p class="obs-nf__msg">
      {{ $t("notFound.message") }}
      <strong>{{ $t("notFound.code") }}</strong>
    </p>
    <!--
      050 (cableado T047): el botón nunca fue del contexto público. Ahí «Volver»
      empuja a "/", que para quien no tiene cuenta es un rebote al acceso: una
      página pública no tiene a dónde volver. Ahora esa rama ni siquiera llega
      hasta acá.
    -->
    <q-btn
      unelevated
      no-caps
      color="primary"
      class="obs-page__btn full-width"
      @click="$router.push('/')"
    >
      {{ $t("notFound.goBack") }}
    </q-btn>
  </AccessLayout>
</template>

<script>
import AccessLayout from "@/components/access/AccessLayout.vue";

export default {
  name: "NotFound",
  components: { AccessLayout },
  props: {
    // Lo pone quien la usa fuera del producto autenticado (el portal público).
    // El catchAll del router la monta sin prop ⇒ el 404 de la consola sigue
    // ofreciendo la salida al Dashboard, y con la maqueta de acceso.
    publicContext: { type: Boolean, default: false },
  },
};
</script>

<style lang="sass" scoped>
.obs-nf__msg
  margin: 0 0 20px
  font-size: 14px
  line-height: 1.5
  color: var(--obs-text-2)
.obs-nf--embebido
  text-align: center
  .obs-nf__msg
    margin: 0
</style>
