import axios from "axios";

const baseUrl = "/services";

export async function getAgentServices(agent_id, params = {}) {
  try {
    const { data } = await axios.get(`${baseUrl}/${agent_id}/`, {
      params: params,
    });
    return data;
  } catch (e) {
    console.error(e);
    // V2-G11 (2026-11-11): sin este return la funcion devuelve undefined y el
    // llamador lo asigna a las filas de una q-table, que lee rows.length y
    // revienta. Un fallo de red tiene que dar tabla vacia, no excepcion.
    return [];
  }
}

export async function getAgentServiceDetails(agent_id, svcname, params = {}) {
  try {
    const { data } = await axios.get(`${baseUrl}/${agent_id}/${svcname}/`, {
      params: params,
    });
    return data;
  } catch (e) {
    console.error(e);
    // V2-G11 (2026-11-11): invariante — una lectora nunca devuelve undefined.
    // Este endpoint rinde UN recurso, asi que el vacio es {} y no [].
    return {};
  }
}

export async function editAgentServiceStartType(agent_id, svcname, payload) {
  const { data } = await axios.put(
    `${baseUrl}/${agent_id}/${svcname}/`,
    payload,
  );
  return data;
}

export async function sendAgentServiceAction(agent_id, svcname, payload) {
  const { data } = await axios.post(
    `${baseUrl}/${agent_id}/${svcname}/`,
    payload,
  );
  return data;
}
