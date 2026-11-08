/* eslint-env node */

// Lectura del árbol de .vue para las pruebas de presencia (las que afirman que
// algo NO está en el código fuente). No montan nada: leen los archivos, que es
// lo único que detecta un defecto que vuelve por copiar y pegar.

import { readdir, readFile } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

// 🪤 Acá NO se puede usar `new URL("../../src", import.meta.url)`, que es el
// modo idiomático. Vite transforma esa forma cuando el primer argumento es un
// literal: la reescribe como URL de ACTIVO y en tiempo de prueba devuelve
// `http://localhost:3000/src`, con lo que `fileURLToPath` revienta con «The URL
// must be of scheme file». Con el argumento armado por concatenación Vite no la
// toca y sí funciona, que es por qué el mismo patrón vive sano en otro spec: la
// diferencia no es el directorio, es si el literal es estático.
// Se resuelve entonces desde `import.meta.url` pelado, que Vite no reescribe.
const AQUI = dirname(fileURLToPath(import.meta.url));
export const SRC = resolve(AQUI, "../../src");

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

// 🪤 Y el motivo de que esto NO se limite a `.vue`: el censo de la elipsis en
// i18n (V2-G08, 16.ª corrida) tiene que mirar TODOS los consumidores de una
// clave, y hay claves que se usan desde `.ts`. Un censo que solo lee `.vue`
// declara «un solo sitio» cuando hay dos.
export async function listarFuentes(
  extensiones = [".vue", ".ts", ".js"],
  dir = SRC,
) {
  const entradas = await readdir(dir, { withFileTypes: true });
  const salida = [];
  for (const entrada of entradas) {
    const ruta = join(dir, entrada.name);
    if (entrada.isDirectory())
      salida.push(...(await listarFuentes(extensiones, ruta)));
    else if (extensiones.some((e) => entrada.name.endsWith(e)))
      salida.push(ruta);
  }
  return salida.sort();
}

export async function leerFuentes(extensiones) {
  const archivos = await listarFuentes(extensiones);
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
