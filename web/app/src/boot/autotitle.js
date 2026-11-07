import { boot } from "quasar/wrappers";

// 050 (T030, G08): un texto cortado con elipsis tiene que poder leerse completo.
// Los rótulos de campo de Quasar y los .ellipsis (incluido el valor de un q-select)
// llevan el texto entero en title, salvo que ya traigan uno propio. Así se cubren
// los diálogos heredados de la v1 sin tocar cada campo.
const SELECTOR = ".q-field__label, .ellipsis, .q-field__messages > div";
const MARCA = "obsAutotitle";

// 🔑 050 (G08, 13.ª corrida): este boot lee el DOM, asi que SOLO repara el
// recorte por CSS. Un texto cortado en JS llega al DOM ya sin cola y lo unico
// que puede copiar es el recorte; el valor completo tiene que venir del dato,
// en un `title` propio. Una salvaguarda que lee el DOM no repara un corte hecho
// antes del DOM, y el diagnostico estaba escrito desde antes en el encabezado
// de `test/components/script-manager-nombre-largo.spec.js` — sin que eso
// cubriera los 15 sitios que seguian recortando en JS.
function titular(el) {
  if (el.hasAttribute("title") && !el.dataset[MARCA]) return;
  const texto = (el.textContent || "").replace(/\s+/g, " ").trim();
  // 🪤 El vaciado va PRIMERO: con `texto` vacio, la guarda de abajo veria
  // cualquier title como «mas largo» y dejaria puesto un title rancio.
  if (!texto) {
    if (el.dataset[MARCA]) {
      el.removeAttribute("title");
      delete el.dataset[MARCA];
    }
    return;
  }
  // 🔴 Y si alguien pone despues un title propio MAS LARGO que lo visible, ese
  // title es el canal bueno: pisarlo con el texto visible seria APAGAR el unico
  // modo de leer el dato entero.
  const propio = el.getAttribute("title");
  if (propio && propio.length > texto.length) {
    delete el.dataset[MARCA];
    return;
  }
  if (el.getAttribute("title") !== texto) {
    el.setAttribute("title", texto);
    el.dataset[MARCA] = "1";
  }
}

// 🪤 Un solo observador por documento. Antes cada llamada a `boot()` dejaba
// otro MutationObserver vivo sobre `documentElement`, sin forma de pararlo: en
// la pagina da trabajo duplicado y en los tests el callback sigue disparando
// despues de que el entorno se destruyo («window is not defined»). Se devuelve
// el observador para poder desconectarlo.
let observador = null;
let pendiente = false;

function barrer() {
  pendiente = false;
  document.querySelectorAll(SELECTOR).forEach(titular);
}

function programar() {
  if (pendiente) return;
  pendiente = true;
  window.requestAnimationFrame(barrer);
}

export function detener() {
  if (!observador) return;
  observador.disconnect();
  observador = null;
  pendiente = false;
}

export default boot(() => {
  if (typeof window === "undefined" || !window.MutationObserver) return null;
  if (!observador) {
    observador = new MutationObserver(programar);
    observador.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }
  programar();
  return observador;
});
