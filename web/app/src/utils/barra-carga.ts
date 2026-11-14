// Color de la barra de carga (V2-G02).
//
// POR QUE EXISTE ESTE MODULO
//
// El rojo de fabrica de Quasar para `LoadingBar` es #f44336: no es ningun token
// del proyecto y, peor, es un color de ESTADO usado para senalar ACTIVIDAD.
// G05 reserva rojo, ambar y verde para estado, asi que la barra va en
// `secondary` (neutro: actividad, ni estado ni accion).
//
// 🪤 El remapeo vivia SUELTO dentro de `store/index.js`, y por eso el arreglo
// no llegaba a las ventanas remotas: `RemoteWindowChrome.vue` arranca su propio
// tema con `fetchDashboardInfo()` y aplicaba `loading_bar_color` CRUDO. Medido
// el 2026-11-13 sobre 343b6a8: `q-loading-bar--top bg-red` = rgb(244,67,54) en
// rem-webterm y rem-webvnc, 2 temas x 2 anchos, 8 de 32 bloques. Un remapeo que
// vive en UN consumidor no es un remapeo: es una excepcion local. Aqui queda en
// un solo lugar y los dos consumidores lo llaman.
export function colorDeBarraDeCarga(crudo?: string | null): string {
  return !crudo || crudo === "red" ? "secondary" : crudo;
}
