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
import { leerVue, leerFuentes } from "../support/vue-sources.js";

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

// Se miran los literales del CÓDIGO. Los de i18n tienen su propio censo abajo.
//
// 🔴 Y ESA SEPARACIÓN fue el hueco por el que entró la 16.ª corrida. Acá vivía
// este comentario: «no se miran los de i18n: una elipsis dentro de una frase
// traducida es prosa («Cargando…»)». Seis críticos midieron entonces
// `dashboard.activityMonitoring` = «Monitoreo de actividad…», que es una clave
// de i18n y NO es prosa: es el rótulo permanente de un ítem de menú, con
// scrollWidth == clientWidth y cero canales. 🔑 Una exención escrita por la
// razón correcta («una frase en gerundio que nombra una operación en curso no
// promete resto de texto») tapa igual todo lo que no es esa frase, si se
// redacta por el ORIGEN del literal y no por su forma. El censo de i18n de
// abajo exime por la RANURA donde se rinde, que es comprobable.
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
    // 🪤 La primera version metia la palabra en la ranura del numero y en
    // pantalla salia «sin dato chequeos · sin dato tareas». Cuando falta algun
    // conteo la frase cambia ENTERA, y son dos frases distintas.
    expect(fuente).toMatch(/automationManager\.policyMetaLoading/);
    expect(fuente).toMatch(/automationManager\.policyMetaError/);
    // 🪤 El `.catch(() => {})` vacío de `loadPolicyCounts` es lo que hacía
    // permanente el hueco: ahora su catch TIENE que escribir el valor. Se
    // afirma sobre ese catch, no sobre cualquier catch vacío del archivo: el
    // de `loadSectionCounts` alimenta una insignia que con `null` simplemente
    // no se dibuja, que es otra cosa y no se toca acá.
    expect(fuente).toMatch(
      /\.catch\(\(\) => \{\s*this\.policyCounts\[pol\.id\]\[k\] = "error";\s*\}\)/,
    );
  });

  it("las dos frases existen en los dos idiomas", async () => {
    for (const idioma of ["es", "en"]) {
      const d = JSON.parse(
        await readFile(resolve(APP, `src/i18n/${idioma}.json`), "utf8"),
      );
      expect(d.automationManager.policyMetaLoading).toBeTruthy();
      expect(d.automationManager.policyMetaError).toBeTruthy();
      // Las dos frases llevan la ranura de equipos, que es el unico conteo
      // que no sale de una peticion aparte y por eso siempre esta.
      expect(d.automationManager.policyMetaLoading).toContain("{agents}");
      expect(d.automationManager.policyMetaError).toContain("{agents}");
    }
  });
});

// ---------------------------------------------------------------------------
// Censo de i18n. Las claves que terminan en marca de corte y por qué cada una
// es legal: no por lo que quiso decir, sino por la RANURA en que se rinde.
//
// La propiedad que hace legal a una marca de corte en una frase de progreso es
// ESTRUCTURAL y se puede comprobar: el elemento que la lleva existe sólo
// mientras la operación está en vuelo (`$q.loading.show`, el `loading-label` de
// una q-table, el `label` de un q-inner-loading) o lleva el valor íntegro en su
// propio `title` (el chrome remoto, que además lo reemplaza por el hostname en
// cuanto llega). Un rótulo PERMANENTE no tiene ninguna de las dos, y eso es lo
// que se castiga.
const RANURAS = {
  // `$q.loading.show({ message })`: pantalla de carga global, se cierra con
  // `$q.loading.hide()`.
  "loading-show": {
    linea: /^\s*message:\s*(?:this\.)?\$?t\(/,
    contexto: /loading\.show\(/,
  },
  // `:loading-label` de q-table: sólo se dibuja con `:loading` en true.
  "tabla-loading-label": { linea: /:loading-label="\$t\(/, contexto: null },
  // `:label` de q-inner-loading: el componente entero vive bajo `:showing`.
  "inner-loading-label": {
    linea: /:label=['"]\$t\(/,
    contexto: /<q-inner-loading/,
  },
  // `:title` de RemoteWindowChrome, que lo rinde con `:title` propio (el mismo
  // texto, canal estático) y lo reemplaza por el hostname cuando llega.
  "chrome-remoto-title": {
    linea: /:title="\$t\(/,
    contexto: /<RemoteWindowChrome/,
  },
};

const MARCA_LEGITIMA_I18N = {
  "installAgent.generatingExe": "loading-show",
  "editCoreSettings.sendingTestEmail": "loading-show",
  "editCoreSettings.sendingTestSms": "loading-show",
  "takeControl.connecting": "chrome-remoto-title",
  "webVNC.connecting": "chrome-remoto-title",
  "reporting.common.pleaseWait": "inner-loading-label",
  "reporting.templateForm.generatingReport": "inner-loading-label",
  "lostEquipment.loading": "tabla-loading-label",
  "diskEncryption.loading": "tabla-loading-label",
  "erase.certificates.loading": "tabla-loading-label",
  "storageMedia.loading": "tabla-loading-label",
};

const TERMINA_EN_MARCA = /(?:…|\.\.\.)\s*$/;

function clavesConMarca(diccionario) {
  const salida = [];
  const andar = (nodo, prefijo) => {
    if (typeof nodo === "string") {
      if (TERMINA_EN_MARCA.test(nodo)) salida.push(prefijo);
    } else if (nodo && typeof nodo === "object") {
      for (const [k, v] of Object.entries(nodo))
        andar(v, prefijo ? `${prefijo}.${k}` : k);
    }
  };
  andar(diccionario, "");
  return salida.sort();
}

// Clasifica el uso de una clave por la ranura en que se rinde. Mira hasta seis
// líneas hacia atrás porque prettier reparte las etiquetas en varias líneas.
function ranuraDeUso(lineas, i) {
  const atras = lineas.slice(Math.max(0, i - 6), i + 1).join("\n");
  for (const [nombre, { linea, contexto }] of Object.entries(RANURAS)) {
    if (!linea.test(lineas[i])) continue;
    if (contexto && !contexto.test(atras)) continue;
    return nombre;
  }
  return null;
}

describe("censo: las claves de i18n que terminan en marca de corte", () => {
  let fuentes;
  const dicc = {};
  beforeAll(async () => {
    fuentes = await leerFuentes([".vue", ".ts", ".js"]);
    for (const idioma of ["es", "en"])
      dicc[idioma] = JSON.parse(
        await readFile(resolve(APP, `src/i18n/${idioma}.json`), "utf8"),
      );
  });

  it("son exactamente las declaradas, y las mismas en los dos idiomas", () => {
    const esperadas = Object.keys(MARCA_LEGITIMA_I18N).sort();
    expect(clavesConMarca(dicc.es)).toEqual(esperadas);
    expect(clavesConMarca(dicc.en)).toEqual(esperadas);
  });

  it("cada uso de cada clave cae en la ranura que declara", () => {
    const fallas = [];
    for (const [clave, ranura] of Object.entries(MARCA_LEGITIMA_I18N)) {
      let usos = 0;
      for (const { ruta, fuente } of fuentes) {
        if (ruta.startsWith("src/i18n/") || !fuente.includes(clave)) continue;
        const lineas = fuente.split("\n");
        for (let i = 0; i < lineas.length; i += 1) {
          if (!lineas[i].includes(clave)) continue;
          usos += 1;
          const vista = ranuraDeUso(lineas, i);
          if (vista !== ranura)
            fallas.push(
              `${clave} en ${ruta}:${i + 1} → ${vista} (≠ ${ranura})`,
            );
        }
      }
      // 🪤 Una clave sin ningún uso es la otra cara del mismo defecto: en esta
      // corrida había DOS (`reporting.common.loading` y `erase.custody.adding`)
      // que nadie llamaba y llevaban el glifo igual. Se borraron; si vuelve a
      // aparecer una, este conteo la delata en vez de dejarla pasar por «no se
      // rinde en ninguna ranura mala».
      if (usos === 0) fallas.push(`${clave} no la usa nadie: es cadena muerta`);
    }
    expect(fallas).toEqual([]);
  });

  // Control negativo del clasificador: si `ranuraDeUso` dijera «ranura buena»
  // para cualquier cosa, la prueba de arriba pasaría siempre.
  it("el clasificador NO acepta un rótulo permanente", () => {
    const permanente = [
      "                <q-item-section>{{",
      '                  $t("dashboard.activityMonitoring")',
      "                }}</q-item-section>",
    ];
    expect(ranuraDeUso(permanente, 1)).toBe(null);
    // Y el positivo: la misma función reconoce una ranura de verdad.
    const transitorio = [
      "            this.$q.loading.show({",
      '              message: this.$t("installAgent.generatingExe"),',
    ];
    expect(ranuraDeUso(transitorio, 1)).toBe("loading-show");
    // Y exige el contexto, no sólo la forma de la línea: la misma línea de
    // `:label` fuera de un q-inner-loading no clasifica.
    expect(ranuraDeUso(["  <q-btn", "    :label=\"$t('x.y')\""], 1)).toBe(null);
  });

  it("los dos rótulos permanentes de la 16.ª corrida quedaron sin glifo", () => {
    expect(dicc.es.dashboard.activityMonitoring).toBe("Monitoreo de actividad");
    expect(dicc.en.dashboard.activityMonitoring).toBe("Activity monitoring");
    for (const idioma of ["es", "en"])
      expect(TERMINA_EN_MARCA.test(dicc[idioma].notFound.message)).toBe(false);
  });

  it("las dos cadenas muertas no volvieron", () => {
    for (const idioma of ["es", "en"]) {
      expect(dicc[idioma].reporting.common.loading).toBeUndefined();
      expect(dicc[idioma].erase.custody.adding).toBeUndefined();
    }
  });

  it("el censo mira de verdad: hay fuentes y hay claves", () => {
    expect(fuentes.length).toBeGreaterThan(200);
    expect(Object.keys(MARCA_LEGITIMA_I18N).length).toBe(11);
  });
});
