<template>
  <div class="fixed-center text-center">
    <p class="text-faded">
      {{ $t("notFound.message") }}
      <strong>{{ $t("notFound.code") }}</strong>
    </p>
    <!--
      050 (cableado T047): en contexto PÚBLICO el botón no va. Esta vista se
      reusa como cuerpo del portal de verificación cuando el tenant lo tiene
      apagado, y ahí «Volver» empuja a "/", que para quien no tiene cuenta es un
      rebote al acceso: una página pública no tiene a dónde volver.
    -->
    <q-btn
      v-if="!publicContext"
      color="secondary"
      style="width: 200px"
      @click="$router.push('/')"
    >
      {{ $t("notFound.goBack") }}
    </q-btn>
  </div>
</template>

<script>
export default {
  name: "NotFound",
  props: {
    // Lo pone quien la usa fuera del producto autenticado (el portal público).
    // El catchAll del router la monta sin prop ⇒ el 404 de la consola sigue
    // ofreciendo la salida al Dashboard.
    publicContext: { type: Boolean, default: false },
  },
};
</script>
