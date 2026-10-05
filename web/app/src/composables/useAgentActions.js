// useAgentActions — las acciones de un agente (046, dirección 1c, T012).
//
// Movido TAL CUAL desde el setup() de components/agents/AgentActionMenu.vue: mismos
// imports, mismos handlers, mismas confirmaciones. AgentActionMenu (menú contextual
// de la tabla y dropdown "Acciones") y la barra de acción del espacio de trabajo
// consumen este composable, así que no pueden divergir. Debe llamarse dentro de un
// setup(): usa inject("refreshDashboard") y onMounted.

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

// ui imports (diálogos que abren las acciones)
import PendingActions from "@/components/logs/PendingActions.vue";
import AgentRecovery from "@/components/modals/agents/AgentRecovery.vue";
import PolicyAdd from "@/components/automation/modals/PolicyAdd.vue";
import RebootLater from "@/components/modals/agents/RebootLater.vue";
import EditAgent from "@/components/modals/agents/EditAgent.vue";
import SendCommand from "@/components/modals/agents/SendCommand.vue";
import RunScript from "@/components/modals/agents/RunScript.vue";
import ConfirmYesDialog from "@/components/agents/ConfirmYesDialog.vue";
import SendEndpointAlert from "@/components/modals/agents/SendEndpointAlert.vue";
import SoundEndpointAlarm from "@/components/modals/agents/SoundEndpointAlarm.vue";

export function useAgentActions() {
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
      // `showCommunityScripts` es el nombre del query param que espera el
      // backend (scripts/views.py): se manda tal cual a propósito.
      const data = await fetchScripts({
        showCommunityScripts: store.state.showScriptTemplates,
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

  // Feature 028 Fase 2: dejó de ser un `$q.dialog` con `prompt`.
  //
  // El `prompt` de Quasar admite un solo campo y NO admite casillas, así que la
  // alarma antirrobo —sonido máximo y sin límite de tiempo— obligó a un modal
  // propio. El envío, la validación y el aviso viven ahí dentro.
  function soundAlarm(agent) {
    $q.dialog({
      component: SoundEndpointAlarm,
      componentProps: {
        agent_id: agent.agent_id,
        hostname: agent.hostname,
      },
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

  // Descriptores de las 25 acciones hoja (046, dirección 1c). La barra de
  // acción del espacio de trabajo los pinta; el menú contextual de la tabla
  // sigue con su plantilla. Los dos llaman a LOS MISMOS handlers de arriba,
  // así que una acción no puede divergir entre los dos lugares (UI-F03/F08).
  // `destructive`: la acción pide confirmación antes de llamar a la API.
  function actionDescriptors(agent) {
    return [
      {
        key: "edit",
        icon: "fas fa-edit",
        label: t("agentActions.edit", { hostname: agent.hostname }),
        run: () => showEditAgent(agent.agent_id),
      },
      {
        key: "pendingActions",
        icon: "far fa-clock",
        label: t("agentActions.pendingActions"),
        run: () => showPendingActionsModal(agent),
      },
      {
        key: "takeControl",
        icon: "fas fa-desktop",
        label: t("agentActions.takeControl"),
        run: () => runTakeControl(agent.agent_id),
      },
      {
        key: "vnc",
        icon: "screen_share",
        label: t("agentActions.vnc"),
        run: () => launchWebVNC(agent.agent_id),
      },
      {
        key: "runUrlAction",
        icon: "open_in_new",
        label: t("agentActions.runUrlAction"),
        disabled: urlActions.value.length === 0,
        children: urlActions.value.map((action) => ({
          key: `url-${action.id}`,
          label: action.name,
          run: () =>
            runURLAction({ agent_id: agent.agent_id, action: action.id }),
        })),
      },
      {
        key: "sendCommand",
        icon: "fas fa-terminal",
        label: t("agentActions.sendCommand"),
        run: () => showSendCommand(agent),
      },
      {
        key: "runScript",
        icon: "fas fa-terminal",
        label: t("agentActions.runScript"),
        run: () => showRunScript(agent),
      },
      {
        key: "runFavoritedScript",
        icon: "star",
        label: t("agentActions.runFavoritedScript"),
        disabled: favoriteScripts.value.length === 0,
        children: favoriteScripts.value.map((script) => ({
          key: `fav-${script.value}`,
          label: script.label,
          run: () => showRunScript(agent, script.value),
        })),
      },
      {
        key: "remoteBackground",
        icon: "terminal",
        label: t("agentActions.remoteBackground"),
        run: () => runRemoteBackground(agent.agent_id, agent.plat),
      },
      {
        key: "maintenance",
        icon: "construction",
        label: agent.maintenance_mode
          ? t("agentActions.disableMaintenance")
          : t("agentActions.enableMaintenance"),
        run: () => toggleMaintenance(agent),
      },
      {
        key: "patchManagement",
        icon: "system_update",
        label: t("agentActions.patchManagement"),
        children: [
          {
            key: "runPatchStatusScan",
            label: t("agentActions.runPatchStatusScan"),
            run: () => runPatchStatusScan(agent),
          },
          {
            key: "installPatchesNow",
            label: t("agentActions.installPatchesNow"),
            run: () => installPatches(agent),
          },
        ],
      },
      {
        key: "runChecks",
        icon: "fas fa-check-double",
        label: t("agentActions.runChecks"),
        run: () => runChecks(agent),
      },
      {
        key: "wakeUp",
        icon: "offline_bolt",
        label: t("agentActions.wakeUp"),
        run: () => wakeUp(agent),
      },
      {
        key: "reboot",
        icon: "power_settings_new",
        label: t("agentActions.reboot"),
        children: [
          {
            key: "rebootNow",
            label: t("agentActions.rebootNow"),
            destructive: true,
            run: () => rebootNow(agent),
          },
          {
            key: "rebootLater",
            label: t("agentActions.rebootLater"),
            run: () => showRebootLaterModal(agent),
          },
        ],
      },
      {
        key: "shutdown",
        icon: "power",
        label: t("agentActions.shutdown"),
        destructive: true,
        run: () => shutdown(agent),
      },
      {
        key: "endpointResponse",
        icon: "crisis_alert",
        label: t("endpointResponse.menu"),
        children: [
          {
            key: "sendAlert",
            icon: "chat",
            label: t("endpointResponse.sendAlert"),
            run: () => showAlertModal(agent),
          },
          {
            key: "lock",
            icon: "lock",
            label: t("endpointResponse.lock"),
            destructive: true,
            run: () => lockScreen(agent),
          },
          {
            key: "alarm",
            icon: "volume_up",
            label: t("endpointResponse.alarm"),
            destructive: true,
            run: () => soundAlarm(agent),
          },
          {
            key: "stopAlarm",
            icon: "volume_off",
            label: t("endpointResponse.stopAlarm"),
            run: () => stopAlarm(agent),
          },
        ],
      },
      {
        key: "assignPolicy",
        icon: "policy",
        label: t("agentActions.assignPolicy"),
        run: () => showPolicyAdd(agent),
      },
      {
        key: "agentRecovery",
        icon: "fas fa-first-aid",
        label: t("agentActions.agentRecovery"),
        run: () => showAgentRecovery(agent),
      },
      {
        key: "removeAgent",
        icon: "delete",
        label: t("agentActions.removeAgent"),
        destructive: true,
        run: () => pingAgent(agent),
      },
    ];
  }

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
    showPolicyAdd,
    showAgentRecovery,
    pingAgent,
    wakeUp,
    launchWebVNC,
    actionDescriptors,
  };
}
