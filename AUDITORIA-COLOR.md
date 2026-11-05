# Auditoría de color — webUI v2 (`web/app/src`)

**Rama:** `v2/auditoria-color` (desde `release/v2`) · **HEAD auditado:** `fb59a20` · **Fecha:** 2026-11-05
**Alcance:** los 190 `.vue` y 71 `.ts/.js` bajo `web/app/src`, incluidos `ee/`, `core/`, `views/`, `layouts/`.
**Tipo de trabajo:** solo análisis. No se modificó ningún archivo de `src`.

## La regla que se audita

No hay un documento de regla en `docs/`; la regla vive en los comentarios de la hoja de tema:

- `web/app/src/css/quasar.variables.sass` es la única fuente de hex («ningún hex vive fuera de este archivo»).
- `web/app/src/css/app.sass` expone esos valores como `--obs-*` y reajusta `--q-*` por tema
  (`body.body--dark` / `body.body--light`) para que marca y texto-sobre-marca pasen AA.
- Los componentes usan `var(--obs-*)` / `var(--q-*)`; nunca hex sueltos (UI-D02).
- El teal (`primary`) es acción o navegación. Un dato o un estado va en su token semántico
  (`--q-positive/negative/warning/info`, `.obs-chip-neutral`, `.obs-icon-neutral`) — V2-G05, UI-D05.

Los ratios de contraste de este informe se calcularon con la fórmula WCAG 2.1 de luminancia
relativa sobre los valores reales que resuelve la cascada (ver «Cómo se verificó»).

---

## Hallazgos, de mayor a menor gravedad

| # | archivo:línea | qué encontré | forma | arreglo propuesto (una línea) |
|---|---|---|---|---|
| 1 | `components/AgentTable.vue:599` | `$q.notify({ color: positive\|info, textColor: "black" })`. `app.sass:327` remapea `.text-black` a `var(--obs-text)`, así que el texto del aviso sale del color de **texto de página** sobre un fondo de **marca**. Claro: `#16202E` sobre `#157A43` = **3,04:1**; sobre `#3F5FD1` = **2,94:1**. Oscuro: `#E6EDF5` sobre `#3ED184` = **1,67:1**; sobre `#6C8CFF` = **2,60:1**. Falla en los cuatro casos | c | borrar la línea `textColor: "black"`: el `text-white` por defecto de Notify ya lo recogen `app.sass:402` (claro) y `app.sass:113-116` (oscuro) hacia `--obs-on-brand` → 5,39–8,41:1 |
| 2 | `components/scripts/ScriptFormModal.vue:25` | `class="text-black bg-warning"` en el `q-banner` del aviso de shebang. Mismo cruce que #1: fondo `var(--q-warning)`, texto `var(--obs-text)`. Claro: `#16202E` sobre `#8A5A00` = **2,77:1**. Oscuro: `#E6EDF5` sobre `#FFC15E` = **1,36:1** | c | cambiar `text-black` por `obs-banner-warn`, la clase que ya usa `layouts/MainLayout.vue:20` para este mismo banner (`--obs-on-brand`) → 5,93:1 claro / 10,29:1 oscuro |
| 3 | **77 tooltips en 74 archivos**, p. ej. `components/AlertsManager.vue:163`, `components/modals/agents/RunScript.vue:20`, `components/modals/agents/RunScript.vue:31`, `ee/reporting/components/ReportsManager.vue:15` | `<q-tooltip class="bg-white text-primary">`. `bg-white` es `background:#fff !important` de Quasar y le gana al `.q-tooltip{background:var(--obs-raised)}` de `app.sass:482` (sin `!important`); `app.sass:488` ya neutralizó el texto a `var(--obs-text) !important`. Resultado en **oscuro**: `#E6EDF5` sobre `#FFFFFF` = **1,18:1**, tooltip invisible. En claro (`#16202E` sobre `#FFFFFF`) queda bien. El arreglo de la ola 6 corrigió el texto y dejó el fondo | a | borrar `bg-white text-primary` del `class` (ambas ya son redundantes): el tooltip cae en el `.q-tooltip` tematizado de `app.sass:482` |
| 4 | `core/dashboard/ui/ObserverTable.vue:105` y `:110` | `.column-bgcolor-dark td:last-child{background-color:#1d1d1d}` y `.column-bgcolor td:last-child{background-color:#ffffff}` para la columna fija. Ninguno de los dos está en la paleta 1c: `#1d1d1d` contra `--obs-surface` oscuro (`#131F31`) da **1,02:1** de diferencia de luminancia, o sea un bloque negro pegado a la superficie navy. Es el componente de tabla compartido de v2 (`ScriptManager`, `core/settings/ScheduleTable`) | a | las dos reglas a `background-color: var(--obs-surface)` y borrar el reparto claro/oscuro de `:9-10` (una sola clase) |
| 5 | `components/agents/workspace/ContextColumn.vue:84` | `<span class="obs-ctx__dot obs-ctx__dot--{ok\|fail\|overdue\|offline}" />`: punto de 8 px, sin borde, sin fondo, sin texto, sin `title`, sin `aria-label` y sin tooltip, dentro de un `q-item clickable`. Es el único indicador de salud por equipo de la columna de contexto y lo único que lo distingue es el color. Además `--offline` **no tiene regla CSS** (`:238-243` define solo `--ok/--fail/--overdue`), así que «desconectado» cae al `--obs-faint` base, idéntico a «sin estado», y contradice `AgentHeader.vue:375`, que pinta desconectado con `var(--q-warning)` | d | añadir `:aria-label`/`:title` con el estado traducido —como hace `AgentHeader.vue:38` con `{{ statusText }}`— y definir `.obs-ctx__dot--offline` con `var(--q-warning)` |
| 6 | `components/agents/WinUpdateTab.vue:132` y `:139` | columna «política»: **el mismo glifo** `fas fa-check` para «aprobar» (`color="info"`, azul) y para «ignorar» (`dash_negative_color`, rojo). Para quien no distingue el rojo del azul son dos tildes idénticas con significado opuesto; el color es el rótulo. La columna de al lado (`:155-179`) ya lo hace bien, con cuatro glifos distintos | d | dar a «ignorar» un glifo propio, `name="fas fa-ban"`, el mismo que ya usa esa columna vecina en `:169` |
| 7 | `components/agents/WinUpdateTab.vue:126` y `:146` | mismo patrón en la misma columna: `fiber_manual_record` para «no hacer nada» (sin color) y para «heredar» (`color="accent"`). Dos puntos idénticos, el color es la única diferencia | d | glifo propio para «heredar», p. ej. `name="fas fa-level-up-alt"` |
| 8 | `components/agents/CommandStream.vue:98`, `:99`, `:103` | consola de comando en vivo con `background:#191818`, `color:#fff`, `border:1px solid #ccc`. Nunca sigue al tema claro, y ese `#ccc` sobre un fondo claro queda en 1,6:1 | a | `var(--obs-deep)`, `var(--obs-on-dark)` y `var(--obs-border)` |
| 9 | `components/graphs/CheckGraph.vue:85`, `:201`, `:205`, `:207`, `:208`, `:220`, `:224`, `:226`, `:227` | apexcharts con `#027BE3` (el azul por defecto de Quasar, previo al rebranding), umbral de error `#C10015`, umbral de aviso `#ff9800` y texto `#FFF`. Ninguno es 1c y ninguno cambia con el tema | a | leerlos de `--q-primary`/`--q-negative`/`--q-warning`/`--obs-on-brand` con `getComputedStyle(document.body).getPropertyValue(...)`, el patrón que ya usan `AgentLocationDialog.vue:230` y `LostCaseTimelineDialog.vue:441` |
| 10 | `components/agents/remotebg/RegistryManager.vue:1060`, `:1061`, `:1065`, `:1068`, `:1080` | `.cell-hover` con `background:#e0e0e0`, `color:#000000`, `border:1px solid #ccc`, `box-shadow: … rgba(0,0,0,0.15)`; `.folder-path` con `border:1px solid #ccc`. Es un globo claro clavado dentro del tema oscuro | a | `var(--obs-raised)`, `var(--obs-text)`, `var(--obs-border)` y `var(--obs-shadow-1)` |
| 11 | `components/scripts/ScriptManager.vue:491` y `:848` | `:style="{ color: props.node.hidden ? 'grey' : '' }"` sobre el **nombre** del script. `grey` de CSS es `#808080`: claro, sobre `--obs-surface` `#FFFFFF` = **3,95:1**; oscuro, sobre `#131F31` = **4,19:1**. Falla AA 4,5:1 en los dos temas (`:491` además es `text-weight-bold` a 14 px, que sigue contando como texto normal) | c | cambiar el `:style` por un `:class` que alterne `obs-text-muted` (`app.sass:492` → `--obs-muted`): `#52647A` sobre `#FFFFFF` = 6,06:1 |
| 12 | `components/agents/remotebg/RegistryManager.vue:14` y `:44` | `text-blue-5` (`#42a5f5`) y `text-yellow-7` (`#fdd835`). Son clases de paleta de Quasar que `app.sass:323-330` **no** remapea (sí remapea `text-grey-6/-7/-9`, `text-black`, `bg-grey-3`). Sobre `--obs-surface` claro: **2,65:1** y **1,40:1**, por debajo del mínimo de 3:1 de contraste no textual para un ícono con significado | a | `class="obs-icon-neutral"` en los dos |
| 13 | `components/modals/coresettings/EditCoreSettings.vue:1455`, `components/modals/alerts/AlertTemplateRelated.vue:89`, `components/automation/modals/RelationsView.vue:161` | `thumbStyle: { backgroundColor: "#027be3" }` en tres barras de scroll. Otra vez el azul previo al rebranding; el primario 1c es `#0A7186` claro / `#14A5C0` oscuro | a | `backgroundColor: "var(--q-primary)"` (las variables CSS funcionan en objetos de estilo inline) |
| 14 | `components/agents/DiskEncryptionDetail.vue:76` | `<q-badge color="primary">` en la columna `is_system_volume`. Es un dato, no una acción, y la columna hermana del mismo archivo ya resuelve bien con positive/negative/grey (`protectionColor()`, `:308`) | b | `class="obs-chip-neutral"` y quitar `color="primary"` |
| 15 | `components/tasks/AutomatedTaskForm.vue:284` | `color="primary"` en el ícono de tipo de shell (Windows/PowerShell). Es un dato; el ícono `terminal` de al lado (`:275`) ya hereda sin color. `.obs-icon-neutral` existe para exactamente esto (`app.sass:119`: «Ícono de dato o de control sin estado (SO, tipo de equipo…): V2-G05») | b | reemplazar `color="primary"` por `class="obs-icon-neutral"` |
| 16 | `components/scripts/AiScriptPromptModal.vue:24` | `<q-chip outline color="primary" :label="shellLabel">` es una insignia de dato (qué shell). Los chips de ejemplo de `:52` sí son `clickable`, ahí el teal corresponde | b | `class="obs-chip-neutral"` y quitar `color="primary"` |
| 17 | `App.vue:98` | `.agent-overdue { background: red !important }`. `red` es `#FF0000`, que no es `--q-negative` en ningún tema, usado como color de **estado** de fila | a | borrar la regla (ver nota de código muerto) o `background: var(--q-negative)` |
| 18 | `App.vue:95` | `.agent-offline { background: gray !important }`, mismo caso con un gris nombrado | a | borrar la regla o `background: var(--obs-muted)` |
| 19 | `App.vue:92` | `.action-completed { background-color: $positive }` usa el literal Sass `#22B364` en vez del token por tema, así que ignora el `#157A43` del tema claro | a | `background-color: var(--q-positive)` |
| 20 | `App.vue:80` | `.bg-dark { background-color: --q-page-dark }` — falta el `var()`, el valor es inválido y el navegador descarta la declaración; manda el `.bg-dark{background:var(--q-dark)!important}` de Quasar. Es una referencia a token escrita mal, que no hace nada | a | borrar la regla (no aporta) o escribirla `var(--obs-page)` |
| 21 | `utils/format.ts:281`, `:282`, `:284`, `:285`, `:287`, `:288`, `:290`, `:291` | `formatScriptSyntax()` genera `style="color:#d4d4d4\|#ffd70a\|#87cefa\|#c586b6"` inline. Sobre `--obs-surface` claro: 1,48:1 / 1,40:1 / 1,72:1 / 2,82:1 | a | borrar la función (ver nota de código muerto) |
| 22 | `components/agents/ConfirmWipeOrderDialog.vue:189` | `border-bottom: 1px solid rgba(128, 128, 128, 0.2)` escrito a mano | a | `border-bottom: 1px solid var(--obs-border)` |
| 23 | `components/ui/WinUpdateDialog.vue:65` | `$q.dark.isActive ? "text-white" : "text-primary"` decide el color del enlace en JS, pero `--q-primary` ya es por tema y pasa AA en los dos (`#14A5C0` sobre `#131F31` = 5,66:1; `#0A7186` sobre `#FFFFFF` = 5,65:1). La rama oscura además deja el enlace del mismo color que el texto normal | a | dejar `text-primary` fijo y borrar el `computed` |
| 24 | `views/LoginView.vue:157`, `:158`, `:159` | `linear-gradient(90deg, rgba(20,20,29,1), rgba(38,42,56,1), rgba(15,18,20,1))` a mano. La pantalla de login es deliberadamente igual en los dos temas, así que **no** es un defecto visible; es la letra de la regla («ningún hex fuera de `quasar.variables.sass`») | a | si se quiere cerrar: `$obs-login-gradient` en `quasar.variables.sass` y `--obs-login-gradient` en `app.sass`, como ya se hizo con `$obs-paper` |

### Código muerto entre los hallazgos

Tres hallazgos no se ven hoy en pantalla, y aun así los dejo en la tabla porque son
precisamente lo que vuelve en cada merge desde `main`:

- `App.vue:92` (`.action-completed`): ninguna plantilla la usa.
- `App.vue:95` y `:98` (`.agent-offline` / `.agent-overdue`): su único productor es
  `AgentTable.vue:610 agentClass()`, que no se referencia en ninguna plantilla del repo.
- `utils/format.ts:277` (`formatScriptSyntax`): sin ningún llamador en todo `web/`.

---

## Revisado y limpio (para que no se vuelva a buscar acá)

Esto lo miré y **no** es hallazgo. Lo anoto porque varios casos parecen violaciones hasta que se
sigue la cascada:

- **`q-tabs`, lo que se preguntaba explícitamente en (c): pasan en tema claro.** Los siete usos
  (`SubTableTabs.vue:6`, `automation/AutomationManager.vue:539`, `modals/alerts/AlertTemplateRelated.vue:14`,
  `modals/agents/EditAgent.vue:6`, `modals/coresettings/EditCoreSettings.vue:21`,
  `modals/coresettings/URLActionsForm.vue:73`, `views/RemoteBackground.vue:3`) usan `class="text-grey"`
  u `obs-text-muted`, y `app.sass:480` redirige `.text-grey` a `var(--obs-muted)`: `#52647A` sobre
  `#FFFFFF` = **6,06:1** inactivas, y `active-color="primary"` da `#0A7186` sobre `#FFFFFF` = **5,65:1**
  activas. **No encontré ninguna `q-tabs` ilegible en tema claro.**
- **Clases de paleta de Quasar ya neutralizadas por `app.sass:323-330`:** `bg-grey-3 text-black`
  (`DiskEncryptionDetail.vue:31`, `:53`), `bg-grey-3 text-grey-9` (`AgentLocationDialog.vue:46`, `:57`)
  y los cinco `text-grey-6` (`EditCoreSettings.vue:834`, `WipeOrderDialog.vue:81`,
  `AiScriptPromptModal.vue:20`, `:49`, `:66`). Resuelven a tokens y dan 8,66:1 / 18,10:1 / 6,06:1.
  Violan la letra de la regla pero están cubiertas por un override global; no las conté.
- **Los ~40 `class="text-primary"` sobre `<span style="cursor:pointer;text-decoration:underline">`**
  (`ChecksTab.vue:398`, `:408`, `:423`, `:432`, `HistoryTab.vue:48`, `AlertsManager.vue:351`, `:364`,
  `AutomatedTasksTab.vue:341`, `WinUpdateTab.vue:198`, `EventLogManager.vue:97`…): son navegación,
  que es el uso correcto del teal. No son (b).
- **`ActionBar.vue:273`** (`.obs-actionbar__btn.bg-primary`): botón de acción, y resuelve el texto con
  `--obs-on-brand`. Correcto.
- **Íconos de severidad en celdas de tabla** (`AgentTable.vue:220`, `ChecksTab.vue:370`, `:378`,
  `AutomatedTasksTab.vue:299`, `:307`, `PolicyStatus.vue:74`, `:82`, `ReportHistoryTable.vue:203`,
  `DebugLog.vue:113`): todos llevan `q-tooltip` y/o `aria-label`, y `ReportHistoryTable` además un
  `q-btn` con borde. No son (d).
- **Punto de estado de `AgentHeader.vue:38`:** va acompañado de `{{ statusText }}`. No es (d).
- **Columna «instalado» de `WinUpdateTab.vue:155-179`:** cuatro estados, cuatro glifos distintos
  (`check` / `tasks` / `ban` / `exclamation`). Es el contraejemplo correcto del hallazgo #6.
- **`DialogWrapper.vue:12`:** usa `content-class="bg-white text-primary"`, y `content-class` no es
  prop de `QTooltip` en Quasar 2, así que no hace nada. Es el único de los 78 que no está afectado
  por el hallazgo #3 — queda como atributo HTML inerte.
- **`dash_info_color` / `dash_positive_color` / `dash_negative_color` / `dash_warning_color`**
  (`store/index.js:36-39`): por defecto valen `"info"`/`"positive"`/`"negative"`/`"warning"`, o sea
  tokens semánticos. No son violaciones.
- **`$q.notify` / `$q.dialog` con `color: "primary"`** (p. ej. `InstallAgent.vue:308`, `:311`): son
  botones y avisos de acción.
- **`App.vue:85` y `:88`** (`.highlight` / `.highlight-dark`): hoy los dos valen `var(--obs-selected)`.
  Redundancia a limpiar, no un defecto de color.

---

## Cómo se verificó

Para no reportar «se ve mal», cada ratio sale de resolver la cascada real y no de mirar el `.vue`:

1. Se descargó `quasar@2.18.5` (la versión exacta de `web/app/package.json:31`) y se extrajeron de
   `dist/quasar.css` las declaraciones que compiten:
   `.bg-white → background:#fff !important`, `.text-black → color:#000 !important`,
   `.text-primary → color:var(--q-primary) !important`, `.bg-warning → background:var(--q-warning) !important`,
   `.text-grey-6 → #9e9e9e !important`, `.text-yellow-7 → #fdd835 !important`,
   `.text-blue-5 → #42a5f5 !important`, `.q-tooltip--style → background:#757575`,
   `.q-layout__section--marginal → background-color:var(--q-primary); color:#fff`.
2. Se cruzaron con los overrides de `app.sass` (especificidad y orden de carga: `app.sass` va después
   del bundle de Quasar, así que un empate lo gana `app.sass`) y con los valores por tema de
   `body--dark` / `body--light`.
3. El par resultante se pasó por la fórmula WCAG 2.1 (luminancia relativa, umbral AA 4,5:1 para texto
   normal y 3:1 para gráficos con significado).

Dos ejemplos de por qué importó el paso 1: el hallazgo #3 **parece** un problema de tema claro y en
realidad el tema claro está bien y el que se rompe es el oscuro; y los cinco `text-grey-6` **parecen**
fallar con 2,68:1 y no fallan, porque `app.sass:329` los remapea.

Umbral usado: AA 4,5:1 para texto normal. Para íconos cito 3:1 (WCAG 1.4.11, contraste no textual) y
lo digo explícito en el hallazgo, para no mezclarlo con el umbral de texto.

---

## Qué elegí NO hacer, y por qué

- **No toqué `src/`.** Es una auditoría; cada hallazgo trae el arreglo en una línea y nada más. Los 24
  arreglos caben en un commit por familia, pero ese commit no es de esta tarea.
- **No corrí lint ni tests.** `web/app/node_modules` no está instalado en este contenedor, así que no
  hay una línea base con la que comparar y cualquier fallo que reportara sería ruido. No sé si hay
  fallos preexistentes de lint o de tests en el front: **no los verifiqué y no afirmo nada sobre
  ellos**. Lo único que instalé fue `quasar@2.18.5` en el directorio temporal de la sesión, fuera del
  repo, solo para leer su CSS; no quedó nada en el árbol de trabajo.
- **No arreglé los 77 tooltips con un `sed`.** Es un cambio de una línea por archivo en 74 archivos y
  sale limpio, pero toca casi todo `components/` y chocaría de frente con las otras tres sesiones que
  trabajan en ramas hermanas. Va como un hallazgo con su receta, y conviene hacerlo solo cuando las
  ramas estén fusionadas.
- **No conté como hallazgos las clases de paleta ya neutralizadas** por `app.sass:323-330`
  (`bg-grey-3`, `text-black`, `text-grey-6/-7/-9`). Inflarían el informe con 11 filas que no se ven en
  pantalla. Están listadas aparte, en «Revisado y limpio», con su ratio.
- **No propuse un lint de color** (regla ESLint o stylelint que prohíba hex en `.vue`), que es el
  arreglo de raíz para que esta familia deje de volver en cada merge desde `main`. Es un cambio de
  configuración del build y no estaba en el encargo; lo dejo apuntado como la recomendación de fondo.
- **No audité `web/app/src/css/`** como fuente de violaciones: por diseño es el único lugar donde los
  hex viven. Lo leí completo, pero para resolver la cascada, no para buscar defectos ahí.
- **No revisé `api/`, `mcp/`, `docs-site/` ni `roles/`.** El encargo decía `web/app/src`.
- **No reporté como (c) el hallazgo #3 aunque es el peor contraste del informe** (1,18:1). Falla en
  tema oscuro y (c) pedía tema claro, así que va como (a) —un literal `#fff` donde debía ir un token—
  y digo el tema explícitamente. La forma (c), tema claro, tiene dos casos reales: #1 y #2, más #11
  que falla en ambos temas.
