import axios from "axios";

// Feature 030 · modo perdido/robado (ADR-025).
//
// El backend responde 400 con `endpoint_response:<código>` cuando rechaza la
// operación —hoy sólo `empty_reason`—. El interceptor de axios
// (src/boot/axios.js) traduce ese código por `endpointResponse.codes.<código>`,
// así que acá no hay nada que manejar más allá de propagar el error.
//
// Ojo con una diferencia respecto de lock/alert/alarm: marcar un equipo como
// perdido NO falla porque el agente no conteste. El caso de uso central es un
// equipo apagado o ya en manos de otro, así que la respuesta trae
// `nats_delivered` como INFORMACIÓN —¿alcanzó a enterarse el equipo?— y no como
// condición de éxito.

const baseUrl = "/agents";

export async function fetchLostEquipment() {
  const { data } = await axios.get(`${baseUrl}/lostmode/`);
  return data;
}

export async function markAgentLost(agent_id, payload) {
  const { data } = await axios.post(
    `${baseUrl}/${agent_id}/lostmode/`,
    payload,
  );
  return data;
}

export async function recoverAgent(agent_id) {
  const { data } = await axios.delete(`${baseUrl}/${agent_id}/lostmode/`);
  return data;
}
