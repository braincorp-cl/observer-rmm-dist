import axios from "axios";

const baseUrl = "/logs";

export async function fetchDebugLog(payload) {
  try {
    const { data } = await axios.patch(`${baseUrl}/debug/`, payload);
    return data;
  } catch (e) {
    // WI-DECISION-03 / Q-LOG-03 fix: catch silencioso reemplazado por console.error
    // El interceptor global de Axios ya muestra Notify.create(negative) para errores HTTP;
    // este log permite debug en DevTools sin duplicar UI noise.
    console.error(e);
  }
}

export async function fetchAuditLog(payload) {
  const { data } = await axios.patch(`${baseUrl}/audit/`, payload);
  return data;
}

// pending actions
export async function fetchPendingActions(params = {}) {
  const { data } = await axios.get(`${baseUrl}/pendingactions/`, {
    params: params,
  });
  return data;
}

export async function fetchAgentPendingActions(agent_id) {
  try {
    const { data } = await axios.get(`/agents/${agent_id}/pendingactions/`);
    return data;
  } catch (e) {
    console.error(e);
  }
}

export async function deletePendingAction(id) {
  const { data } = await axios.delete(`${baseUrl}/pendingactions/${id}/`);
  return data;
}
