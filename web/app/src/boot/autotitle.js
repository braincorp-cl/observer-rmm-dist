import { boot } from "quasar/wrappers";

// 050 (T030, G08): un texto cortado con elipsis tiene que poder leerse completo.
// Los rótulos de campo de Quasar y los .ellipsis (incluido el valor de un q-select)
// llevan el texto entero en title, salvo que ya traigan uno propio. Así se cubren
// los diálogos heredados de la v1 sin tocar cada campo.
const SELECTOR = ".q-field__label, .ellipsis";
const MARCA = "obsAutotitle";

function titular(el) {
  if (el.hasAttribute("title") && !el.dataset[MARCA]) return;
  const texto = (el.textContent || "").replace(/\s+/g, " ").trim();
  if (!texto) {
    if (el.dataset[MARCA]) {
      el.removeAttribute("title");
      delete el.dataset[MARCA];
    }
    return;
  }
  if (el.getAttribute("title") !== texto) {
    el.setAttribute("title", texto);
    el.dataset[MARCA] = "1";
  }
}

export default boot(() => {
  if (typeof window === "undefined" || !window.MutationObserver) return;
  let pendiente = false;
  const barrer = () => {
    pendiente = false;
    document.querySelectorAll(SELECTOR).forEach(titular);
  };
  const programar = () => {
    if (pendiente) return;
    pendiente = true;
    window.requestAnimationFrame(barrer);
  };
  new MutationObserver(programar).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  programar();
});
