// @vitest-environment node

/* eslint-env node */

// Hallazgo #3 de AUDITORIA-COLOR.md (`git show 9f419ad:AUDITORIA-COLOR.md`):
//
//   <q-tooltip class="bg-white text-primary">
//
// `bg-white` es `background:#fff !important` de Quasar y le gana al
// `.q-tooltip{background:var(--obs-raised)}` de css/app.sass:482, que no lleva
// !important. En tema oscuro el texto ya está forzado a var(--obs-text)
// (app.sass:488), así que el resultado es #E6EDF5 sobre #FFFFFF = 1,18:1: el
// tooltip queda invisible.
//
// Esta es una prueba de PRESENCIA, no de montaje: el defecto no se reproduce
// montando un componente —habría que compilar el sass y medir el cascade— sino
// leyendo el código, que es además por donde vuelve: se propaga copiando y
// pegando el bloque del botón de ayuda de un modal al siguiente.
//
// ESTADO: el hallazgo #3 NO está arreglado. El merge 467d451 cerró 18 de los 24
// hallazgos de color y este quedó fuera. Hay 78 etiquetas en 74 archivos, que
// quedan inventariadas en q-tooltip-bg-white.baseline.json. La prueba es un
// trinquete en los dos sentidos:
//
//   - una etiqueta nueva en un archivo que no está en el inventario, o una de
//     más en uno que sí está, falla: eso es la reintroducción;
//   - una de menos también falla, pidiendo actualizar el inventario: así la
//     deuda solo puede bajar, y el día que llegue a cero el inventario queda
//     vacío y la prueba pasa a ser la regla estricta sin tocar una línea.

import { describe, it, expect } from "vitest";
import { leerVue, etiquetasDeApertura } from "../support/vue-sources.js";
import inventario from "./q-tooltip-bg-white.baseline.json";

const PROHIBIDO = /\bbg-white\b/;

async function tooltipsConFondoBlanco() {
  const archivos = await leerVue();
  const porArchivo = {};
  const detalle = [];
  for (const { ruta, fuente } of archivos) {
    for (const { etiqueta, linea } of etiquetasDeApertura(
      fuente,
      "q-tooltip",
    )) {
      if (PROHIBIDO.test(etiqueta)) {
        porArchivo[ruta] = (porArchivo[ruta] ?? 0) + 1;
        detalle.push(`${ruta}:${linea}`);
      }
    }
  }
  return { porArchivo, detalle };
}

describe("q-tooltip no lleva bg-white (AUDITORIA-COLOR.md #3)", () => {
  it("ningún componente reintroduce bg-white en un q-tooltip", async () => {
    const { porArchivo } = await tooltipsConFondoBlanco();

    const nuevos = Object.keys(porArchivo)
      .filter((ruta) => inventario[ruta] === undefined)
      .sort();
    expect(
      nuevos,
      "q-tooltip con bg-white en archivos que no estaban: borrá `bg-white " +
        "text-primary` del class — el .q-tooltip de css/app.sass:482 ya " +
        "tematiza fondo y texto",
    ).toEqual([]);

    const crecieron = Object.keys(porArchivo)
      .filter((ruta) => porArchivo[ruta] > (inventario[ruta] ?? 0))
      .map((ruta) => `${ruta}: ${inventario[ruta]} → ${porArchivo[ruta]}`)
      .sort();
    expect(
      crecieron,
      "archivos ya conocidos que ahora traen MÁS q-tooltip con bg-white",
    ).toEqual([]);
  });

  it("el inventario de deuda no tiene entradas de más", async () => {
    // Si alguien arregla uno de los 74, esta prueba falla y pide bajar el
    // inventario. Es lo que impide que el trinquete se afloje con el tiempo.
    const { porArchivo } = await tooltipsConFondoBlanco();
    const sobrantes = Object.keys(inventario)
      .filter((ruta) => (porArchivo[ruta] ?? 0) < inventario[ruta])
      .map((ruta) => `${ruta}: ${inventario[ruta]} → ${porArchivo[ruta] ?? 0}`)
      .sort();
    expect(
      sobrantes,
      "deuda pagada: bajá estos archivos en " +
        "test/styles/q-tooltip-bg-white.baseline.json",
    ).toEqual([]);
  });

  it("el inventario sigue siendo deuda pendiente y no un permiso permanente", async () => {
    // Deja el número a la vista en cada corrida y deja constancia de que el
    // objetivo es cero. No sube nunca: el trinquete de arriba lo impide.
    const total = Object.values(inventario).reduce((a, b) => a + b, 0);
    expect(total).toBeLessThanOrEqual(78);
  });
});
