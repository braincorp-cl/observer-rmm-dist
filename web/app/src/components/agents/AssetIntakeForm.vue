<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card class="q-dialog-plugin" style="min-width: 45vw">
      <q-bar>
        {{ $t("erase.intakeForm.title") }}
        <q-space />
        <q-btn dense flat icon="close" v-close-popup>
          <q-tooltip>{{ $t("erase.intakeForm.cancel") }}</q-tooltip>
        </q-btn>
      </q-bar>

      <q-form ref="form" @submit="onSubmit">
        <q-card-section class="scroll" style="max-height: 65vh">
          <!-- D1: el ingreso ancla la cadena de custodia. El cliente es
               obligatorio (recorta el aislamiento multi-tenant); el resto
               identifica el equipo y el medio. -->
          <div class="row q-col-gutter-md">
            <q-select
              class="col-12 col-sm-6"
              dense
              filled
              emit-value
              map-options
              v-model="intake.client"
              :options="clientOptions"
              :label="$t('erase.intakeForm.client')"
              :rules="[(val) => !!val || $t('erase.intakeForm.required')]"
              @update:model-value="onClientChange"
            />
            <q-select
              class="col-12 col-sm-6"
              dense
              filled
              clearable
              emit-value
              map-options
              v-model="intake.site"
              :options="siteOptions"
              :label="$t('erase.intakeForm.site')"
              :disable="!intake.client"
            />
            <q-select
              class="col-12 col-sm-6"
              dense
              filled
              emit-value
              map-options
              v-model="intake.state"
              :options="stateOptions"
              :label="$t('erase.intakeForm.state')"
            />
            <q-input
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.asset_tag"
              :label="$t('erase.intakeForm.assetTag')"
            />
            <q-input
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.equipment_serial"
              :label="$t('erase.intakeForm.equipmentSerial')"
            />
            <q-input
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.media_serial"
              :label="$t('erase.intakeForm.mediaSerial')"
            />
            <q-input
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.ticket_ref"
              :label="$t('erase.intakeForm.ticketRef')"
            />
            <q-input
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.delivered_by"
              :label="$t('erase.intakeForm.deliveredBy')"
            />
            <q-input
              class="col-12"
              dense
              filled
              type="textarea"
              autogrow
              v-model="intake.notes"
              :label="$t('erase.intakeForm.notes')"
            />
          </div>

          <!-- Regla D1: un activo no funcional o sin medio detectable se enruta
               directo a destrucción física. Se avisa acá para que el operador
               no espere un borrado lógico que no va a ocurrir. -->
          <q-banner
            v-if="routesToPhysical"
            dense
            class="bg-orange-1 text-orange-9 q-mt-md"
          >
            <template v-slot:avatar>
              <q-icon name="warning" color="warning" />
            </template>
            {{ $t("erase.intakeForm.physicalRouteNotice") }}
          </q-banner>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn
            flat
            :label="$t('erase.intakeForm.cancel')"
            v-close-popup
          />
          <q-btn
            :loading="loading"
            color="primary"
            :label="$t('erase.intakeForm.save')"
            type="submit"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script>
// Feature 039 · Observer Erase · T032 — ingreso de activo a baja (D1).
//
// Formaliza la recepción antes de cualquier operación. El `process_id` y el
// `received_by` los pone el servidor (no se escriben acá). Si el equipo está
// no funcional o sin medio, el propio registro enruta a destrucción física.

import { onMounted, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent } from "quasar";

import { fetchClients } from "@/api/clients";
import { createAssetIntake } from "@/api/erase";
import { notifySuccess } from "@/utils/notify";

export default {
  name: "AssetIntakeForm",
  emits: [...useDialogPluginComponent.emits],
  setup() {
    const { t } = useI18n();
    const { dialogRef, onDialogHide, onDialogOK } = useDialogPluginComponent();

    const clients = ref([]);
    const clientOptions = ref([]);
    const siteOptions = ref([]);
    const loading = ref(false);

    const intake = ref({
      client: null,
      site: null,
      state: "functional",
      asset_tag: "",
      equipment_serial: "",
      media_serial: "",
      ticket_ref: "",
      delivered_by: "",
      notes: "",
    });

    const stateOptions = [
      { value: "functional", label: t("erase.intake.state.functional") },
      { value: "non_functional", label: t("erase.intake.state.non_functional") },
      { value: "no_media", label: t("erase.intake.state.no_media") },
    ];

    const routesToPhysical = computed(
      () =>
        intake.value.state === "non_functional" ||
        intake.value.state === "no_media",
    );

    async function loadClients() {
      const data = (await fetchClients()) ?? [];
      clients.value = data;
      clientOptions.value = data.map((c) => ({ value: c.id, label: c.name }));
    }

    function onClientChange() {
      intake.value.site = null;
      const client = clients.value.find((c) => c.id === intake.value.client);
      siteOptions.value = (client?.sites ?? []).map((s) => ({
        value: s.id,
        label: s.name,
      }));
    }

    async function onSubmit() {
      loading.value = true;
      try {
        const created = await createAssetIntake(intake.value);
        notifySuccess(
          t("erase.intakeForm.created", { id: created.process_id }),
        );
        onDialogOK(created);
      } catch (e) {
        console.error(e);
      } finally {
        loading.value = false;
      }
    }

    onMounted(loadClients);

    return {
      dialogRef,
      onDialogHide,
      intake,
      clientOptions,
      siteOptions,
      stateOptions,
      routesToPhysical,
      loading,
      onClientChange,
      onSubmit,
    };
  },
};
</script>
