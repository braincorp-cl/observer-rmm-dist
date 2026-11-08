/* eslint-env node */

// 050 / V2-G08: un «…» es la marca de un texto RECORTADO. Si aparece pegado a
// un texto que no se recortó, miente; y si marca un recorte, el valor completo
// tiene que salir por algún canal.
//
// 🔴 Por qué existe este spec. En la 15.ª corrida, tres críticos midieron el
// mismo elemento: el `lead` de `AiScriptPromptModal` era
// `${prefix.trim()}…` —el prefijo de la frase que el operador continúa— y
// salía como un `<div>` suelto con `scrollWidth == clientWidth` (726 = 726),
// terminando en U+2026 y con CERO canales: `title` nulo, `aria-label` nulo,
// `q-tooltip` vacío en DOM y en hover. El «…» era decorativo, pero para quien
// lee —y para el detector— es indistinguible de un recorte.
//
// 🔑 La relación «este texto sigue en ese campo» es ESTRUCTURAL, no
// tipográfica. El prefijo pasó a ser el rótulo del `q-input` que se completa:
// un rótulo se lee sin ambigüedad y no necesita glifo.
//
// 🪤 Y el censo de la clase destapó un segundo sitio que nadie midió:
// `AutomationManager.policyMeta` rellenaba el conteo ausente con «…», que
// además de tener forma de corte no distinguía «cargando» de «falló», porque
// su `.catch(() => {})` dejaba el valor en `null` para siempre.
//
// Censo de los sitios donde el código PEGA una elipsis, congelado acá: los
// únicos legítimos son los que marcan un recorte de verdad y llevan canal.
import { describe, it, expect, beforeAll } from "vitest";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { leerVue } from "../support/vue-sources.js";

// 🪤 La ruta NO se arma con `new URL("literal", import.meta.url)`: Vite
// reescribe esa forma y deja de apuntar al archivo. Ver vue-sources.js.
const APP = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

// Sitios donde el código pega «…» o «...» a un valor. Cada uno dice por qué es
// legítimo. Un sitio nuevo tiene que entrar acá a mano, con su razón.
const ELIPSIS_LEGITIMA = {
  "src/components/agents/AssetCustodyTimeline.vue":
    "recorta el hash a 16 de 64 hex y el :title del mismo nodo trae los 64",
  "src/utils/format.ts":
    "truncateText: solo pega «...» cuando txt.length > chars, y cada llamador declara su canal",
};

let vue;
beforeAll(async () => {
  vue = await leerVue();
});

// Se miran los literales del CÓDIGO, no los de i18n: una elipsis dentro de una
// frase traducida es prosa («Cargando…»), y eso no es lo que se persigue.
const PEGA_ELIPSIS = /(?:`[^`\n]*|["'][^"'\n]*)(?:…|\.\.\.)(?:`|["'])/;

const sinComentarios = (fuente) =>
  fuente
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/.*$/gm, "$1 ");

describe("censo: quién pega una elipsis a un valor", () => {
  it("solo los sitios declarados, cada uno con su razón", () => {
    const hallados = [];
    for (const { ruta, fuente } of vue) {
      if (PEGA_ELIPSIS.test(sinComentarios(fuente))) hallados.push(ruta);
    }
    // format.ts no es .vue: se mira aparte, abajo.
    expect(hallados.sort()).toEqual(
      Object.keys(ELIPSIS_LEGITIMA)
        .filter((r) => r.endsWith(".vue"))
        .sort(),
    );
  });

  it("truncateText sigue siendo el único sitio de utils que la pega", async () => {
    const src = await readFile(resolve(APP, "src/utils/format.ts"), "utf8");
    const limpio = sinComentarios(src);
    expect(PEGA_ELIPSIS.test(limpio)).toBe(true);
    // Y lo decisivo del arreglo de la corrida anterior: `>`, no `>=`. Con
    // `>=`, un texto de largo exacto salía ENTERO con «...» pegado.
    expect(limpio).toMatch(
      /txt\.length > chars \? txt\.substring\(0, chars\) \+ "\.\.\." : txt/,
    );
  });

  it("el censo mira de verdad: hay .vue que leer", () => {
    expect(vue.length).toBeGreaterThan(100);
  });
});

describe("AiScriptPromptModal: el prefijo es rótulo, no fragmento con glifo", () => {
  let fuente;
  beforeAll(async () => {
    fuente = await readFile(
      resolve(APP, "src/components/scripts/AiScriptPromptModal.vue"),
      "utf8",
    );
  });

  it("ya no existe un `lead` que pegue la elipsis", () => {
    expect(fuente).not.toMatch(/const lead = computed/);
    expect(fuente).not.toMatch(/\{\{ lead \}\}/);
  });

  it("el prefijo entra como rótulo del campo que se completa", () => {
    expect(fuente).toMatch(/:label="prefix\.trim\(\)"/);
    expect(fuente).toMatch(/stack-label/);
  });

  // El prefijo tiene que seguir siendo EL MISMO texto que se envía: si se
  // separan, la pantalla y lo que recibe el modelo dejan de coincidir, que es
  // justo la propiedad que el comentario original defendía.
  it("lo que se muestra y lo que se envía salen del mismo `prefix`", () => {
    expect(fuente).toMatch(
      /onDialogOK\(`\$\{prefix\.value\}\$\{promptText\.value\.trim\(\)\}`\)/,
    );
  });
});

describe("AutomationManager: el hueco de un conteo se lee, y dice cuál es", () => {
  let fuente;
  beforeAll(async () => {
    fuente = await readFile(
      resolve(APP, "src/components/automation/AutomationManager.vue"),
      "utf8",
    );
  });

  it("el relleno ya no es un glifo con forma de corte", () => {
    expect(sinComentarios(fuente)).not.toMatch(/\?\s*"…"\s*:/);
  });

  it("distingue cargando de fallado, y el fallo deja de ser silencioso", () => {
    expect(fuente).toMatch(/automationManager\.countLoading/);
    expect(fuente).toMatch(/automationManager\.countError/);
    // 🪤 El `.catch(() => {})` vacío de `loadPolicyCounts` es lo que hacía
    // permanente el hueco: ahora su catch TIENE que escribir el valor. Se
    // afirma sobre ese catch, no sobre cualquier catch vacío del archivo: el
    // de `loadSectionCounts` alimenta una insignia que con `null` simplemente
    // no se dibuja, que es otra cosa y no se toca acá.
    expect(fuente).toMatch(
      /\.catch\(\(\) => \{\s*this\.policyCounts\[pol\.id\]\[k\] = "error";\s*\}\)/,
    );
  });

  it("las dos palabras existen en los dos idiomas", async () => {
    for (const idioma of ["es", "en"]) {
      const d = JSON.parse(
        await readFile(resolve(APP, `src/i18n/${idioma}.json`), "utf8"),
      );
      expect(d.automationManager.countLoading).toBeTruthy();
      expect(d.automationManager.countError).toBeTruthy();
    }
  });
});
