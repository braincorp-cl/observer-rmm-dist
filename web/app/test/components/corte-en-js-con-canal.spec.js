/* eslint-env node */

// 050 / V2-G08: ningun texto recortado puede quedar sin un canal que lo lea
// entero. Este spec vigila la CLASE, no una pagina.
//
// 🔴 Por que existe. El encabezado de `script-manager-nombre-largo.spec.js`
// YA tenia el diagnostico exacto escrito: un recorte hecho en JavaScript llega
// al DOM sin cola, asi que el `title` que alguien le ponga repite la elipsis y
// `src/boot/autotitle.js` tampoco lo salva, porque copia `el.textContent`. Con
// ese diagnostico en la mano blinde UNA pagina —/scripts— y deje quince sitios
// mas recortando en JS. La 13.a corrida del gauntlet encontro el que importaba:
// el hash de la Cadena de custodia, cortado a 16 de 64 hex, con el `title` que
// el boot le habia puesto repitiendo el recorte.
//
// 🔑 Un test que protege la pagina donde encontraste la clase no dice nada de
// los otros quince sitios de la misma clase. Lo que hace falta es el CENSO.
//
// Que vigila:
//   1. el censo completo de recortes por JS en `src/`, congelado: un sitio
//      nuevo obliga a declarar su canal acá;
//   2. que el valor COMPLETO de cada sitio aparezca en la plantilla fuera del
//      recorte (en `title`, en un `q-tooltip` o en el dialogo que lo abre);
//   3. que `truncateText` marque solo cuando de verdad quito cola — con `>=`
//      pegaba «...» a un texto entero, un corte falso;
//   4. que exista UNA sola definicion de `truncateText`;
//   5. que el boot no PISE un `title` propio mas largo que lo visible.
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { readFileSync, readdirSync, statSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, resolve, join, relative } from "path";
import { truncateText } from "@/utils/format";

const AQUI = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(AQUI, "../../src");

function archivos(dir) {
  const out = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) out.push(...archivos(p));
    else if (/\.(vue|js|ts)$/.test(e)) out.push(p);
  }
  return out;
}

// Las dos formas de recortar en JS que hay en el arbol. `corto()` es local de
// AssetCustodyTimeline y corta un hash; `truncateText` es el util compartido.
const RECORTES = /\b(?:truncateText|corto)\(\s*([^),]+)/g;
function censo() {
  const sitios = [];
  for (const p of archivos(SRC)) {
    const rel = relative(SRC, p).split("\\").join("/");
    const txt = readFileSync(p, "utf8");
    for (const m of txt.matchAll(RECORTES)) {
      const arg = m[1].trim();
      // La firma de la propia funcion y el cuerpo del util no son usos.
      if (/[:=]/.test(arg) || arg === "txt" || arg === "hash") continue;
      sitios.push({ archivo: rel, valor: arg, texto: txt });
    }
  }
  return sitios;
}

// El censo congelado: archivo → valores recortados. Un sitio nuevo rompe el
// test y hay que declararlo acá junto con su canal.
const ESPERADO = {
  "components/scripts/ScriptManager.vue": [
    "props.row.name",
    "props.row.args.toString(",
    "props.row.description",
  ],
  "components/modals/coresettings/CustomFieldsTable.vue": [
    "props.row.default_value_string",
  ],
  "components/modals/coresettings/URLActionsTable.vue": [
    "props.row.name",
    "props.row.desc",
    "props.row.pattern",
  ],
  "components/agents/AutomatedTasksTab.vue": [
    "props.row.schedule",
    "props.row.check_name",
  ],
  "components/agents/WinUpdateTab.vue": [
    "props.row.title",
    "props.row.description",
  ],
  // ⚠️ Excepcion declarada: el recorte vive en la definicion de la columna
  // (`format: (val) => ...`), asi que el valor no se nombra en el sitio. Su
  // canal es el slot `body-cell-command`, cuyo `q-tooltip` rinde
  // `props.col.field(props.row)`, o sea el valor sin recortar.
  "components/agents/HistoryTab.vue": ["val"],
  "components/agents/ChecksTab.vue": ["props.row.readable_desc"],
  "components/agents/remotebg/EventLogManager.vue": ["props.row.message"],
  "components/agents/remotebg/ServicesManager.vue": ["props.row.display_name"],
  "components/agents/AssetCustodyTimeline.vue": ["ev.record_hash"],
};

// Los que no pueden probarse nombrando el valor, con su canal verificado a mano.
const SIN_NOMBRE_PROPIO = {
  "components/agents/HistoryTab.vue": "props.col.field(props.row)",
};

describe("V2-G08: censo de recortes por JavaScript", () => {
  it("no hay mas sitios de recorte que los declarados", () => {
    const visto = {};
    for (const s of censo()) {
      (visto[s.archivo] = visto[s.archivo] || []).push(s.valor);
    }
    expect(visto).toEqual(ESPERADO);
  });

  it("cada sitio nombra su valor completo fuera del recorte", () => {
    const sinCanal = [];
    for (const s of censo()) {
      const canal = SIN_NOMBRE_PROPIO[s.archivo] || s.valor;
      // Las apariciones del valor que NO son el recorte mismo.
      const fuera = s.texto
        .split("\n")
        .filter((l) => l.includes(canal) && !/truncateText\(|corto\(/.test(l));
      if (!fuera.length) sinCanal.push(`${s.archivo} :: ${s.valor}`);
    }
    expect(sinCanal).toEqual([]);
  });
});

describe("V2-G08: la marca de recorte no puede ser falsa", () => {
  it("un texto del largo exacto del limite sale intacto y sin «...»", () => {
    // 🪤 Con `>=`, `substring(0, 5)` de un texto de 5 devolvia el texto ENTERO
    // y se le pegaba «...»: una elipsis sobre algo que no se corto.
    expect(truncateText("12345", 5)).toBe("12345");
    expect(truncateText("123456", 5)).toBe("12345...");
    expect(truncateText("1234", 5)).toBe("1234");
  });

  it("existe una sola definicion de truncateText en el arbol", () => {
    const defs = archivos(SRC).filter((p) =>
      /(?:export )?function truncateText|^\s*truncateText\(txt/m.test(
        readFileSync(p, "utf8"),
      ),
    );
    expect(defs.map((p) => relative(SRC, p))).toEqual(["utils/format.ts"]);
  });
});

describe("V2-G08: el boot no apaga un title propio mejor", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.useFakeTimers();
    window.requestAnimationFrame = (fn) => setTimeout(() => fn(0), 0);
    window.cancelAnimationFrame = (id) => clearTimeout(id);
  });

  afterEach(async () => {
    // 🪤 El observador del boot es de documento y sobrevive al test: si no se
    // desconecta, su callback dispara cuando jsdom ya se fue.
    const { detener } = await import("@/boot/autotitle");
    detener();
    vi.useRealTimers();
  });

  it("un title mas largo que el texto visible sobrevive al barrido", async () => {
    const boot = (await import("@/boot/autotitle")).default;
    boot();

    const d = document.createElement("div");
    d.className = "ellipsis";
    d.textContent = "Hash: 9f2c41a7be0d5364…";
    document.body.appendChild(d);
    // 🪤 Este primer barrido es lo que hace que el test PRUEBE la guarda. Si el
    // elemento llegara con su title ya puesto, `titular()` saldria por la rama
    // de «title propio sin marca» y la guarda no se tocaria: el control
    // negativo —quitarla— pasaba igual. Hay que dejar que el boot lo titule
    // primero (marca puesta) y recien entonces poner el title del dato.
    await vi.advanceTimersByTimeAsync(60);
    expect(d.dataset.obsAutotitle).toBe("1");
    expect(d.getAttribute("title")).toBe("Hash: 9f2c41a7be0d5364…");

    // Lo que hace Vue cuando el valor completo viene del dato y no del DOM.
    const completo = "Hash: 9f2c41a7be0d5364" + "0".repeat(48);
    d.setAttribute("title", completo);
    d.textContent = "Hash: 9f2c41a7be0d5364…";
    await vi.advanceTimersByTimeAsync(60);

    expect(d.getAttribute("title")).toBe(completo);
  });

  it("sigue titulando el .ellipsis que no trae title propio", async () => {
    const boot = (await import("@/boot/autotitle")).default;
    boot();

    const d = document.createElement("div");
    d.className = "ellipsis";
    d.textContent = "   un rotulo   largo  ";
    document.body.appendChild(d);
    vi.advanceTimersByTime(60);

    expect(d.getAttribute("title")).toBe("un rotulo largo");
  });

  it("al vaciarse el texto, el title que el boot puso se retira", async () => {
    const boot = (await import("@/boot/autotitle")).default;
    boot();

    const d = document.createElement("div");
    d.className = "ellipsis";
    d.textContent = "algo";
    document.body.appendChild(d);
    vi.advanceTimersByTime(60);
    expect(d.getAttribute("title")).toBe("algo");

    // 🪤 Si la guarda del title largo corriera ANTES del vaciado, con el texto
    // vacio veria cualquier title como «mas largo» y lo dejaria rancio.
    //
    // 🪤 Y acá hace falta la version ASINCRONA del reloj: el barrido que cuenta
    // es el que programa el MutationObserver, y su callback es una microtarea.
    // `advanceTimersByTime` es sincrono, no la deja correr, y lo unico que se
    // habria medido es el barrido inicial que `boot()` programa por su cuenta.
    d.textContent = "";
    await vi.advanceTimersByTimeAsync(60);
    expect(d.hasAttribute("title")).toBe(false);
  });
});
