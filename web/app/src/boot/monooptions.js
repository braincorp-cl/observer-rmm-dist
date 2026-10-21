import { boot } from "quasar/wrappers";

// 050 (ola 6, G01): un select cuyo valor va en Mono (obs-mono-values, o el de filas
// por página de una tabla) abre su menú teletransportado fuera del campo, así que
// la regla del campo no alcanza a sus opciones. QSelect liga el control con su
// listbox por aria-controls; se marca ese listbox para que sus opciones hereden Mono.
const SELECTOR =
  ".obs-mono-values [aria-controls], .q-table__bottom .q-select [aria-controls]";
const CLASE = "obs-mono-options";

function marcar(control) {
  const id = control.getAttribute("aria-controls");
  if (!id) return;
  const lista = document.getElementById(id);
  if (lista && !lista.classList.contains(CLASE)) lista.classList.add(CLASE);
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
