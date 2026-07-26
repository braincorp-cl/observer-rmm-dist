<template>
  <q-list dense style="min-width: 200px">
    <!-- edit agent -->
    <q-item clickable v-close-popup @click="showEditAgent(agent.agent_id)">
      <q-item-section side>
        <q-icon size="xs" name="fas fa-edit" />
      </q-item-section>
      <q-item-section>{{
        $t("agentActions.edit", { hostname: agent.hostname })
      }}</q-item-section>
    </q-item>
    <!-- agent pending actions -->
    <q-item clickable v-close-popup @click="showPendingActionsModal(agent)">
      <q-item-section side>
        <q-icon size="xs" name="far fa-clock" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.pendingActions") }}</q-item-section>
    </q-item>
    <!-- take control -->
    <q-item
      clickable
      v-ripple
      v-close-popup
      @click="runTakeControl(agent.agent_id)"
    >
      <q-item-section side>
        <q-icon size="xs" name="fas fa-desktop" />
      </q-item-section>

      <q-item-section>{{ $t("agentActions.takeControl") }}</q-item-section>
    </q-item>

    <!-- vnc -->
    <q-item
      clickable
      v-ripple
      v-close-popup
      @click="launchWebVNC(agent.agent_id)"
    >
      <q-item-section side>
        <q-icon size="xs" name="screen_share" />
      </q-item-section>

      <q-item-section>{{ $t("agentActions.vnc") }}</q-item-section>
    </q-item>

    <q-item clickable v-ripple :disable="urlActions.length === 0">
      <q-item-section side>
        <q-icon size="xs" name="open_in_new" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.runUrlAction") }}</q-item-section>
      <q-item-section side>
        <q-icon name="keyboard_arrow_right" />
      </q-item-section>
      <q-menu auto-close anchor="top end" self="top start">
        <q-list>
          <q-item
            v-for="action in urlActions"
            :key="action.id"
            dense
            clickable
            v-close-popup
            @click="
              runURLAction({ agent_id: agent.agent_id, action: action.id })
            "
          >
            <q-item-section>{{ action.name }}</q-item-section>
          </q-item>
        </q-list>
      </q-menu>
    </q-item>

    <q-item clickable v-ripple v-close-popup @click="showSendCommand(agent)">
      <q-item-section side>
        <q-icon size="xs" name="fas fa-terminal" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.sendCommand") }}</q-item-section>
    </q-item>

    <q-item clickable v-ripple v-close-popup @click="showRunScript(agent)">
      <q-item-section side>
        <q-icon size="xs" name="fas fa-terminal" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.runScript") }}</q-item-section>
    </q-item>

    <q-item clickable v-ripple :disable="favoriteScripts.length === 0">
      <q-item-section side>
        <q-icon size="xs" name="star" />
      </q-item-section>
      <q-item-section>{{
        $t("agentActions.runFavoritedScript")
      }}</q-item-section>
      <q-item-section side>
        <q-icon name="keyboard_arrow_right" />
      </q-item-section>
      <q-menu auto-close anchor="top end" self="top start">
        <q-list>
          <q-item
            v-for="script in favoriteScripts"
            :key="script.value"
            dense
            clickable
            v-close-popup
            @click="showRunScript(agent, script.value)"
          >
            <q-item-section>{{ script.label }}</q-item-section>
          </q-item>
        </q-list>
      </q-menu>
    </q-item>

    <q-item
      clickable
      v-close-popup
      @click="runRemoteBackground(agent.agent_id, agent.plat)"
    >
      <q-item-section side>
        <q-icon size="xs" name="terminal" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.remoteBackground") }}</q-item-section>
    </q-item>

    <!-- maintenance mode -->
    <q-item clickable v-close-popup @click="toggleMaintenance(agent)">
      <q-item-section side>
        <q-icon size="xs" name="construction" />
      </q-item-section>
      <q-item-section>
        {{
          agent.maintenance_mode
            ? $t("agentActions.disableMaintenance")
            : $t("agentActions.enableMaintenance")
        }}
      </q-item-section>
    </q-item>

    <!-- patch management -->
    <q-item clickable>
      <q-item-section side>
        <q-icon size="xs" name="system_update" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.patchManagement") }}</q-item-section>
      <q-item-section side>
        <q-icon name="keyboard_arrow_right" />
      </q-item-section>

      <q-menu auto-close anchor="top right" self="top left">
        <q-list dense style="min-width: 100px">
          <q-item clickable v-ripple @click="runPatchStatusScan(agent)">
            <q-item-section>{{
              $t("agentActions.runPatchStatusScan")
            }}</q-item-section>
          </q-item>
          <q-item clickable v-ripple @click="installPatches(agent)">
            <q-item-section>{{
              $t("agentActions.installPatchesNow")
            }}</q-item-section>
          </q-item>
        </q-list>
      </q-menu>
    </q-item>

    <q-item clickable v-close-popup @click="runChecks(agent)">
      <q-item-section side>
        <q-icon size="xs" name="fas fa-check-double" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.runChecks") }}</q-item-section>
    </q-item>

    <q-item clickable v-close-popup @click="wakeUp(agent)">
      <q-item-section side>
        <q-icon size="xs" name="offline_bolt" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.wakeUp") }}</q-item-section>
    </q-item>

    <q-item clickable>
      <q-item-section side>
        <q-icon size="xs" name="power_settings_new" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.reboot") }}</q-item-section>
      <q-item-section side>
        <q-icon name="keyboard_arrow_right" />
      </q-item-section>

      <q-menu auto-close anchor="top right" self="top left">
        <q-list dense style="min-width: 100px">
          <!-- reboot now -->
          <q-item clickable v-ripple @click="rebootNow(agent)">
            <q-item-section>{{ $t("agentActions.rebootNow") }}</q-item-section>
          </q-item>
          <!-- reboot later -->
          <q-item clickable v-ripple @click="showRebootLaterModal(agent)">
            <q-item-section>{{
              $t("agentActions.rebootLater")
            }}</q-item-section>
          </q-item>
        </q-list>
      </q-menu>
    </q-item>

    <q-item clickable v-close-popup @click="shutdown(agent)">
      <q-item-section side>
        <q-icon size="xs" name="power" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.shutdown") }}</q-item-section>
    </q-item>

    <!-- respuesta rápida de endpoint (feature 028) -->
    <q-item clickable>
      <q-item-section side>
        <q-icon size="xs" name="crisis_alert" />
      </q-item-section>
      <q-item-section>{{ $t("endpointResponse.menu") }}</q-item-section>
      <q-item-section side>
        <q-icon name="keyboard_arrow_right" />
      </q-item-section>

      <q-menu auto-close anchor="top right" self="top left">
        <q-list dense style="min-width: 100px">
          <!-- mensaje en pantalla -->
          <q-item clickable v-ripple @click="showAlertModal(agent)">
            <q-item-section side>
              <q-icon size="xs" name="chat" />
            </q-item-section>
            <q-item-section>{{
              $t("endpointResponse.sendAlert")
            }}</q-item-section>
          </q-item>

          <!-- bloqueo de pantalla -->
          <q-item clickable v-ripple @click="lockScreen(agent)">
            <q-item-section side>
              <q-icon size="xs" name="lock" />
            </q-item-section>
            <q-item-section>{{ $t("endpointResponse.lock") }}</q-item-section>
          </q-item>

          <q-separator />

          <!-- alarma sonora -->
          <q-item clickable v-ripple @click="soundAlarm(agent)">
            <q-item-section side>
              <q-icon size="xs" name="volume_up" />
            </q-item-section>
            <q-item-section>{{ $t("endpointResponse.alarm") }}</q-item-section>
          </q-item>

          <q-item clickable v-ripple @click="stopAlarm(agent)">
            <q-item-section side>
              <q-icon size="xs" name="volume_off" />
            </q-item-section>
            <q-item-section>{{
              $t("endpointResponse.stopAlarm")
            }}</q-item-section>
          </q-item>
        </q-list>
      </q-menu>
    </q-item>

    <q-item clickable v-close-popup @click="showPolicyAdd(agent)">
      <q-item-section side>
        <q-icon size="xs" name="policy" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.assignPolicy") }}</q-item-section>
    </q-item>

    <q-item
      clickable
      v-if="
        $integrations &&
        $integrations.agentMenuIntegrations &&
        $integrations.agentMenuIntegrations.length > 0
      "
    >
      <q-item-section side>
        <q-icon size="xs" name="analytics" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.reporting") }}</q-item-section>
      <q-item-section side>
        <q-icon name="keyboard_arrow_right" />
      </q-item-section>
      <integrations-context-menu type="agent" :id="agent.agent_id" />
    </q-item>

    <q-item clickable v-close-popup @click="showAgentRecovery(agent)">
      <q-item-section side>
        <q-icon size="xs" name="fas fa-first-aid" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.agentRecovery") }}</q-item-section>
    </q-item>

    <q-item clickable v-close-popup @click="pingAgent(agent)">
      <q-item-section side>
        <q-icon size="xs" name="delete" />
      </q-item-section>
      <q-item-section>{{ $t("agentActions.removeAgent") }}</q-item-section>
    </q-item>

    <q-separator />
    <q-item clickable v-close-popup>
      <q-item-section>{{ $t("agentActions.close") }}</q-item-section>
    </q-item>
  </q-list>
</template>

<script>
// composition imports
import { ref, inject, onMounted } from "vue";
import { useStore } from "vuex";
import { useQuasar } from "quasar";
import { useI18n } from "vue-i18n";
import { fetchURLActions, runURLAction } from "@/api/core";
import {
  editAgent,
  agentRebootNow,
  agentShutdown,
  agentLockScreen,
  agentSoundAlarm,
  agentStopAlarm,
  sendAgentPing,
  removeAgent,
  runRemoteBackground,
  runTakeControl,
  runWebVNC,
  wakeUpWOL,
} from "@/api/agents";
import { runAgentUpdateScan, runAgentUpdateInstall } from "@/api/winupdates";
import { runAgentChecks } from "@/api/checks";
import { fetchScripts } from "@/api/scripts";
import { notifySuccess, notifyError } from "@/utils/notify";

// ui imports
import PendingActions from "@/components/logs/PendingActions.vue";
import AgentRecovery from "@/components/modals/agents/AgentRecovery.vue";
import PolicyAdd from "@/components/automation/modals/PolicyAdd.vue";
import RebootLater from "@/components/modals/agents/RebootLater.vue";
import EditAgent from "@/components/modals/agents/EditAgent.vue";
import SendCommand from "@/components/modals/agents/SendCommand.vue";
import RunScript from "@/components/modals/agents/RunScript.vue";
import IntegrationsContextMenu from "@/components/ui/IntegrationsContextMenu.vue";
import ConfirmYesDialog from "@/components/agents/ConfirmYesDialog.vue";
import SendEndpointAlert from "@/components/modals/agents/SendEndpointAlert.vue";

// Feature 028: duplicados de observerrmm/constants.py (ALARM_*). Sólo acotan lo
// que el operador puede escribir; el servidor y el agente validan igual.
const ALARM_MIN_SECONDS = 5;
const ALARM_DEFAULT_SECONDS = 30;
const ALARM_MAX_SECONDS = 300;

export default {
  name: "AgentActionMenu",
  components: {
    IntegrationsContextMenu,
  },
  props: {
    agent: !Object,
  },
  setup() {
    // setup quasar
    const $q = useQuasar();

    // setup vuex
    const store = useStore();

    // setup i18n
    const { t } = useI18n();

    const refreshDashboard = inject("refreshDashboard");

    const urlActions = ref([]);
    const favoriteScripts = ref([]);

    function showEditAgent(agent_id) {
      $q.dialog({
        component: EditAgent,
        componentProps: {
          agent_id: agent_id,
        },
      }).onOk(refreshDashboard);
    }

    function showPendingActionsModal(agent) {
      $q.dialog({
        component: PendingActions,
        componentProps: {
          agent: agent,
        },
      });
    }

    async function getURLActions() {
      try {
        urlActions.value = (await fetchURLActions())
          .filter((action) => action.action_type === "web")
          .sort((a, b) => a.name.localeCompare(b.name));
      } catch (e) {
        console.error(e);
      }
    }

    function showSendCommand(agent) {
      $q.dialog({
        component: SendCommand,
        componentProps: {
          agent: agent,
        },
      });
    }

    function showRunScript(agent, script = undefined) {
      $q.dialog({
        component: RunScript,
        componentProps: {
          agent,
          script,
        },
      });
    }

    async function getFavoriteScripts() {
      favoriteScripts.value = [];

      try {
        const data = await fetchScripts({
          showCommunityScripts: store.state.showCommunityScripts,
        });

        const scripts = data.filter((script) => !!script.favorite);

        favoriteScripts.value = scripts
          .map((script) => ({
            label: script.name,
            value: script.id,
            timeout: script.default_timeout,
            args: script.args,
          }))
          .sort((a, b) => a.label.localeCompare(b.label));
      } catch (e) {
        console.error(e);
      }
    }

    async function toggleMaintenance(agent) {
      let data = {
        maintenance_mode: !agent.maintenance_mode,
      };

      try {
        await editAgent(agent.agent_id, data);
        notifySuccess(
          agent.maintenance_mode
            ? t("agentActions.maintenanceDisabled", {
                hostname: agent.hostname,
              })
            : t("agentActions.maintenanceEnabled", {
                hostname: agent.hostname,
              }),
        );
        store.commit("setRefreshSummaryTab", true);
        refreshDashboard();
      } catch (e) {
        console.error(e);
      }
    }

    async function runPatchStatusScan(agent) {
      try {
        await runAgentUpdateScan(agent.agent_id);
        notifySuccess(
          t("agentActions.scanShortly", { hostname: agent.hostname }),
        );
      } catch (e) {
        console.error(e);
      }
    }

    async function installPatches(agent) {
      try {
        const data = await runAgentUpdateInstall(agent.agent_id);
        notifySuccess(data);
      } catch (e) {
        console.error(e);
      }
    }

    async function runChecks(agent) {
      try {
        const data = await runAgentChecks(agent.agent_id);
        notifySuccess(data);
      } catch (e) {
        console.error(e);
      }
    }

    async function wakeUp(agent) {
      try {
        const data = await wakeUpWOL(agent.agent_id);
        notifySuccess(data);
      } catch (e) {
        console.error(e);
      }
    }

    function showRebootLaterModal(agent) {
      $q.dialog({
        component: RebootLater,
        componentProps: {
          agent: agent,
        },
      }).onOk(refreshDashboard);
    }

    function launchWebVNC(agent_id) {
      $q.dialog({
        title: t("agentActions.vncPortTitle"),
        message: t("agentActions.vncPortMessage"),
        prompt: {
          model: "5900",
          type: "text",
        },
        cancel: true,
        ok: { label: t("agentActions.launch"), color: "primary" },
        persistent: true,
      }).onOk((port) => {
        runWebVNC(agent_id, port);
      });
    }

    function rebootNow(agent) {
      $q.dialog({
        title: t("agentActions.rebootConfirmTitle"),
        message: t("agentActions.rebootConfirmMessage", {
          hostname: agent.hostname,
        }),
        cancel: true,
        persistent: true,
      }).onOk(async () => {
        $q.loading.show();
        try {
          await agentRebootNow(agent.agent_id);
          notifySuccess(
            t("agentActions.rebootSuccess", { hostname: agent.hostname }),
          );
          $q.loading.hide();
        } catch (e) {
          $q.loading.hide();
          console.error(e);
        }
      });
    }

    function shutdown(agent) {
      $q.dialog({
        component: ConfirmYesDialog,
        componentProps: {
          hostname: agent.hostname,
          actionVerb: t("agentActions.verbShutdown"),
          title: t("agentActions.confirmShutdownTitle"),
          okLabel: t("agentActions.shutdown"),
          okColor: "negative",
        },
      }).onOk(async () => {
        $q.loading.show();
        try {
          await agentShutdown(agent.agent_id);
          notifySuccess(
            t("agentActions.shutdownSuccess", { hostname: agent.hostname }),
          );
          $q.loading.hide();
        } catch (e) {
          $q.loading.hide();
          console.error(e);
        }
      });
    }

    // Feature 028 · respuesta rápida de endpoint.
    //
    // `lock` y `alarm` piden confirmación porque el usuario del equipo las nota
    // de inmediato: una le corta la sesión y la otra hace ruido a su alrededor.
    // `alert` no la pide: el propio modal donde se redacta el mensaje ya es el
    // paso deliberado, y pedir dos confirmaciones para mandar un texto sobra.
    // `stopAlarm` tampoco: detener el ruido tiene que ser inmediato.

    function showAlertModal(agent) {
      $q.dialog({
        component: SendEndpointAlert,
        componentProps: {
          agent_id: agent.agent_id,
          hostname: agent.hostname,
        },
      });
    }

    function lockScreen(agent) {
      $q.dialog({
        component: ConfirmYesDialog,
        componentProps: {
          hostname: agent.hostname,
          actionVerb: t("endpointResponse.verbLock"),
          title: t("endpointResponse.confirmLockTitle"),
          okLabel: t("endpointResponse.lock"),
          okColor: "negative",
        },
      }).onOk(async () => {
        $q.loading.show();
        try {
          await agentLockScreen(agent.agent_id);
          notifySuccess(
            t("endpointResponse.lockSuccess", { hostname: agent.hostname }),
          );
        } catch (e) {
          console.error(e);
        }
        $q.loading.hide();
      });
    }

    function soundAlarm(agent) {
      $q.dialog({
        title: t("endpointResponse.alarmDurationTitle"),
        message: t("endpointResponse.alarmDurationMessage", {
          hostname: agent.hostname,
        }),
        prompt: {
          model: String(ALARM_DEFAULT_SECONDS),
          type: "number",
          // El tope también está en el servidor y en el agente; acá es sólo para
          // que el operador no escriba un valor que le van a recortar en silencio.
          min: ALARM_MIN_SECONDS,
          max: ALARM_MAX_SECONDS,
        },
        cancel: true,
        persistent: true,
        ok: { label: t("endpointResponse.alarm"), color: "negative" },
      }).onOk(async (duration) => {
        $q.loading.show();
        try {
          await agentSoundAlarm(agent.agent_id, { duration: Number(duration) });
          notifySuccess(
            t("endpointResponse.alarmSuccess", { hostname: agent.hostname }),
          );
        } catch (e) {
          console.error(e);
        }
        $q.loading.hide();
      });
    }

    async function stopAlarm(agent) {
      $q.loading.show();
      try {
        await agentStopAlarm(agent.agent_id);
        notifySuccess(
          t("endpointResponse.stopAlarmSuccess", { hostname: agent.hostname }),
        );
      } catch (e) {
        console.error(e);
      }
      $q.loading.hide();
    }

    function showPolicyAdd(agent) {
      $q.dialog({
        component: PolicyAdd,
        componentProps: {
          type: "agent",
          object: agent,
        },
      }).onOk(refreshDashboard);
    }

    function showAgentRecovery(agent) {
      $q.dialog({
        component: AgentRecovery,
        componentProps: {
          agent: agent,
        },
      });
    }

    async function pingAgent(agent) {
      try {
        $q.loading.show();
        const data = await sendAgentPing(agent.agent_id);
        $q.loading.hide();
        if (data.status === "offline") {
          $q.dialog({
            title: t("agentActions.agentOfflineTitle"),
            message: t("agentActions.agentOfflineMessage", {
              hostname: agent.hostname,
            }),
            cancel: { label: t("agentActions.no"), color: "negative" },
            ok: { label: t("agentActions.yes"), color: "positive" },
            persistent: true,
          })
            .onOk(() => deleteAgent(agent))
            .onCancel(() => {
              return;
            });
        } else if (data.status === "online") {
          deleteAgent(agent);
        } else {
          notifyError(t("agentActions.somethingWrong"));
        }
      } catch (e) {
        $q.loading.hide();
        console.error(e);
      }
    }

    function deleteAgent(agent) {
      $q.dialog({
        component: ConfirmYesDialog,
        componentProps: {
          hostname: agent.hostname,
          actionVerb: t("agentActions.verbDeletion"),
          title: t("agentActions.confirmDeletionTitle"),
          okLabel: t("agentActions.uninstall"),
          okColor: "negative",
        },
      }).onOk(async () => {
        try {
          const data = await removeAgent(agent.agent_id);
          notifySuccess(data);
          refreshDashboard(
            false /* clearTreeSelected */,
            true /* clearSubTable */,
          );
        } catch (e) {
          console.error(e);
        }
      });
    }

    onMounted(async () => {
      await getURLActions();
      await getFavoriteScripts();
    });

    return {
      // reactive data
      urlActions,
      favoriteScripts,

      // methods
      showEditAgent,
      showPendingActionsModal,
      runTakeControl,
      runRemoteBackground,
      getURLActions,
      runURLAction,
      showSendCommand,
      showRunScript,
      getFavoriteScripts,
      toggleMaintenance,
      runPatchStatusScan,
      installPatches,
      runChecks,
      showRebootLaterModal,
      rebootNow,
      shutdown,
      showAlertModal,
      lockScreen,
      soundAlarm,
      stopAlarm,
      ALARM_MIN_SECONDS,
      ALARM_DEFAULT_SECONDS,
      ALARM_MAX_SECONDS,
      showPolicyAdd,
      showAgentRecovery,
      pingAgent,
      wakeUp,
      launchWebVNC,
    };
  },
};
</script>
