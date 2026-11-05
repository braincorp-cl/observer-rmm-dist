/* eslint-env node */

// Corredor de pruebas del frontend v2.
//
// Por qué un archivo aparte de quasar.config.js: @quasar/app-vite 1.10.2 lleva
// Vite 2 y vitest 2 lleva su propio Vite 5 anidado (node_modules/vitest/
// node_modules/vite). Son dos Vite distintos y conviven sin pisarse: el build
// (`quasar build`) sigue usando el Vite 2 de la raíz y las pruebas usan el 5.
// Por eso aquí NO se usa quasar.config.js ni @quasar/vite-plugin: se replica a
// mano lo poco que las pruebas necesitan de ese plugin (el alias `@`, los
// `define` de __QUASAR_*, y Quasar instalado a mano en test/setup/quasar.js).
//
// @vitejs/plugin-vue va clavado en 2.3.4 —no en la última— porque es la versión
// que @quasar/app-vite 1.10.2 ya resuelve en la raíz: pedir la 5.x rompe el
// `peerDependency` de Vite 2 y npm rechaza el árbol entero.

import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

const resolveSrc = (p) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: [
      { find: /^@\//, replacement: resolveSrc("./src") + "/" },
      { find: /^src\//, replacement: resolveSrc("./src") + "/" },
      // Quasar publica la condición "node" apuntando al bundle de SSR
      // (dist/quasar.server.prod.js), que no monta componentes. vitest resuelve
      // las dependencias con esa condición, así que se fija el bundle de
      // cliente a mano. Es `^quasar$` exacto para no tocar `quasar/lang/es`,
      // `quasar/wrappers` ni `quasar/src/...`.
      { find: /^quasar$/, replacement: "quasar/dist/quasar.client.js" },
    ],
  },
  define: {
    // Los inyecta @quasar/vite-plugin en el build real; el código fuente de
    // Quasar (quasar/dist/quasar.client.js) los referencia.
    __QUASAR_SSR__: false,
    __QUASAR_SSR_SERVER__: false,
    __QUASAR_SSR_CLIENT__: false,
    __QUASAR_SSR_PWA__: false,
  },
  test: {
    // `test/**` es de vitest. El `src/utils/coords.test.mjs` de la 051 corre
    // con node:test y lo lanza el script `test:node` de package.json, así que
    // se deja fuera a propósito: la extensión es el contrato (.spec.js vitest,
    // .test.mjs node:test).
    include: ["test/**/*.spec.js", "src/**/*.spec.js"],
    environment: "jsdom",
    globals: false,
    setupFiles: ["./test/setup/quasar.js"],
    restoreMocks: true,
    server: {
      deps: {
        // Quasar se publica con condición "node" apuntando al bundle de SSR
        // (dist/quasar.server.prod.js). Si vitest lo externaliza, Node resuelve
        // esa condición y los componentes no montan. Inline fuerza que pase por
        // Vite, que con environment jsdom usa la condición "import" (cliente).
        inline: ["quasar", /^@quasar\//],
      },
    },
  },
});
