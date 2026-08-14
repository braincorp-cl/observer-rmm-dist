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

// Feature 030 · Fase 1 · la línea de tiempo del caso.
//
// Devuelve `{state, evidence}`: el caso (motivo, quién lo abrió, cadencia) y sus
// piezas ordenadas de la más reciente a la más antigua.
export async function fetchLostEvidence(agent_id) {
  const { data } = await axios.get(`${baseUrl}/${agent_id}/lostmode/evidence/`);
  return data;
}

// Descarga UNA pieza de evidencia como blob.
//
// Por qué blob y no un `<img src="...">` apuntando a la URL: la descarga tiene
// que llevar la cabecera de autenticación —la evidencia está detrás de un
// permiso propio (`can_view_lost_evidence`, ADR-025)— y una etiqueta <img> no la
// manda. Además, así la imagen nunca queda en una URL que alguien pueda pegar
// en otra parte: el object URL vive en esta pestaña y se revoca al cerrar.
export async function fetchLostEvidenceFile(agent_id, id) {
  const { data } = await axios.get(
    `${baseUrl}/${agent_id}/lostmode/evidence/${id}/file/`,
    { responseType: "blob" },
  );
  return data;
}

// Feature 030 · Fase 3 · T022 · exportación del caso a PDF.
//
// Devuelve la RESPUESTA COMPLETA y no sólo el blob, a diferencia de las otras
// de este archivo: el nombre del archivo lo decide el servidor y viaja en
// `Content-Disposition`. Armarlo en el cliente daría un nombre distinto al que
// quedó registrado en la auditoría, y este documento es justamente el que
// alguien va a tener que poder rastrear.
//
// El permiso `can_view_lost_evidence` NO se comprueba acá: exportar sólo exige
// operar el caso. Lo que ese permiso decide en el servidor es si el PDF lleva
// las imágenes, y el propio documento lo declara en la portada cuando faltan.
export async function exportLostCase(agent_id) {
  return await axios.get(`${baseUrl}/${agent_id}/lostmode/export/`, {
    responseType: "blob",
  });
}
