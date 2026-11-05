// 050 / V2-P10: el `|` literal dentro de un mensaje de i18n.
//
// 🪤 En vue-i18n el `|` es el separador de PLURALES. Un mensaje que lo lleva
// como carácter —un título "X | VNC", una lista de letras "(D|d|H|h)"— se parte
// en ramas y `t()` sin contador devuelve SOLO LA PRIMERA. No hay aviso, no hay
// error de consola, no falla el build: el texto simplemente aparece cortado.
//
// Cómo se encontró: el gauntlet de V2-P10 midió el `document.title` de la
// ventana de VNC y vio `"DESKTOP-8I6R7NF - BrainCorp Lab - Talca DC"` en la v2
// contra `"… | VNC"` en la v1. La v1 construía el título con una plantilla de
// JS (sin i18n) y por eso el sufijo sobrevivía; al pasarlo por `t()` se perdió.
// El mismo defecto estaba ya en `takeControl` y `remoteBackground` desde que
// T048 llevó esos títulos a i18n, y en el mensaje de validación de periodos,
// que mostraba "…seguidos de (D" y nada más.
//
// La cura es la interpolación literal de vue-i18n: `{'|'}`.
//
// Esta prueba vigila las dos mitades del contrato:
//   1. los mensajes que llevan `|` literal se rinden COMPLETOS;
//   2. los que son plurales de verdad siguen eligiendo rama por contador.
// Lo segundo importa tanto como lo primero: escapar un plural de verdad lo
// rompería al revés, y el síntoma sería igual de silencioso.
import { describe, it, expect } from "vitest";
import { createI18n } from "vue-i18n";

import es from "@/i18n/es.json";
import en from "@/i18n/en.json";

function tr(locale) {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: "en",
    messages: { es, en },
  }).global.t;
}

function get(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}

// Mensajes donde el `|` es un carácter, no un separador de ramas.
const LITERALES = [
  "takeControl.metaTitle",
  "remoteBackground.metaTitle",
  "webVNC.metaTitle",
  "automatedTask.timePeriodErr",
];

// Mensajes donde el `|` SÍ separa ramas de plural. No deben escaparse nunca.
const PLURALES = [
  "agentWorkspace.badges.failingChecks",
  "agentWorkspace.badges.pendingPatches",
  "agentWorkspace.badges.pendingActions",
  "agentWorkspace.context.equipmentCount",
  "settingsPage.unsaved",
];

const CATALOGOS = { es, en };

describe("i18n · el | literal no se come el resto del mensaje", () => {
  for (const locale of ["es", "en"]) {
    describe(locale, () => {
      const t = tr(locale);
      const cat = CATALOGOS[locale];

      for (const clave of LITERALES) {
        it(`${clave} se rinde completo`, () => {
          const crudo = get(cat, clave);
          expect(crudo, `${clave} no existe en ${locale}.json`).toBeTruthy();

          // El catálogo debe traer el | escapado, nunca desnudo.
          expect(
            crudo.includes("{'|'}"),
            `${clave} lleva un | sin escapar: ${crudo}`,
          ).toBe(true);

          const salida = t(clave, {
            hostname: "DESKTOP-8I6R7NF",
            client: "BrainCorp Lab",
            site: "Talca DC",
          });

          // La barra sobrevive al render…
          expect(salida, `${clave} perdió la barra: ${salida}`).toContain("|");
          // …y con ella todo lo que venía después. Si vue-i18n hubiera partido
          // el mensaje, la salida sería un prefijo propio del original.
          const esperado = crudo.replace(/\{'\|'\}/g, "|");
          const colaEsperada = esperado.slice(esperado.lastIndexOf("|"));
          expect(salida.endsWith(colaEsperada.trimEnd())).toBe(true);
        });
      }

      for (const clave of PLURALES) {
        it(`${clave} sigue siendo un plural de verdad`, () => {
          const crudo = get(cat, clave);
          expect(crudo).toBeTruthy();
          // Un plural lleva sus ramas separadas por | DESNUDO: escaparlo lo
          // convertiría en un solo mensaje y el contador dejaría de elegir.
          expect(
            crudo.includes("{'|'}"),
            `${clave} es un plural y no debe llevar el | escapado`,
          ).toBe(false);
          expect(crudo.split("|").length).toBeGreaterThanOrEqual(2);

          const cero = t(clave, { n: 0 }, 0);
          const uno = t(clave, { n: 1 }, 1);
          const varios = t(clave, { n: 5 }, 5);
          expect(new Set([cero, uno, varios]).size).toBeGreaterThan(1);
          expect(varios).toContain("5");
        });
      }
    });
  }

  it("ningún mensaje nuevo cuela un | sin escapar fuera de la lista de plurales", () => {
    const permitidos = new Set(PLURALES);
    const sospechosos = [];

    for (const [locale, cat] of Object.entries(CATALOGOS)) {
      const recorrer = (nodo, ruta = []) => {
        if (nodo && typeof nodo === "object") {
          for (const [k, v] of Object.entries(nodo)) recorrer(v, [...ruta, k]);
          return;
        }
        if (typeof nodo !== "string") return;
        const clave = ruta.join(".");
        // Se mira el | DESNUDO: los escapados ya van como {'|'}.
        const desnudo = nodo.replace(/\{'\|'\}/g, "").includes("|");
        if (desnudo && !permitidos.has(clave)) {
          sospechosos.push(`${locale}.json → ${clave}: ${nodo}`);
        }
      };
      recorrer(cat);
    }

    expect(
      sospechosos,
      "Un | desnudo parte el mensaje en ramas de plural y t() devuelve solo " +
        "la primera, sin ningún aviso. Si es un carácter, escríbelo {'|'}; " +
        "si de verdad es un plural, agrégalo a PLURALES en este spec.\n" +
        sospechosos.join("\n"),
    ).toEqual([]);
  });
});
