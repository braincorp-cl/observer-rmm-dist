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
//    inalcanzables, así que las flechas izquierda/derecha tienen que moverse
//    dentro de la fila. 🔴 Aquí decía «siete de las quince tablas tienen dos o
//    más»: era FALSO, salió de un clasificador mío que contaba enfocables POR
//    ARCHIVO y no por tabla. Contado en el DOM servido dentro de una fila real
//    y con el mismo selector que usa `moverEnLaFila`: AgentTable 1,
//    PendingActions 1, AdminManager 1, SoftwareTab 2.
// 5. 🔴 La RECURSIÓN SINCRÓNICA de `enfocar`: su propio `focus()` despacha
//    `focusin` antes de retornar, y si recicló el nodo ese `focusin` vuelve a
//    entrar por `alEntrarFoco`. Es el `RangeError: Maximum call stack size
//    exceeded` medido en el sha servido.
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

// 🔴 El modo de fallo que el séptimo veredicto midió en producción: DOS rejillas
// montadas a la vez. `data-fila` es un índice POR TABLA, así que una búsqueda
// global con `document.querySelector` devuelve el host de la OTRA tabla —en el
// diálogo «Instalar software» había 75 hosts, 42 dentro y 33 detrás del velo, y
// dos con `data-fila="1"`—, la trampa de foco del diálogo rebotaba al botón
// `close` y los controles de las 42 filas quedaban sin vía de teclado.
function montarDosTablas(nA, nB) {
  document.body.innerHTML = "";
  const raices = [];
  for (const [nombre, n] of [
    ["A", nA],
    ["B", nB],
  ]) {
    const raiz = document.createElement("div");
    raiz.className = "raiz-" + nombre;
    const tabla = document.createElement("table");
    const tbody = document.createElement("tbody");
    tbody.className = "q-virtual-scroll__content";
    tbody.tabIndex = -1;
    for (let i = 0; i < n; i++) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      const host = document.createElement("div");
      host.className = "obs-rej__host";
      host.setAttribute("data-fila", String(i));
      host.textContent = nombre + i;
      host.tabIndex = i === 0 ? 0 : -1;
      td.appendChild(host);
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
    tabla.appendChild(tbody);
    raiz.appendChild(tabla);
    document.body.appendChild(raiz);
    raices.push(raiz);
  }
  return raices;
}

function contextoEn(raiz, nFilas) {
  const estado = { foco: 0, moviendo: false, scrollA: [] };
  const rejilla = crearRejilla({
    filas: () => new Array(nFilas).fill(0),
    tabla: () => ({
      $el: raiz,
      scrollTo: (i) => estado.scrollA.push(i),
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
    alSiguienteCuadro: (fn) => fn(),
  });
  return { estado, rejilla };
}

describe("patrón de rejilla: DOS rejillas en el mismo documento", () => {
  it("cada una enfoca el host de SU tabla, no el de la otra", () => {
    const [raizA, raizB] = montarDosTablas(5, 5);
    const a = contextoEn(raizA, 5);
    const b = contextoEn(raizB, 5);

    b.rejilla.mover(1);
    expect(document.activeElement.textContent).toBe("B1");
    expect(raizB.contains(document.activeElement)).toBe(true);

    a.rejilla.mover(1);
    expect(document.activeElement.textContent).toBe("A1");
    expect(raizA.contains(document.activeElement)).toBe(true);
  });

  it("el host de la OTRA tabla no cuenta como host propio", () => {
    const [raizA, raizB] = montarDosTablas(3, 3);
    const b = contextoEn(raizB, 3);
    const hostAjeno = raizA.querySelector('[data-fila="0"]');
    // Si `esHost` sólo mirara la clase, esto se tomaría como «el foco ya está
    // en la fila» y la rejilla de B no se recuperaría nunca.
    b.estado.foco = 2;
    b.rejilla.alEntrarFoco({ target: raizB.querySelector("tbody") });
    expect(document.activeElement.textContent).toBe("B2");
    expect(hostAjeno.classList.contains("obs-rej__host")).toBe(true);
  });

  it("las flechas de una no mueven la fila de la otra", () => {
    const [raizA, raizB] = montarDosTablas(6, 6);
    const a = contextoEn(raizA, 6);
    const b = contextoEn(raizB, 6);
    b.rejilla.mover(0);
    b.rejilla.alTecla({
      key: "End",
      target: raizB.querySelector("tbody"),
      preventDefault: () => {},
    });
    expect(b.estado.foco).toBe(5);
    expect(a.estado.foco).toBe(0);
    expect(document.activeElement.textContent).toBe("B5");
  });
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

// 🔴 El segundo defecto que el séptimo veredicto midió: 184
// `RangeError: Maximum call stack size exceeded` en este mismo archivo. Medido en
// la flota servida: cada Fin/Inicio produce ~22 `focusin`, TODOS sobre
// `q-virtual-scroll__content`, y sin guarda de reentrada cada uno arrancaba otra
// escalera de reintentos, así que se apilaban.
describe("patrón de rejilla: UNA sola escalera de reintentos en vuelo", () => {
  it("22 focusin seguidos sobre el scroller no apilan 22 escaleras", () => {
    vi.useFakeTimers();
    const espia = vi.spyOn(globalThis, "setTimeout");
    const { tbody } = montarTabla(3);
    const { estado, rejilla } = contexto(171);
    // la fila 170 no existe todavía: la escalera arranca y se queda esperando
    estado.foco = 170;
    for (let i = 0; i < 22; i++) rejilla.alEntrarFoco({ target: tbody });
    const programados = espia.mock.calls.length;
    expect(programados).toBeLessThanOrEqual(22);
    // y al avanzar el reloj, el total de reintentos NO explota
    vi.advanceTimersByTime(2000);
    expect(espia.mock.calls.length).toBeLessThan(40);
    espia.mockRestore();
  });

  it("no atiende el scroller mientras hay un movimiento en vuelo", () => {
    vi.useFakeTimers();
    montarTabla(3);
    const { estado, rejilla } = contexto(171);
    rejilla.mover(170); // deja `moviendo` en true, con su escalera
    expect(estado.moviendo).toBe(true);
    const espia = vi.spyOn(globalThis, "setTimeout");
    for (let i = 0; i < 10; i++) {
      rejilla.alEntrarFoco({ target: document.querySelector("tbody") });
    }
    // ninguna escalera nueva: el movimiento en vuelo ya tiene la suya
    expect(espia.mock.calls.length).toBe(0);
    espia.mockRestore();
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

// 🔴 La recursión sincrónica, que es el `RangeError: Maximum call stack size
// exceeded` medido DOS veces sobre el sha servido `69b0168`
// (`266ca4a5.js 0:866`, que es este composable y la columna del `focus()`).
//
// 🔑 Por qué llegó tan tarde al banco de pruebas: lo buscaba con una sonda
// `window.onerror` DENTRO de la página, y ese canal es CIEGO a este error —su
// control positivo me devolvió `"Script error."` con `stack: null`—. El canal
// que sí lo ve es el log del navegador. Dos no-reproducciones mías lo
// declararon ausente antes de que una tercera medición, con el canal correcto,
// lo pusiera 12 veces en mi propia sesión.
describe("rejilla: el focus() propio no puede reentrar por focusin", () => {
  /**
   * Monta el escenario exacto: un host cuyo `focus()` RECICLA el nodo, o sea
   * deja el foco en el scroller en vez de en él. Sin guarda, `alEntrarFoco`
   * vuelve a llamar a `enfocar` dentro del mismo `focus()` y la pila crece
   * hasta reventar.
   */
  function montarConReciclajeAlEnfocar(nFilas) {
    const { tbody } = montarTabla(nFilas);
    const envoltorio = document.createElement("div");
    document.body.appendChild(envoltorio);
    envoltorio.appendChild(document.querySelector("table"));
    const cuenta = { focus: 0 };
    for (const host of document.querySelectorAll(".obs-rej__host")) {
      host.focus = function () {
        cuenta.focus++;
        // El reciclaje: el foco NO queda en el host, cae en el scroller, y el
        // `focusin` se despacha SINCRÓNICAMENTE, como en el navegador.
        tbody.dispatchEvent(
          new window.FocusEvent("focusin", { bubbles: true }),
        );
      };
    }
    return { tbody, envoltorio, cuenta };
  }

  it("no desborda la pila cuando el focus() deja el foco en el scroller", () => {
    const { envoltorio, cuenta } = montarConReciclajeAlEnfocar(4);
    const { rejilla } = contexto(4);
    envoltorio.addEventListener("focusin", rejilla.alEntrarFoco);
    vi.useFakeTimers();
    // Sin la guarda esto lanza RangeError; con ella, un solo focus().
    expect(() => rejilla.enfocar(0, 16)).not.toThrow();
    expect(cuenta.focus).toBe(1);
  });

  it("si el foco no pegó, reintenta por escalera y no se rinde en el acto", () => {
    const { envoltorio, cuenta } = montarConReciclajeAlEnfocar(4);
    const { estado, rejilla } = contexto(4);
    envoltorio.addEventListener("focusin", rejilla.alEntrarFoco);
    vi.useFakeTimers();
    estado.moviendo = true;
    rejilla.enfocar(0, 16);
    expect(cuenta.focus).toBe(1);
    // El movimiento sigue EN VUELO: el foco no quedó en la fila pedida.
    expect(estado.moviendo).toBe(true);
    vi.advanceTimersByTime(16);
    expect(cuenta.focus).toBe(2);
  });

  it("cuando el focus() SÍ pega, apaga la bandera y no reintenta", () => {
    montarTabla(4);
    const { estado, rejilla } = contexto(4);
    vi.useFakeTimers();
    estado.moviendo = true;
    rejilla.enfocar(2, 16);
    expect(document.activeElement.getAttribute("data-fila")).toBe("2");
    expect(estado.moviendo).toBe(false);
    const activo = document.activeElement;
    vi.advanceTimersByTime(600);
    expect(document.activeElement).toBe(activo);
  });
});

// 🔴 Asomar la fila cuando `scrollTo` por índice no alcanza. Medido en el sha
// servido `ee57472`: en `UserSessionsTable`, Fin dejaba la fila 20 en `y=756,2`
// con `h=14` sobre una ventana de 757 —0,8 px visibles— y el anillo no se
// dibujaba. La tabla cabe entera en su `max-height`, así que su scroller
// virtual no tiene recorrido: lo que estaba fuera lo estaba por el scroll del
// DIÁLOGO, que nadie movía.
//
// 🪤 Lo que vigila el control de abajo es la PROPORCIÓN: `scrollIntoView` ya
// está medido como malo cuando sustituye al `scrollTo` por índice (recicla el
// nodo y el foco salta de fila), así que no puede llamarse en las filas que ya
// se ven. En este mismo ítem arreglar un caso con una regla general ya rompió
// catorce estables una vez.
describe("rejilla: asomar la fila que quedó fuera de la ventana", () => {
  function montarConRects(rects) {
    const { tbody } = montarTabla(rects.length);
    const llamadas = [];
    const hosts = [...document.querySelectorAll(".obs-rej__host")];
    hosts.forEach((host, i) => {
      host.getBoundingClientRect = () => rects[i];
      host.scrollIntoView = (o) => llamadas.push({ fila: i, opciones: o });
    });
    return { tbody, hosts, llamadas };
  }
  const dentro = { top: 300, bottom: 314, left: 10, right: 120, height: 14, width: 110 };
  // 0,8 px visibles de 14, que es el caso medido
  const alBorde = { top: 756.2, bottom: 770.2, left: 10, right: 120, height: 14, width: 110 };

  beforeEach(() => {
    window.innerHeight = 757;
    window.innerWidth = 1440;
  });

  it("la asoma cuando casi toda la fila quedó fuera", () => {
    const { llamadas } = montarConRects([dentro, alBorde]);
    const { estado, rejilla } = contexto(2);
    vi.useFakeTimers();
    estado.moviendo = true;
    rejilla.enfocar(1, 16);
    expect(llamadas).toHaveLength(1);
    expect(llamadas[0].fila).toBe(1);
    expect(llamadas[0].opciones).toEqual({ block: "nearest", inline: "nearest" });
    expect(estado.moviendo).toBe(false);
  });

  it("🪤 NO la toca cuando ya se ve: no pelea con el scrollTo por índice", () => {
    const { llamadas } = montarConRects([dentro, dentro]);
    const { rejilla } = contexto(2);
    vi.useFakeTimers();
    rejilla.enfocar(1, 16);
    expect(llamadas).toHaveLength(0);
    expect(document.activeElement.getAttribute("data-fila")).toBe("1");
  });

  it("si al asomarla se recicla el nodo, recupera el foco en esa misma fila", () => {
    const { llamadas, hosts } = montarConRects([dentro, alBorde]);
    const { rejilla } = contexto(2);
    vi.useFakeTimers();
    // El reciclaje: al asomar, el foco se cae del host.
    hosts[1].scrollIntoView = (o) => {
      llamadas.push({ fila: 1, opciones: o });
      hosts[1].blur();
    };
    rejilla.enfocar(1, 16);
    expect(llamadas).toHaveLength(1);
    expect(document.activeElement).toBe(hosts[1]);
  });
});
