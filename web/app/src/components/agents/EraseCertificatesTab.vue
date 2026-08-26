<template>
  <div class="q-pa-sm">
    <div class="row items-center q-mb-sm">
      <div class="text-subtitle2">{{ $t("erase.tab.title") }}</div>
      <q-space />
      <q-btn
        dense
        flat
        no-caps
        icon="refresh"
        color="primary"
        :loading="loading"
        :label="$t('erase.tab.refresh')"
        @click="load"
      />
    </div>

    <!-- El certificado sobrevive al equipo: se emite contra el activo y no
         contra la señal del agente, así que la pestaña aplica a cualquier
         plataforma, no sólo Windows. -->
    <EraseCertificatesTable
      :rows="rows"
      :loading="loading"
      @view="openDetail"
    />

    <div v-if="!loading && !rows.length" class="text-caption text-grey q-mt-sm">
      {{ $t("erase.tab.empty") }}
    </div>
  </div>
</template>

<script>
// Feature 039 · Observer Erase · T031 — certificados de borrado de un equipo.
//
// Pestaña de nivel superior de la ficha del activo (hermana de Activos/Auditoría),
// no dentro de Activos: ese panel es Windows-only y un certificado de borrado no
// lo es. Recorta la reportería al equipo con `?agent_id=`; el alcance por
// cliente/sitio lo sigue aplicando el servidor.

import { onMounted, ref, watch, computed } from "vue";
import { useStore } from "vuex";
import { useQuasar } from "quasar";

import EraseCertificatesTable from "@/components/agents/EraseCertificatesTable.vue";
import EraseCertificateDetailDialog from "@/components/agents/EraseCertificateDetailDialog.vue";
import { fetchEraseCertificates } from "@/api/erase";

export default {
  name: "EraseCertificatesTab",
  components: { EraseCertificatesTable },
  setup() {
    const store = useStore();
    const $q = useQuasar();
    const selectedAgent = computed(() => store.state.selectedRow);

    const rows = ref([]);
    const loading = ref(false);

    async function load() {
      if (!selectedAgent.value) return;
      loading.value = true;
      try {
        rows.value = (await fetchEraseCertificates(selectedAgent.value)) ?? [];
      } finally {
        loading.value = false;
      }
    }

    function openDetail(row) {
      $q.dialog({
        component: EraseCertificateDetailDialog,
        componentProps: { pk: row.id },
      });
    }

    watch(selectedAgent, (value) => {
      if (value) load();
    });

    onMounted(() => {
      if (selectedAgent.value) load();
    });

    return { rows, loading, load, openDetail };
  },
};
</script>
