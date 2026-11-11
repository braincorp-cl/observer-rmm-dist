// V2-G01: la vara manda la FECHA a Archivo y LA HORA a JetBrains Mono
// (pista 2026-10-18). Una celda de bitacora rinde las dos juntas y el formato lo
// elige el usuario, asi que el trozo no se puede identificar por su POSICION:
// con el formato por defecto "MMM-DD-YYYY - HH:mm" el trozo del medio es un
// guion. Esta prueba congela la regla de forma y, sobre todo, sus NEGATIVOS.
import { describe, it, expect } from "vitest";
import { esHoraDeReloj } from "@/utils/format";

describe("V2-G01 · esHoraDeReloj", () => {
  it("reconoce la hora en los formatos que el usuario puede elegir", () => {
    for (const h of ["21:47", "9:05", "00:00", "13:52:07", "21:47:00"]) {
      expect(esHoraDeReloj(h), `deberia ser hora: ${h}`).toBe(true);
    }
  });

  it("control negativo: la fecha y los separadores NO son hora", () => {
    // Trozos reales de los formatos que el proyecto ofrece.
    for (const f of ["MMM-DD-YYYY", "nov-10-2026", "2026-11-10", "10/11/2026", "-", "", "PM"]) {
      expect(esHoraDeReloj(f), `NO deberia ser hora: ${f}`).toBe(false);
    }
  });

  it("parte el formato por defecto en fecha, separador y hora", () => {
    const partes = "nov-10-2026 - 21:47".split(" ");
    expect(partes).toHaveLength(3);
    expect(partes.map(esHoraDeReloj)).toEqual([false, false, true]);
  });
});
