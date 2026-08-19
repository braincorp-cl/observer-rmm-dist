import axios from "axios";

// Feature 037 · cifrado de disco (Fase 3, la consola).
//
// Dos lecturas y ninguna escritura propia: el panel de flota (RF-04) y el
// detalle por agente (RF-05/RF-09). El refresco (RF-06) NO vive acá —reusa
// `refreshAgentWMI` de `@/api/agents`, que dispara el mismo `sysinfo` que puebla
// el resto de los activos—; duplicar el endpoint sería una segunda forma de
// pedir lo mismo.
//
// Los códigos llegan CRUDOS (RN-A05): el backend no interpreta el número de WMI,
// y la traducción a texto legible es cosa de la consola. Por eso las tablas de
// códigos viven en los componentes, no acá ni en el servidor.

const baseUrl = "/agents";

// Panel de cumplimiento (RF-04). El sujeto es el AGENTE, no el volumen: una fila
// por equipo con el veredicto de su volumen de sistema. Los filtros van como
// query params; un `state` desconocido lo rechaza el backend con 400 (el
// interceptor lo traduce a un toast), nunca devuelve la flota entera.
export async function fetchDiskEncryptionFleet(params = {}) {
  const { data } = await axios.get(`${baseUrl}/diskencryption/`, {
    params: params,
  });
  return data;
}

// Detalle de un equipo (RF-05 y RF-09): TODOS sus volúmenes —no sólo el de
// sistema— y el registro de cambios. Los tres campos del equipo (supported,
// query_error, measured_at) viajan explícitos para que la consola distinga «no
// lo soporta» de «no pudimos leer» de «nunca reportó» (RN-A03, RF-07).
export async function fetchDiskEncryptionDetail(agent_id) {
  const { data } = await axios.get(`${baseUrl}/${agent_id}/diskencryption/`);
  return data;
}
