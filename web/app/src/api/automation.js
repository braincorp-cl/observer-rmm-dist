import axios from "axios";

const baseUrl = "/automation";

export async function sendPatchPolicyReset(payload) {
  const { data } = await axios.post(`${baseUrl}/patchpolicy/reset/`, payload);
  return data;
}

export async function fetchPolicyChecks(id) {
  try {
    const { data } = await axios.get(`${baseUrl}/policies/${id}/checks/`);
    return data;
  } catch (e) {
    console.error(e);
    // V2-G11 (2026-11-11): invariante — una lectora nunca devuelve undefined.
    // Este endpoint rinde una COLECCION, asi que el vacio es [].
    return [];
  }
}
