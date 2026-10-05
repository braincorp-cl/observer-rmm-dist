// useAgentUrgency — los 4 números de urgencia del espacio de trabajo 1c (046, T019).
//
// Salen de las MISMAS GET que ya usa la v1 (RN-01: ninguna llamada nueva):
//   - chequeos fallando y reinicio requerido: el detalle del agente (fetchAgent)
//   - acciones pendientes: fetchAgentPendingActions (diálogo "Acciones pendientes")
//   - parches pendientes: fetchAgentUpdates, contando solo las APROBADAS y no
//     instaladas, que es lo que la v1 llama "parche pendiente" (columna de la tabla,
//     has_patches_pending). Una actualización con action "nothing" no cuenta (RN-05).
import { ref } from "vue";
import { fetchAgentPendingActions } from "@/api/logs";
import { fetchAgentUpdates } from "@/api/winupdates";

export function useAgentUrgency() {
  const failingChecks = ref(0);
  const pendingPatches = ref(0);
  const pendingActions = ref(0);
  const rebootRequired = ref(false);

  async function loadUrgency(agent) {
    failingChecks.value = agent?.checks?.failing ?? 0;
    rebootRequired.value = !!agent?.needs_reboot;
    pendingActions.value = 0;
    pendingPatches.value = 0;
    if (!agent) return;
    try {
      const actions = await fetchAgentPendingActions(agent.agent_id);
      pendingActions.value = Array.isArray(actions)
        ? actions.filter((a) => a.status === "pending").length
        : 0;
    } catch (e) {
      console.error(e);
    }
    if (agent.plat === "windows") {
      try {
        const updates = await fetchAgentUpdates(agent.agent_id);
        pendingPatches.value = Array.isArray(updates)
          ? updates.filter((u) => u.action === "approve" && !u.installed).length
          : 0;
      } catch (e) {
        console.error(e);
      }
    }
  }

  return {
    failingChecks,
    pendingPatches,
    pendingActions,
    rebootRequired,
    loadUrgency,
  };
}
