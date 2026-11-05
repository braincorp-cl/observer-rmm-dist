/* eslint-env node */

// Lectura del árbol de .vue para las pruebas de presencia (las que afirman que
// algo NO está en el código fuente). No montan nada: leen los archivos, que es
// lo único que detecta un defecto que vuelve por copiar y pegar.

import { readdir, readFile } from "node:fs/promises";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const SRC = fileURLToPath(new URL("../../src", import.meta.url));

export async function listarVue(dir = SRC) {
  const entradas = await readdir(dir, { withFileTypes: true });
  const salida = [];
  for (const entrada of entradas) {
    const ruta = join(dir, entrada.name);
    if (entrada.isDirectory()) salida.push(...(await listarVue(ruta)));
    else if (entrada.name.endsWith(".vue")) salida.push(ruta);
  }
  return salida.sort();
}

// Ruta relativa a web/app/src con separador «/» en cualquier plataforma, que es
// la forma en que se guardan los inventarios.
export const rutaCorta = (absoluta) =>
  "src/" + relative(SRC, absoluta).split(sep).join("/");

export async function leerVue() {
  const archivos = await listarVue();
  return Promise.all(
    archivos.map(async (ruta) => ({
      ruta: rutaCorta(ruta),
      fuente: await readFile(ruta, "utf8"),
    })),
  );
}

// Etiquetas de apertura de un componente, con sus atributos y su número de
// línea. `[^>]*` cruza saltos de línea, así que toma las etiquetas repartidas
// en varias líneas, que es como las deja prettier.
export function etiquetasDeApertura(fuente, nombre) {
  const re = new RegExp(`<${nombre}\\b[^>]*>`, "gi");
  const salida = [];
  let m;
  while ((m = re.exec(fuente)) !== null) {
    salida.push({
      etiqueta: m[0],
      linea: fuente.slice(0, m.index).split("\n").length,
    });
  }
  return salida;
}
