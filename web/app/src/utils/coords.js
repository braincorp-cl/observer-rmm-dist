// Feature 051 · coordenadas del sitio (feature 026) escritas a mano.
//
// El campo era `type="number"`: con la coma decimal de es-CL/es-MX el navegador
// entrega "" y la coordenada se convertía en `null` sin aviso. Con las dos
// escritas con coma, «ambas o ninguna» aceptaba «ninguna» y el sitio quedaba
// guardado sin ubicación, perdiendo el respaldo de geo y la geocerca.
//
// Regla: vacío = sin coordenada (null); un número con punto o coma = ese
// número; cualquier otro texto = NaN, que la validación rechaza. Un texto que
// no es número nunca se convierte en «sin coordenada».

const NUMERO = /^[+-]?\d+(?:[.,]\d+)?$/;

export function parseCoord(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : NaN;
  const texto = String(value).trim();
  if (texto === "") return null;
  if (!NUMERO.test(texto)) return NaN;
  return Number(texto.replace(",", "."));
}

// Devuelve null si el par es válido, o el motivo: "invalid" (no es número o
// fuera de rango, o falta su pareja) o "nullIsland" (0, 0). Ambas o ninguna:
// media coordenada no ubica nada y el backend la rechaza igual.
export function coordError(own, other, max) {
  const a = parseCoord(own);
  const b = parseCoord(other);
  if (a === null && b === null) return null;
  if (a === null || Number.isNaN(a) || Math.abs(a) > max) return "invalid";
  // (0, 0) es el "null island" del Atlántico: siempre es un campo a medio
  // llenar, nunca una oficina.
  if (a === 0 && b === 0) return "nullIsland";
  return null;
}
