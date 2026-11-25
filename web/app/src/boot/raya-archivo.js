import { boot } from "quasar/wrappers";

// 050 (V2-G01, tanda sobre 6f99005): el «—» que marca un dato AUSENTE es interfaz
// y va en Archivo aunque su celda sea una ranura Mono (argumentos de /scripts,
// tablas del inventario, actividad, reconciliación). La tanda midió cientos de
// esos nodos repartidos en muchas plantillas distintas; en vez de ramificar cada
// celda, se marca aquí la hoja cuyo texto ENTERO es la raya. Mismo molde que
// boot/monooptions.js: un MutationObserver que barre una vez por cuadro.
const RAYA = "—";
const CLASE = "obs-raya";

function revisar(el) {
  if (!(el instanceof Element)) return;
  const hojas = el.childElementCount === 0 ? [el] : el.querySelectorAll("*:not(:has(*))");
  for (const h of hojas) {
    const esRaya = h.textContent.trim() === RAYA;
    if (esRaya !== h.classList.contains(CLASE)) h.classList.toggle(CLASE, esRaya);
  }
}

export default boot(() => {
  if (typeof window === "undefined" || !window.MutationObserver) return;
  let pendientes = new Set();
  let agendado = false;
  const barrer = () => {
    agendado = false;
    const lote = pendientes;
    pendientes = new Set();
    lote.forEach((el) => el.isConnected && revisar(el));
  };
  new MutationObserver((registros) => {
    for (const r of registros) {
      const el = r.type === "characterData" ? r.target.parentElement : r.target;
      if (el) pendientes.add(el);
    }
    if (!agendado) {
      agendado = true;
      window.requestAnimationFrame(barrer);
    }
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
});
