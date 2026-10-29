<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="min-width: 680px; max-width: 90vw">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="text-h6">{{ $t("erase.custody.title") }}</div>
          <div class="text-caption text-grey-7">
            {{ $t("erase.custody.subtitle") }}
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense v-close-popup />
      </q-card-section>

      <q-card-section>
        <div class="row items-center q-gutter-sm q-mb-sm">
          <q-chip
            dense
            :color="chainIntact ? 'positive' : 'negative'"
            text-color="white"
            :icon="chainIntact ? 'verified' : 'link_off'"
          >
            {{
              chainIntact
                ? $t("erase.custody.chainIntact")
                : $t("erase.custody.chainBroken")
            }}
          </q-chip>
          <div class="text-caption text-grey-7">
            {{ intake.process_id }} {{ sep }}
            {{ intake.equipment_serial || dash }}
          </div>
        </div>

        <!-- No hay botones de editar ni borrar, y no están escondidos: el
             servidor los rechaza. Corregir se hace añadiendo un eslabón. -->
        <q-banner dense class="bg-grey-2 text-grey-8 q-mb-md">
          <template v-slot:avatar><q-icon name="lock" /></template>
          {{ $t("erase.custody.immutableNotice") }}
        </q-banner>

        <div v-if="loading" class="text-center q-pa-md">
          <q-spinner size="2em" />
        </div>

        <div v-else-if="!events.length" class="text-grey-7 q-pa-md">
          {{ $t("erase.custody.empty") }}
          <div class="text-caption q-mt-xs">
            {{ $t("erase.custody.emptyLegacy") }}
          </div>
        </div>

        <!-- En orden de CADENA (id), no por fecha: un evento registrado tarde
             sobre un hecho antiguo no reordena los eslabones. -->
        <q-timeline v-else dense>
          <q-timeline-entry
            v-for="ev in events"
            :key="ev.id"
            :title="ev.kind_label || labelCustodyKind(ev.kind)"
            :subtitle="formatDate(ev.at)"
            :icon="iconFor(ev.kind)"
          >
            <div class="text-body2">
              <div v-if="ev.location">
                {{ campo("location", ev.location) }}
              </div>
              <div>{{ campo("actor", ev.actor || dash) }}</div>
              <div v-if="hasDetail(ev)" class="text-caption text-grey-7">
                {{ campo("detail", detailText(ev)) }}
              </div>
              <div class="text-caption text-grey-6 ellipsis">
                {{ campo("recordHash", corto(ev.record_hash)) }}
              </div>
            </div>
          </q-timeline-entry>
        </q-timeline>
      </q-card-section>

      <q-separator />

      <q-card-section>
        <div class="row q-col-gutter-sm">
          <q-select
            class="col-12 col-sm-4"
            dense
            filled
            emit-value
            map-options
            v-model="nuevo.kind"
            :options="kindOptions"
            :label="$t('erase.custody.kind')"
          />
          <q-input
            class="col-12 col-sm-4"
            dense
            filled
            type="datetime-local"
            v-model="nuevo.at"
            :label="$t('erase.custody.at')"
            :hint="$t('erase.custody.atHint')"
          />
          <q-input
            class="col-12 col-sm-4"
            dense
            filled
            v-model="nuevo.location"
            :label="$t('erase.custody.location')"
          />
        </div>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat :label="$t('erase.detail.close')" v-close-popup />
        <q-btn
          color="primary"
          :loading="saving"
          :disable="!nuevo.kind"
          :label="$t('erase.custody.add')"
          @click="agregar"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";
import { fetchCustodyEvents, createCustodyEvent } from "@/api/erase";
import { labelCustodyKind } from "@/utils/erase";
import { notifySuccess } from "@/utils/notify";
import { formatDate } from "@/utils/format";

// Mismo orden que `CustodyEventKind` en el modelo, menos `received`: ese lo
// escribe el servidor al crear el acta y el backend rechaza un segundo.
const KINDS = [
  "relocated",
  "stored",
  "handed_to_processor",
  "sanitized",
  "destroyed",
  "returned",
];

const ICONOS = {
  received: "inventory_2",
  relocated: "local_shipping",
  stored: "warehouse",
  handed_to_processor: "factory",
  sanitized: "cleaning_services",
  destroyed: "delete_forever",
  returned: "assignment_return",
};

export default {
  name: "AssetCustodyTimeline",
  props: {
    intakeId: { type: Number, required: true },
  },
  emits: [...useDialogPluginComponent.emits],
  setup(props) {
    const { dialogRef, onDialogHide } = useDialogPluginComponent();
    const { t } = useI18n();

    const dash = "—";
    const sep = "·";
    const loading = ref(false);
    const saving = ref(false);
    const events = ref([]);
    const intake = ref({});
    const chainIntact = ref(true);
    const nuevo = ref({ kind: null, at: "", location: "" });

    const kindOptions = KINDS.map((value) => ({
      value,
      label: t(`erase.custody.kinds.${value}`),
    }));

    const cargar = async () => {
      loading.value = true;
      try {
        const data = await fetchCustodyEvents(props.intakeId);
        events.value = data.events ?? [];
        intake.value = data.intake ?? {};
        chainIntact.value = data.chain_intact ?? false;
      } finally {
        loading.value = false;
      }
    };

    const agregar = async () => {
      saving.value = true;
      try {
        // `at` vacío = ahora, que es lo que decide el servidor. Mandarlo vacío
        // sería una fecha inválida.
        const payload = { kind: nuevo.value.kind };
        if (nuevo.value.at) payload.at = new Date(nuevo.value.at).toISOString();
        if (nuevo.value.location) payload.location = nuevo.value.location;
        await createCustodyEvent(props.intakeId, payload);
        notifySuccess(t("erase.custody.added"));
        nuevo.value = { kind: null, at: "", location: "" };
        await cargar();
      } finally {
        saving.value = false;
      }
    };

    onMounted(cargar);

    return {
      dialogRef,
      onDialogHide,
      dash,
      sep,
      loading,
      saving,
      events,
      intake,
      chainIntact,
      nuevo,
      kindOptions,
      agregar,
      labelCustodyKind,
      formatDate,
      iconFor: (kind) => ICONOS[kind] || "radio_button_unchecked",
      // El `: ` va acá y no en la plantilla: el gate `lint:i18n` trata
      // cualquier texto crudo en el template como falta de traducción.
      campo: (clave, valor) => `${t(`erase.custody.${clave}`)}: ${valor}`,
      corto: (hash) => `${(hash || "").slice(0, 16)}…`,
      hasDetail: (ev) => ev.detail && Object.keys(ev.detail).length > 0,
      detailText: (ev) =>
        Object.entries(ev.detail || {})
          .map(([k, v]) => `${k}: ${v}`)
          .join(" · "),
    };
  },
};
</script>
