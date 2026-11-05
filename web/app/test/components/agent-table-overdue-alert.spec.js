/* eslint-env node */

// Hallazgo #1 de AUDITORIA-COLOR.md (`git show 9f419ad:AUDITORIA-COLOR.md`),
// arreglado en 05222b0: el aviso de «alerta por vencimiento conmutada» llevaba
// `textColor: "black"`, que css/app.sass:327 remapea a var(--obs-text) —texto
// de página sobre un fondo de marca— y daba 3,04:1 (positivo) y 2,94:1 (info)
// en tema claro, 1,67:1 y 2,60:1 en oscuro: AA falla en los cuatro casos.
//
// Lo que se puede probar acá es la causa, no el efecto: que la llamada a
// $q.notify no manda textColor y que el color sigue siendo un token semántico
// del store, no un literal. El contraste en sí NO se prueba en jsdom —haría
// falta compilar el sass, resolver el cascade y medir el color calculado en un
// navegador de verdad— y queda anotado como tal en test/README.md.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

vi.mock("@/api/agents", () => ({
  runTakeControl: vi.fn(),
  runRemoteBackground: vi.fn(),
}));
vi.mock("@/api/core", () => ({ runURLAction: vi.fn() }));

const { mountAgentTable, esperarFilas, UN_EQUIPO } = await import(
  "../support/agent-table.js"
);

let montaje;
let notify;

beforeEach(async () => {
  vi.useFakeTimers();
  montaje = mountAgentTable();
  await esperarFilas();
  notify = vi
    .spyOn(montaje.wrapper.vm.$q, "notify")
    .mockImplementation(() => {});
});

afterEach(() => {
  montaje.wrapper.unmount();
  vi.useRealTimers();
});

describe("AgentTable · el aviso de alerta por vencimiento", () => {
  // Las tres categorías, encendiendo y apagando: son los cuatro pares de color
  // que midió la auditoría (positivo e info, en claro y en oscuro).
  for (const categoria of ["email", "text", "dashboard"]) {
    for (const estadoPrevio of [false, true]) {
      it(`no fija textColor (${categoria}, ${estadoPrevio ? "apagando" : "encendiendo"})`, async () => {
        montaje.wrapper.vm.overdueAlert(categoria, UN_EQUIPO, estadoPrevio);
        await vi.runAllTimersAsync();

        expect(montaje.axiosPut).toHaveBeenCalledOnce();
        expect(notify).toHaveBeenCalledOnce();

        const aviso = notify.mock.calls[0][0];
        expect(Object.keys(aviso)).not.toContain("textColor");
        // El por defecto de Notify es text-white, y es el que los overrides
        // por tema de app.sass llevan a --obs-on-brand.
        expect(aviso.textColor).toBeUndefined();
      });
    }
  }

  it("el color del aviso es un token semántico, no un literal de color", async () => {
    montaje.wrapper.vm.overdueAlert("email", UN_EQUIPO, false);
    await vi.runAllTimersAsync();
    expect(notify.mock.calls[0][0].color).toBe("positive");

    notify.mockClear();
    montaje.wrapper.vm.overdueAlert("email", UN_EQUIPO, true);
    await vi.runAllTimersAsync();
    expect(notify.mock.calls[0][0].color).toBe("info");
  });
});
