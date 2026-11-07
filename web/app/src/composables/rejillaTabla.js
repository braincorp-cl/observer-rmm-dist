import { ref, nextTick } from "vue";

/**
 * 050 (V2-G15) — PATRÓN DE REJILLA para las tablas con desplazamiento virtual.
 *
 * Por qué existe este archivo y no quince copias. El defecto que lo motiva está
 * MEDIDO en `_reversa_forward/050-ui-v2-webui-oficial-200`: en una `q-table` con
 * `virtual-scroll`, Quasar SOBRE-RENDERIZA filas por encima y por debajo del
 * pliegue del contenedor, y el tabulador aterriza en ellas. En
 * `t041-instalar-software` eso daba **13 paradas de TAB** con los botones `add`
 * en `y=785..1031` y `y=-321..-239` sobre un viewport de 757, en los dos temas:
 * controles que el teclado SÍ visita y en los que no hay anillo en ningún píxel
 * de la pantalla, porque la capa del anillo se oculta a propósito cuando el
 * control está entero fuera de la vista.
 *
 * 🪤 Y el arreglo barato ya está medido como MALO: traer la fila a la vista con
 * `scrollIntoView` o `focus()` no sirve, porque **el nodo de la fila SE
 * RECICLA** y al desplazar el contenedor el foco queda sobre OTRA fila (medido
 * en la flota: BOG-SRV-PROXY ⇒ BUE-CAJA-01). Por eso la tabla pasa a ser UNA
 * sola parada de tabulador y las flechas mueven la fila, con `scrollTo` POR
 * ÍNDICE del scroller virtual, que es lo único que mantiene sincronizados la
 * fila enfocada y su dato.
 *
 * Todo lo que sigue es la generalización de lo que `AgentTable.vue` ya hacía, y
 * cada 🪤 es una corrección que costó una medición.
 */

/** Selector de los controles de una fila, para moverse DENTRO de ella. */
const CONTROLES_DE_FILA =
  'a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"]),' +
  '[contenteditable="true"]';

/**
 * 🪤 Dónde aterriza el foco cuando el reciclaje destruye el nodo enfocado.
 * Chrome NO lo manda al `<body>`: lo SUBE al ancestro enfocable más cercano, y
 * el scroller virtual de Quasar lleva `tabindex="-1"`. Desde ahí la rejilla
 * queda MUERTA, porque los `keydown` viven en la fila. Estos son los ancestros
 * en los que hay que atajarlo.
 */
const ANCESTROS_DEL_SCROLLER =
  ".q-virtual-scroll__content, .q-table__middle, tbody, table";

/**
 * Crea el controlador de la rejilla. No usa reactividad de Vue a propósito: el
 * estado (`filaFoco`, `moviendoFoco`) vive en el componente, que es quien sabe
 * si está en Options API o en `<script setup>`.
 *
 * @param {object} ctx
 * @param {() => Array} ctx.filas        filas en el MISMO orden que la tabla.
 * @param {() => object|null} ctx.tabla  la instancia de `q-table` (para `scrollTo`).
 * @param {() => string} ctx.claseHost  clase del host enfocable de la fila
 *        (p. ej. `obs-rej__host`). El host lleva además `data-fila` con el
 *        índice. 🪤 Se pide la CLASE y no un selector con `{i}`: con el selector
 *        había que destriparlo con `replace` para saber si un nodo era el host,
 *        y eso se rompe en silencio en cuanto el selector cambia de forma.
 * @param {() => number} ctx.leerFoco
 * @param {(n: number) => void} ctx.fijarFoco
 * @param {() => boolean} ctx.leerMoviendo
 * @param {(b: boolean) => void} ctx.fijarMoviendo
 * @param {(fn: Function) => void} ctx.alSiguienteCuadro  `nextTick` del componente.
 */
export function crearRejilla(ctx) {
  /**
   * 🪤 El tope NO es `filas.length`: casi todas estas tablas llevan `:filter`,
   * y con un filtro activo las filas RENDERIZADAS son menos. El índice que
   * `scrollTo` y `data-fila` usan es el de la lista filtrada y ordenada
   * (`props.rowIndex`), así que el tope tiene que salir de ahí o Fin se iría a
   * un índice que no existe. `filteredSortedRows` es la lista que la propia
   * `q-table` renderiza; `filas()` queda sólo como respaldo para cuando la
   * instancia todavía no está montada.
   */
  function ultimaFila() {
    const tabla = ctx.tabla();
    const vistas = tabla && tabla.filteredSortedRows;
    if (Array.isArray(vistas)) return vistas.length - 1;
    return (ctx.filas() || []).length - 1;
  }

  function selector(idx) {
    return "." + ctx.claseHost() + '[data-fila="' + idx + '"]';
  }

  /**
   * 🔴 La raíz donde se BUSCA el host, y el porqué está medido. La primera
   * versión usaba `document.querySelector(selector(idx))`, o sea una búsqueda
   * GLOBAL con un índice que es POR TABLA. Con dos rejillas montadas a la vez
   * los `data-fila` COLISIONAN, y el séptimo veredicto lo midió en el diálogo
   * «Instalar software»: 75 `.obs-rej__host` en el documento —42 dentro del
   * diálogo y 33 en la tabla de software que queda detrás—, DOS con
   * `data-fila="1"`, y el primero del documento es el de detrás del velo. La
   * primera flecha enfocaba ése, la trampa de foco del diálogo rebotaba el foco
   * al botón `close`, y de ahí no salía: los controles de las 42 filas del
   * diálogo quedaban sin vía de teclado. O sea que el patrón estaba ROTO justo
   * en la superficie por la que se desplegó.
   *
   * Se acota al elemento raíz de la propia `q-table`. Si la instancia aún no
   * está montada se cae al documento, que es el único caso en que no hay
   * ambigüedad posible (no hay tabla todavía).
   */
  function raiz() {
    const tabla = ctx.tabla();
    const el = tabla && (tabla.$el || tabla.el);
    return el && el.querySelector ? el : document;
  }

  function buscarHost(idx) {
    return raiz().querySelector(selector(idx));
  }

  /**
   * 🪤 Y `esHost` tampoco puede quedarse en «tiene la clase»: un host de OTRA
   * rejilla también la tiene. Se exige además que esté dentro de ESTA tabla.
   */
  function esHost(t) {
    if (!t || !t.classList || !t.classList.contains(ctx.claseHost())) return false;
    const r = raiz();
    return r === document || r.contains(t);
  }

  /**
   * 🪤 Un solo cuadro NO alcanza en un salto largo, y el precio era la rejilla
   * entera. Inicio/Fin mueven el scroller cientos de filas: el nodo de la fila
   * destino todavía no existe cuando corre el primer reintento, así que el
   * `.focus()` no encontraba nada; el nodo que SÍ tenía el foco ya lo había
   * destruido el reciclaje, y el foco caía en `tbody.q-virtual-scroll__content`.
   * El nodo destino de un salto de 170 filas apareció a los ~83 ms medidos, y
   * el scroller puede tardar más con la ventana pequeña: se reintenta en
   * escalera hasta 512 ms.
   */
  /**
   * 🔴 UNA sola escalera en vuelo, y el porqué está medido. La primera versión
   * no tenía guarda de reentrada: cada `focusin` que aterriza en el scroller
   * llamaba a `enfocar()` y arrancaba OTRA escalera de reintentos. Medido en la
   * flota servida: cada Fin/Inicio produce ~22 `focusin`, todos sobre
   * `q-virtual-scroll__content` (110 en tres teclas), así que las escaleras se
   * apilaban — y eso es el `RangeError: Maximum call stack size exceeded` que el
   * séptimo veredicto contó 184 veces en este mismo archivo, con la columna del
   * error cayendo justo en el `.focus()` de abajo.
   */
  let tempo = 0;

  function cancelarEscalera() {
    if (tempo) {
      clearTimeout(tempo);
      tempo = 0;
    }
  }

  /**
   * 🔴 Guarda de REENTRADA SINCRÓNICA, y el porqué está MEDIDO en el sha
   * servido `69b0168`, DOS VECES y con el mismo dedo apuntando al mismo sitio:
   * `266ca4a5.js 0:866 Uncaught RangeError: Maximum call stack size exceeded`,
   * donde `266ca4a5.js` es ESTE archivo y la columna 866 cae exactamente en el
   * `focus()` de abajo.
   *
   * El ciclo. `focus()` despacha `focusin` EN EL ACTO, antes de retornar. Si
   * ese `focus()` recicla el nodo de la fila —y en un salto de Inicio/Fin lo
   * recicla—, el nodo enfocado se destruye durante el propio despacho y Chrome
   * sube el foco al scroller. Ese `focusin` del scroller entra a
   * `alEntrarFoco`, que llama a `enfocar`, que llama a `focus()`… sin pasar
   * NUNCA por el bucle de eventos. La escalera de reintentos no protege de
   * esto, porque no hay `setTimeout` de por medio: es una pila.
   *
   * 🪤 Y la guarda anterior (`return` mientras `leerMoviendo()`) no lo atajaba
   * porque `enfocar` apagaba la bandera ANTES del `focus()`: cuando el
   * `focusin` reentrante llegaba, el movimiento ya constaba como terminado. Por
   * eso ahora la bandera se apaga DESPUÉS, y sólo cuando el foco quedó de
   * verdad en la fila pedida.
   */
  let enfocando = false;

  function enfocar(idx, espera) {
    cancelarEscalera();
    const el = buscarHost(idx);
    if (el) {
      if (document.activeElement === el) {
        ctx.fijarMoviendo(false);
        return;
      }
      enfocando = true;
      try {
        // 🪤 `preventScroll`: `focus()` arrastra el elemento a la vista y eso
        // pelearía con la rueda del usuario y con el `scrollTo` por índice, que
        // es el que debe decidir dónde queda el scroller.
        el.focus({ preventScroll: true });
      } finally {
        enfocando = false;
      }
      // 🪤 Y no se da por hecho que PEGÓ. Si el `focus()` recicló el nodo, el
      // foco quedó en el scroller: se compara contra el host que hay AHORA en
      // ese índice, porque el nodo puede ser otro, y si no pegó se reintenta
      // por escalera en vez de dejar la tabla sin parada de tabulador.
      const ahora = buscarHost(idx);
      if (ahora && document.activeElement === ahora) {
        ctx.fijarMoviendo(false);
        return;
      }
    }
    if (espera > 512) {
      ctx.fijarMoviendo(false);
      return;
    }
    tempo = setTimeout(() => {
      tempo = 0;
      enfocar(idx, espera * 2);
    }, espera);
  }

  function mover(i) {
    const ultima = ultimaFila();
    if (ultima < 0) return;
    const idx = Math.max(0, Math.min(ultima, i));
    ctx.fijarFoco(idx);
    ctx.fijarMoviendo(true);
    const tabla = ctx.tabla();
    if (tabla && tabla.scrollTo) tabla.scrollTo(idx);
    ctx.alSiguienteCuadro(() => enfocar(idx, 16));
  }

  function enElScroller(t) {
    if (!t || !t.matches || esHost(t)) return false;
    return t.matches(ANCESTROS_DEL_SCROLLER);
  }

  /**
   * El foco aterrizó en el scroller: se devuelve a la fila del tabulador.
   *
   * 🪤 Y se IGNORA en DOS casos, cada uno medido: mientras hay un movimiento en
   * vuelo —ese movimiento ya tiene su escalera, y atender además cada `focusin`
   * del scroller es lo que apilaba ~22 escaleras por tecla— y mientras `enfocar`
   * está dentro de su propio `focus()`, que es la recursión sincrónica del
   * `RangeError`.
   */
  function alEntrarFoco(ev) {
    // 🔴 Lo primero: el `focusin` que ESTE módulo acaba de provocar con su
    // propio `focus()` no se atiende. Es la mitad de la guarda contra el
    // RangeError medido; la otra mitad es apagar la bandera después del foco.
    if (enfocando) return;
    if (ctx.leerMoviendo()) return;
    if (!enElScroller(ev.target)) return;
    enfocar(ctx.leerFoco(), 16);
  }

  /**
   * Mueve el foco DENTRO de la fila, entre sus controles. Las tablas con varios
   * controles por fila (casillas de selección más botones de acción) lo
   * necesitan: con una sola parada por tabla, sin esto los demás controles de la
   * fila quedarían inalcanzables.
   *
   * 🪤 Los controles se leen del DOM de la fila enfocada en el momento, no de
   * una lista por tabla: el reciclaje cambia el nodo y una lista fijada a mano
   * se desincroniza en silencio.
   */
  function moverEnLaFila(paso) {
    const host = buscarHost(ctx.leerFoco());
    const fila = host && host.closest("tr");
    if (!fila) return false;
    const ctrls = [host].concat(
      Array.prototype.filter.call(
        fila.querySelectorAll(CONTROLES_DE_FILA),
        (e) => e !== host && e.offsetParent !== null,
      ),
    );
    if (ctrls.length < 2) return false;
    const i = ctrls.indexOf(document.activeElement);
    const j = Math.max(0, Math.min(ctrls.length - 1, (i < 0 ? 0 : i) + paso));
    if (j === i) return false;
    ctrls[j].focus({ preventScroll: true });
    return true;
  }

  /**
   * Teclas de la rejilla. Se atiende tanto desde la fila como desde el scroller:
   * cuando el foco quedó en el scroller el oyente de la fila no existe.
   */
  function alTecla(ev) {
    const t = ev.target;
    const enFila = !!(t && t.closest && t.closest("tr"));
    if (!esHost(t) && !enElScroller(t) && !enFila) return;
    const ultima = ultimaFila();
    if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") {
      if (moverEnLaFila(ev.key === "ArrowRight" ? 1 : -1)) ev.preventDefault();
      return;
    }
    const destino = {
      ArrowDown: ctx.leerFoco() + 1,
      ArrowUp: ctx.leerFoco() - 1,
      Home: 0,
      End: ultima,
    };
    if (!(ev.key in destino)) return;
    ev.preventDefault();
    mover(destino[ev.key]);
  }

  /**
   * 🪤 Si la fila con `tabindex="0"` se sale de la ventana renderizada (el
   * usuario desplazó con la rueda), la tabla se queda SIN parada de tabulador y
   * deja de ser alcanzable. Se la trae al primer índice visible, que es el dato
   * que entrega el propio evento del scroller.
   */
  function alDesplazarVirtual(det) {
    if (!det || ctx.leerMoviendo()) return;
    const { from, to } = det;
    if (typeof from !== "number" || typeof to !== "number") return;
    const f = ctx.leerFoco();
    if (f < from || f > to) ctx.fijarFoco(from);
  }

  return { mover, enfocar, alEntrarFoco, alTecla, alDesplazarVirtual };
}

/**
 * Mixin para los componentes en Options API, que son la mayoría. El componente
 * declara `rejillaFilas` (computada que devuelve las filas), `rejillaRef`
 * (nombre del `ref` de la `q-table`) y, si cambia el host, `rejillaClaseHost`.
 */
export const mixinRejillaTabla = {
  data() {
    return {
      filaFoco: 0,
      // Hay un movimiento de foco en vuelo: el scroller va a emitir eventos
      // mientras salta y no debe repuntar `filaFoco` a mitad del salto.
      moviendoFoco: false,
    };
  },
  created() {
    this.$_rejilla = crearRejilla({
      filas: () => this.rejillaFilas,
      tabla: () => this.$refs[this.rejillaRef || "tablaRejilla"],
      claseHost: () => this.rejillaClaseHost || "obs-rej__host",
      leerFoco: () => this.filaFoco,
      fijarFoco: (n) => {
        this.filaFoco = n;
      },
      leerMoviendo: () => this.moviendoFoco,
      fijarMoviendo: (b) => {
        this.moviendoFoco = b;
      },
      alSiguienteCuadro: (fn) => this.$nextTick(fn),
    });
  },
  methods: {
    moverFilaFoco(i) {
      this.$_rejilla.mover(i);
    },
    alEntrarFoco(ev) {
      this.$_rejilla.alEntrarFoco(ev);
    },
    alTeclaRejilla(ev) {
      this.$_rejilla.alTecla(ev);
    },
    alDesplazarVirtual(det) {
      this.$_rejilla.alDesplazarVirtual(det);
    },
  },
};

/**
 * Envoltorio para los componentes en `<script setup>`. Mismo núcleo, estado en
 * `ref`s propios.
 *
 * @param {object} o
 * @param {import("vue").Ref} o.refTabla  `ref` de la `q-table`.
 * @param {() => Array} o.filas
 * @param {string} [o.claseHost]
 */
export function usarRejillaTabla(o) {
  const filaFoco = ref(0);
  const moviendoFoco = ref(false);
  const rejilla = crearRejilla({
    filas: o.filas,
    tabla: () => o.refTabla.value,
    claseHost: () => o.claseHost || "obs-rej__host",
    leerFoco: () => filaFoco.value,
    fijarFoco: (n) => {
      filaFoco.value = n;
    },
    leerMoviendo: () => moviendoFoco.value,
    fijarMoviendo: (b) => {
      moviendoFoco.value = b;
    },
    alSiguienteCuadro: (fn) => nextTick(fn),
  });
  return {
    filaFoco,
    moviendoFoco,
    moverFilaFoco: rejilla.mover,
    alEntrarFoco: rejilla.alEntrarFoco,
    alTeclaRejilla: rejilla.alTecla,
    alDesplazarVirtual: rejilla.alDesplazarVirtual,
  };
}
