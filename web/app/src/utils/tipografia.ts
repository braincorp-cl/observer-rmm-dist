// V2-G01 (2026-11-20): un valor hecho SOLO de palabras —sin ningún dígito— no
// es un valor dedicado de la lista cerrada (IP, MAC, versión, conteo, tamaño,
// ruta, comando, especificación, identificador generado): es un nombre, una
// empresa, un estado o una palabra suelta, y va en Archivo. La tanda sobre
// 738ceb0 midió en JetBrains Mono «Microsoft Corporation», «OK», «Juan»,
// «Multiprocessor Free», «None» y «Ninguno», todos de esta clase.
export function esPalabra(v: unknown): boolean {
  return typeof v === "string" && /\p{L}/u.test(v) && !/\d/.test(v);
}
