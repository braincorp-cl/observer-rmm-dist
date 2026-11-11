// Censo congelado de V2-G11: ninguna funcion de LECTURA puede devolver undefined
// en su camino de error.
//
// Por que existe: `catch (e) { console.error(e) }` sin `return` hace que la
// funcion devuelva undefined. El llamador lo asigna a las filas de una q-table
// y Quasar lee `rows.length` ⇒ TypeError de render. Un fallo de red tiene que
// dar tabla vacia, no una excepcion.
//
// 🪤 Lo que NO es la clase: `catch` sin return hay 208 en el arbol, y la mayoria
// son acciones de disparar-y-olvidar donde undefined no dana a nadie. Contar
// esas 208 como defectos es sobreconteo. La clase es LECTORA (fetch/get/load) ⇒
// su valor va a una coleccion que la vista recorre o mide.
//
// En la pasada global de T051 (2026-11-11) se midieron 34 lectoras asi y 15
// sitios peligrosos. Solo UNO se habia visto en 19 corridas de gauntlet, porque
// es el unico cuyo endpoint da 404 en staging; los otros 14 esperaban su propio
// fallo de red.
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve, join } from "node:path";

const APP = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const API = join(APP, "src/api");

// Piso del control positivo: si el censo encuentra menos lectoras que esto, lo
// que se rompio es la MEDICION (¿se movio src/api?), no el producto.
const PISO_LECTORAS = 25;

function lectorasDe(archivo) {
  const src = readFileSync(join(API, archivo), "utf8");
  const lineas = src.split("\n");
  const out = [];
  for (let i = 0; i < lineas.length; i++) {
    const m = /^export\s+async\s+function\s+(\w+)/.exec(lineas[i]);
    if (!m) continue;
    const nombre = m.group ?? m[1];
    if (!/^(fetch|get|load|list)/.test(nombre)) continue;
    // cuerpo de la funcion hasta su llave de cierre en columna 0
    let fin = i + 1;
    while (fin < lineas.length && !/^\}/.test(lineas[fin])) fin++;
    const cuerpo = lineas.slice(i, fin).join("\n");
    const mc = /\}\s*catch\s*\([^)]*\)\s*\{([\s\S]*)$/.exec(cuerpo);
    if (!mc) continue; // sin catch: el error sube, que es legitimo
    out.push({ archivo, nombre, catchBody: mc[1] });
  }
  return out;
}

describe("V2-G11 · ninguna lectora devuelve undefined al fallar", () => {
  const archivos = readdirSync(API).filter((f) => /\.(js|ts)$/.test(f));
  const lectoras = archivos.flatMap(lectorasDe);

  it("el censo se pudo medir (sin esto, cualquier verde es ciego)", () => {
    expect(archivos.length, "no se encontraron archivos en src/api").toBeGreaterThan(5);
    expect(
      lectoras.length,
      `el censo hallo ${lectoras.length} lectoras con catch, por debajo del piso de ${PISO_LECTORAS}`,
    ).toBeGreaterThanOrEqual(PISO_LECTORAS);
  });

  it("cada lectora con catch retorna algo en el catch", () => {
    const mudas = lectoras
      .filter((l) => !/\breturn\b|\bthrow\b/.test(l.catchBody))
      .map((l) => `${l.archivo}::${l.nombre}`);
    expect(
      mudas,
      "estas lectoras devuelven undefined cuando la peticion falla; el llamador " +
        "lo asignara a una coleccion y la vista reventara al medir .length:\n  " +
        mudas.join("\n  "),
    ).toEqual([]);
  });

  it("control negativo: el detector reconoce un catch mudo", () => {
    const mudo = `
      } catch (e) {
        console.error(e);
      }`;
    const conRetorno = `
      } catch (e) {
        console.error(e);
        return [];
      }`;
    const cuerpo = (s) => /\}\s*catch\s*\([^)]*\)\s*\{([\s\S]*)$/.exec(s)[1];
    expect(/\breturn\b|\bthrow\b/.test(cuerpo(mudo))).toBe(false);
    expect(/\breturn\b|\bthrow\b/.test(cuerpo(conRetorno))).toBe(true);
  });
});
