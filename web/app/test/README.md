# Pruebas del frontend (web/app)

## Cómo se corre

```bash
npm ci
npm test
```

`npm test` corre las dos suites, en este orden:

| script      | corredor    | archivos            | para qué                                         |
| ----------- | ----------- | ------------------- | ------------------------------------------------ |
| `test:node` | `node:test` | `src/**/*.test.mjs` | la suite de la 051 (`src/utils/coords.test.mjs`) |
| `test`      | vitest      | `test/**/*.spec.js` | todo lo nuevo: componentes y presencia           |

`npm run test:watch` deja vitest en modo vigilancia.

Son dos corredores porque la prueba de coordenadas de la 051 se escribió con
`node:test` cuando el proyecto no tenía ninguno, y migrarla no era parte de
montar el corredor. La extensión es el contrato: **`.spec.js` es vitest,
`.test.mjs` es `node:test`**. Migrarla es un cambio de cinco líneas
(`import { test } from "vitest"`) y deja un solo corredor.

El archivo va nombrado uno por uno en `test:node`, sin glob: `node --test` toma
globs desde Node 21 y recorre directorios hasta Node 20, y el proyecto fija
Node 20.20.2 (`.nvmrc`, los dos workflows) mientras los entornos de desarrollo
suelen traer 22. Una ruta explícita corre igual en las dos.

## Cómo está armado

- `vitest.config.mjs` — config del corredor. Está **aparte de
  `quasar.config.js`** a propósito: `@quasar/app-vite` 1.10.2 trae Vite 2 y
  vitest 2 trae su propio Vite 5 anidado. Los dos conviven: `quasar build`
  sigue usando el Vite 2 de la raíz.
- `test/setup/quasar.js` — registra los 122 componentes y las 11 directivas de
  Quasar en todos los montajes de `@vue/test-utils`. En el build real eso lo
  hace `@quasar/vite-plugin` reescribiendo las plantillas; acá se usa el otro
  modo de instalación que Quasar admite (`opts.components` / `opts.directives`).
- `test/support/` — helpers de montaje y de lectura del árbol de `.vue`.

Las versiones están elegidas contra lo que el proyecto ya usa, no contra el
último release de cada cosa: `@vitejs/plugin-vue` va clavado en **2.3.4**, que
es la que `@quasar/app-vite` 1.10.2 ya resuelve en la raíz. Pedir la 5.x rompe
el `peerDependency` de Vite 2 y npm rechaza el árbol entero.

## Qué hay cubierto

- `test/components/agent-table-hostname.spec.js` — la celda del hostname de la
  flota como control de teclado (hallazgo #1 de `AUDITORIA-A11Y.md`, arreglado
  en 05222b0) y la ventana de 250 ms del clic/doble clic (046 F4 / RN-03).
  Monta `AgentTable.vue` con el `QTable` de verdad y actúa sobre el DOM.
- `test/components/agent-table-overdue-alert.spec.js` — el `$q.notify` de
  `overdueAlert` sin `textColor` (hallazgo #1 de `AUDITORIA-COLOR.md`).
- `test/components/script-manager-nombre-largo.spec.js` — la regla de
  aceptación G08 en la página /scripts: un script de nombre largo se recorta por
  CSS y el valor entero queda en `title`. Falla si alguien vuelve al recorte por
  JavaScript (`truncateText`), que deja el texto cortado en el DOM y con eso
  inutiliza también a `src/boot/autotitle.js`.
- `test/styles/q-tooltip-bg-white.spec.js` — prueba de presencia: ningún
  `<q-tooltip>` nuevo con `bg-white` (hallazgo #3 de `AUDITORIA-COLOR.md`,
  **todavía sin arreglar**: 78 etiquetas en 74 archivos, inventariadas en
  `q-tooltip-bg-white.baseline.json`).

## Qué NO se puede probar acá

- **Contraste de color real.** Medir que un aviso o un tooltip cumpla AA exige
  compilar `css/app.sass`, resolver el cascade (los `!important` de Quasar
  contra los overrides por tema) y leer el color calculado. jsdom no calcula
  cascade ni color computado. Lo que sí se prueba es la **causa** en el código:
  que no se manden `textColor` ni clases de color crudas. La medición vive en
  las auditorías (`git show 9f419ad:AUDITORIA-COLOR.md`) y necesitaría un
  navegador de verdad.
- **La tecla Menú / Shift+F10.** Que el navegador traduzca esa tecla a un
  evento `contextmenu` sobre el elemento enfocado es del navegador, no del
  componente. Lo que sí se prueba es que el `contextmenu` burbujee desde el
  `<div>` enfocable hasta el `@contextmenu` del `<q-tr>`.
- **Lo que pasa después de `$router.push`.** El espacio de trabajo del equipo
  carga datos del backend. Las pruebas verifican que se navega con la ruta y
  los parámetros correctos; montar la vista destino pediría API.
- **El foco visible.** Es el hallazgo #3 de `AUDITORIA-A11Y.md` y vive en CSS
  (`outline` / `box-shadow`): mismo problema que el contraste.
