import axios from "axios";

const baseUrl = "/tasks";

export async function fetchTasks(params = {}) {
  try {
    const { data } = await axios.get(`${baseUrl}/`, { params: params });
    return data;
  } catch (e) {
    console.error(e);
    // V2-G11 (2026-11-11): invariante — una lectora nunca devuelve undefined.
    // Este endpoint rinde una COLECCION, asi que el vacio es [].
    return [];
  }
}

export async function saveTask(payload) {
  const { data } = await axios.post(`${baseUrl}/`, payload);
  return data;
}

export async function updateTask(id, payload) {
  const { data } = await axios.put(`${baseUrl}/${id}/`, payload);
  return data;
}

export async function removeTask(id) {
  const { data } = await axios.delete(`${baseUrl}/${id}/`);
  return data;
}

export async function runTask(id, payload) {
  const { data } = await axios.post(`${baseUrl}/${id}/run/`, payload);
  return data;
}
