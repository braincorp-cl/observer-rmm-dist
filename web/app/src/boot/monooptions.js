import { boot } from "quasar/wrappers";

// 050 (ola 6, G01): un select cuyo valor va en Mono (obs-mono-values, o el de filas
// por página de una tabla) abre su menú teletransportado fuera del campo, así que
// la regla del campo no alcanza a sus opciones. QSelect liga el control con su
// listbox por aria-controls; se marca ese listbox para que sus opciones hereden Mono.
const SELECTOR =
  ".obs-mono-values [aria-controls], .q-table__bottom .q-select [aria-controls]";
const CLASE = "obs-mono-options";

// Lotes 5809d7e (G01): una opción escrita con palabras («Todas», «All» del paginador)
// no es un conteo y va en Archivo (aclaración 2026-10-27); la marca obs-ui-text la
// saca de la regla Mono, en el menú y en el valor mostrado del paginador.
const esPalabra = (el) => !/^\s*\d/.test(el.textContent || "");

function palabras(raiz, selector) {
  raiz.querySelectorAll(selector).forEach((el) => {
    const p = esPalabra(el);
    if (el.classList.contains("obs-ui-text") !== p) el.classList.toggle("obs-ui-text", p);
  });
}

function marcar(control) {
  const id = control.getAttribute("aria-controls");
  if (!id) return;
  const lista = document.getElementById(id);
  if (lista && !lista.classList.contains(CLASE)) lista.classList.add(CLASE);
  if (lista) palabras(lista, ".q-item__label");
  const campo = control.closest(".q-table__bottom .q-select");
  if (campo) palabras(campo, ".q-field__native > span");
}

export default boot(() => {
  if (typeof window === "undefined" || !window.MutationObserver) return;
  let pendiente = false;
  const barrer = () => {
    pendiente = false;
    document.querySelectorAll(SELECTOR).forEach(marcar);
  };
  new MutationObserver(() => {
    if (pendiente) return;
    pendiente = true;
    window.requestAnimationFrame(barrer);
  }).observe(document.documentElement, { childList: true, subtree: true });
});
