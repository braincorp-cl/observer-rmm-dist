/* eslint-env node */

// Regla de aceptación (V2-G05): rojo, ámbar y verde sólo significan ESTADO; el
// teal sólo marca acción o navegación. La enmienda del 2026-10-14 exime «un
// número o una insignia de estado DENTRO de un control» y cierra con la frase
// que decide este archivo:
//
//     «viola si la superficie propia del control, es decir su fondo, borde o
//      RÓTULO, lleva color de estado».
//
// 🔴 17.ª corrida: un `q-icon` ámbar DENTRO del `q-btn` «Dependencias», en la
// misma línea que el rótulo (textContent del botón: «warning Dependencias»).
// 🔴 18.ª corrida: lo saqué del botón y lo puse «al lado»... dentro del
// `label.q-field` del q-select, que es OTRO control — el slot `#after` se rinde
// dentro del campo. Medido: icono rect 879,247,18,18 contenido en el del campo
// 437,236,566,60, sin fondo ni borde propios, position relative. Cinco de los
// seis críticos lo cazaron.
//
// 🔑 Dos lecciones, y la segunda corrige a la primera:
//
//  1. La clase no es «estar dentro de ESTE botón», es «caer sobre la superficie
//     propia de ALGÚN control». Mover el color al contenedor no lo saca.
//  2. La prueba que escribí en la 17.ª —«un marcador trae fondo o borde
//     propios»— describe cómo se DIBUJAN normalmente los marcadores, no qué los
//     hace marcadores. Un marcador dibujado como icono pelado no tiene ninguno
//     de los dos. Prueba medida: los iconos `obs-fleet__state` del árbol de
//     flota salen «glifo del rótulo» por esa prueba y son estado legítimo (17
//     corridas verdes, y la evidencia pedida del criterio ORDENA censarlos).
//     Lo que los divide es si el elemento REPORTA UN DATO: trae liga a un campo
//     de la API y además nombra el estado en su propio rótulo accesible o viene
//     pegado al dato que informa. Un glifo del rótulo no reporta nada: el color
//     es todo el mensaje.
//
// Por eso esta guarda NO intenta decidir sola: censa y exige que cada sitio
// esté en una LISTA CERRADA con su razón, igual que el criterio maneja sus
// excepciones (a)..(d). Un sitio nuevo reprueba hasta que alguien lo justifique.
//
// 🪤 Y el censo por la ESCRITURA del atributo siempre pierde una codificación.
// Van tres: el literal `color="warning"` perdió el binding (`:color="x ?
// 'warning' : undefined"`); el binding perdió la clase (`class="text-negative"`);
// y la clase perdió el nombre COMPUESTO (`:class="`obs-fleet__state--${st}`"`),
// que es por donde el árbol de flota se escapó. El censo autoritativo es el del
// DOM por COLOR COMPUTADO (`instrumento/sonda_g05_rotulo.py` en el hub); éste
// fija los sitios conocidos.

import { describe, it, expect } from "vitest";
import { leerVue } from "../support/vue-sources.js";

const ESTADOS = ["warning", "negative", "positive", "info"];
const UNO = `(${ESTADOS.join("|")})`;

// color= / :color= / text-color= / :text-color=, con el estado en el valor
const COLOR = new RegExp(
  `(?::|v-bind:)?(?:color|text-color)\\s*=\\s*"[^"]*\\b${UNO}\\b`,
);
// class / :class con `text-<estado>`
const CLASE = new RegExp(`:?class\\s*=\\s*["\`][^"\`]*\\btext-${UNO}\\b`);
// 🪤 la tercera codificación: el nombre de clase COMPUESTO en una plantilla
// literal, que es como se pinta el estado del árbol de flota.
const CLASE_COMPUESTA = /:class\s*=\s*["`][\s\S]*?--\$\{/;

// Superficie propia de un control. Incluye el campo (q-field/q-select/q-input):
// 🔴 mi sonda de la 17.ª no lo tenía en la lista y por eso publicó un cero.
const CONTROLES = new Set([
  "q-btn",
  "button",
  "a",
  "tr",
  "q-item",
  "q-tab",
  "q-toggle",
  "q-checkbox",
  "q-radio",
  "q-field",
  "q-select",
  "q-input",
  "observer-dropdown",
  "q-tree",
]);

// 🔴 19.ª corrida, y esto es la causa de que esta guarda pasara 24/24 mientras
// el DOM medía la violación: `[^>]*` corta la lista de atributos en el PRIMER
// `>`, y en `v-if="item.checks.failing > 0"` ese `>` está DENTRO del valor. El
// `class="obs-ctx__fail"` que venía después nunca entraba en los atributos, así
// que el censo no podía ver el elemento. No era una codificación nueva: era que
// mi parser no respetaba las comillas.
const ETIQUETA = /<(\/?)([a-zA-Z][\w.-]*)((?:"[^"]*"|'[^']*'|[^>"'])*?)(\/?)>/g;
const VACIOS = new Set(["br", "hr", "img", "input", "q-separator", "q-space"]);

// 🪤 La CUARTA codificación: el color de estado puede venir de una clase del
// PROYECTO cuya regla CSS pone el token (`.obs-ctx__fail { color:
// var(--q-negative) }`). Ninguna de las tres pasadas anteriores la veía, porque
// todas miraban la escritura del atributo. Así que las clases no se enumeran a
// mano: se LEEN de los bloques <style> del árbol.
const PROPIEDAD =
  /^\s*(color|background|background-color|border|border-color|border-top-color|border-left-color|border-right-color|border-bottom-color)\s*:\s*(.+)$/;
const TOKEN_ESTADO = new RegExp(`var\\(\\s*--q-${UNO}\\s*\\)`);

// Devuelve {clase: {token, propiedad, anidada}} para un archivo.
export function clasesDeEstado(fuente) {
  const salida = {};
  for (const [, bloque] of fuente.matchAll(
    /<style[^>]*>([\s\S]*?)<\/style>/g,
  )) {
    const lineas = bloque.split("\n");
    for (let i = 0; i < lineas.length; i += 1) {
      const m = PROPIEDAD.exec(lineas[i]);
      if (!m || !TOKEN_ESTADO.test(m[2])) continue;
      // el selector es la línea anterior que no es una propiedad
      for (let j = i - 1; j >= 0; j -= 1) {
        const cand = lineas[j];
        if (!cand.trim() || PROPIEDAD.test(cand)) continue;
        const sel = cand.trim().replace(/\{$/, "").trim();
        // ¿está anidado bajo otro selector con más indentación arriba?
        const sangria = cand.length - cand.trimStart().length;
        let anidada = false;
        for (let k = j - 1; k >= 0; k -= 1) {
          const arriba = lineas[k];
          if (!arriba.trim() || PROPIEDAD.test(arriba)) continue;
          const sa = arriba.length - arriba.trimStart().length;
          if (sa < sangria) anidada = true;
          break;
        }
        for (const [, clase] of sel.matchAll(/\.([A-Za-z0-9_-]+)/g)) {
          salida[clase] = {
            token: "--q-" + TOKEN_ESTADO.exec(m[2])[1],
            propiedad: m[1],
            selector: sel,
            anidada,
          };
        }
        break;
      }
    }
  }
  return salida;
}

function clasesDelElemento(atributos) {
  const fuera = [];
  for (const [, valor] of atributos.matchAll(
    /[\w:-]*class\s*=\s*["`]([\s\S]*?)["`]/g,
  ))
    fuera.push(...(valor.match(/[A-Za-z0-9_-]+/g) || []));
  return fuera;
}

function pintaEstado(atributos, delProyecto = {}) {
  if (COLOR.test(atributos)) return "atributo color";
  if (CLASE.test(atributos)) return "clase text-<estado>";
  if (CLASE_COMPUESTA.test(atributos)) return "clase compuesta";
  for (const c of clasesDelElemento(atributos)) {
    const d = delProyecto[c];
    // una regla ANIDADA pinta a un descendiente, no a este elemento
    if (d && !d.anidada)
      return `clase del proyecto .${c} (${d.propiedad}: ${d.token})`;
  }
  return null;
}

// Censo: todo elemento con color de estado que cuelgue de un control, con la
// CADENA de controles y el atributo CRUDO que se vio (enmienda s4: el booleano
// solo no basta).
export function estadoSobreUnControl(fuente, ruta = "") {
  const delProyecto = clasesDeEstado(fuente);
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
    const cadena = pila.map((p) => p.nombre).filter((n) => CONTROLES.has(n));
    const via = pintaEstado(atributos, delProyecto);
    if (cadena.length && !CONTROLES.has(nombre) && via) {
      hallados.push({
        ruta,
        etiqueta: nombre,
        linea: tpl.slice(0, m.index).split("\n").length + desplazamiento,
        cadena_de_control: cadena,
        via,
        atributo_crudo: atributos.replace(/\s+/g, " ").trim(),
      });
    }
    if (!auto && !VACIOS.has(nombre)) pila.push({ nombre, atributos });
  }
  return hallados;
}

// LISTA CERRADA. Cada entrada dice POR QUÉ no viola. Un sitio que no esté acá
// reprueba: la guarda no decide, obliga a justificar.
const DECLARADOS = {
  "src/components/scripts/ScriptManager.vue:203":
    "excepcion (b) del 2026-10-16, aprobada por el usuario: la estrella de " +
    "favorito de Scripts va en ambar como pide la maqueta. Su q-btn es `round` " +
    "y SIN rotulo, asi que el icono es la superficie del control.",
  "src/components/scripts/ScriptManager.vue:421":
    "la misma estrella de la excepcion (b), en el arbol del gestor.",
  "src/views/DashboardView.vue:81":
    "MARCADOR: reporta un dato (failing_checks.error / failing_checks.warning / " +
    "maintenance_mode del nodo), nombra el estado en su propio aria-label y " +
    "tooltip (fleet.stateError / stateWarning / stateMaintenance) y viene " +
    "pegado al conteo que informa (.obs-fleet__count). Es el caso que la " +
    "enmienda del 2026-10-14 exime y que la evidencia pedida ORDENA censar; la " +
    "prueba «trae fondo o borde propios» de la 17.a corrida lo condenaba por " +
    "error, y por eso se corrigio.",
  // 🪤 Este sitio lo destapo la TERCERA codificacion del censo (el nombre de
  // clase compuesto): dos censos anteriores no lo veian.
  "src/components/agents/workspace/ContextColumn.vue:84":
    "MARCADOR con superficie propia: el punto de salud se dibuja con " +
    "`background: var(--q-positive|--q-negative|--q-warning)` sobre 8x8 con " +
    "border-radius, reporta dot(item) y trae role=img, aria-label y title con " +
    "el estado traducido (el arreglo de color-senal-unica.spec.js).",
  // 🪤 Movido de :42 a :46 el 2026-11-13 por un comentario de V2-G01 cuatro
  // lineas mas arriba; el sitio es el MISMO q-badge y nada del producto
  // cambio. Este censo congela `archivo:linea`, asi que cualquier edicion
  // por encima de un sitio listado lo rompe. Es el precio de que la lista
  // sea auditable -el numero lleva al sitio exacto-, no un defecto, pero
  // conviene saberlo antes de culpar al producto.
  "src/components/agents/ConfirmWipeOrderDialog.vue:46":
    "q-badge: trae fondo propio y reporta order.dry_run.",
  "src/components/agents/LostCaseTimelineDialog.vue:207":
    "q-chip: fondo propio, reporta screen.note del caso.",
  "src/components/agents/LostCaseTimelineDialog.vue:224":
    "q-chip: fondo propio, reporta webcam.note del caso.",
  "src/components/automation/AutomationManager.vue:53":
    "q-badge Activa/Inactiva: fondo propio y liga declarada al campo `active` " +
    "de GET /automation/policies/.",
  "src/components/ui/SecretInput.vue:19":
    "familia de la excepcion (c): es el mensaje del slot #hint del campo, que " +
    "informa el estado «el secreto se borro». El TEXTO ya lo dice; el color " +
    "acompana, no es el unico portador.",
  "src/ee/reporting/components/VariablesSelector.vue:15":
    "el q-item NO es clickable (el control es el span.cursor-pointer de otra " +
    "seccion), asi que el icono no cae sobre la superficie de ningun control; " +
    "y trae su q-tooltip con el estado.",
  "src/ee/reporting/components/VariablesSelector.vue:47":
    "igual que el de la linea 15: q-item no clickable.",
};

describe("un color de estado no pinta la superficie propia de un control (V2-G05)", () => {
  it("el censo da exactamente la lista cerrada declarada", async () => {
    const fuentes = await leerVue();
    const hallados = fuentes.flatMap(({ ruta, fuente }) =>
      estadoSobreUnControl(fuente, ruta),
    );
    const claves = hallados.map((h) => `${h.ruta}:${h.linea}`).sort();
    expect(claves).toEqual(Object.keys(DECLARADOS).sort());
    // y cada entrada declarada trae una razon escrita, no un booleano
    for (const [sitio, razon] of Object.entries(DECLARADOS)) {
      expect(razon.length, sitio).toBeGreaterThan(40);
    }
  });

  it("el árbol de flota sigue siendo un marcador comprobable, no una declaración", async () => {
    const fuentes = await leerVue();
    const tablero = fuentes.find((f) => f.ruta.endsWith("DashboardView.vue"));
    expect(tablero).toBeTruthy();
    // reporta un dato
    expect(tablero.fuente).toMatch(/failing_checks\?\.error/);
    expect(tablero.fuente).toMatch(/failing_checks\?\.warning/);
    expect(tablero.fuente).toMatch(/maintenance_mode/);
    // nombra el estado en su propio rótulo accesible, y lo repite en tooltip
    expect(tablero.fuente).toMatch(/:aria-label="stateLabel\(st\)"/);
    expect(tablero.fuente).toMatch(
      /<q-tooltip>\{\{ stateLabel\(st\) \}\}<\/q-tooltip>/,
    );
    // y viene pegado al dato que informa
    expect(tablero.fuente).toMatch(/obs-fleet__count/);
  });

  it("«Dependencias» lleva el estado en el TEXTO, sin color de estado en juego", async () => {
    const fuentes = await leerVue();
    const forma = fuentes.find((f) =>
      f.ruta.endsWith("ee/reporting/components/ReportScheduleForm.vue"),
    );
    expect(forma).toBeTruthy();
    expect(estadoSobreUnControl(forma.fuente, forma.ruta)).toEqual([]);
    // el estado se lee en palabras, y la clave existe en los dos idiomas
    expect(forma.fuente).toMatch(
      /areDependenciesMet\s*\n?\s*\?\s*\$t\("reporting\.scheduleForm\.dependenciesLabel"\)/,
    );
    expect(forma.fuente).toMatch(
      /:\s*\$t\("reporting\.scheduleForm\.dependenciesMissing"\)/,
    );
    // y ya no queda ningún q-icon con color en ese archivo
    expect(forma.fuente).not.toMatch(/color="warning"/);
  });

  it("el historial sigue con el glifo sin color de estado", async () => {
    const fuentes = await leerVue();
    const hist = fuentes.find((f) => f.ruta.endsWith("ReportHistoryTable.vue"));
    expect(hist.fuente).toMatch(
      /<q-icon name="warning" size="xs" class="q-mr-xs" \/>/,
    );
    expect(hist.fuente).not.toMatch(/color="negative"/);
  });

  it("las claves del rótulo existen en los dos diccionarios", async () => {
    const es = (await import("@/i18n/es.json")).default;
    const en = (await import("@/i18n/en.json")).default;
    for (const [nombre, d] of [
      ["es", es],
      ["en", en],
    ]) {
      const f = d.reporting.scheduleForm;
      expect(f.dependenciesLabel, nombre).toBeTruthy();
      expect(f.dependenciesMissing, nombre).toBeTruthy();
      expect(f.dependenciesMissing, nombre).not.toEqual(f.dependenciesLabel);
    }
  });

  it("el clasificador trae sus controles positivos y negativos", () => {
    const enBoton =
      '<template><q-btn color="primary"><q-icon name="warning" color="warning" /> Dependencias</q-btn></template>';
    const enCampo =
      '<template><q-select><template #after><q-icon name="warning" color="warning" /><q-btn>Dependencias</q-btn></template></q-select></template>';
    const dinamico =
      "<template><q-btn><q-icon :color=\"row.favorite ? 'warning' : undefined\" /></q-btn></template>";
    const porClase =
      '<template><tr><span class="text-negative">x</span></tr></template>';
    const claseCompuesta =
      '<template><q-tree><q-icon :class="`obs-fleet__state obs-fleet__state--${st}`" /></q-tree></template>';
    const fuera =
      '<template><q-icon name="warning" color="warning" /><q-btn color="primary">Dependencias</q-btn></template>';
    const sinPlantilla =
      "<script setup>const c = 'color=\"warning\"';</script>";

    expect(estadoSobreUnControl(enBoton)).toHaveLength(1); // 17.ª corrida
    expect(estadoSobreUnControl(enCampo)).toHaveLength(1); // 🔴 18.ª corrida
    expect(estadoSobreUnControl(dinamico)).toHaveLength(1); // 🪤 el binding
    expect(estadoSobreUnControl(porClase)).toHaveLength(1); // 🪤 la clase
    expect(estadoSobreUnControl(claseCompuesta)).toHaveLength(1); // 🪤 compuesta
    expect(estadoSobreUnControl(fuera)).toEqual([]); // negativo: fuera
    expect(estadoSobreUnControl(sinPlantilla)).toEqual([]); // negativo: sin template
  });

  // Cuando el color de estado lo lleva un DESCENDIENTE (regla anidada), el
  // elemento pintado tiene que ser el NÚMERO: es la exención textual del
  // 2026-10-14 («el número rojo de un KPI que filtra») y el patrón que el
  // proyecto ya usaba en `.obs-fleet__kpi-num--neg` junto a un
  // `.obs-fleet__kpi-label` neutro.
  const ANIDADAS_DECLARADAS = {
    "src/components/agents/workspace/ContextColumn.vue:obs-ctx__fail":
      "el rotulo del q-item clickable quedo en --obs-muted y el color de estado " +
      "lo lleva el span.mono con item.checks.failing, que es el numero exento.",
    "src/components/agents/workspace/ContextColumn.vue:obs-ctx__chip--on-neg":
      "igual: el rotulo del q-chip clickable encendido va neutro y el rojo queda " +
      "en el span.mono con failingCount.",
  };

  it("las reglas anidadas que pintan estado están declaradas y apuntan al número", async () => {
    const fuentes = await leerVue();
    const anidadas = [];
    for (const { ruta, fuente } of fuentes) {
      const clases = clasesDeEstado(fuente);
      for (const [clase, d] of Object.entries(clases)) {
        if (d.anidada) anidadas.push({ ruta, clase, ...d });
      }
    }
    // toda regla anidada pinta sobre `.mono`, que es la clase del número
    for (const a of anidadas) {
      expect(a.selector, `${a.ruta} ${a.clase}`).toMatch(/^\.mono$/);
    }
    // Y el padre de cada una está declarado con su razón.
    // 🪤 Acá puse primero un `(?:\s+[^\n]*\n)*?` y colgó vitest por
    // backtracking catastrófico, porque `\s` cruza saltos de línea: 16 procesos
    // de node girando hasta que los maté. Se recorre por líneas, que además se
    // lee sin descifrar nada.
    const padres = new Set();
    for (const { ruta, fuente } of fuentes) {
      for (const [, bloque] of fuente.matchAll(
        /<style[^>]*>([\s\S]*?)<\/style>/g,
      )) {
        const lineas = bloque.split("\n");
        let padre = null;
        for (let i = 0; i < lineas.length; i += 1) {
          const ln = lineas[i];
          if (!ln.trim()) continue;
          if (
            ln.length === ln.trimStart().length &&
            /^\.[A-Za-z0-9_-]+$/.test(ln.trim())
          )
            padre = ln.trim().slice(1);
          if (
            padre &&
            /^\s+\.mono$/.test(ln) &&
            TOKEN_ESTADO.test(lineas[i + 1] || "")
          )
            padres.add(`${ruta}:${padre}`);
        }
      }
    }
    expect([...padres].sort()).toEqual(Object.keys(ANIDADAS_DECLARADAS).sort());
    for (const [sitio, razon] of Object.entries(ANIDADAS_DECLARADAS))
      expect(razon.length, sitio).toBeGreaterThan(40);
  });

  it("🪤 el parser respeta las comillas: un `>` dentro de un atributo no corta la etiqueta", () => {
    // Este es el control del fallo de la 19.ª: con `[^>]*` el `class` quedaba
    // fuera de los atributos y el elemento era invisible para el censo.
    const conMayor =
      '<template><q-item clickable><q-item-label v-if="a.b.failing > 0" class="text-negative">x</q-item-label></q-item></template>';
    expect(estadoSobreUnControl(conMayor)).toHaveLength(1);
    // y el caso que motivó todo, con la clase del proyecto resuelta del <style>
    const conClaseDelProyecto =
      '<template><q-item clickable><div v-if="n > 0" class="mi-fallo">x</div></q-item></template>' +
      "<style>\n.mi-fallo\n  color: var(--q-negative)\n</style>";
    expect(estadoSobreUnControl(conClaseDelProyecto)).toHaveLength(1);
    // negativo: la misma clase pero con la regla ANIDADA pinta al descendiente
    const anidada =
      '<template><q-item clickable><div class="mi-fallo">x</div></q-item></template>' +
      "<style>\n.mi-fallo\n  color: var(--obs-muted)\n  .mono\n    color: var(--q-negative)\n</style>";
    expect(estadoSobreUnControl(anidada)).toEqual([]);
  });

  it("el censo mira de verdad", async () => {
    const fuentes = await leerVue();
    expect(fuentes.length).toBeGreaterThan(100);
    // si se planta el defecto de la 18.ª en la fuente real, el censo lo caza
    const real = fuentes.find((f) =>
      f.ruta.endsWith("ee/reporting/components/ReportScheduleForm.vue"),
    );
    const plantado = real.fuente.replace(
      "              <q-btn",
      '              <q-icon name="warning" color="warning" />\n              <q-btn',
    );
    expect(plantado).not.toEqual(real.fuente);
    expect(estadoSobreUnControl(plantado, real.ruta)).toHaveLength(1);
  });
});
