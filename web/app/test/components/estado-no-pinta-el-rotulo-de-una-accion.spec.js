/* eslint-env node */

// Regla de aceptación (V2-G05): rojo, ámbar y verde sólo significan ESTADO; el
// teal sólo marca acción o navegación. La enmienda del 2026-10-14 exime «un
// número o una insignia de estado DENTRO de un control» —el KPI, el contador de
// la campana— y cierra con la frase que decide este archivo:
//
//     «viola si la superficie propia del control, es decir su fondo, borde o
//      RÓTULO, lleva color de estado».
//
// 🔴 17.ª corrida del gauntlet: dos sitios llevaban un `q-icon` con color de
// estado DENTRO del `q-btn`, en la misma línea que el rótulo:
//
//   · ee/reporting/components/ReportScheduleForm.vue — «warning» en ámbar
//     delante de «Dependencias» (medido: color rgb(138,90,0) = --q-warning en
//     claro y rgb(255,193,94) en oscuro, rect 885,247,18,18 contenido en el del
//     botón 881,240,122,32, y el textContent del botón era «warning
//     Dependencias»).
//   · ee/reporting/components/ReportHistoryTable.vue — «warning» en
//     --q-negative delante de «Ver el error».
//
// 🔑 Y la exención no estaba mal redactada: ya nombraba el rótulo. Lo que falló
// fue que en los DOS archivos había un comentario mío DECLARANDO que el
// elemento era «la insignia de estado que va dentro», en vez de comprobar sobre
// cuál de las tres superficies caía. La propiedad que lo decide es comprobable y
// no se declara:
//
//   · un marcador de estado trae SUPERFICIE PROPIA (fondo o borde) y su texto
//     NO entra en el textContent del control;
//   · un glifo del rótulo no tiene ninguna de las dos cosas.
//
// Lo que esta guarda puede ver desde la fuente es la relación estructural
// —quién es descendiente de quién—, que es la mitad barata y la que caducó. La
// otra mitad (fondo propio, textContent) se mide en el navegador, en
// `instrumento/sonda_g05_rotulo.py` del hub.
//
// 🪤 Y el censo se escribe sobre la estructura, no sobre el literal: la primera
// pasada buscó `color="warning"` y devolvió DOS sitios, porque la estrella de
// favorito de Scripts lo lleva en un binding
// (`:color="props.row.favorite ? 'warning' : undefined"`). Un censo que sólo
// mira el literal estático declara «dos» donde hay tres.

import { describe, it, expect } from "vitest";
import { leerVue } from "../support/vue-sources.js";

const ESTADOS = ["warning", "negative", "positive", "info"];
const B = `\\b(${ESTADOS.join("|")})\\b`;

// `color=` / `:color=` / `text-color=` / `:text-color=`, con el estado adentro
// del valor (que puede ser una expresión).
const COLOR = new RegExp(
  `(?::|v-bind:)?(?:color|text-color)\\s*=\\s*"[^"]*${B}`,
);
// clase `text-<estado>`, estática o en un `:class`
const CLASE = new RegExp(
  `:?class\\s*=\\s*"[^"]*\\btext-(${ESTADOS.join("|")})\\b`,
);

const ETIQUETA = /<(\/?)([a-zA-Z][\w.-]*)([^>]*?)(\/?)>/g;
// elementos que nunca abren contexto aunque no se cierren solos
const VACIOS = new Set(["br", "hr", "img", "input", "q-separator", "q-space"]);

function pintaEstado(atributos) {
  return COLOR.test(atributos) || CLASE.test(atributos);
}

// Devuelve los descendientes de un `q-btn` que llevan color de estado, con la
// línea y el atributo CRUDO que se vio (enmienda s4: el booleano solo no basta).
export function estadoDentroDeUnBoton(fuente, ruta = "") {
  const plantilla = /<template>([\s\S]*)<\/template>/.exec(fuente);
  if (!plantilla) return [];
  const tpl = plantilla[1];
  const desplazamiento =
    fuente.slice(0, plantilla.index).split("\n").length - 1;
  const pila = [];
  const hallados = [];
  ETIQUETA.lastIndex = 0;
  let m;
  while ((m = ETIQUETA.exec(tpl)) !== null) {
    const [, cierre, etiqueta, atributos, auto] = m;
    const nombre = etiqueta.toLowerCase();
    if (cierre) {
      for (let i = pila.length - 1; i >= 0; i -= 1) {
        if (pila[i].nombre === nombre) {
          pila.length = i;
          break;
        }
      }
      continue;
    }
    const boton = pila.filter((p) => p.nombre === "q-btn").pop();
    if (boton && nombre !== "q-btn" && pintaEstado(atributos)) {
      hallados.push({
        ruta,
        etiqueta: nombre,
        linea: tpl.slice(0, m.index).split("\n").length + desplazamiento,
        atributo_crudo: atributos.replace(/\s+/g, " ").trim(),
        boton_crudo: boton.atributos.replace(/\s+/g, " ").trim(),
      });
    }
    if (!auto && !VACIOS.has(nombre)) pila.push({ nombre, atributos });
  }
  return hallados;
}

// Lista cerrada. Un sitio que no esté acá es un fallo, no una excepción nueva.
const EXENTOS = {
  "src/components/scripts/ScriptManager.vue":
    "excepcion (b) aprobada por el usuario el 2026-10-16: la estrella de " +
    "favorito de Scripts va en ambar como pide la maqueta. Y su q-btn es " +
    "`round` SIN rotulo: el icono es la superficie del control, no parte de un " +
    "rotulo que convive con el.",
};

describe("un color de estado no pinta el rótulo de una acción (V2-G05)", () => {
  it("el censo de los descendientes de q-btn con color de estado da exactamente la lista exenta", async () => {
    const fuentes = await leerVue();
    const hallados = fuentes.flatMap(({ ruta, fuente }) =>
      estadoDentroDeUnBoton(fuente, ruta),
    );
    const porArchivo = {};
    for (const h of hallados) (porArchivo[h.ruta] ||= []).push(h);
    expect(Object.keys(porArchivo).sort()).toEqual(Object.keys(EXENTOS).sort());
    // y el exento es el que creemos que es, con su atributo crudo a la vista
    const estrella = porArchivo["src/components/scripts/ScriptManager.vue"];
    expect(estrella).toHaveLength(1);
    expect(estrella[0].atributo_crudo).toMatch(/favorite \? 'warning'/);
    expect(estrella[0].boton_crudo).toMatch(/\bround\b/);
  });

  it("los dos sitios de la 17.ª corrida ya no pintan estado dentro del botón", async () => {
    const fuentes = await leerVue();
    const porRuta = Object.fromEntries(fuentes.map((f) => [f.ruta, f.fuente]));
    for (const ruta of [
      "src/ee/reporting/components/ReportScheduleForm.vue",
      "src/ee/reporting/components/ReportHistoryTable.vue",
    ]) {
      expect(porRuta[ruta], ruta).toBeTruthy();
      expect(estadoDentroDeUnBoton(porRuta[ruta], ruta)).toEqual([]);
    }
    // el ámbar de «Dependencias» no desapareció: salió del botón y quedó como
    // marcador del campo, con rótulo accesible propio
    const forma = porRuta["src/ee/reporting/components/ReportScheduleForm.vue"];
    expect(forma).toMatch(/name="warning"\s+color="warning"/);
    expect(forma).toMatch(/dependenciesMissing/);
    // y el glifo del historial sigue ahí, sin color de estado
    const hist = porRuta["src/ee/reporting/components/ReportHistoryTable.vue"];
    expect(hist).toMatch(
      /<q-icon name="warning" size="xs" class="q-mr-xs" \/>/,
    );
    expect(hist).not.toMatch(/color="negative"/);
  });

  it("la clave del marcador existe en los dos diccionarios", async () => {
    const es = (await import("@/i18n/es.json")).default;
    const en = (await import("@/i18n/en.json")).default;
    for (const [nombre, d] of [
      ["es", es],
      ["en", en],
    ]) {
      const v = d.reporting.scheduleForm.dependenciesMissing;
      expect(v, nombre).toBeTruthy();
      expect(v, nombre).not.toMatch(/[…]|\.\.\.$/);
    }
  });

  it("el clasificador trae su propio control positivo y negativo", () => {
    const dentro =
      '<template><q-btn color="primary"><q-icon name="warning" color="warning" /> Dependencias</q-btn></template>';
    const dinamico =
      "<template><q-btn><q-icon :color=\"row.favorite ? 'warning' : undefined\" /></q-btn></template>";
    const porClase =
      '<template><q-btn><span class="text-negative">3</span></q-btn></template>';
    const hermano =
      '<template><q-icon name="warning" color="warning" /><q-btn color="primary">Dependencias</q-btn></template>';
    const fueraDePlantilla =
      "<script setup>const c = 'color=\"warning\"';</script>";

    expect(estadoDentroDeUnBoton(dentro)).toHaveLength(1); // positivo
    expect(estadoDentroDeUnBoton(dinamico)).toHaveLength(1); // 🪤 el binding
    expect(estadoDentroDeUnBoton(porClase)).toHaveLength(1); // 🪤 la clase
    expect(estadoDentroDeUnBoton(hermano)).toEqual([]); // negativo: hermano
    expect(estadoDentroDeUnBoton(fueraDePlantilla)).toEqual([]); // sin template

    // y el cierre del botón acota de verdad: lo que viene DESPUÉS no entra
    const despues =
      '<template><q-btn>Acción</q-btn><q-icon color="negative" /></template>';
    expect(estadoDentroDeUnBoton(despues)).toEqual([]);
  });

  it("el censo mira de verdad", async () => {
    const fuentes = await leerVue();
    expect(fuentes.length).toBeGreaterThan(100);
    expect(fuentes.some((f) => f.ruta.endsWith("ReportScheduleForm.vue"))).toBe(
      true,
    );
    // y si se planta el defecto en una fuente real, el censo lo caza
    const real = fuentes.find((f) => f.ruta.endsWith("ReportHistoryTable.vue"));
    const plantado = real.fuente.replace(
      '<q-icon name="warning" size="xs" class="q-mr-xs" />',
      '<q-icon name="warning" color="negative" size="xs" class="q-mr-xs" />',
    );
    expect(plantado).not.toEqual(real.fuente);
    expect(estadoDentroDeUnBoton(plantado, real.ruta)).toHaveLength(1);
  });
});
