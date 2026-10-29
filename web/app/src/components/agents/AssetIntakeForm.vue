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
            <!-- Feature 053 · RF-12: el equipo es lo que permite que esta acta
                 sirva de expediente para una orden de borrado o de rescate. Es
                 OPCIONAL a propósito — un disco suelto no tiene equipo— y se
                 filtra por el cliente (o el sitio, si ya se eligió). -->
            <q-select
              class="col-12 col-sm-6"
              dense
              filled
              clearable
              use-input
              input-debounce="200"
              emit-value
              map-options
              v-model="intake.agent"
              :options="agentOptionsFiltered"
              :label="$t('erase.intakeForm.equipment')"
              :hint="$t('erase.intakeForm.equipmentHint')"
              :disable="!intake.client"
              :loading="loadingAgents"
              @filter="filterAgents"
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
            <!-- RF-10: un lector USB de codigo de barras ES un teclado
                 (HID): teclea el codigo en el campo con foco y manda Enter. Lo
                 unico que hay que construir es que ese Enter NO envie el acta a
                 medio llenar y pase al siguiente campo de serie, que es el
                 gesto que el operador espera: escanear, escanear, escanear.
                 Sin camara y sin dependencias nuevas. -->
            <q-input
              ref="campoAssetTag"
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.asset_tag"
              :label="$t('erase.intakeForm.assetTag')"
              :hint="$t('erase.intakeScanHint')"
              @keydown.enter.prevent="enfocarSerie('campoEquipmentSerial')"
            />
            <!-- RF-04: el técnico los teclea al recibir. No se leen del
                 inventario porque un disco suelto o un equipo nunca enrolado
                 no tiene de dónde leerlos, y el certificado los necesita. -->
            <q-input
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.equipment_make"
              :label="$t('erase.intakeForm.equipmentMake')"
            />
            <q-input
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.equipment_model"
              :label="$t('erase.intakeForm.equipmentModel')"
            />
            <q-input
              ref="campoEquipmentSerial"
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.equipment_serial"
              :label="$t('erase.intakeForm.equipmentSerial')"
              :hint="$t('erase.intakeScanHint')"
              @keydown.enter.prevent="enfocarSerie('campoMediaSerial')"
            />
            <q-input
              ref="campoMediaSerial"
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.media_serial"
              :label="$t('erase.intakeForm.mediaSerial')"
              :hint="$t('erase.intakeScanHint')"
              @keydown.enter.prevent="enfocarSerie(null)"
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
            <!-- RF-09: tipo de medio. Lo teclea quien recibe, porque un disco
                 suelto o un equipo nunca enrolado no tiene inventario del cual
                 leerlo. Vacío = no consta. -->
            <q-select
              class="col-12 col-sm-6"
              dense
              filled
              clearable
              emit-value
              map-options
              v-model="intake.media_type"
              :options="mediaTypeOptions"
              :label="$t('erase.intakeForm.mediaType')"
              :hint="$t('erase.intakeForm.mediaTypeHint')"
            />
            <!-- RF-03: el mínimo del Apéndice C exige declarar dónde quedó el
                 medio. Vacío es válido: significa que todavía no consta. -->
            <q-select
              class="col-12 col-sm-6"
              dense
              filled
              clearable
              emit-value
              map-options
              v-model="intake.media_disposition"
              :options="dispositionOptions"
              :label="$t('erase.intakeForm.disposition')"
              :hint="$t('erase.intakeForm.dispositionHint')"
            />
            <q-input
              v-if="intake.media_disposition === 'other'"
              class="col-12 col-sm-6"
              dense
              filled
              v-model="intake.media_disposition_detail"
              :label="$t('erase.intakeForm.dispositionDetail')"
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
          <q-btn flat :label="$t('erase.intakeForm.cancel')" v-close-popup />
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

import { fetchAgents } from "@/api/agents";
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
    const agentOptions = ref([]);
    const agentOptionsFiltered = ref([]);
    const loadingAgents = ref(false);
    const loading = ref(false);

    // RF-10: refs de los tres campos de serie, para que el Enter del lector
    // mueva el foco en vez de enviar el acta.
    const campoAssetTag = ref(null);
    const campoEquipmentSerial = ref(null);
    const campoMediaSerial = ref(null);
    const camposDeSerie = {
      campoAssetTag,
      campoEquipmentSerial,
      campoMediaSerial,
    };

    function enfocarSerie(siguiente) {
      // `null` = ultimo campo de la cadena: se suelta el foco y NO se envia.
      // Enviar acá seria justo el defecto que RF-10 arregla, porque el operador
      // todavia tiene que elegir destino del medio y quien entrega.
      if (!siguiente) return;
      const campo = camposDeSerie[siguiente];
      if (campo && campo.value) campo.value.focus();
    }

    const intake = ref({
      client: null,
      site: null,
      // Feature 053: el equipo es el que convierte esta acta en expediente
      // (RF-12). Opcional — un disco suelto no tiene equipo.
      agent: null,
      state: "functional",
      asset_tag: "",
      equipment_make: "",
      equipment_model: "",
      equipment_serial: "",
      media_serial: "",
      media_type: "",
      media_disposition: "",
      media_disposition_detail: "",
      ticket_ref: "",
      delivered_by: "",
      notes: "",
    });

    const stateOptions = [
      { value: "functional", label: t("erase.intake.state.functional") },
      {
        value: "non_functional",
        label: t("erase.intake.state.non_functional"),
      },
      { value: "no_media", label: t("erase.intake.state.no_media") },
    ];

    // Mismo orden que `MediaType` en el modelo.
    const mediaTypeOptions = [
      "hdd",
      "ssd",
      "nvme",
      "optical",
      "tape",
      "mobile",
      "other",
    ].map((value) => ({ value, label: t(`erase.mediaType.${value}`) }));

    // Mismo orden que `MediaDisposition` en el modelo.
    const dispositionOptions = [
      "internal_reuse",
      "external_reuse",
      "returned",
      "recycled",
      "destroyed",
      "retained",
      "other",
    ].map((value) => ({ value, label: t(`erase.disposition.${value}`) }));

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
      loadAgents();
    }

    async function loadAgents() {
      intake.value.agent = null;
      agentOptions.value = [];
      agentOptionsFiltered.value = [];
      if (!intake.value.client) return;
      loadingAgents.value = true;
      try {
        // `detail: false` no es un ahorro, es un requisito: el serializer de la
        // tabla NO devuelve el `id`, y la FK del acta se guarda por pk.
        const data =
          (await fetchAgents({ client: intake.value.client, detail: false })) ??
          [];
        agentOptions.value = data.map((a) => ({
          value: a.id,
          label: a.site ? `${a.hostname} · ${a.site}` : a.hostname,
        }));
        agentOptionsFiltered.value = agentOptions.value;
      } finally {
        loadingAgents.value = false;
      }
    }

    function filterAgents(texto, update) {
      update(() => {
        const aguja = (texto ?? "").toLowerCase();
        agentOptionsFiltered.value = aguja
          ? agentOptions.value.filter((o) =>
              o.label.toLowerCase().includes(aguja),
            )
          : agentOptions.value;
      });
    }

    async function onSubmit() {
      loading.value = true;
      try {
        // Los `q-select` con `clearable` dejan `null` al limpiarse, y los campos
        // de texto del acta son `blank=True` pero NO `null=True`: mandar `null`
        // los rechaza con "This field may not be null". El `agent` sí admite
        // null, porque su FK lo permite.
        const payload = { ...intake.value };
        for (const campo of [
          "media_type",
          "media_disposition",
          "media_disposition_detail",
        ]) {
          payload[campo] = payload[campo] ?? "";
        }
        // El detalle sólo tiene sentido con destino "otro"; si se cambió el
        // destino después de escribirlo, no se arrastra.
        if (payload.media_disposition !== "other") {
          payload.media_disposition_detail = "";
        }
        const created = await createAssetIntake(payload);
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
      campoAssetTag,
      campoEquipmentSerial,
      campoMediaSerial,
      enfocarSerie,
      clientOptions,
      siteOptions,
      agentOptionsFiltered,
      stateOptions,
      mediaTypeOptions,
      dispositionOptions,
      routesToPhysical,
      loading,
      loadingAgents,
      onClientChange,
      filterAgents,
      onSubmit,
    };
  },
};
</script>
