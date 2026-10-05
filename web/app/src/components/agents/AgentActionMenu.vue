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
// La lógica vive en composables/useAgentActions.js (046, T012-T013): esta
// plantilla y la barra de acción del espacio de trabajo comparten handlers.
import { useAgentActions } from "@/composables/useAgentActions";
import IntegrationsContextMenu from "@/components/ui/IntegrationsContextMenu.vue";

export default {
  name: "AgentActionMenu",
  components: {
    IntegrationsContextMenu,
  },
  props: {
    agent: !Object,
  },
  setup() {
    return useAgentActions();
  },
};
</script>
