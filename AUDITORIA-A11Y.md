# Auditoría de operación por teclado — WebUI v2

**Alcance:** todo `web/app/src` (190 `.vue`, 39 `.ts`, 32 `.js`, ~60.600 líneas) + `src/css/app.sass` y
`src/css/quasar.variables.sass`.
**Fecha:** 2026-11-05 · **Rama:** `v2/auditoria-a11y` · **Base:** `fb59a20`
**Pregunta:** ¿se puede operar la consola sin ratón?

**Respuesta corta: no.** El camino principal de la consola —abrir un equipo desde la tabla de la flota y
ejecutar cualquier acción sobre él— no tiene ninguna ruta de teclado. Además no hay anillo de foco visible
en ninguna parte de la app, en ningún tema, así que incluso donde el tabulador sí llega, no se ve dónde está.

El chrome nuevo de la v2 (riel, cabecera del equipo, barra de acción, columna de contexto, encabezado de
flota) está bien hecho: `aria-label` en todos los botones de solo ícono, `aria-current`, `aria-pressed`,
landmarks `<nav>`/`<aside>`/`<main>`/`<h1>`. Los defectos se concentran en dos lugares: **(1)** los
componentes heredados de la v1 que el rediseño reusó sin reescribir, y **(2)** los huecos que Quasar deja
y que nuestro CSS no tapa (el anillo de foco, el nombre de los diálogos, los tooltips como única etiqueta).

## Cómo se separó «Quasar» de «nuestro código»

No hay `node_modules` en el entorno, así que en vez de confiar en la memoria se descargó
`quasar@2.18.5` (la versión que fija `package.json`) y se leyó el fuente de los componentes implicados.
Lo comprobado:

| Componente Quasar | Qué hace | Veredicto |
|---|---|---|
| `QDialog` | mueve el foco al abrir, lo devuelve al cerrar (`refocusTarget`), contiene el tabulador (`addFocusout`), cierra con Escape, `role="dialog"` + `aria-modal` | **lo resuelve** — familia (c) no se le imputa |
| `QMenu` | igual: foco al abrir, `refocusTarget`, `addFocusout`, `addEscapeKey`, `role="menu"` | **lo resuelve** |
| `QItem clickable` | `tabindex="0"`, `role="listitem"`, `onKeyup` Enter(13)/Espacio(32) | **lo resuelve** |
| `QChip clickable` | `tabindex="0"` + `onKeyup` | **lo resuelve** |
| `QTree` | nodos con `tabindex="0"`, `role="treeitem"`, `aria-expanded`, Enter selecciona y Espacio expande | **lo resuelve** |
| `QField`/`QInput`/`QSelect` con `label` | genera `targetUid` → `id` en el control y `for` en el rótulo | **lo resuelve** |
| `QBtnDropdown` | pone `aria-haspopup`, `aria-expanded`, `aria-controls` solo | **lo resuelve** |
| `QTabs`/`QTab` | `role="tablist"`/`tab`, navegación con flechas | **lo resuelve** |
| `QIcon` | renderiza **siempre** `aria-hidden="true"` y nunca `tabindex` | **hueco** — un `@click` acá es inalcanzable *y* mudo |
| `QTooltip` | solo `role="tooltip"`; **no** cablea `aria-describedby` al elemento que describe | **hueco** — un tooltip no es un rótulo accesible |
| `QTr`/`QTd`/`QTh` | `<tr>`/`<td>`/`<th>` pelados: ni `tabindex`, ni `role`, ni manejo de teclas | **hueco** — un `@click` en una fila es solo ratón |
| `q-focus-helper` (CSS) | `.q-focus-helper, .q-focusable { outline: 0 }` y lo reemplaza por un velo `currentColor` a `opacity .22` | **hueco** — Quasar quita el outline; el anillo de reemplazo no contrasta |

Lo que Quasar resuelve **no** se cuenta como defecto más abajo. Eso descarta 260 de los 308 `@click`
que la primera pasada marcó como sospechosos (casi todos `q-item clickable`).

## Hallazgos

Gravedad = cuántos usuarios × con qué frecuencia. #1–#4 están en el camino que todo operador recorre todos
los días; #14 en adelante son rincones.

| # | archivo:línea | fam. | Qué pasa exactamente | Arreglo propuesto (una línea) |
|---|---|---|---|---|
| 1 | `components/AgentTable.vue:93` | a | Abrir un equipo está atado a `@click` en el `<q-tr>`. La fila no es enfocable y ninguna celda trae enlace ni botón: el hostname es texto pelado (`:318`). **Sin ratón no se puede entrar a ningún equipo de la flota**, que es el camino principal de la consola. | Envolver el hostname en un `<router-link :to="/agents/${row.agent_id}">` y dejar el `@click` de la fila como atajo redundante. |
| 2 | `components/AgentTable.vue:96` | a | `<q-menu context-menu>` anclado al `<q-tr>`: todas las acciones por equipo (`AgentActionMenu`: tomar control, ejecutar script, reiniciar, mantenimiento…) salen solo con clic derecho. Como el `<tr>` no es enfocable, la tecla Menú/Shift+F10 tampoco llega — no hay nada a qué apuntarla. | Añadir una columna de acciones con un `<q-btn icon="more_vert" :aria-label>` que abra el mismo `AgentActionMenu`, y conservar el menú contextual. |
| 3 | `css/app.sass` (ausencia, todo el archivo) | b | **Cero reglas `:focus-visible` o `:focus` de foco en los 968 renglones** (la única `a:focus` del archivo, `:439`, es cosmética de Leaflet). Quasar hace `outline: 0` en todo lo enfocable y lo reemplaza por un velo `currentColor @ .22`. Medido con la paleta propia: riel claro inactivo **1,33:1**, riel claro activo **1,37:1**, nav de secciones claro **1,37–1,46:1**, riel oscuro **1,42–1,46:1**. Todo lejos del 3:1 de SC 2.4.11. En la práctica el foco no se ve en ninguna pantalla ni tema. | Un bloque global `:focus-visible { outline: 2px solid var(--q-primary); outline-offset: 2px }` más un token `--obs-focus` por tema en `app.sass`. |
| 4 | `components/clients/ClientsManager.vue:58` y `:64` (patrón repetido en **28** tablas: `ScriptManager.vue:158`/`:168`, `agents/ChecksTab.vue:182`/`:188`, `agents/AutomatedTasksTab.vue:99`/`:105`, `AlertsManager.vue:51`/`:56`, `automation/AutomationManager.vue:329`/`:338`, `accounts/PermissionsManager.vue:37`/`:42`, `AdminManager.vue:68`/`:74`, `clients/SitesTable.vue:58`/`:64`, `core/APIKeysTable.vue:35`/`:41`, `modals/coresettings/{KeyStore,URLActions,CustomFields}Table.vue`, `core/settings/components/ScheduleTable.vue:30`, `ee/reporting/components/*Table.vue`, …) | a | Editar una fila está atado a `@dblclick` sobre `<q-tr>` y el resto de las acciones (editar / borrar / agregar) a `<q-menu context-menu>` sobre la misma fila no enfocable. El doble clic no tiene equivalente de teclado en ningún navegador. Resultado: en la administración de clientes, sitios, scripts, políticas, chequeos, tareas, usuarios, roles, llaves, campos propios y reportes **solo «Nuevo» es alcanzable**; nada existente se puede editar ni borrar sin ratón. | Columna de acciones con botones reales (`edit`/`delete` con `aria-label`) en cada tabla, replicando los ítems del menú contextual. |
| 5 | `layouts/MainLayout.vue:70` (y **184** instancias del mismo patrón: `AlertsIcon.vue:2`, ~90 botones `icon="close"` de diálogo —`components/clients/ClientsManager.vue:14`, `components/checks/*.vue:7`, …—, ~30 `icon="refresh"` de barra, los 16 de `ee/reporting/components/EditorToolbar.vue:128-344`) | d | Botones de solo ícono sin `aria-label`, sin `label` y sin texto en el slot. `QBtn` dibuja el ícono con `QIcon`, que lleva `aria-hidden="true"`: **el botón no tiene nombre accesible alguno**. 115 de ellos traen `<q-tooltip>`, que da el texto al ratón pero no al lector de pantalla (`QTooltip` no cablea `aria-describedby`). `MainLayout.vue:70` —el refresco del encabezado global— no tiene ni tooltip. | Añadir `:aria-label` con el mismo `$t(...)` que ya usa el tooltip; `components/ui/SecretInput.vue:31` ya lo hace bien y sirve de molde. |
| 6 | `views/LoginView.vue:37` (mismo patrón en `accounts/ResetPass.vue:15` y `:33`, `modals/admin/UserForm.vue:35`, `modals/admin/UserResetPasswordForm.vue:23`, `modals/coresettings/KeyStoreForm.vue:36`) | a | El ojo de «ver contraseña» es un `<q-icon @click>` en el slot `append`: `aria-hidden="true"` y sin `tabindex`. Inalcanzable e invisible para el teclado **en la pantalla de ingreso**, que todo usuario cruza en cada sesión. | Reemplazar el `q-icon` por `<q-btn flat round dense :icon :aria-label>` como ya hace `components/ui/SecretInput.vue:25-31`. |
| 7 | `components/AlertsIcon.vue:45` y `:54`; `components/modals/alerts/AlertsOverview.vue:153`, `:164`, `:175`, `:184`, `:193` | a | Posponer / resolver / reactivar una alerta son `<q-icon @click>`: `aria-hidden` y no enfocables. Son las dos únicas superficies de triaje de alertas de la consola, y en las dos el gesto es el mismo. **El triaje de alertas es íntegramente de ratón**, siendo tarea diaria. | Cambiar los 7 `q-icon` por `q-btn flat round dense` con `:aria-label`. |
| 8 | `views/DashboardView.vue:392`, `:404`, `:416`, `:428` (casillas) y `:444`, `:456`, `:468`, `:480`, `:492` (radios) | d | El menú «Más filtros» de la flota pone el rótulo visible en un `q-item-section` **hermano** del control, nunca asociado. Las 4 casillas y los 5 radios se anuncian «casilla, sin marcar» / «botón de radio» sin nombre. Es el filtro principal de la tabla de equipos. | Pasar el texto al prop `label` del propio `q-checkbox`/`q-radio` y quitar el `q-item-section` duplicado. |
| 9 | `layouts/MainLayout.vue:133` | d | El interruptor de tema claro/oscuro del encabezado global es un `q-toggle` sin `label` ni `aria-label`: `role="checkbox"` anónimo. Está en todas las pantallas. | `:aria-label="$t('layout.darkMode')"` en el `q-toggle`. |
| 10 | `layouts/MainLayout.vue:139` | d | El botón de terminal web lleva `label=">_"`: su nombre accesible es literalmente `>_`, que no dice nada. Es el único rótulo «mentiroso» que apareció en toda la app. | Dejar el `>_` como contenido visual y añadir `:aria-label="$t('layout.webTerminal')"`. |
| 11 | `components/AgentTable.vue:47` y `:50` (vacíos); `:26`, `:33`, `:40`, `:53`, `:60`, `:67`, `:74`, `:81` (solo ícono) | d | 10 de las columnas de la tabla principal no tienen encabezado accesible: dos `<q-th>` completamente vacíos (plataforma, tipo de equipo) y ocho con un `q-icon` + tooltip, que no aporta nombre. Las casillas de alerta SMS / correo / tablero de cada fila (`:100`, `:115`, `:127`, `:142`, `:154`, `:169`) tampoco tienen rótulo, así que se anuncian como tres casillas idénticas sin saber cuál es cuál. Mismo patrón en otras 23 cabeceras (`AutomatedTasksTab.vue`, `ChecksTab.vue`, `AlertsManager.vue`, `PolicyChecksTab.vue`, …) y 8 `q-th` vacíos más. | Poner el texto del tooltip en el `<q-th>` con una clase `sr-only`, y `:aria-label` en cada `q-checkbox` de fila. |
| 12 | todos los `q-dialog` (**116**, p. ej. `components/clients/ClientsForm.vue:2`, `modals/admin/UserForm.vue:2`, `tasks/AutomatedTaskForm.vue:2`) | d | Quasar pone `role="dialog"` + `aria-modal`, pero **ninguno de los 116 tiene `aria-label` ni `aria-labelledby`**. El título vive en un `<div class="text-h6">` suelto. Todo diálogo de la consola se anuncia como «diálogo» sin nombre. | `aria-labelledby` apuntando al id del título (y convertir ese `div.text-h6` en `<h2>`). |
| 13 | `components/shell/NavMenu.vue:8`, `:48`, `:68`, `:95`, `:150`, `:229`, `:275`; también `agents/workspace/AgentHeader.vue:151`, `agents/workspace/ActionBar.vue:53`, `layouts/MainLayout.vue:152`, `views/DashboardView.vue:14` | d | Patrón `QBtn` + `QMenu` hijo: Quasar no deduce nada, así que los **7 menús del riel** (y los demás disparadores) se anuncian como botones corrientes, sin `aria-haspopup` ni `aria-expanded`. Además el ítem «Agregar» (`NavMenu.vue:21`) abre un submenú señalado solo por un `q-icon` de flecha (`aria-hidden`), sin marca de que haya submenú. | Usar `q-btn-dropdown` —que ya pone `aria-haspopup`/`aria-expanded`/`aria-controls`— o añadir esos tres atributos a mano. |
| 14 | `components/shell/ObsSectionNav.vue:12` | d | El `<nav>` genérico marca la sección activa solo con `active-class` (color + fondo): no hay `aria-current`. Sin ver la pantalla no se sabe en qué sección se está. Afecta a toda página que usa esta nav (espacio del equipo, Scripts, Ajustes, Automatización, Alertas). | `:aria-current="item.key === section ? 'page' : undefined"` en el `q-item`, como ya hace `NavRail.vue:42`. |
| 15 | `views/AgentWorkspace.vue:13-21` | c | Bajo 1200 px la columna de contexto se abre superpuesta (`.obs-ws__ctx--overlay`, `position:absolute; z-index:5`) con un velo propio. No es `QDialog`: **no mueve el foco al abrir, no lo devuelve al botón que la abrió (`AgentHeader.vue:12`), no contiene el tabulador y no cierra con Escape**; el velo es un `<div @click>` sin equivalente de teclado. Es el único overlay hecho a mano de la app. | Envolverla en un `q-dialog position="left"` (hereda foco, contención y Escape) o añadir `@keydown.esc`, foco inicial y retorno a mano. |
| 16 | `views/DashboardView.vue:80-87` | d | Los íconos de estado de cada nodo del árbol de clientes traen `:aria-label="stateLabel(st)"` — pero están en un `q-icon`, que renderiza `aria-hidden="true"`. **El rótulo se escribió y el atributo lo anula:** ARIA ignora todo lo que haya en un elemento oculto. El esfuerzo está hecho y no sirve. | Mover el rótulo a un `<span class="sr-only">` hermano, o poner `aria-hidden="false"` + `role="img"` en el `q-icon`. |
| 17 | todas las páginas (`layouts/MainLayout.vue:69` en adelante) | a | No existe enlace de salto. Entre el riel (11 botones), los 7 menús y el encabezado (idioma, tema, terminal, equipos, alertas, usuario) hay **más de 15 paradas de tabulador antes del contenido**, y se repiten en cada navegación. | Un `<a href="#main" class="skip-link">` como primer hijo de `q-layout`, visible al recibir foco. |
| 18 | `components/agents/ChecksTab.vue:395`, `:403`, `:418`, `:427`; `agents/AutomatedTasksTab.vue:339`; `agents/HistoryTab.vue:46`; `AlertsManager.vue:349`, `:362`; `automation/AutomationManager.vue:479`, `:491`, `:506`, `:514`; `automation/PolicyAutomatedTasksTab.vue:196`; `automation/PolicyChecksTab.vue:222`; `automation/modals/PolicyStatus.vue:107`, `:122`, `:130` | a | 19 pseudo-enlaces `<span style="text-decoration: underline" @click>` sin `tabindex` ni `role`: son el único acceso a la salida de un script, al detalle de un ping, al visor de eventos, al gráfico de un chequeo y al estado de una política. Se ven como enlaces y no se comportan como tales. | Convertir a `<q-btn flat dense no-caps>` o aplicar el patrón de `clients/ClientsManager.vue:116` (`role="button"` + `tabindex="0"` + `@keyup.enter`), agregándole también Espacio. |
| 19 | `components/agents/WinUpdateTab.vue:195`; `agents/remotebg/EventLogManager.vue:94`; `software/InstallSoftware.vue:55` | a | Tres `<q-td @click>`: el detalle de un parche, el mensaje de un evento y la descripción de un paquete se abren haciendo clic en la celda. `QTd` es un `<td>` pelado. | Mover el `@click` a un `q-btn flat dense` dentro de la celda. |
| 20 | `components/automation/AutomationManager.vue:522`; `core/APIKeysTable.vue:79`; `agents/WmiDetail.vue` (ok) / `modals/alerts/AlertTemplateForm.vue:81`, `:128`; `tasks/AutomatedTaskForm.vue:294`; `ee/reporting/components/ReportScheduleForm.vue:165` | a | Seis `<q-icon @click>` más, fuera de las familias ya listadas: copiar una política, copiar una llave de API, quitar un correo o un SMS de una plantilla de alerta, quitar una acción de una tarea. Inalcanzables y `aria-hidden`. | Reemplazar por `q-btn flat round dense` con `:aria-label`. |
| 21 | `core/dashboard/ui/ObserverTable.vue:22` | d | El botón de selección de columnas, presente en toda tabla que use `column-select`, es `<q-btn dense flat icon="more_horiz">` sin nombre accesible (y la columna lleva `label: "Column Select"` en inglés sin i18n, aunque nunca se dibuja porque el slot la reemplaza). | `:aria-label="$t('observerTable.columnSelect')"` en el botón y pasar la etiqueta a i18n. |
| 22 | `views/ActivityLiveView.vue:60`; `agents/ActividadTab.vue:161`; `agents/LostCaseTimelineDialog.vue:145`, `:167` | a | Abrir una captura de pantalla en grande es un `<div @click>` (dos casos) o un `<img @click.stop>` (dos casos). En la tarjeta de ActivityLive el botón de refresco sí es alcanzable, así que queda una tarjeta mitad operable. En la línea de tiempo el `q-item` contenedor sí responde a Enter, pero abre otra acción distinta (`focusCycle`), no la evidencia. | Envolver la miniatura en un `q-btn flat` o darle `role="button"` + `tabindex="0"` + `@keyup.enter`. |
| 23 | `ee/reporting/components/VariablesSelector.vue:24`, `:70`, `:88` | a | Copiar una variable al portapapeles son dos `<span @click>` y un `<q-badge @click>` (`QBadge` tampoco lleva `tabindex`). Módulo EE de reportes, tráfico bajo. | `q-btn flat dense` con `:aria-label`. |
| 24 | `css/app.sass:439` | b | `body .leaflet-bar a, a:hover, a:focus` fijan el mismo `background-color` para los tres estados, con lo que se anula el cambio de fondo con que Leaflet marca el foco en los controles del mapa. Queda el outline del navegador, así que el daño es menor, y solo afecta a los diálogos de ubicación. | Quitar `a:focus` del selector y dejar que la regla global de `:focus-visible` (#3) lo cubra. |

## Lo que se buscó y **no** aparece

Vale la pena dejarlo escrito: estas cuatro cosas se buscaron a propósito y el código sale limpio.

- **`outline: none` / `outline: 0` escrito por el proyecto: cero.** La búsqueda en los 190 `.vue` y los dos
  `.sass` no devuelve ni una. El problema de la familia (b) no es que alguien lo haya quitado: es que Quasar
  lo quita en su propio CSS y nuestro tema nunca pone un anillo de reemplazo. La diferencia importa para
  arreglarlo (#3 es una regla global, no 190 parches).
- **`aria-label` que no coincide con el rótulo visible: ninguno.** Los 65 `aria-label` de la app salen todos
  de `$t(...)`; se compararon uno a uno contra el `label` y el tooltip del mismo elemento y en los 38 casos
  con ambos la clave i18n es la misma. No hay rótulos en inglés sueltos ni textos divergentes. El único caso
  de «rótulo que no dice nada» es el `label=">_"` de #10.
- **Diálogos que atrapan al usuario: ninguno.** Los 16 `q-dialog` con `persistent` o `no-esc-dismiss` se
  revisaron uno por uno: todos tienen un botón «Cancelar»/«No» con rótulo y alcanzable
  (`ui/ConfirmDialog.vue:25`, `agents/ConfirmYesDialog.vue:37`, `remotebg/RegistryValueModal.vue:102`, …) y
  tres de ellos (`RunScript`, `SendCommand`, `WebsocketSendCommand`) se reponen Escape a mano con
  `@keydown.esc`. `persistent` ahí es una decisión deliberada, no un defecto. Ningún `q-dialog` ni `q-menu`
  de la app usa `no-focus` o `no-refocus`.
- **El árbol de clientes y sitios es operable por teclado.** Es la navegación principal del tablero y se
  sospechó de ella por el `<q-menu context-menu>` de `DashboardView.vue:92`; resultó que `QTree` da
  `tabindex="0"`, `role="treeitem"`, `aria-expanded`, Enter para seleccionar y Espacio para expandir. El
  nodo **sí** puede recibir foco, así que la tecla Menú/Shift+F10 abre su menú contextual. No se cuenta
  como defecto (aunque sea poco descubrible). Es exactamente el contraste con #2: ahí la fila no es
  enfocable y por eso no hay nada que hacer.
- **Patrones correctos que ya viven en el repo** y sirven de molde para los arreglos:
  `components/clients/ClientsManager.vue:116-126` (`role="button"` + `tabindex="0"` + `@keyup.enter`),
  `components/ui/SecretInput.vue:25-31` (botón real con `aria-label` en el `append` de un campo),
  `components/shell/NavRail.vue:41-42` (`aria-label` + `aria-current`),
  `components/agents/workspace/ContextColumn.vue:40` (`aria-pressed`),
  `components/AlertsManager.vue:90` (`<a href="#" @click.prevent>` — enfocable y activable con Enter, al
  contrario que el `<span>` subrayado del #18 en el mismo archivo, `:349`).

## Método

1. `git remote -v` para confirmar el repo (`braincorp-cl/observer-rmm-dist`) antes de tocar nada.
2. Barrido estructural de los 190 `.vue` con un analizador de etiquetas multilínea en Python (una regex de
   una línea pierde la mayoría: encuentra 1 de los 308 `@click` sospechosos, porque en este código los
   atributos van partidos en varios renglones).
3. Descarga y lectura del fuente de `quasar@2.18.5` para decidir, componente por componente, qué resuelve
   el framework. Sin esto, la mitad de los «hallazgos» serían falsos (los `q-item clickable`) y se perderían
   los que importan (el `aria-hidden` de `QIcon`, el `outline: 0` del `q-focus-helper`).
4. Cálculo de contraste del indicador de foco con la paleta real de `quasar.variables.sass`, componiendo el
   velo `currentColor @ .22` sobre cada superficie y midiendo en WCAG 2.x. De ahí salen los números de #3.
5. Lectura completa de los componentes de más tráfico: `MainLayout`, `NavRail`, `NavMenu`, `ObsSectionNav`,
   `AgentTable`, `DashboardView`, `AgentWorkspace`, `AgentHeader`, `SectionNav`, `ActionBar`,
   `ContextColumn`, `ObserverTable`, `AlertsIcon`, `LoginView`, `ClientsManager`.
6. Verificación de cada `archivo:línea` citado contra el contenido real del archivo.

**Límite honesto:** esto es análisis estático. No se levantó la app ni se pasó axe ni un lector de pantalla
—no hay `node_modules` y la tarea es de análisis—, así que los números de contraste de #3 son calculados
sobre los tokens del tema, no medidos en pantalla. Nada de lo anotado depende de eso: los 24 hallazgos salen
de la estructura del marcado y del fuente de Quasar, no de cómo se vea al renderizar. Lo que sí convendría
confirmar en vivo es el orden del tabulador dentro de las tablas virtualizadas (`virtual-scroll`), que no se
puede deducir del marcado.

## Qué elegí NO hacer, y por qué

- **No se tocó ni un archivo de `src`.** La tarea es de análisis; el informe propone arreglos en una línea
  cada uno pero no los aplica. Varios (#3, #4, #5) son barridos de decenas o cientos de archivos y merecen
  su propia rama y su propia revisión, no un commit colgado de una auditoría.
- **No se reportaron los 260 `q-item clickable`** que la primera pasada marcó. Quasar les da `tabindex`,
  `role` y Enter/Espacio. Inflar el informe con ellos lo volvería inútil.
- **No se reportaron los 159 campos de formulario «sin label» como 159 defectos.** El patrón real es uno:
  el rótulo visible vive en un `<div class="col-2">` o en un `q-item-section` hermano y nunca se asocia
  (`modals/admin/UserForm.vue:13` junto a `:14` es el ejemplo canónico). Quedó como #8 para el caso de más
  tráfico —el filtro de la flota— porque ahí no hay ni rótulo adyacente que ayude al usuario con lupa. Los
  demás son la misma línea de arreglo repetida y entrarían en el barrido de #5. Que `QField` **sí** asocia
  el `label` cuando se usa el prop fue comprobado en el fuente, así que no es un defecto del framework ni de
  todos los campos: solo de los que ponen el rótulo afuera.
- **No se auditó estructura de encabezados, orden del DOM, `alt` de imágenes, contraste de texto, zoom ni
  movimiento.** Son problemas de accesibilidad reales (y hay material: solo `DashboardView` tiene `<main>`,
  los títulos de diálogo son `div.text-h6` en vez de `<h2>`, el riel es un `<aside>` sin `<nav>`) pero caen
  fuera de las cuatro familias pedidas y de la pregunta «¿se opera sin ratón?». Se mencionan de paso en #12
  y en los hallazgos donde el arreglo los roza.
- **No se tocó `.eslintrc.js` ni se agregó `eslint-plugin-vuejs-accessibility`.** Sería la forma de que #1,
  #4, #5, #6 y #18 no vuelvan, pero agregar una dependencia y un conjunto de reglas nuevas rompería el lint
  de todas las ramas hermanas que están trabajando en paralelo. Queda como recomendación.
- **No se corrió `npm run lint` ni los tests, y no se arregló nada de eso.** No hay `node_modules` en el
  entorno y la tarea no es de implementación, así que **no se verificó el estado del lint ni de los tests y
  este informe no afirma nada sobre ellos**. Lo que sí es preexistente y solo se nombra: el repo tiene un
  único test de unidad en toda la WebUI (`src/utils/coords.test.mjs`), no hay corredor de tests configurado
  en `package.json`, no hay ninguna regla de lint de accesibilidad, y `lint:i18n` enumera a mano 180 rutas
  de archivo en una sola línea de `package.json` —frágil, pero ajeno a esto—.
- **No se tocó nada fuera de este archivo nuevo en la raíz,** por las sesiones que trabajan en ramas
  hermanas.
