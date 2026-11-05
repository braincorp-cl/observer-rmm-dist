/* eslint-env node */

// Celda del hostname de la flota: el control de teclado de la auditoría A11Y
// (hallazgo #1) y la ventana de 250 ms del clic/doble clic (046 F4 / RN-03).
//
// Es una prueba de integración contra el QTable de verdad: se monta
// AgentTable.vue entero y se actúa sobre el DOM que pinta, no sobre los métodos
// del componente. Así cubre lo que de verdad se rompió —que el <div> de la
// celda sea alcanzable y operable, y que el clic de la fila siga burbujeando
// por debajo de él— y no solo que los métodos existan.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// Estos dos módulos arrastran `@/router`, que al importarse construye el router
// real y con él TODAS las vistas (monaco, xterm, leaflet, apexcharts). No hace
// falta nada de eso para pintar una fila.
vi.mock("@/api/agents", () => ({
  runTakeControl: vi.fn(),
  runRemoteBackground: vi.fn(),
}));
vi.mock("@/api/core", () => ({ runURLAction: vi.fn() }));

const { mountAgentTable, esperarFilas, UN_EQUIPO, VENTANA_DOBLE_CLIC_MS } =
  await import("../support/agent-table.js");

const RUTA_ESPERADA = {
  name: "Agent",
  params: { agent_id: UN_EQUIPO.agent_id },
};

let montaje;

function celdaHostname() {
  const control = montaje.wrapper.find(".obs-agtbl__host");
  expect(control.exists()).toBe(true);
  return control;
}

function fila() {
  const tr = montaje.wrapper.find("tbody.q-virtual-scroll__content tr");
  expect(tr.exists()).toBe(true);
  return tr;
}

beforeEach(async () => {
  vi.useFakeTimers();
  montaje = mountAgentTable();
  await esperarFilas();
});

afterEach(() => {
  montaje.wrapper.unmount();
  vi.useRealTimers();
});

describe("AgentTable · la celda del hostname es un control de teclado", () => {
  it("expone role=button, tabindex=0 y el rótulo accesible con el nombre del equipo", () => {
    const control = celdaHostname();
    expect(control.attributes("role")).toBe("button");
    expect(control.attributes("tabindex")).toBe("0");
    expect(control.attributes("aria-label")).toBe(
      `Abrir el equipo ${UN_EQUIPO.hostname}`,
    );
  });

  it("es el único camino de teclado: el <tr> de la fila no es enfocable", () => {
    // El arreglo deliberadamente NO puso tabindex en el <q-tr> (su rol
    // implícito es `row`). Si alguien lo "mejora" moviéndolo a la fila, esto
    // avisa.
    expect(fila().attributes("tabindex")).toBeUndefined();
    expect(fila().attributes("role")).toBeUndefined();
    const enfocables = montaje.wrapper.findAll(
      'tbody.q-virtual-scroll__content [tabindex="0"]',
    );
    expect(enfocables).toHaveLength(1);
    expect(enfocables[0].classes()).toContain("obs-agtbl__host");
  });

  it("Enter abre el equipo", async () => {
    await celdaHostname().trigger("keyup", { key: "Enter" });
    expect(montaje.push).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(VENTANA_DOBLE_CLIC_MS);
    expect(montaje.push).toHaveBeenCalledWith(RUTA_ESPERADA);
  });

  it("Espacio abre el equipo", async () => {
    await celdaHostname().trigger("keyup", { key: " " });
    await vi.advanceTimersByTimeAsync(VENTANA_DOBLE_CLIC_MS);
    expect(montaje.push).toHaveBeenCalledWith(RUTA_ESPERADA);
  });

  it("Espacio no desplaza la página (keydown con preventDefault)", () => {
    // `@keydown.space.prevent` existe para que la barra espaciadora no haga
    // scroll mientras se opera la tabla con el teclado.
    const evento = new window.KeyboardEvent("keydown", {
      key: " ",
      bubbles: true,
      cancelable: true,
    });
    celdaHostname().element.dispatchEvent(evento);
    expect(evento.defaultPrevented).toBe(true);
  });

  it("abrir con el teclado marca la fila activa antes de navegar", async () => {
    await celdaHostname().trigger("keyup", { key: "Enter" });
    expect(montaje.commit).toHaveBeenCalledWith(
      "setActiveRow",
      UN_EQUIPO.agent_id,
    );
    expect(montaje.commit).toHaveBeenCalledWith(
      "setAgentPlatform",
      UN_EQUIPO.plat,
    );
  });

  it("el menú contextual sigue saliendo desde la celda enfocada", () => {
    // La tecla Menú / Shift+F10 la traduce el navegador a un evento
    // `contextmenu` sobre el elemento con foco; eso es del navegador y no se
    // puede sintetizar en jsdom. Lo que sí es nuestro, y es lo que se prueba,
    // es que el evento burbujee desde el <div> enfocable hasta el @contextmenu
    // del <q-tr> (AgentTable.vue:90).
    celdaHostname().element.dispatchEvent(
      new window.MouseEvent("contextmenu", { bubbles: true, cancelable: true }),
    );
    expect(montaje.commit).toHaveBeenCalledWith(
      "setActiveRow",
      UN_EQUIPO.agent_id,
    );
  });
});

describe("AgentTable · el clic y el doble clic no cambiaron", () => {
  it("un clic sobre la celda burbujea a la fila y navega a los 250 ms", async () => {
    // El <div> del arreglo no lleva @click propio justamente para esto.
    await celdaHostname().trigger("click");
    await vi.advanceTimersByTimeAsync(VENTANA_DOBLE_CLIC_MS - 1);
    expect(montaje.push).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(montaje.push).toHaveBeenCalledWith(RUTA_ESPERADA);
  });

  it("un clic en cualquier parte de la fila navega igual", async () => {
    await fila().trigger("click");
    await vi.advanceTimersByTimeAsync(VENTANA_DOBLE_CLIC_MS);
    expect(montaje.push).toHaveBeenCalledWith(RUTA_ESPERADA);
  });

  it("el doble clic cancela la navegación: la ventana de 250 ms no se come el dblclick", async () => {
    // Secuencia real del navegador: click, click, dblclick.
    await fila().trigger("click");
    await fila().trigger("click");
    await fila().trigger("dblclick");
    await vi.advanceTimersByTimeAsync(2000);
    expect(montaje.push).not.toHaveBeenCalled();
  });

  it("el doble clic sobre la celda del hostname también cancela", async () => {
    const control = celdaHostname();
    await control.trigger("click");
    await control.trigger("dblclick");
    await vi.advanceTimersByTimeAsync(2000);
    expect(montaje.push).not.toHaveBeenCalled();
  });

  it("si el doble clic llega tarde, el clic ya navegó (la ventana es de 250 ms, no infinita)", async () => {
    await fila().trigger("click");
    await vi.advanceTimersByTimeAsync(VENTANA_DOBLE_CLIC_MS);
    expect(montaje.push).toHaveBeenCalledTimes(1);
    await fila().trigger("dblclick");
    await vi.advanceTimersByTimeAsync(2000);
    expect(montaje.push).toHaveBeenCalledTimes(1);
  });
});
