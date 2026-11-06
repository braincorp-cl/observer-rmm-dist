// 050 / V2-G15: el boot del anillo de foco está ÍNTEGRO y crea su capa.
//
// 🔴 Por qué existe este spec. Al retirar una guarda del boot corté el texto
// entre el comentario que la introducía y `function ocultar()`, y en ese tramo
// vivían TAMBIÉN `HOLGURA_VENTANA` y `noSenalaNingunLugar`, que `pintar()`
// llama. Resultado: `ReferenceError` en cada cuadro y la capa del anillo nunca
// se creaba —`crear()` sólo se llama desde `pintar()`—, o sea el anillo apagado
// en TODA la consola, desplegado y servido.
//
// 🔑 Y ninguna comprobación lo vio: `node --check` pasa porque la sintaxis es
// válida, el build pasa, y los tests pasaban porque NO cubrían el boot. Lo cazó
// una medición en el navegador (un TAB real con `focus-visible` en true y
// `capas_en_el_dom: 0`), que es caro y llega tarde. Esto lo caza en la CI.
//
// Lo que se vigila son los dos modos de fallo de un archivo así:
//   1. una referencia a algo que el archivo ya no define (lo que pasó);
//   2. el boot que se registra pero no crea su capa cuando el foco llega por
//      teclado (el efecto observable, no la forma del código).
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const AQUI = dirname(fileURLToPath(import.meta.url));
const RUTA = resolve(AQUI, "../../src/boot/anillo-foco.js");

describe("boot del anillo de foco: integridad del archivo", () => {
  it("no llama a ninguna función que el archivo no defina", () => {
    const src = readFileSync(RUTA, "utf8");
    // Se quitan comentarios y cadenas: el texto en prosa lleva paréntesis y
    // produciría falsos positivos (`anillo(`, `píxeles(`...).
    const limpio = src
      .replace(/\/\*[\s\S]*?\*\//g, " ")
      .replace(/(^|[^:])\/\/.*$/gm, "$1 ")
      .replace(/"(?:[^"\\]|\\.)*"/g, '""')
      .replace(/'(?:[^'\\]|\\.)*'/g, "''")
      .replace(/`(?:[^`\\]|\\.)*`/g, "``");
    const definidas = new Set();
    for (const re of [
      /function\s+([A-Za-z_$][\w$]*)/g,
      /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:function|\()/g,
    ]) {
      let m;
      while ((m = re.exec(limpio))) definidas.add(m[1]);
    }
    const propias = [...definidas];
    expect(propias.length).toBeGreaterThan(5);

    // Cada llamada a una función de nombre simple (no `algo.metodo()`) tiene que
    // estar definida acá o ser una global conocida.
    const GLOBALES = new Set([
      "if", "for", "while", "switch", "return", "typeof", "catch", "function",
      // 🪤 Palabras clave que van seguidas de `(` y no son llamadas:
      // `export default (` fue el primer falso positivo de este spec.
      "default", "else", "do", "new", "delete", "in", "of", "await", "yield",
      "throw", "try", "void",
      "requestAnimationFrame", "cancelAnimationFrame", "setTimeout",
      "clearTimeout", "getComputedStyle", "parseFloat", "parseInt", "Number",
      "String", "Boolean", "Array", "Object", "Math", "JSON", "isNaN",
    ]);
    const faltantes = new Set();
    const llamadas = /(^|[^.\w$])([a-z_$][\w$]*)\s*\(/g;
    let m;
    while ((m = llamadas.exec(limpio))) {
      const n = m[2];
      if (!definidas.has(n) && !GLOBALES.has(n)) faltantes.add(n);
    }
    expect([...faltantes].sort()).toEqual([]);
  });

  it("declara las piezas que `pintar` necesita", () => {
    const src = readFileSync(RUTA, "utf8");
    for (const pieza of [
      "function crear(",
      "function pintar(",
      "function ocultar(",
      "function noSenalaNingunLugar(",
      "function dentroDeLaVentana(",
      "HOLGURA_VENTANA",
    ]) {
      expect(src).toContain(pieza);
    }
  });
});

describe("boot del anillo de foco: crea su capa con el teclado", () => {
  let quitar;

  beforeEach(() => {
    document.body.innerHTML = "";
    vi.useFakeTimers();
    // jsdom no tiene `:focus-visible`; se hace que case con lo enfocado, que es
    // el caso que importa (foco llegado por tecla).
    const matches = window.Element.prototype.matches;
    quitar = () => {
      window.Element.prototype.matches = matches;
    };
    window.Element.prototype.matches = function (sel) {
      if (sel === ":focus-visible") return this === document.activeElement;
      return matches.call(this, sel);
    };
    window.requestAnimationFrame = (fn) => setTimeout(() => fn(0), 0);
    window.cancelAnimationFrame = (id) => clearTimeout(id);
  });

  afterEach(() => {
    quitar();
    vi.useRealTimers();
  });

  it("tras una tecla y un foco real, la capa existe en el DOM", async () => {
    const boot = (await import("@/boot/anillo-foco")).default;
    boot();

    const b = document.createElement("button");
    b.textContent = "control";
    document.body.appendChild(b);
    b.getBoundingClientRect = () => ({
      x: 40, y: 40, left: 40, top: 40, right: 140, bottom: 70,
      width: 100, height: 30,
    });

    // 🪤 El orden importa: primero la TECLA (el boot sólo pinta si la última
    // interacción fue de teclado) y después el foco.
    document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Tab" }));
    b.focus();
    b.dispatchEvent(new window.FocusEvent("focusin", { bubbles: true }));
    vi.advanceTimersByTime(60);

    const capas = document.querySelectorAll("#obs-anillo-foco");
    expect(capas.length).toBe(1);
    expect(capas[0].style.boxShadow).toContain("--obs-focus");
  });
});
