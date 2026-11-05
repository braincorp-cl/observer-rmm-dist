/* eslint-env node */

// Regla de aceptación: el color NO puede ser la única señal de un control ni de
// un dato. Si dos cosas distintas sólo se diferencian por el color, quien no
// distingue ese par no puede usar la pantalla.
//
// Tres defectos de esa familia, uno por bloque:
//
//  1. ContextColumn — el punto de salud por equipo (8 px, sin borde, sin texto,
//     sin title y sin aria-label) era el único indicador de estado de la
//     columna. Se le da el estado traducido, como ya hace AgentHeader con
//     `statusText`.
//  2. ContextColumn — `.obs-ctx__dot--offline` se usaba en la plantilla pero no
//     tenía regla CSS: «desconectado» caía al `--obs-faint` base, idéntico a
//     «sin estado».
//  3. WinUpdateTab — la columna «política» repetía glifo entre «aprobar» e
//     «ignorar» (`fas fa-check`) y entre «no hacer nada» y «heredar»
//     (`fiber_manual_record`), dejando el color como único rótulo.
//
// El contraste de los colores en sí no se prueba acá: eso necesita un navegador
// de verdad (ver test/README.md).

import { describe, it, expect, vi, afterEach } from "vitest";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { mount, flushPromises } from "@vue/test-utils";
import { createI18n } from "vue-i18n";
import messages from "@/i18n";

const fetchAgents = vi.fn();
vi.mock("@/api/agents", () => ({ fetchAgents: (...a) => fetchAgents(...a) }));

// ContextColumn usa useRoute()/useRouter() en <script setup>: eso no se cubre
// con `global.mocks`, que sólo alcanza a $route/$router de la Options API.
const push = vi.fn();
vi.mock("vue-router", () => ({
  useRoute: () => ({
    params: {
      agent_id: "3a7f1e2c-0000-4000-8000-000000000001",
      section: "summary",
    },
  }),
  useRouter: () => ({ push }),
}));

const ContextColumn = (
  await import("@/components/agents/workspace/ContextColumn.vue")
).default;

const leer = (p) =>
  readFile(fileURLToPath(new URL("../../" + p, import.meta.url)), "utf8");

const EQUIPO = {
  agent_id: "3a7f1e2c-0000-4000-8000-000000000001",
  hostname: "EQUIPO-01",
  description: "",
  status: "online",
  checks: { failing: 0 },
};

// Los cuatro estados que devuelve dot(): el tercer campo es la clase esperada.
const ESTADOS = [
  ["en línea y sano", { status: "online", checks: { failing: 0 } }, "ok"],
  [
    "con chequeos fallando",
    { status: "online", checks: { failing: 2 } },
    "fail",
  ],
  ["sin respuesta", { status: "overdue", checks: { failing: 0 } }, "overdue"],
  ["desconectado", { status: "offline", checks: { failing: 0 } }, "offline"],
];

async function montar(equipo, locale = "es") {
  fetchAgents.mockResolvedValue([{ ...EQUIPO, ...equipo }]);
  const i18n = createI18n({
    legacy: false,
    globalInjection: true,
    locale,
    fallbackLocale: "en",
    messages,
  });
  const wrapper = mount(ContextColumn, {
    props: {
      agent: { client: "Cliente Uno", site_name: "Sitio Uno", site: 1 },
    },
    global: { plugins: [i18n] },
    attachTo: document.body,
  });
  await flushPromises();
  await vi.waitFor(() => {
    if (!wrapper.find(".obs-ctx__dot").exists()) throw new Error("sin punto");
  });
  return wrapper;
}

let montado;
afterEach(() => {
  montado?.unmount();
  montado = null;
  fetchAgents.mockReset();
});

describe("ContextColumn · el punto de salud no es sólo color", () => {
  for (const [nombre, equipo, clase] of ESTADOS) {
    it(`un equipo ${nombre} lleva el estado en aria-label y en title`, async () => {
      montado = await montar(equipo);
      const punto = montado.find(".obs-ctx__dot");

      expect(punto.classes()).toContain(`obs-ctx__dot--${clase}`);

      const rotulo = punto.attributes("aria-label");
      const title = punto.attributes("title");
      expect(rotulo, "sin aria-label el color es la única señal").toBeTruthy();
      expect(title).toBe(rotulo);
      // Sin traducir, vue-i18n devuelve la propia clave.
      expect(rotulo).not.toContain("agentWorkspace.context.status");
      // aria-label en un <span> genérico lo ignora la ARIA: necesita rol.
      expect(punto.attributes("role")).toBe("img");
    });
  }

  it("los cuatro estados dan cuatro textos distintos, en es y en en", async () => {
    for (const locale of ["es", "en"]) {
      const textos = [];
      for (const [, equipo] of ESTADOS) {
        montado = await montar(equipo, locale);
        textos.push(montado.find(".obs-ctx__dot").attributes("aria-label"));
        montado.unmount();
        montado = null;
        fetchAgents.mockReset();
      }
      expect(new Set(textos).size, `textos repetidos en ${locale}`).toBe(4);
    }
  });
});

describe("ContextColumn · toda clase de punto usada tiene regla CSS", () => {
  it("--offline está definida y no cae al --obs-faint base", async () => {
    const fuente = await leer(
      "src/components/agents/workspace/ContextColumn.vue",
    );
    const estilos = fuente.slice(fuente.indexOf("<style"));
    for (const clase of ESTADOS.map(([, , c]) => c)) {
      expect(
        estilos,
        `.obs-ctx__dot--${clase} se usa en la plantilla pero no tiene regla`,
      ).toContain(`.obs-ctx__dot--${clase}`);
    }
    // Coherencia con AgentHeader, que pinta desconectado con --q-warning.
    const header = await leer(
      "src/components/agents/workspace/AgentHeader.vue",
    );
    expect(header).toMatch(
      /\.obs-agenthdr__status--offline \.obs-agenthdr__dot\s*\n\s*background: var\(--q-warning\)/,
    );
    expect(estilos).toMatch(
      /\.obs-ctx__dot--offline\s*\n\s*background: var\(--q-warning\)/,
    );
  });

  it("ninguna regla del punto usa un color literal", async () => {
    const fuente = await leer(
      "src/components/agents/workspace/ContextColumn.vue",
    );
    const estilos = fuente.slice(fuente.indexOf("<style"));
    for (const regla of estilos.match(
      /\.obs-ctx__dot[^\n]*\n(?:\s+[^\n]*\n)*/g,
    ) ?? []) {
      expect(regla).not.toMatch(/#[0-9a-f]{3,8}\b|\brgba?\(|\bhsla?\(/i);
    }
  });
});

describe("WinUpdateTab · la columna «política» no se lee sólo por color", () => {
  it("los cuatro valores de política usan cuatro glifos distintos", async () => {
    const fuente = await leer("src/components/agents/WinUpdateTab.vue");
    const glifos = {};
    for (const accion of ["nothing", "approve", "ignore", "inherit"]) {
      const re = new RegExp(
        `action ===? '${accion}'[\\s\\S]{0,120}?name="([^"]+)"`,
      );
      const m = fuente.match(re);
      expect(m, `no se encontró el icono de '${accion}'`).toBeTruthy();
      glifos[accion] = m[1];
    }
    expect(
      new Set(Object.values(glifos)).size,
      `glifos repetidos: ${JSON.stringify(glifos)}`,
    ).toBe(4);
    // Los dos que se arreglaron, clavados: «ignorar» toma el glifo que la
    // columna vecina ya usa para «ignorada».
    expect(glifos.ignore).toBe("fas fa-ban");
    expect(glifos.inherit).not.toBe(glifos.nothing);
  });
});
