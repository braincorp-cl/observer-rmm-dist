<template>
  <div class="fixed-center text-center">
    <p class="text-faded">
      {{ $t("notFound.message") }}
      <strong>{{ $t("notFound.code") }}</strong>
    </p>
    <q-btn color="secondary" style="width: 200px" @click="$router.push('/')">
      {{ $t("notFound.goBack") }}
    </q-btn>
  </div>
</template>

<script>
export default {
  name: "NotFound",
};
</script>
