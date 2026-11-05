import axios from "axios";

// Feature 055 · inventario de medios de almacenamiento (la consola).
//
// Dos lecturas y ninguna escritura: el panel de flota (RF-06) y el detalle por
// equipo (RF-01). Toda la feature es de SOLO LECTURA — no hay endpoint que
// altere un disco, y no lo habrá acá (RN-01).
//
// Los códigos llegan CRUDOS (RN-04): el backend no interpreta el número que
// entrega el sistema, y la traducción a texto legible es cosa de la consola.
// Por eso las tablas de códigos viven en los componentes y en el i18n, no acá
// ni en el servidor.

const baseUrl = "/agents";

// Panel de categoría alcanzable (RF-06). El sujeto es el AGENTE, no el disco:
// una fila por equipo con el veredicto de su disco de sistema (RN-03). Un
// `verdict` desconocido lo rechaza el backend con 400 —el interceptor lo
// traduce a un toast—, y nunca devuelve la flota entera como si el filtro se
// hubiera aplicado.
export async function fetchStorageMediaFleet(params = {}) {
  const { data } = await axios.get(`${baseUrl}/storagemedia/`, {
    params: params,
  });
  return data;
}

// Detalle de un equipo (RF-01): TODOS sus discos fijos, no sólo el de sistema.
// Los cuatro campos del equipo (supported, query_error, capabilities_probed,
// measured_at) viajan explícitos para que la consola distinga «no lo soporta»
// de «no pudimos leer» de «no se sondeó» de «nunca reportó» (RN-02).
export async function fetchStorageMediaDetail(agent_id) {
  const { data } = await axios.get(`${baseUrl}/${agent_id}/storagemedia/`);
  return data;
}
