// V2-G01 (2026-11-20, corregido tras la tanda sobre fe48eb4): un valor hecho
// SOLO de palabras —sin ningún dígito— es un nombre, una empresa, un estado o
// una palabra suelta, y va en Archivo. La primera versión olvidó las FORMAS de
// identificador sin dígitos y mandó a Archivo «C:\Windows», «C:» y los
// PNPDeviceID `SWD\MSRRAS\MS_*`, que son ruta (clase 5) e identificador
// (clase 10). Esas formas se reconocen aparte y nunca son palabra.
export function esIdentificador(v: unknown): boolean {
  return typeof v === "string" && (/[\\|_]/.test(v) || /^[A-Za-z]:/.test(v));
}

export function esPalabra(v: unknown): boolean {
  return (
    typeof v === "string" &&
    /\p{L}/u.test(v) &&
    !/\d/.test(v) &&
    !esIdentificador(v)
  );
}

// V2-G01 (2026-11-21): un modelo de hardware es especificación (clase 7) y va
// en mono AUNQUE sea solo palabras («VMware SVGA II Adapter»): la tanda sobre
// 6a1ef85 lo midió en Archivo y era violación. Lo único que sale del mono es
// el marcador de AUSENCIA que manda el agente cuando no hay dato («None»,
// «N/A», «No Enclosure N/A»): no es un valor, es la falta de uno.
export function esAusencia(v: unknown): boolean {
  if (v === null || v === undefined) return true;
  const t = String(v).trim();
  return t === "" || /^(none|n\/a|unknown|no enclosure( n\/a)?)$/i.test(t);
}
