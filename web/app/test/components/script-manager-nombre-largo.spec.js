/* eslint-env node */

// Regla de aceptación G08: ningún texto recortado con elipsis sin un canal que
// permita leerlo entero (`title` o tooltip).
//
// La página /scripts (ScriptManager.vue con `embedded`) recorta el nombre, la
// descripción y los argumentos por CSS —`.ellipsis` sobre un ancho máximo— y
// pone el valor COMPLETO en `title`. El riesgo es volver al patrón de la v1,
// que recortaba por JavaScript con `truncateText(valor, N)`: ahí el texto que
// llega al DOM ya viene cortado, así que el `title` —si alguien lo agrega—
// repite la elipsis, y `src/boot/autotitle.js` tampoco lo salva, porque toma el
// texto del propio elemento (`el.textContent`) y ese texto ya perdió la cola.
//
// Por eso la prueba no mira clases ni anchos (jsdom no calcula layout: no puede
// distinguir recortado de no recortado). Mira lo único que decide si el dato se
// puede leer: que el valor entero esté en el DOM, sea como texto o como `title`,
// y que ningún `title` termine en «...».
//
// Qué NO cubre: que el recorte visual ocurra de verdad. Eso es layout y se
// verificó en navegador (scrollWidth 691 > clientWidth 260 en la celda del
// nombre, con el título completo).

import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createStore } from "vuex";
import { createI18n } from "vue-i18n";
import { createRouter, createMemoryHistory } from "vue-router";
import messages from "@/i18n";

// El gestor pide los scripts al backend apenas se monta. Es lo único que cruza
// la frontera del proceso, así que es lo único que se finge.
const fetchScripts = vi.fn();
vi.mock("@/api/scripts", () => ({
  fetchScripts: (...args) => fetchScripts(...args),
  editScript: vi.fn(() => Promise.resolve({})),
  downloadScript: vi.fn(() => Promise.resolve({})),
  removeScript: vi.fn(() => Promise.resolve({})),
}));

// Los diálogos de edición cargan monaco-editor, que no resuelve fuera del
// build de Quasar (su package.json no declara `main`/`exports`) y que esta
// prueba no abre nunca: el gestor solo los importa para pasárselos a $q.dialog.
const dialogoVacio = { default: { name: "DialogoStub", template: "<div/>" } };
vi.mock("@/components/scripts/ScriptFormModal.vue", () => dialogoVacio);
vi.mock("@/components/scripts/ScriptSnippetFormModal.vue", () => dialogoVacio);

const ScriptManager = (await import("@/components/scripts/ScriptManager.vue"))
  .default;

// Un nombre de 111 caracteres, una descripción de 138 y argumentos de 86: los
// tres pasan de largo los límites que usaba el recorte por JS (50 / 30 / 30).
const NOMBRE_LARGO =
  "Observer RMM - Reinstalacion desatendida del agente con validacion de huella y purga de cache (Windows 11 24H2)";
const DESC_LARGA =
  "Reinstala el agente, valida la huella del certificado contra el keystore, purga la cache de MeshCentral y reporta el resultado al servidor.";
const ARGS_LARGOS = [
  "-ServidorDestino",
  "observer-rmm.interno.example.com",
  "-ModoDesatendido",
  "-ReintentosMaximos",
  "5",
];

const UN_SCRIPT = {
  id: 1,
  name: NOMBRE_LARGO,
  description: DESC_LARGA,
  shell: "powershell",
  default_timeout: 90,
  category: "Mantenimiento programado de equipos de sucursal",
  args: ARGS_LARGOS,
  run_as_user: false,
  env_vars: [],
  script_body: "",
  supported_platforms: ["windows"],
  script_type: "userdefined",
  favorite: false,
  hidden: false,
};

async function montarGestor(scripts = [UN_SCRIPT]) {
  fetchScripts.mockResolvedValue(scripts);

  const store = createStore({
    state: { showScriptTemplates: true },
    getters: { showScriptTemplates: (s) => s.showScriptTemplates },
    mutations: { setShowScriptTemplates: () => {} },
  });

  const i18n = createI18n({
    legacy: false,
    globalInjection: true,
    locale: "es",
    fallbackLocale: "en",
    messages,
  });

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/scripts/:library?", name: "Scripts", component: { template: "<div/>" } },
    ],
  });
  router.push("/scripts");
  await router.isReady();

  const wrapper = mount(ScriptManager, {
    props: { embedded: true },
    global: {
      plugins: [store, i18n, router],
      // La navegación lateral no es lo que se prueba y pinta su propia lista.
      stubs: { ObsSectionNav: true },
    },
    attachTo: document.body,
  });

  await flushPromises();
  return wrapper;
}

// Cada trozo de texto del cuerpo de la tabla por separado, no el texto de la
// celda entera: el nombre y la descripción van en dos <div> apilados dentro de
// la misma celda, así que juntarlos escondería una elipsis a mitad de camino.
function textosDelCuerpo(wrapper) {
  const cuerpo = wrapper.find("tbody").element;
  const caminante = document.createTreeWalker(cuerpo, NodeFilter.SHOW_TEXT);
  const salida = [];
  let nodo;
  while ((nodo = caminante.nextNode())) {
    const texto = (nodo.nodeValue || "").replace(/\s+/g, " ").trim();
    if (texto) salida.push(texto);
  }
  return salida;
}

describe("ScriptManager /scripts: un nombre largo se puede leer entero (G08)", () => {
  beforeEach(() => {
    localStorage.clear();
    fetchScripts.mockReset();
  });

  it("ninguna celda recorta el texto por JavaScript", async () => {
    const wrapper = await montarGestor();

    const cortadas = textosDelCuerpo(wrapper).filter((t) => t.endsWith("..."));

    expect(
      cortadas,
      "hay celdas con «...» en el texto: eso es recorte por JS " +
        "(truncateText). El recorte va por CSS (.ellipsis + max-width) para " +
        "que el texto entero siga en el DOM y en el title",
    ).toEqual([]);

    wrapper.unmount();
  });

  it("el nombre, la descripción y los argumentos llevan el valor completo en title", async () => {
    const wrapper = await montarGestor();

    const titulos = wrapper
      .findAll("tbody [title]")
      .map((el) => el.attributes("title"));

    for (const [campo, valor] of [
      ["nombre", NOMBRE_LARGO],
      ["descripción", DESC_LARGA],
      ["argumentos", ARGS_LARGOS.join(" ")],
    ]) {
      expect(
        titulos,
        `la celda de ${campo} no expone el valor entero en title`,
      ).toContain(valor);
    }

    wrapper.unmount();
  });

  it("ningún title repite la elipsis del texto recortado", async () => {
    // El otro final malo: recortar por JS y poner ESE texto en el title. El
    // canal existe pero no sirve de nada, porque dice lo mismo que la celda.
    const wrapper = await montarGestor();

    const conElipsis = wrapper
      .findAll("tbody [title]")
      .map((el) => el.attributes("title"))
      .filter((t) => t && t.endsWith("..."));

    expect(
      conElipsis,
      "un title que termina en «...» no deja leer nada: tiene que llevar el " +
        "valor sin recortar",
    ).toEqual([]);

    wrapper.unmount();
  });

  it("el texto completo está en el DOM, que es lo que lee autotitle", async () => {
    // src/boot/autotitle.js arma el title con el.textContent. Si el texto que
    // llega al DOM ya viene cortado, ese canal queda inservible para cualquier
    // .ellipsis futuro de esta tabla.
    const wrapper = await montarGestor();
    const cuerpo = wrapper.find("tbody").text().replace(/\s+/g, " ");

    expect(cuerpo).toContain(NOMBRE_LARGO);
    expect(cuerpo).toContain(DESC_LARGA);

    wrapper.unmount();
  });
});
