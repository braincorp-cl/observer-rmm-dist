// 050 (V2-G15): el anillo de foco se dibuja en una CAPA, no en el control.
//
// 🔑 Por qué existe este archivo y no son tres reglas de CSS. Un anillo dibujado
// por el propio control NO se puede garantizar en esta consola: se probaron
// cinco geometrías en una noche y cada una murió por un mecanismo distinto,
// todos medidos en píxeles sobre lo servido, no razonados:
//
//   · un ANCESTRO que recorta — `outline` 2px por fuera y `overflow:hidden` con
//     holgura 0: `.obs-ctx__list`, luego `.obs-fleet__tree`, luego
//     `div.row.no-wrap.items-center` del ActionBar del agente (292 de 349 lados
//     sin banda). Enumerarlos falló TRES veces y un sexto no se descarta leyendo;
//   · un DESCENDIENTE que tapa — con el anillo hacia adentro, la banda interna
//     la borran `.q-focus-helper` (#414A57 donde iba #16202E) y el texto de la
//     propia celda (#555F6E);
//   · un HERMANO POSTERIOR que pinta encima, sin ningún overflow de por medio:
//     el ítem siguiente del riel de ajustes borra la banda de abajo;
//   · y una INSIGNIA flotante, que es `position:absolute` y gana al outline.
//
// Los tres primeros son propiedades del ÁRBOL, no del control, así que ninguna
// regla sobre el control los puede evitar. La capa sí: vive en `<body>`, encima
// de todo, y no tiene ancestro que la recorte, descendiente que la tape ni
// hermano que la pise. Las dos bandas están siempre completas en los cuatro
// lados, y la forma es la misma en toda la consola POR CONSTRUCCIÓN — no hay un
// sexto contenedor que encontrar.
//
// Lo que NO cambia: el color sale de los mismos tokens `--obs-focus` y
// `--obs-focus-alt`, el disparador sigue siendo `:focus-visible` (se ve al
// tabular, no al hacer clic) y el orden de tonos es el de siempre: 2px de
// --obs-focus afuera, 2px de --obs-focus-alt adentro, contrastando 13,90:1
// entre sí, que es lo que mide la enmienda A del criterio.
//
// 🪤 El anillo puede solaparse 4px con el borde de un contenedor apretado, y es
// A PROPÓSITO: entre «se ve el foco pisando 4px de la cromática vecina» y «no se
// ve el foco», el criterio pide lo primero. Es lo que hace que la primera fila
// de una lista con scroll tenga anillo.

const ID = "obs-anillo-foco";

let capa = null;
let objetivo = null;
let raf = 0;
// 🪤 Modalidad de la última interacción. Hace falta por un caso MEDIDO: en un
// `<input type="datetime-local">` el TAB recorre los segmentos internos
// (año, mes, día, hora, minuto) y en el ÚLTIMO de ellos Chrome deja de casar
// `:focus-visible` aunque el input siga siendo `document.activeElement` —su
// `outline` computado pasa de `3px none` a `0px none`—. Con la regla a secas el
// anillo desaparecía durante una pulsación de TAB y volvía en la siguiente, ya
// sobre «Cancelar»: una tecla sin foco visible en ningún lado. Medido en
// «Reiniciar más tarde», parada 8 de 11, en los dos temas.
let teclado = false;

function crear() {
  if (capa) return capa;
  capa = document.createElement("div");
  capa.id = ID;
  capa.setAttribute("aria-hidden", "true");
  Object.assign(capa.style, {
    position: "fixed",
    top: "0",
    left: "0",
    display: "none",
    pointerEvents: "none",
    // Encima de los diálogos y menús de Quasar (6000-7000) y por debajo de sus
    // notificaciones (9500): el foco tiene que verse DENTRO de un diálogo.
    zIndex: "9400",
    // Las dos bandas, hacia afuera. La primera sombra se pinta encima, así que
    // --obs-focus-alt ocupa [0,2] y --obs-focus [2,4].
    boxShadow:
      "0 0 0 2px var(--obs-focus-alt), 0 0 0 4px var(--obs-focus)",
  });
  document.body.appendChild(capa);
  return capa;
}

// 🪤 El elemento que recibe el foco no siempre es el que hay que marcar. En un
// campo de Quasar el foco va al `<input>` y el borde visible es el de
// `.q-field__control`; en una casilla, al input oculto. Y un botón con insignia
// flotante es, para el ojo, el botón MÁS su insignia: marcar sólo la caja del
// botón dejaba la insignia fuera del anillo.
function cajaDe(el) {
  const campo = el.closest(".q-field__control");
  if (campo) return campo;
  const marca = el.closest(".q-checkbox, .q-radio, .q-toggle");
  if (marca) {
    return (
      marca.querySelector(
        ".q-checkbox__inner, .q-radio__inner, .q-toggle__track",
      ) || marca
    );
  }
  const ctrl = el.closest(".q-btn, .q-item, .q-tab, .q-chip") || el;
  return ctrl;
}

function rectUnion(el) {
  const r = el.getBoundingClientRect();
  let x1 = r.left, y1 = r.top, x2 = r.right, y2 = r.bottom;
  const insignias = el.querySelectorAll(".q-badge--floating");
  for (const b of insignias) {
    const rb = b.getBoundingClientRect();
    if (!rb.width || !rb.height) continue;
    x1 = Math.min(x1, rb.left); y1 = Math.min(y1, rb.top);
    x2 = Math.max(x2, rb.right); y2 = Math.max(y2, rb.bottom);
  }
  return { left: x1, top: y1, width: x2 - x1, height: y2 - y1 };
}

// 🪤 Un control a RAS del borde de la ventana se queda SIN anillo en ese lado.
// Las bandas van por FUERA del rect, así que en un elemento de ancho completo
// —`.q-table__middle.q-virtual-scroll` del gestor de informes mide 1280x636 en
// x=0— caen en x=-4 y x=vw+3, y el navegador no dibuja nada fuera de la
// ventana. Medido a 1280, 1440, 1600 y 1920 y en los dos temas: cero píxeles de
// token en izq y der, con la serie hacia adentro en fondo puro. El criterio es
// explícito —una banda ausente, tapada o RECORTADA anula el indicador entero—,
// así que en el lado donde el anillo no cabe se mete HACIA ADENTRO: se recorta
// el rect 4px por ese lado y las dos bandas quedan completas, pisando 4px del
// propio control. Es la misma decisión que el solape con un contenedor
// apretado: antes pisar 4px de cromática que no verse.
function dentroDeLaVentana(r) {
  const B = 4; // el grosor de las dos bandas juntas
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let x1 = r.left;
  let y1 = r.top;
  let x2 = r.left + r.width;
  let y2 = r.top + r.height;
  if (x1 < B) x1 = B;
  if (y1 < B) y1 = B;
  if (x2 > vw - B) x2 = vw - B;
  if (y2 > vh - B) y2 = vh - B;
  return { left: x1, top: y1, width: x2 - x1, height: y2 - y1 };
}

function ocultar() {
  objetivo = null;
  if (raf) { cancelAnimationFrame(raf); raf = 0; }
  if (capa) capa.style.display = "none";
}

function pintar() {
  raf = 0;
  if (!objetivo || !objetivo.isConnected) return ocultar();
  // 🪤 Si el elemento perdió :focus-visible sin disparar focusout (pasa cuando
  // el usuario cambia a ratón sobre el mismo control), el anillo se tiene que
  // ir: se vuelve a preguntar en cada cuadro, no sólo al enfocar.
  try {
    if (
      !objetivo.matches(":focus-visible") &&
      // ... salvo que el foco siga PUESTO en el mismo elemento y la última
      // interacción haya sido una tecla. Esto NO afloja el control del ratón:
      // un `pointerdown` apaga la bandera (y además oculta el anillo), así que
      // el clic sigue sin dibujar nada.
      !(teclado && document.activeElement === objetivo)
    ) {
      return ocultar();
    }
  } catch (e) {
    /* navegador sin :focus-visible: se deja el anillo, que es el lado seguro */
  }
  const caja = cajaDe(objetivo);
  const r = rectUnion(caja);
  if (
    r.width < 1 || r.height < 1 ||
    r.left > window.innerWidth || r.top > window.innerHeight ||
    r.left + r.width < 0 || r.top + r.height < 0
  ) {
    capa.style.display = "none";
    return seguir();
  }
  const rv = dentroDeLaVentana(r);
  if (rv.width < 1 || rv.height < 1) {
    capa.style.display = "none";
    return seguir();
  }
  const cs = getComputedStyle(caja);
  const c = crear();
  c.style.display = "block";
  c.style.transform = `translate(${Math.round(rv.left)}px, ${Math.round(rv.top)}px)`;
  c.style.width = `${Math.round(rv.width)}px`;
  c.style.height = `${Math.round(rv.height)}px`;
  // El anillo sigue la forma del control. Las bandas van por fuera, así que el
  // radio se agranda con ellas para que el arco no se achate.
  c.style.borderRadius = cs.borderRadius === "0px" ? "0px" : cs.borderRadius;
  seguir();
}

// Mientras hay anillo se sigue el rect cuadro a cuadro: el control se mueve con
// el scroll, con una lista virtual que recicla filas, con un diálogo que entra
// con animación y con cualquier relayout. Un listener de `scroll` no cubre los
// dos últimos.
function seguir() {
  if (objetivo && !raf) raf = requestAnimationFrame(pintar);
}

function alEnfocar(ev) {
  const el = ev.target;
  if (!el || el === document.body || !el.matches) return ocultar();
  try {
    if (!el.matches(":focus-visible")) return ocultar();
  } catch (e) {
    /* sin soporte: se marca igual */
  }
  objetivo = el;
  pintar();
}

export default () => {
  if (typeof document === "undefined") return;
  document.addEventListener(
    "keydown",
    () => {
      teclado = true;
    },
    true,
  );
  document.addEventListener(
    "pointerdown",
    () => {
      teclado = false;
    },
    true,
  );
  document.addEventListener("focusin", alEnfocar, true);
  document.addEventListener("focusout", ocultar, true);
  // Un clic de ratón quita :focus-visible en el cuadro siguiente; el bucle de
  // `pintar` lo detecta, pero esto lo hace inmediato y sin un cuadro de anillo
  // espurio.
  document.addEventListener("pointerdown", ocultar, true);
  window.addEventListener("resize", seguir, { passive: true });
};
