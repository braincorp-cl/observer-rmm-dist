// 050 / V2-G15: el núcleo del PATRÓN DE REJILLA, extraído de `AgentTable.vue`
// para las quince tablas con desplazamiento virtual que tienen controles en la
// fila.
//
// Este spec vigila los modos de fallo que YA COSTARON una medición cada uno, no
// una idea abstracta de "navega bien":
//
// 1. 🪤 El salto largo deja el foco en el SCROLLER. Inicio/Fin mueven el
//    scroller cientos de filas y el nodo destino todavía no existe cuando corre
//    el primer reintento; el nodo que tenía el foco ya lo destruyó el reciclaje,
//    así que Chrome SUBE el foco al ancestro enfocable (el scroller, con
//    `tabindex="-1"`) y desde ahí la rejilla queda muerta. Se exige que el
//    reintento en escalera recupere la fila cuando el nodo aparece tarde.
// 2. 🪤 La rueda del usuario deja la tabla SIN parada de tabulador. Si la fila
//    con `tabindex="0"` sale de la ventana renderizada, la tabla deja de ser
//    alcanzable; el evento del scroller tiene que repuntar el foco al primer
//    índice visible, y NO debe hacerlo a mitad de un salto en vuelo.
// 3. 🪤 Con una sola parada por tabla, los DEMÁS controles de la fila quedarían
//    inalcanzables. Siete de las quince tablas tienen dos o más, así que las
//    flechas izquierda/derecha tienen que moverse dentro de la fila.
// 4. Los límites: no se sale por arriba de la primera fila ni por debajo de la
//    última, y una tabla vacía no revienta.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { crearRejilla } from "@/composables/rejillaTabla";

function montarTabla(nFilas, ctrlsPorFila = 1) {
  document.body.innerHTML = "";
  const tabla = document.createElement("table");
  const tbody = document.createElement("tbody");
  tbody.className = "q-virtual-scroll__content";
  tbody.tabIndex = -1;
  for (let i = 0; i < nFilas; i++) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    const host = document.createElement("div");
    host.className = "obs-rej__host";
    host.setAttribute("data-fila", String(i));
    host.setAttribute("role", "button");
    host.tabIndex = i === 0 ? 0 : -1;
    td.appendChild(host);
    for (let c = 1; c < ctrlsPorFila; c++) {
      const b = document.createElement("button");
      b.textContent = "accion" + c;
      td.appendChild(b);
    }
    tr.appendChild(td);
    tbody.appendChild(tr);
  }
  tabla.appendChild(tbody);
  document.body.appendChild(tabla);
  return { tabla, tbody };
}

function contexto(nFilas, opciones = {}) {
  const estado = { foco: 0, moviendo: false, scrollA: [] };
  const rejilla = crearRejilla({
    filas: () => new Array(nFilas).fill(0),
    tabla: () => ({
      scrollTo: (i) => estado.scrollA.push(i),
      filteredSortedRows: opciones.filtradas,
    }),
    claseHost: () => "obs-rej__host",
    leerFoco: () => estado.foco,
    fijarFoco: (n) => {
      estado.foco = n;
    },
    leerMoviendo: () => estado.moviendo,
    fijarMoviendo: (b) => {
      estado.moviendo = b;
    },
    alSiguienteCuadro: opciones.alSiguienteCuadro || ((fn) => fn()),
  });
  return { estado, rejilla };
}

// `offsetParent` es siempre null en jsdom, y el filtro de controles de la fila
// lo usa para descartar lo invisible: se simula visible.
beforeEach(() => {
  Object.defineProperty(window.HTMLElement.prototype, "offsetParent", {
    configurable: true,
    get() {
      return this.parentNode;
    },
  });
});
afterEach(() => {
  vi.useRealTimers();
});

describe("patrón de rejilla: mover la fila", () => {
  it("mueve el foco a la fila pedida y desplaza el scroller POR ÍNDICE", () => {
    montarTabla(10);
    const { estado, rejilla } = contexto(10);
    rejilla.mover(4);
    expect(estado.foco).toBe(4);
    expect(estado.scrollA).toEqual([4]);
    expect(document.activeElement.getAttribute("data-fila")).toBe("4");
  });

  it("no se sale por los extremos y tolera una tabla vacía", () => {
    montarTabla(3);
    const { estado, rejilla } = contexto(3);
    rejilla.mover(-5);
    expect(estado.foco).toBe(0);
    rejilla.mover(99);
    expect(estado.foco).toBe(2);

    montarTabla(0);
    const vacia = contexto(0);
    expect(() => vacia.rejilla.mover(1)).not.toThrow();
    expect(vacia.estado.scrollA).toEqual([]);
  });
});

describe("patrón de rejilla: el tope con un filtro activo", () => {
  // 🪤 Casi todas estas tablas llevan `:filter`. Si el tope saliera de
  // `filas.length`, Fin mandaría el scroller a un índice que no existe en la
  // lista filtrada y el `.focus()` no encontraría nodo: el foco se quedaría en
  // el scroller, que es el estado del que cuesta volver.
  it("Fin va a la última fila FILTRADA, no a la última de los datos", () => {
    montarTabla(3);
    const { estado, rejilla } = contexto(500, { filtradas: [0, 0, 0] });
    rejilla.mover(499);
    expect(estado.foco).toBe(2);
    expect(estado.scrollA).toEqual([2]);
  });

  it("si la tabla aún no está montada, cae al largo de los datos", () => {
    montarTabla(4);
    const { estado, rejilla } = contexto(4, { filtradas: undefined });
    rejilla.mover(99);
    expect(estado.foco).toBe(3);
  });
});

describe("patrón de rejilla: el nodo destino que aparece TARDE", () => {
  it("reintenta en escalera hasta que el nodo del salto existe", () => {
    vi.useFakeTimers();
    // La tabla arranca con 3 filas renderizadas: la fila 170 NO existe todavía,
    // igual que tras un salto de Fin en el scroller real.
    montarTabla(3);
    const { estado, rejilla } = contexto(171);
    rejilla.mover(170);
    expect(estado.foco).toBe(170);
    expect(estado.moviendo).toBe(true);
    expect(document.activeElement).not.toHaveProperty("dataset.fila", "170");

    // El scroller termina de renderizar: aparece el nodo.
    const host = document.createElement("div");
    host.className = "obs-rej__host";
    host.setAttribute("data-fila", "170");
    host.tabIndex = 0;
    document.querySelector("tbody").appendChild(host);

    vi.advanceTimersByTime(600);
    expect(document.activeElement.getAttribute("data-fila")).toBe("170");
    expect(estado.moviendo).toBe(false);
  });

  it("se rinde a los 512 ms y no deja el movimiento colgado", () => {
    vi.useFakeTimers();
    montarTabla(3);
    const { estado, rejilla } = contexto(171);
    rejilla.mover(170);
    vi.advanceTimersByTime(5000);
    expect(estado.moviendo).toBe(false);
  });
});

describe("patrón de rejilla: el foco que aterriza en el scroller", () => {
  it("lo devuelve a la fila que lleva el tabulador", () => {
    const { tbody } = montarTabla(5);
    const { estado, rejilla } = contexto(5);
    estado.foco = 2;
    tbody.focus();
    rejilla.alEntrarFoco({ target: tbody });
    expect(document.activeElement.getAttribute("data-fila")).toBe("2");
  });

  it("no interfiere cuando el foco ya está en el host de la fila", () => {
    montarTabla(5);
    const { rejilla } = contexto(5);
    const host = document.querySelector('[data-fila="3"]');
    const antes = document.activeElement;
    rejilla.alEntrarFoco({ target: host });
    expect(document.activeElement).toBe(antes);
  });

  it("atiende las teclas de la rejilla también desde el scroller", () => {
    const { tbody } = montarTabla(5);
    const { estado, rejilla } = contexto(5);
    estado.foco = 1;
    const ev = { key: "End", target: tbody, preventDefault: vi.fn() };
    rejilla.alTecla(ev);
    expect(ev.preventDefault).toHaveBeenCalled();
    expect(estado.foco).toBe(4);
  });
});

describe("patrón de rejilla: la rueda del usuario", () => {
  it("repunta la parada de tabulador al primer índice visible", () => {
    montarTabla(5);
    const { estado, rejilla } = contexto(200);
    estado.foco = 0;
    rejilla.alDesplazarVirtual({ from: 120, to: 140 });
    expect(estado.foco).toBe(120);
  });

  it("NO repunta a mitad de un salto en vuelo", () => {
    montarTabla(5);
    const { estado, rejilla } = contexto(200);
    estado.foco = 170;
    estado.moviendo = true;
    rejilla.alDesplazarVirtual({ from: 10, to: 30 });
    expect(estado.foco).toBe(170);
  });

  it("deja el foco donde está si sigue dentro de lo renderizado", () => {
    montarTabla(5);
    const { estado, rejilla } = contexto(200);
    estado.foco = 15;
    rejilla.alDesplazarVirtual({ from: 10, to: 30 });
    expect(estado.foco).toBe(15);
  });
});

describe("patrón de rejilla: los demás controles de la fila", () => {
  it("las flechas izquierda/derecha recorren los controles de la fila", () => {
    montarTabla(4, 3); // host + 2 botones por fila
    const { estado, rejilla } = contexto(4);
    rejilla.mover(1);
    const host = document.querySelector('[data-fila="1"]');
    expect(document.activeElement).toBe(host);

    const der = { key: "ArrowRight", target: host, preventDefault: vi.fn() };
    rejilla.alTecla(der);
    expect(der.preventDefault).toHaveBeenCalled();
    expect(document.activeElement.textContent).toBe("accion1");

    rejilla.alTecla({
      key: "ArrowRight",
      target: document.activeElement,
      preventDefault: vi.fn(),
    });
    expect(document.activeElement.textContent).toBe("accion2");

    rejilla.alTecla({
      key: "ArrowLeft",
      target: document.activeElement,
      preventDefault: vi.fn(),
    });
    expect(document.activeElement.textContent).toBe("accion1");
    // Y la fila NO cambió por moverse dentro de ella.
    expect(estado.foco).toBe(1);
  });

  it("en una fila de un solo control la flecha no hace nada", () => {
    montarTabla(4, 1);
    const { rejilla } = contexto(4);
    rejilla.mover(2);
    const ev = {
      key: "ArrowRight",
      target: document.activeElement,
      preventDefault: vi.fn(),
    };
    rejilla.alTecla(ev);
    expect(ev.preventDefault).not.toHaveBeenCalled();
    expect(document.activeElement.getAttribute("data-fila")).toBe("2");
  });

  it("abajo y arriba siguen moviendo la FILA, no el control", () => {
    montarTabla(4, 3);
    const { estado, rejilla } = contexto(4);
    rejilla.mover(1);
    rejilla.alTecla({
      key: "ArrowDown",
      target: document.activeElement,
      preventDefault: vi.fn(),
    });
    expect(estado.foco).toBe(2);
    expect(document.activeElement.getAttribute("data-fila")).toBe("2");
  });
});
