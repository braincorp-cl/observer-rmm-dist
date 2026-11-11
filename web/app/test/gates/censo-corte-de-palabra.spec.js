// Censo congelado de V2-G07: el default de corte en una celda de tabla es el
// seguro para prosa, y `anywhere` es OPT-IN.
//
// Por que existe: el default ERA `anywhere`, que parte la palabra siempre -aunque
// cabria entera en la linea siguiente-. Se eligio asi para que una URL o un GUID
// no fijara el ancho de la columna, o sea para no provocar el scroll horizontal
// que persigue V2-G06: los dos criterios se empujaban y el producto no podia
// cumplir los dos. Con la enmienda de G06 del 2026-11-11 -cuenta el scroll de la
// PAGINA, no el area propia de una tabla ancha- el default se invirtio.
//
// Es una sola linea de CSS y volver a ponerla en `anywhere` no rompe ninguna
// prueba de componente: se revierte en silencio. De ahi este censo.
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const SASS = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../src/css/app.sass",
);

describe("V2-G07 · el corte de palabra en celdas", () => {
  const sass = readFileSync(SASS, "utf8");

  // Bloques `  .q-table td<algo>` con su propiedad overflow-wrap, en orden.
  const reglas = [
    ...sass.matchAll(
      /^\s*\.q-table td(\S*)\n(?:\s+[^\n]*\n)*?\s+overflow-wrap:\s*(\S+)/gm,
    ),
  ].map((m) => ({ sel: m[1] || "(default)", valor: m[2] }));

  it("el censo se pudo medir (sin esto, cualquier verde es ciego)", () => {
    expect(
      reglas.length,
      "no se hallo ninguna regla `.q-table td ... overflow-wrap` en app.sass: " +
        "cambio el nombre del archivo o la estructura del bloque",
    ).toBeGreaterThanOrEqual(3);
  });

  it("el default de una celda NO es anywhere", () => {
    const def = reglas.find((r) => r.sel === "(default)");
    expect(def, "no hay regla por defecto para .q-table td").toBeTruthy();
    expect(
      def.valor,
      "el default volvio a `anywhere`: eso parte la palabra siempre y reabre " +
        "V2-G07. `anywhere` va en la clase obs-break-anywhere, por columna.",
    ).toBe("break-word");
  });

  it("anywhere existe, pero solo como opt-in por clase", () => {
    const conAnywhere = reglas.filter((r) => r.valor === "anywhere");
    expect(conAnywhere.length, "el opt-in desaparecio").toBeGreaterThanOrEqual(
      1,
    );
    for (const r of conAnywhere) {
      expect(r.sel, `anywhere sin clase que lo pida: ${r.sel}`).toContain(
        ".obs-break-anywhere",
      );
    }
  });
});
