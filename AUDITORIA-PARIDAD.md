# Auditoría de paridad v1 → v2 (webUI)

**Fecha:** 2026-11-05
**Rama de trabajo:** `v2/auditoria-paridad` (creada desde `release/v2`)
**v1 leída en:** `origin/main` (`da0e21b`, 2026-11-04), sin checkout — vía `git show main:<ruta>` y `git diff`
**v2 leída en:** `HEAD` (`fb59a20`)
**Alcance:** sólo lectura. No se modificó ningún archivo de `src/`.

---

## 0. Resumen en una frase

El rediseño de la v2 **no eliminó ningún destino de la v1**: el hueco de paridad
es por completo **deriva de ramas**. `release/v2` se bifurcó de `main` el
**23-oct-2026** (`1079c0b`) y desde entonces `main` acumuló **111 commits**, entre
ellos tres features completas de producto (**052** roles delegables, **053** olas
2–4 de Observer Erase, **055** inventario de medios). Nada de eso viajó a la v2.

La prueba es doble:

- `git ls-tree` del punto de bifurcación contra `HEAD`: **0 archivos de `src/`
  borrados** por la v2.
- Nombres de ruta del punto de bifurcación contra `HEAD`: **0 rutas eliminadas**,
  6 agregadas (`Alerts`, `Automation`, `EraseIntake`, `Preferences`, `Scripts`,
  `Settings`).
- Claves i18n `nav.*`: la v1 tiene exactamente **una** que la v2 no tiene
  (`nav.storageMedia`); la v2 tiene una que la v1 no tiene (`nav.eraseIntake`).

Por eso la tabla se ordena por gravedad de uso, pero la causa raíz de casi todo es
la misma: **falta un merge de `main` a `release/v2`**, no un recorte de diseño.

---

## 1. Mapa de la navegación, lado por lado

| v1 | v2 |
|---|---|
| Barra de menús `FileBar.vue` (7 botones con rótulo, arriba del dashboard) | Riel de iconos `NavRail.vue` (60 px, izquierda, en toda la consola) + `NavMenu.vue` (los mismos 7 menús, ícono + tooltip) |
| Menú contextual de la fila del agente `AgentActionMenu.vue` | `AgentActionMenu.vue` — **plantilla byte a byte idéntica** (sólo se movió el `setup()` a `composables/useAgentActions.js`) |
| Pestañas de sección `SubTableTabs.vue` (12 `q-tab` planas) | `SectionNav.vue` → `ObsSectionNav.vue` (las mismas 12, agrupadas en Operación / Inventario / Registro) |
| Detalle del agente: `AgentView.vue` (Resumen fijo + pestañas) | `AgentWorkspace.vue` (columna de contexto + cabecera + nav lateral + barra de acción) |

Verificado destino por destino: los 7 menús de `FileBar.vue` están los 7 en
`NavMenu.vue`, con los mismos handlers y los mismos diálogos. Las 12 secciones del
agente están las 12 en `SECTIONS` de `web/app/src/views/AgentWorkspace.vue:89-102`.
Las 13 secciones de Ajustes globales están las 13 en `SECTION_GROUPS` de
`web/app/src/components/modals/coresettings/EditCoreSettings.vue:1380-1386`.

---

## 2. El hueco: lo que un usuario hace en la v1 y en la v2 no tiene camino

Gravedad: **Alta** = destino o acción de uso diario sin ningún camino en la v2 ·
**Media** = campo o sub-vista de un flujo que sí existe, pero incompleto ·
**Baja** = interacción o atajo, con el destino alcanzable por otra vía.

| Destino o acción de la v1 | Dónde vive en v1 (archivo:línea) | Equivalente en la v2 | Gravedad |
|---|---|---|---|
| **Herramientas → Inventario de medios de almacenamiento** (página de flota: filtro por cliente/sitio/veredicto, categoría de sanitización alcanzable por equipo) | `web/app/src/components/FileBar.vue:176` → ruta `web/app/src/router/routes.js:53-55` → `web/app/src/views/StorageMediaView.vue` | **VACÍO** — no hay ítem de menú, no hay ruta, no existe la vista. Cero referencias a `StorageMedia` en todo el árbol de la v2 | **Alta** |
| **Portal PÚBLICO de verificación de certificados** (`/verificar/:id`, sin autenticación: lo abre el cliente, el auditor o el tribunal que recibe un certificado) | `web/app/src/router/routes.js:190-192` → `web/app/src/views/VerifyCertificateView.vue` | **VACÍO** — la ruta no existe; un enlace `/verificar/...` ya emitido cae en el `catchAll` → `NotFound` | **Alta** (es el único destino del hueco que ve alguien de afuera) |
| **Certificados de borrado → pestaña Reconciliación** (ingresos sin certificado, por cliente, con rango de fechas y umbral de días estancados) | `web/app/src/views/EraseCertificatesView.vue:30` (pestaña), panel y `loadReconciliation()` en `:151-300` y `:729` | **VACÍO** — la v2 sólo tiene los modos `certificates` e `intake` (`routes.js:98-116`); no hay tercer modo ni ruta | **Alta** |
| **Ver cadena de custodia de un ingreso** (línea de tiempo inmutable, verificación de hash encadenado) y **agregar un evento de custodia** (recibido / almacenado / sanitizado / entregado a procesador / destruido / devuelto / reubicado) | `web/app/src/views/EraseCertificatesView.vue:133-134` y `:292-293` → `web/app/src/components/agents/AssetCustodyTimeline.vue` (alta en `:91-119`) | **VACÍO** — el componente no existe en la v2 y ningún botón lo invoca | **Alta** |
| **Emitir certificado: método de verificación, evidencia, archivo de evidencia y concurrencia de testigo** (nombre / rol / contacto, con aviso cuando no hay verificación) | `web/app/src/views/EraseCertificatesView.vue:344-345`, `:352`, `:362-363`, `:371-403` | **Parcial** — el diálogo de la v2 (`views/EraseCertificatesView.vue:140-190`) sólo pide método, operador y razón. Se puede emitir, pero el certificado sale sin verificación ni testigo | **Alta** |
| **Perfiles asignables de un rol** (feature 052: qué perfiles puede repartir quien porta este rol — delegación restringida de la administración de usuarios) | `web/app/src/components/accounts/RolesForm.vue:76-79` | **VACÍO** — el campo no está en el formulario de rol de la v2; el backend lo valida igual, pero no hay dónde configurarlo | **Alta** |
| **Activos del equipo → sub-sección Medios de almacenamiento** (medio por medio: tipo, bus, autocifrado, capacidades de sanitización, avisos) | `web/app/src/components/agents/AssetsTab.vue:43` y `:95-96` → `web/app/src/components/agents/StorageMediaDetail.vue` | **VACÍO** — `assetOptions` de la v2 tiene 14 sub-secciones (`AssetsTab.vue:67-84`); falta `storage_media`. El resto, incluido cifrado, está | **Media** |
| **Acta de ingreso: equipo, marca, modelo, tipo de medio, destino del medio y detalle del destino** | `web/app/src/components/agents/AssetIntakeForm.vue:57`, `:97`, `:104`, `:152`, `:166`, `:175` | **Parcial** — el formulario de la v2 tiene 9 campos; faltan esos 6 (`AssetIntakeForm.vue:26-94`) | **Media** |
| **Detalle de un certificado: marca, modelo, hostname, tipo y origen del medio, destino y su detalle, método y evidencia de verificación, concurrencia (nombre/rol/contacto/fecha)** | `web/app/src/components/agents/EraseCertificateDetailDialog.vue:201-220`, aviso en `:66` | **Parcial** — el diálogo de la v2 no muestra esas filas | **Media** |
| **Retención de adjuntos de borrado por cliente** (con piso y herencia del valor global) | `web/app/src/components/clients/ClientsForm.vue:45-46`, herencia en `:125` y `:183` | **VACÍO** — el formulario de cliente de la v2 no tiene el campo | **Media** |
| **Ajustes globales → retención de adjuntos, purga agendada y interruptor del portal público** | `web/app/src/components/modals/coresettings/EditCoreSettings.vue:1008`, `:1025`, `:1047` | **VACÍO** — la sección Retención de la v2 no incluye esos tres ajustes | **Media** |
| **Columna «Destino del medio» en la tabla de certificados** | `web/app/src/views/EraseCertificatesView.vue:543` | **VACÍO** | **Baja** |
| **Ver el detalle de un equipo sin salir de la lista** (el panel de 12 pestañas se abría *debajo* de la tabla; el árbol de clientes y la tabla seguían a la vista, y se podía saltar entre equipos de cualquier cliente del filtro activo) | `web/app/src/views/DashboardView.vue:488` (`<SubTableTabs />` dentro del `q-splitter` de `:262`) | **Cambio deliberado** — un clic navega al espacio de trabajo (`components/AgentTable.vue:565-571`). Se recupera parcialmente con `ContextColumn.vue`, que lista los equipos **del mismo sitio**; no los del filtro completo | **Baja** (ver §3) |
| **Gestor de scripts → vista de carpetas** (árbol por categoría, con menú contextual por nodo) | `web/app/src/components/scripts/ScriptManager.vue:73-78` (botón) y `:132-342` (`q-tree`) | **Cambio deliberado** — en la página (`embedded`) el árbol y su botón están tras `v-if="!embedded && !tableView"` (`ScriptManager.vue:395`, `:614`), y la barra de la v1 tras `v-if="!embedded"` (`:283`). Las categorías sobreviven como ítems de `ObsSectionNav`; las 7 acciones de fila están completas en `rowActions()` (`:1296-1318`) | **Baja** (ver §3) |

### Lo que NO es hueco (verificado, no supuesto)

- **Menú contextual de la fila del agente:** plantilla idéntica (diff vacío en las
  líneas 1-306 de `AgentActionMenu.vue`). Montado en los dos lados desde
  `AgentTable.vue:97`, `SummaryTab.vue:122` y, en la v2, también desde
  `workspace/AgentHeader.vue:160`.
- **Los 7 menús de la barra:** Archivo (Agregar cliente/sitio, Auditoría, Log de
  depuración), Ver (Acciones pendientes), Agentes (Instalar, Despliegues,
  Actualizar), Ajustes (Clientes, Scripts, Automatización, Alertas, Permisos,
  Usuarios, Globales), Herramientas (3 masivas + 4 de respuesta rápida + Equipos
  perdidos + Monitoreo en vivo + Cifrado + Erase ×2 + Mantenimiento + Limpiar
  caché + Recuperar agentes), Reportería, Ayuda → todos presentes en
  `NavMenu.vue`.
- **Menú contextual del árbol de clientes/sitios:** las 10 acciones de la v1
  (editar, borrar, agregar sitio, mantenimiento, monitoreo de actividad, instalar
  agente, política, plantilla de alerta, acción URL, correr chequeos) están en
  `views/DashboardView.vue:101-250`.
- **Ajustes globales:** 13 secciones en los dos lados. El diálogo de la v1 sigue
  disponible sin `embedded`.
- **Preferencias de usuario, Gestor de automatización, Gestor de alertas:** mismos
  campos y mismas acciones; sólo cambia el envase (diálogo → página).
- **Encabezado:** idioma, tema, alertas, chip de equipos, terminal web y menú de
  usuario siguen en `layouts/MainLayout.vue`.
- **Equipos perdidos, Monitoreo en vivo, Cifrado de disco, Órdenes de borrado:**
  sin cambios funcionales (sólo se movió el título a `ObsPageHead`).

---

## 3. Lo que se quitó A PROPÓSITO en el rediseño

Sólo lo que el código o sus comentarios dejan explícito. Nada de esto es un
destino perdido: son interacciones reemplazadas.

| Qué | Evidencia en el código |
|---|---|
| **La barra de menús con rótulos** pasa a riel de iconos con tooltip | `components/shell/NavMenu.vue:2-6`: «Menús de la barra v1 (FileBar.vue) pasados al riel de iconos (046, dirección 1c): mismos ítems, mismos handlers y mismos diálogos; solo cambia el disparador». `store/index.js:101`: «046 F1: sin la barra de menús (FileBar, 40 px) la tabla recupera ese alto» |
| **Las 12 pestañas planas del agente** pasan a navegación lateral agrupada; la vista de agente deja de tener pestañas | `components/agents/workspace/SectionNav.vue:2-5`; `ObsSectionNav.vue:2-6`: «Es una lista de navegación, no un tablist (UI-E04)» |
| **Un clic en la fila navega** al espacio de trabajo, en vez de abrir el panel inferior | `components/AgentTable.vue:562-564`: «046 F4 (RN-03): un clic navega al espacio de trabajo 1c. Espera 250 ms para no comerse el doble clic de la v1… si llega el doble clic, se cancela». El doble clic configurable (editar / tomar control / segundo plano / acción URL) se conserva |
| **Los sub-paneles de Activos** pasan de pestañas a bloques desplegables | `components/agents/AssetsTab.vue:9-14`: «las subsecciones de Activos van apiladas como bloques desplegables (q-expansion-item), no como pestañas ni como un selector que conmuta paneles: la vista de agente no tiene pestañas (UI-E04)» |
| **Scripts / Automatización / Alertas / Ajustes globales / Preferencias** pasan de diálogo a página con la sección en la URL | `components/shell/NavMenu.vue:113` («050 (T026): los tres gestores navegan a su página»); `router/routes.js:10`, `:28`, `:37`; `views/ScriptsView.vue:2`, `SettingsView.vue:2`, `PreferencesView.vue:2` |
| **Custodia de activos** sale de ser la segunda pestaña de `/erase-certificates` y pasa a ruta propia `/erase-intake` | `router/routes.js:107-108`: «050 (V2-S02): custodia de activos (Bloque D) con ruta propia; antes era la segunda pestaña» |
| **Ayuda:** sólo «Documentación». GitHub / Bug Report / Feature Request ocultos; Discord eliminado. **Firma de código** oculta con `v-if="false"`. **SSO** descartado | `NavMenu.vue:272-274`, `:138-145` — y lo mismo, palabra por palabra, en `FileBar.vue:255-257`, `:110-117`: **ya estaba así en la v1**, no es un hueco |

**No se encontró** ni un comentario, ni un ADR, ni una nota de versión que diga que
Inventario de medios, el portal público, la reconciliación, la cadena de custodia
o los perfiles asignables se hayan quitado a propósito. No se quitaron: **nunca
llegaron** (ver §4).

---

## 4. Por qué: fechas, no decisiones

Punto de bifurcación `main` ↔ `release/v2`: `1079c0b`, **23-oct-2026**.
En ese commit **no existían** `StorageMediaView.vue`, `VerifyCertificateView.vue`,
`AssetCustodyTimeline.vue`, ni las claves `erase.reconciliation.*`, ni
`assignable_roles`. Comprobado con `git cat-file -e` y `git show` sobre el
merge-base.

Commits de `main` que trajeron cada cosa, todos **posteriores** a la bifurcación:

| Feature | Commit en `main` | Fecha |
|---|---|---|
| 052 · delegación restringida de la administración de usuarios | `53a55a5` | 2026-10-23 |
| 053 T012-T013 · Apéndice C: verificación, concurrencia, acta con equipo | `e14ac8d`, `ab98739` | 2026-10-28 |
| 053 ola 2 · consola de custodia y reconciliación | `f8618ed` | 2026-10-29 |
| Retención de adjuntos por cliente + purga agendada | `572745c`, `ac87d62` | 2026-10-29 |
| 053 ola 4 · portal público de verificación (release 1.4.40) | `2d3ead5` | 2026-11-01 |
| 055 · inventario de medios de almacenamiento (release 1.4.41) | `4728894`, `dac06af` y 4 más | 2026-11-02 |

**Consecuencia práctica:** 11 de las 14 filas de la tabla se cierran con un merge
de `main` a `release/v2` y el re-cableado de dos ítems de navegación
(`nav.storageMedia` en `NavMenu.vue`, la ruta `/verificar`). No se cierran
reescribiendo la v2. Las features 055 y 053 traen además backend (modelos,
migración `0074_storage_media`, `natsapi`), así que el merge no es sólo de
`web/app`.

---

## 5. Hallazgos secundarios (no son hueco de paridad)

- **Código muerto en la v2:** `components/FileBar.vue`, `views/AgentView.vue` y
  `components/SubTableTabs.vue` siguen en el árbol pero **nadie los importa** —
  sólo se los nombra en comentarios. Un auditor que abra `FileBar.vue` creerá que
  la barra de menús sigue viva.
- `web/app/package.json`, en el script `lint:i18n`, todavía lista esos tres
  archivos huérfanos.
- La v2 **agrega** cosas que la v1 no tiene: exportar la tabla del dashboard
  (`ExportTableBtn` en `DashboardView.vue`), indicadores de urgencia clicables,
  `/erase-intake` como ruta propia, y mantenimiento / política / refrescar WMI
  directo en la cabecera del agente.

---

## 6. Qué revisé

- `git show main:<ruta>` y `git diff origin/main HEAD` sobre los 155 archivos de
  `web/app/src` que difieren.
- Lectura completa, lado a lado: `FileBar.vue` ↔ `NavMenu.vue` + `NavRail.vue`;
  `SubTableTabs.vue` ↔ `SectionNav.vue` + `ObsSectionNav.vue`;
  `AgentActionMenu.vue` (plantilla diff-vacía); `AgentView.vue` ↔
  `AgentWorkspace.vue`; `DashboardView.vue`; `MainLayout.vue`; `router/routes.js`.
- Verificación de que los gestores que pasaron a página no perdieron contenido:
  `EditCoreSettings.vue` (13 secciones), `ScriptManager.vue` (7 acciones de fila),
  `AutomationManager.vue` (9 acciones de política), `AlertsManager.vue`,
  `UserPreferences.vue` (todos los campos), `AssetsTab.vue` (14 de 15
  sub-secciones).
- Diff de **todas** las claves i18n (`es.json`, aplanado): 203 claves sólo en v1.
  Ésa es la lista de la que sale §2; no hay hallazgo en la tabla que no tenga una
  clave o una línea detrás.
- `git ls-tree` y nombres de ruta del merge-base contra `HEAD`, para separar
  «quitado por el rediseño» de «nunca llegó».
- Búsqueda de importaciones colgantes en la v2 hacia los componentes que la v1
  tiene y la v2 no: **ninguna**. La v2 es internamente consistente.

---

## 7. Qué elegí NO hacer, y por qué

- **No toqué `src/`.** Era una auditoría. Las 14 filas de §2 son el insumo de otra
  decisión (¿merge o re-implementación?), y esa decisión no es mía.
- **No escribí ni propuse migraciones**, aunque 055 trae la `0074_storage_media`
  en el lado de `main`. Fuera de alcance por pedido explícito.
- **No corrí `eslint` ni la suite de tests.** `web/app/node_modules` **no está
  instalado** en este contenedor, así que habría tenido que instalar dependencias
  —cambio de entorno, no de auditoría— para producir un resultado que de todos
  modos no diría nada de un informe que no modifica código. No hay directorio de
  tests en `web/app`. **No vi fallas de lint o de tests, ni preexistentes ni
  nuevas: no las medí.** Como no cambié ningún archivo de `src/`, ninguna falla
  puede venir de este commit.
- **No hice `checkout` de `main`**, tal como se pidió: todo salió de
  `git show main:<ruta>` y `git diff` sobre la copia de trabajo de la v2.
- **No abrí la consola en un navegador.** Lo que se afirma acá se sostiene en
  rutas, montajes de componente y claves i18n, que es lo que decide si hay o no
  camino. Dos cosas quedan por tanto sin confirmar en pantalla: cómo se ve de
  verdad el riel con 11 iconos apilados, y si la `ContextColumn` alcanza en la
  práctica para sustituir el salto entre equipos del panel inferior de la v1.
  Las dejo marcadas como Baja, no como «sin hueco».
- **No moví ni borré el código muerto** (`FileBar.vue`, `AgentView.vue`,
  `SubTableTabs.vue`): es una limpieza real, pero es un cambio en `src/` y hay
  sesiones trabajando en ramas hermanas. Queda nombrado en §5.
- **No abrí PR ni toqué otra rama.** Commit y push sólo en
  `v2/auditoria-paridad`.
