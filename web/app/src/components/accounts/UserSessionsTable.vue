<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card style="width: 60vw; max-width: 90vw; min-height: 40vh">
      <q-bar>
        {{ $t("userSessions.title", { username: user.username }) }}
        <q-space />
        <q-btn v-close-popup dense flat icon="close">
          <q-tooltip>{{ $t("userSessions.close") }}</q-tooltip>
        </q-btn>
      </q-bar>
      <!-- 🪤 050 (V2-G15): PATRÓN DE REJILLA. Ver composables/rejillaTabla.js:
           con una parada por fila el tabulador cae en las filas sobre-renderizadas
           que el desplazamiento virtual deja fuera del contenedor. -->
      <div @focusin="alEntrarFoco" @keydown="alTeclaRejilla">
      <q-table
        dense
        :table-class="{
          'table-bgcolor': !$q.dark.isActive,
          'table-bgcolor-dark': $q.dark.isActive,
        }"
        :style="{ 'max-height': `${$q.screen.height - 24}px` }"
        class="tbl-sticky"
        :rows="sessions"
        :columns="columns"
        :loading="loading"
        :pagination="{ rowsPerPage: 0, sortBy: 'display', descending: true }"
        row-key="id"
        binary-state-sort
        virtual-scroll
        @virtual-scroll="alDesplazarVirtual"
        :virtual-scroll-item-size="33"
        :virtual-scroll-sticky-size-start="28"
        :rows-per-page-options="[0]"
        ref="tablaRejilla"
      >
        <template #top>
          <q-space />
          <q-btn
            :label="$t('userSessions.removeAll')"
            @click="removeAllSessions"
            size="sm"
            outline
          />
        </template>
        <template #body="props">
          <q-tr>
            <!-- rows -->
            <!-- Host enfocable de la fila: la ÚNICA parada de tabulador de la
                 tabla, y desde ella la flecha derecha llega al botón de
                 desconectar. -->
            <td>
              <span
                class="obs-rej__host mono"
                :data-fila="props.rowIndex"
                :tabindex="props.rowIndex === filaFoco ? 0 : -1"
                @focus="filaFoco = props.rowIndex"
                >{{ formatDate(props.row.created) }}</span
              >
            </td>
            <td class="mono">{{ formatDate(props.row.expiry) }}</td>
            <td>
              <q-btn
                size="sm"
                tabindex="-1"
                @click="removeSession(props.row)"
                :label="$t('userSessions.disconnect')"
                outline
              ></q-btn>
            </td>
          </q-tr>
        </template>
      </q-table>
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
// composition imports
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDialogPluginComponent, useQuasar, type QTableColumn } from "quasar";
import { notifySuccess } from "@/utils/notify";
import { formatDate } from "@/utils/format";
import {
  fetchUserSessions,
  deleteAllUserSessions,
  deleteUserSession,
} from "@/api/accounts";
import { usarRejillaTabla } from "@/composables/rejillaTabla";

//types
// SSO descartado (ADR-010, 2026-06-17): tipo SSOUser reemplazado por User base (módulo ee/sso vaciado).
import type { AuthToken, User } from "@/types/accounts";

const { t } = useI18n();

const columns = computed<QTableColumn[]>(() => [
  {
    name: "created",
    label: t("userSessions.colCreated"),
    field: "created",
    align: "left",
    sortable: true,
  },
  {
    name: "expiry",
    label: t("userSessions.colExpires"),
    field: "expiry",
    align: "left",
    sortable: true,
  },
  {
    name: "action",
    label: "",
    field: "action",
    align: "left",
    sortable: true,
  },
]);

// emits
defineEmits([...useDialogPluginComponent.emits]);

// props
const props = defineProps<{
  user: User;
}>();

const { dialogRef, onDialogHide } = useDialogPluginComponent();
const $q = useQuasar();

const sessions = ref([] as AuthToken[]);

// Patrón de rejilla: la tabla es UNA parada de tabulador y las flechas mueven la
// fila. El `ref` de la plantilla tiene que existir acá o `scrollTo` por índice
// no encuentra la tabla.
const tablaRejilla = ref();
const {
  filaFoco,
  alEntrarFoco,
  alTeclaRejilla,
  alDesplazarVirtual,
} = usarRejillaTabla({
  refTabla: tablaRejilla,
  filas: () => sessions.value,
});
const loading = ref(false);

function removeSession(token: AuthToken) {
  $q.dialog({
    title: t("userSessions.confirmDisconnect", { user: token.user }),
    message: t("userSessions.signedOutImmediately"),
    cancel: true,
    ok: { label: t("userSessions.delete"), color: "primary" },
  }).onOk(async () => {
    loading.value = true;
    try {
      await deleteUserSession(token.digest);
      notifySuccess(t("userSessions.sessionDeleted"));
    } finally {
      loading.value = false;
      await getSessions();
    }
  });
}

function removeAllSessions() {
  $q.dialog({
    title: t("userSessions.confirmDisconnectAll", {
      username: props.user.username,
    }),
    cancel: true,
    ok: { label: t("userSessions.delete"), color: "primary" },
  }).onOk(async () => {
    loading.value = true;
    try {
      await deleteAllUserSessions(props.user.id);
      notifySuccess(t("userSessions.sessionsDeleted"));
    } finally {
      loading.value = false;
      onDialogHide();
    }
  });
}

async function getSessions() {
  sessions.value = await fetchUserSessions(props.user.id);
}

onMounted(getSessions);
</script>
