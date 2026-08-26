import axios from "axios";

// Feature 039 · Observer Erase — la consola de los Bloques C (certificación) y
// D (custodia), más la gobernanza B0 de las órdenes de borrado.
//
// Tres superficies, ninguna destructiva:
//  - Certificados (C): reportería y descargas (PDF/JSON). Sólo lectura.
//  - Ingresos de activos (D1) y certificación de destrucción física (C7).
//  - Órdenes gobernadas (B0): listar, segunda confirmación y cancelación. El
//    despacho real al equipo es del Bloque A y sigue GATED (ADR-029): desde acá
//    una orden se confirma a dos personas y se cancela, pero no viaja al equipo.
//
// El alcance por cliente/sitio lo recorta `filter_by_role` en el servidor; el
// 403 lo traduce a un toast el interceptor de axios, igual que el resto del
// producto (no se gatea por permiso en el cliente).

const baseUrl = "/erase";

// --- Certificados (Bloque C) -------------------------------------------------

// Reportería (RF-C). Con `agentId` recorta al equipo (la pestaña de la ficha del
// activo); sin él, devuelve todo lo que el rol autoriza.
export async function fetchEraseCertificates(agentId) {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await axios.get(`${baseUrl}/certificates/`, { params });
  return data;
}

// Detalle de un certificado + el resultado de verificar documento, firma y
// cadena (se recalcula en el servidor en cada lectura, no se cachea).
export async function fetchEraseCertificate(pk) {
  const { data } = await axios.get(`${baseUrl}/certificates/${pk}/`);
  return data;
}

// El nombre del PDF lo decide el servidor (`Content-Disposition`): es el mismo
// que quedó en la auditoría, así que se devuelve la respuesta completa y se
// arma la descarga con esa cabecera, no con un nombre inventado en el cliente.
export async function fetchEraseCertificatePDF(pk) {
  return await axios.get(`${baseUrl}/certificates/${pk}/pdf/`, {
    responseType: "blob",
  });
}

export async function fetchEraseCertificateJSON(pk) {
  return await axios.get(`${baseUrl}/certificates/${pk}/json/`, {
    responseType: "blob",
  });
}

// --- Custodia (Bloque D) -----------------------------------------------------

export async function fetchAssetIntakes() {
  const { data } = await axios.get(`${baseUrl}/intake/`);
  return data;
}

export async function createAssetIntake(payload) {
  const { data } = await axios.post(`${baseUrl}/intake/`, payload);
  return data;
}

// C7 · emite el certificado de destrucción física para un activo ya ingresado.
// Es el flujo de valor inmediato: no necesita el Bloque A ni el B.
export async function certifyAssetDestruction(pk, payload) {
  const { data } = await axios.post(
    `${baseUrl}/intake/${pk}/certify-destruction/`,
    payload,
  );
  return data;
}

// --- Órdenes gobernadas (B0) -------------------------------------------------

export async function fetchWipeOrders() {
  const { data } = await axios.get(`${baseUrl}/orders/`);
  return data;
}

export async function fetchWipeOrder(pk) {
  const { data } = await axios.get(`${baseUrl}/orders/${pk}/`);
  return data;
}

// Segunda confirmación (RF-G02). El servidor rechaza con 409 si la confirma la
// misma persona que ordenó o si la orden no está en un estado confirmable.
export async function confirmWipeOrder(pk, payload) {
  const { data } = await axios.post(
    `${baseUrl}/orders/${pk}/confirm/`,
    payload,
  );
  return data;
}

export async function cancelWipeOrder(pk, payload) {
  const { data } = await axios.post(`${baseUrl}/orders/${pk}/cancel/`, payload);
  return data;
}

// --- Recuperación de archivos (fileretrieval · B1 · NO destructiva) ----------
//
// Recuperar archivos ANTES de borrar. Se ordena desde un caso perdido abierto
// (el servidor rechaza con 409 si no lo hay). El permiso `can_retrieve_files` lo
// gatea en el servidor; acá no se gatea en el cliente (el 403 lo traduce el
// interceptor de axios, igual que el resto del producto).

export async function createFileRetrievalOrder(agentId, payload) {
  const { data } = await axios.post(
    `${baseUrl}/agents/${agentId}/fileretrieval/`,
    payload,
  );
  return data;
}

export async function fetchFileRetrievalOrders(agentId) {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await axios.get(`${baseUrl}/fileretrieval/`, { params });
  return data;
}

export async function fetchFileRetrievalOrder(pk) {
  const { data } = await axios.get(`${baseUrl}/fileretrieval/${pk}/`);
  return data;
}

export async function cancelFileRetrievalOrder(pk) {
  const { data } = await axios.post(`${baseUrl}/fileretrieval/${pk}/cancel/`, {});
  return data;
}

// La descarga la sirve el servidor con su propio nombre; se devuelve el blob.
export async function downloadRetrievedFile(pk, fileId) {
  return await axios.get(
    `${baseUrl}/fileretrieval/${pk}/files/${fileId}/download/`,
    { responseType: "blob" },
  );
}
