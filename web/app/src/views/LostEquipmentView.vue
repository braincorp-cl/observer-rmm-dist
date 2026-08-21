<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">{{ $t("lostEquipment.title") }}</div>
      <q-space />
      <q-btn
        dense
        flat
        icon="refresh"
        :loading="loading"
        @click="load"
        :aria-label="$t('lostEquipment.refresh')"
      >
        <q-tooltip>{{ $t("lostEquipment.refresh") }}</q-tooltip>
      </q-btn>
    </div>

    <!-- El color de texto va EXPLICITO junto al de fondo: `bg-grey-3` sola deja
         el texto heredando el del tema, y en modo oscuro eso es texto claro sobre
         gris claro -- el aviso de gobernanza quedaba ilegible justo en el modulo
         donde mas importa que se lea. Mismo par que usan los otros banners del
         producto (`text-black bg-warning` en ScriptFormModal). -->
    <q-banner dense class="bg-grey-3 text-black q-mb-md">
      <template v-slot:avatar>
        <q-icon name="policy" color="primary" />
      </template>
      {{ $t("lostEquipment.governanceNotice") }}
    </q-banner>

    <q-table
      dense
      flat
      bordered
      row-key="agent_id"
      @row-click="openTimeline"
      :rows="rows"
      :columns="columns"
      :loading="loading"
      :rows-per-page-options="[25, 50, 0]"
      :no-data-label="$t('lostEquipment.noData')"
      :loading-label="$t('lostEquipment.loading')"
    >
      <template v-slot:body-cell-marked_at="props">
        <q-td :props="props">{{ formatDate(props.row.marked_at) }}</q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props">
          <!-- T023 · paraguas 028. Las tres acciones de la 028 se alcanzan
               desde acá y no sólo desde el menú del equipo: quien opera un caso
               está en ESTA pantalla, y obligarlo a buscar el equipo en el
               listado general para bloquearlo es el minuto que no tiene. Son
               las mismas llamadas y los mismos modales, sin copia. -->
          <q-btn
            dense
            flat
            round
            color="primary"
            icon="more_vert"
            @click.stop
            :aria-label="$t('lostEquipment.colActions')"
          >
            <q-menu auto-close>
              <q-list dense style="min-width: 210px">
                <q-item clickable @click="lockScreen(props.row)">
                  <q-item-section avatar>
                    <q-icon name="lock" size="xs" />
                  </q-item-section>
                  <q-item-section>{{ $t("endpointResponse.lock") }}</q-item-section>
                </q-item>

                <q-item clickable @click="showAlertModal(props.row)">
                  <q-item-section avatar>
                    <q-icon name="campaign" size="xs" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("endpointResponse.sendAlert")
                  }}</q-item-section>
                </q-item>

                <q-item clickable @click="soundAlarm(props.row)">
                  <q-item-section avatar>
                    <q-icon name="volume_up" size="xs" />
                  </q-item-section>
                  <q-item-section>{{ $t("endpointResponse.alarm") }}</q-item-section>
                </q-item>

                <q-item clickable @click="stopAlarm(props.row)">
                  <q-item-section avatar>
                    <q-icon name="volume_off" size="xs" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("endpointResponse.stopAlarm")
                  }}</q-item-section>
                </q-item>

                <q-separator />

                <!-- T022 · el caso completo en un PDF, para que salga de la
                     consola y entre en una denuncia. -->
                <q-item clickable @click="exportCase(props.row)">
                  <q-item-section avatar>
                    <q-icon name="picture_as_pdf" size="xs" />
                  </q-item-section>
                  <q-item-section>{{
                    $t("lostEquipment.exportCase")
                  }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>

          <q-btn
            dense
            flat
            no-caps
            color="primary"
            icon="check_circle"
            :label="$t('lostEquipment.recover')"
            @click.stop="askRecover(props.row)"
          />
        </q-td>
      </template>
    </q-table>

    <!-- Detalle del caso: un renglón por ciclo de captura (punto en el mapa +
         miniatura de la pantalla). Se abre al pinchar una fila. -->
    <LostCaseTimelineDialog
      v-if="selected"
      v-model="timelineDialog"
      :agent-id="selected.agent_id"
      :hostname="selected.hostname"
    />

    <!-- marcar como perdido -->
    <q-dialog v-model="markDialog" persistent>
      <q-card style="min-width: 420px">
        <q-card-section class="text-subtitle1 text-bold">
          {{ $t("lostEquipment.markTitle") }}
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-select
            dense
            filled
            emit-value
            map-options
            use-input
            input-debounce="0"
            v-model="form.agent_id"
            :options="agentOptions"
            :label="$t('lostEquipment.agentLabel')"
            @filter="filterAgents"
          />
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-input
            dense
            filled
            autogrow
            v-model="form.reason"
            :label="$t('lostEquipment.reasonLabel')"
            :hint="$t('lostEquipment.reasonHint')"
            :rules="[
              (val) => !!val.trim() || $t('lostEquipment.reasonRequired'),
            ]"
          />
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-input
            dense
            filled
            type="number"
            v-model.number="form.interval_min"
            :label="$t('lostEquipment.intervalLabel')"
            :hint="$t('lostEquipment.intervalHint')"
            :min="MIN_INTERVAL_MIN"
            :max="MAX_INTERVAL_MIN"
          />
        </q-card-section>

        <!--
          Feature 038: overrides de la cascada POR ESTE CASO. Máxima precedencia.
          "Heredar" (por defecto) deja decidir a la política del equipo o global,
          así que un operador que no toca nada no cambia nada. El bloqueo es
          silencioso-diferido: se recolecta evidencia y recién luego se bloquea.
        -->
        <q-card-section class="q-pt-none">
          <q-expansion-item
            dense
            icon="tune"
            :label="$t('lostEquipment.cascadeTitle')"
            :caption="$t('lostEquipment.cascadeCaption')"
          >
            <div class="q-pt-sm q-gutter-sm">
              <q-select
                dense
                filled
                emit-value
                map-options
                v-model="form.cascade.auto_lock"
                :options="triOptions"
                :label="$t('lostEquipment.cascadeAutoLock')"
              />
              <q-input
                dense
                filled
                type="number"
                v-model.number="form.cascade.lock_delay_min"
                :label="$t('lostEquipment.cascadeLockDelay')"
                :hint="$t('lostEquipment.cascadeLockDelayHint')"
                :min="0"
                :max="60"
              />
              <q-select
                dense
                filled
                emit-value
                map-options
                v-model="form.cascade.no_hibernate"
                :options="triOptions"
                :label="$t('lostEquipment.cascadeNoHibernate')"
              />
              <q-select
                dense
                filled
                emit-value
                map-options
                v-model="form.cascade.webcam_override"
                :options="triOptions"
                :label="$t('lostEquipment.cascadeWebcamOverride')"
              />
              <q-select
                dense
                filled
                emit-value
                map-options
                v-model="form.cascade.alarm"
                :options="triOptions"
                :label="$t('lostEquipment.cascadeAlarm')"
              />
            </div>
          </q-expansion-item>
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-banner dense class="bg-orange-1 text-orange-9">
            <template v-slot:avatar>
              <q-icon name="warning" color="warning" />
            </template>
            {{ $t("lostEquipment.markWarning") }}
          </q-banner>
        </q-card-section>

        <q-separator />

        <q-card-actions align="right">
          <q-btn flat :label="$t('lostEquipment.cancel')" v-close-popup />
          <q-btn
            flat
            color="negative"
            :loading="saving"
            :disable="!form.agent_id || !form.reason.trim()"
            :label="$t('lostEquipment.markLost')"
            @click="submitMark"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <ConfirmDialog
      v-model="recoverDialog"
      type="confirm"
      icon="check_circle"
      icon-color="positive"
      :title="$t('lostEquipment.confirmRecoverTitle')"
      :message="
        $t('lostEquipment.confirmRecoverMessage', {
          hostname: pending?.hostname ?? '',
        })
      "
      @confirm="doRecover"
    />

    <q-page-sticky position="bottom-right" :offset="[18, 18]">
      <q-btn fab icon="add" color="negative" @click="openMark">
        <q-tooltip>{{ $t("lostEquipment.markLost") }}</q-tooltip>
      </q-btn>
    </q-page-sticky>
  </q-page>
</template>

<script>
// Feature 030 · módulo "Equipos perdidos" (ADR-025) — ESQUELETO de la Fase 0.
//
// Homologación del flujo de la consola de Prey, no de su código: su panel es
// propietario y cerrado (sólo el cliente es GPL), así que no se incrusta ni se
// copia; se reimplementa el flujo de trabajo.
//
// Lo que hay hoy: listar los casos abiertos, abrir uno con motivo obligatorio y
// cerrarlo. Lo que NO hay: la línea de tiempo de evidencia, porque la Fase 0 no
// captura nada — el marcador de dónde entra está en el template.
//
// Sin gating por permiso en el cliente, a propósito: no existe en ningún
// componente para ninguna de las ~30 flags de `Role`, y el 403 del backend ya se
// traduce a un toast por el interceptor de axios. Introducirlo sólo acá rompería
// la consistencia sin ganar seguridad — el permiso lo aplica el servidor.

import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useQuasar } from "quasar";

import ConfirmDialog from "@/components/ui/ConfirmDialog.vue";
import ConfirmYesDialog from "@/components/agents/ConfirmYesDialog.vue";
import LostCaseTimelineDialog from "@/components/agents/LostCaseTimelineDialog.vue";
import SendEndpointAlert from "@/components/modals/agents/SendEndpointAlert.vue";
import SoundEndpointAlarm from "@/components/modals/agents/SoundEndpointAlarm.vue";
import { fetchAgents, agentLockScreen, agentStopAlarm } from "@/api/agents";
import {
  exportLostCase,
  fetchLostEquipment,
  markAgentLost,
  recoverAgent,
} from "@/api/lostmode";
import { notifySuccess, notifyWarning } from "@/utils/notify";
import { formatDate } from "@/utils/format";

// Duplicados de observerrmm/constants.py (LOST_MODE_*_INTERVAL_MIN). Acá sólo
// evitan que el operador escriba un valor que el servidor va a recortar sin
// avisarle; el recorte de verdad lo hacen el endpoint y el agente.
const MIN_INTERVAL_MIN = 1;
const MAX_INTERVAL_MIN = 60;
const DEFAULT_INTERVAL_MIN = 5;

export default {
  name: "LostEquipmentView",
  components: { ConfirmDialog, LostCaseTimelineDialog },
  setup() {
    const { t } = useI18n();
    const $q = useQuasar();

    const rows = ref([]);
    const loading = ref(false);
    const saving = ref(false);

    const markDialog = ref(false);
    const recoverDialog = ref(false);
    const pending = ref(null);

    // El caso abierto en la línea de tiempo. Va en una variable propia y no en
    // `pending` (que es la fila que se va a recuperar) porque son dos cosas que
    // pueden estar vivas a la vez: mirar la evidencia de un equipo y confirmar
    // la recuperación de otro.
    const timelineDialog = ref(false);
    const selected = ref(null);

    const agents = ref([]);
    const agentOptions = ref([]);

    // Feature 038: overrides de la cascada por caso. `null` = heredar (del equipo
    // o del global). El servidor sólo pisa la precedencia con un valor explícito,
    // así que "heredar" en todo equivale a no mandar nada.
    const emptyCascade = () => ({
      auto_lock: null,
      lock_delay_min: null,
      no_hibernate: null,
      webcam_override: null,
      alarm: null,
    });

    // Tri-estado para cada contramedida: heredar / activar / desactivar.
    const triOptions = [
      { label: t("lostEquipment.cascadeInherit"), value: null },
      { label: t("lostEquipment.cascadeEnable"), value: true },
      { label: t("lostEquipment.cascadeDisable"), value: false },
    ];

    const form = ref({
      agent_id: null,
      reason: "",
      interval_min: DEFAULT_INTERVAL_MIN,
      cascade: emptyCascade(),
    });

    const columns = [
      {
        name: "hostname",
        label: t("lostEquipment.colHostname"),
        field: "hostname",
        align: "left",
        sortable: true,
      },
      {
        name: "client_name",
        label: t("lostEquipment.colClient"),
        field: "client_name",
        align: "left",
        sortable: true,
      },
      {
        name: "site_name",
        label: t("lostEquipment.colSite"),
        field: "site_name",
        align: "left",
        sortable: true,
      },
      {
        name: "marked_at",
        label: t("lostEquipment.colMarkedAt"),
        field: "marked_at",
        align: "left",
        sortable: true,
      },
      {
        name: "marked_by",
        label: t("lostEquipment.colMarkedBy"),
        field: "marked_by",
        align: "left",
        sortable: true,
      },
      {
        name: "reason",
        label: t("lostEquipment.colReason"),
        field: "reason",
        align: "left",
      },
      {
        name: "interval_min",
        label: t("lostEquipment.colInterval"),
        field: "interval_min",
        align: "right",
      },
      {
        name: "actions",
        label: t("lostEquipment.colActions"),
        field: "actions",
        align: "right",
      },
    ];

    async function load() {
      loading.value = true;
      try {
        rows.value = await fetchLostEquipment();
      } finally {
        loading.value = false;
      }
    }

    async function openMark() {
      form.value = {
        agent_id: null,
        reason: "",
        interval_min: DEFAULT_INTERVAL_MIN,
        cascade: emptyCascade(),
      };
      markDialog.value = true;

      if (agents.value.length === 0) {
        const data = (await fetchAgents()) ?? [];
        agents.value = data.map((a) => ({
          label: `${a.hostname} — ${a.client_name} / ${a.site_name}`,
          value: a.agent_id,
        }));
      }
      agentOptions.value = agents.value;
    }

    function filterAgents(val, update) {
      update(() => {
        const needle = val.toLowerCase();
        agentOptions.value = needle
          ? agents.value.filter((a) => a.label.toLowerCase().includes(needle))
          : agents.value;
      });
    }

    async function submitMark() {
      // El motivo también se exige acá, no sólo en el backend: ahorra el viaje y
      // da el error en el acto. La validación que manda sigue siendo la del
      // servidor (código `empty_reason`), porque es la que sostiene ADR-025.
      if (!form.value.reason.trim()) {
        notifyWarning(t("lostEquipment.reasonRequired"));
        return;
      }

      saving.value = true;
      try {
        const r = await markAgentLost(form.value.agent_id, {
          reason: form.value.reason.trim(),
          interval_min: form.value.interval_min,
          // Feature 038: los overrides por caso. `null` = heredar; el servidor
          // los interpreta y devuelve la cascada resuelta en `r.cascade`.
          cascade: form.value.cascade,
        });
        markDialog.value = false;

        // `nats_delivered: false` NO es un fallo: el caso quedó abierto igual.
        // Se distingue en el aviso porque al operador le importa saber si el
        // equipo alcanzó a enterarse o si se enterará al reconectar.
        if (r?.nats_delivered) {
          notifySuccess(t("lostEquipment.markedNotified"));
        } else {
          $q.notify({
            type: "info",
            message: t("lostEquipment.markedPending"),
            timeout: 6000,
          });
        }
        await load();
      } finally {
        saving.value = false;
      }
    }

    function openTimeline(evt, row) {
      selected.value = row;
      timelineDialog.value = true;
    }

    function askRecover(row) {
      pending.value = row;
      recoverDialog.value = true;
    }

    // T023 · paraguas 028: las mismas tres acciones del menú del equipo,
    // alcanzables desde el caso.
    //
    // Se llaman las funciones de `@/api/agents` directo y se reutilizan los dos
    // modales de la 028 en vez de montar variantes propias: si mañana la alarma
    // suma un campo, tiene que sumarlo en los dos lugares a la vez. Duplicar el
    // modal acá sería garantizar que un día divergen.
    //
    // `lock` confirma y `alarm`/`alert` traen su propio modal, igual que en
    // AgentActionMenu. `stopAlarm` no confirma: detener el ruido es urgente.

    function lockScreen(row) {
      $q.dialog({
        component: ConfirmYesDialog,
        componentProps: {
          hostname: row.hostname,
          actionVerb: t("endpointResponse.verbLock"),
          title: t("endpointResponse.confirmLockTitle"),
          okLabel: t("endpointResponse.lock"),
          okColor: "negative",
        },
      }).onOk(async () => {
        $q.loading.show();
        try {
          await agentLockScreen(row.agent_id);
          notifySuccess(
            t("endpointResponse.lockSuccess", { hostname: row.hostname }),
          );
        } catch (e) {
          console.error(e);
        }
        $q.loading.hide();
      });
    }

    function showAlertModal(row) {
      $q.dialog({
        component: SendEndpointAlert,
        componentProps: { agent_id: row.agent_id, hostname: row.hostname },
      });
    }

    function soundAlarm(row) {
      $q.dialog({
        component: SoundEndpointAlarm,
        componentProps: { agent_id: row.agent_id, hostname: row.hostname },
      });
    }

    async function stopAlarm(row) {
      $q.loading.show();
      try {
        await agentStopAlarm(row.agent_id);
        notifySuccess(
          t("endpointResponse.stopAlarmSuccess", { hostname: row.hostname }),
        );
      } catch (e) {
        console.error(e);
      }
      $q.loading.hide();
    }

    // T022 · descarga del caso en PDF.
    //
    // El nombre sale de `Content-Disposition` y no se arma acá: es el que el
    // servidor dejó en la auditoría, y un documento de evidencia tiene que
    // poder rastrearse por su nombre. Si la cabecera no llega —un proxy que la
    // recorte— se cae a uno derivado del hostname, que es peor pero sirve.
    function nombreDeLaCabecera(headers, hostname) {
      const cd = headers?.["content-disposition"] ?? "";
      const m = /filename="([^"]+)"/.exec(cd);
      return m ? m[1] : `caso-equipo-perdido-${hostname}.pdf`;
    }

    async function exportCase(row) {
      $q.loading.show();
      try {
        const r = await exportLostCase(row.agent_id);
        const blob = new Blob([r.data], { type: "application/pdf" });
        const url = window.URL.createObjectURL(blob);

        const link = document.createElement("a");
        link.href = url;
        link.download = nombreDeLaCabecera(r.headers, row.hostname);
        link.click();

        // El object URL se revoca: si no, el PDF entero queda vivo en memoria
        // de la pestaña hasta que alguien la cierre, y un caso largo con
        // imágenes embebidas no es un archivo chico.
        window.URL.revokeObjectURL(url);

        notifySuccess(t("lostEquipment.exported", { hostname: row.hostname }));
      } catch (e) {
        console.error(e);
      }
      $q.loading.hide();
    }

    async function doRecover() {
      await recoverAgent(pending.value.agent_id);
      notifySuccess(
        t("lostEquipment.recovered", { hostname: pending.value.hostname }),
      );
      pending.value = null;
      await load();
    }

    onMounted(load);

    return {
      MIN_INTERVAL_MIN,
      MAX_INTERVAL_MIN,
      rows,
      columns,
      loading,
      saving,
      markDialog,
      recoverDialog,
      timelineDialog,
      selected,
      pending,
      form,
      triOptions,
      agentOptions,
      load,
      openMark,
      filterAgents,
      submitMark,
      openTimeline,
      askRecover,
      doRecover,
      lockScreen,
      showAlertModal,
      soundAlarm,
      stopAlarm,
      exportCase,
      formatDate,
    };
  },
};
</script>
