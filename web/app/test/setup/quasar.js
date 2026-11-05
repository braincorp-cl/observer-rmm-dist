/* eslint-env node */

// Instala Quasar en todos los montajes de @vue/test-utils.
//
// En el build real, @quasar/vite-plugin reescribe las plantillas para importar
// cada componente de Quasar que se usa (<q-table> → import QTable). Las pruebas
// no usan ese plugin (ver el comentario de vitest.config.mjs), así que acá se
// registran los componentes y las directivas de forma global, que es el otro
// modo de instalación que Quasar admite: install-quasar.js lee opts.components
// y opts.directives y registra cada uno por su `name`.

// Las pruebas de presencia corren con `environment: node` (no necesitan DOM) y
// el bundle de cliente de Quasar toca `window` al cargarse, así que el import
// va adentro del guard, no arriba.
if (typeof window !== "undefined") {
  const { config } = await import("@vue/test-utils");
  const allQuasar = await import("quasar");
  const { Quasar, Dialog, Loading, Notify } = allQuasar;

  // Componentes: todo lo exportado como QAlgo (QTable, QTr, QTd, QTooltip…).
  const components = Object.fromEntries(
    Object.entries(allQuasar).filter(
      ([name, value]) =>
        /^Q[A-Z]/.test(name) &&
        value !== null &&
        typeof value === "object" &&
        typeof value.name === "string",
    ),
  );

  // Directivas: lo exportado en PascalCase que no es componente ni plugin y
  // trae hooks de directiva (ClosePopup, Ripple, Intersection…). Vue resuelve
  // `v-close-popup` contra la clave `ClosePopup`, así que el nombre alcanza.
  const directives = Object.fromEntries(
    Object.entries(allQuasar).filter(
      ([name, value]) =>
        /^[A-Z]/.test(name) &&
        !/^Q[A-Z]/.test(name) &&
        value !== null &&
        typeof value === "object" &&
        typeof value.name === "string" &&
        typeof value.install !== "function" &&
        (typeof value.mounted === "function" ||
          typeof value.beforeMount === "function" ||
          typeof value.created === "function"),
    ),
  );

  config.global.plugins.push([
    Quasar,
    {
      components,
      directives,
      // Los tres que el árbol de la flota usa por $q: loading.show/hide en el
      // doble clic, notify en overdueAlert y dialog en editar equipo.
      plugins: { Dialog, Loading, Notify },
    },
  ]);
}
