# Auditoría pre-merge · `git merge main` dentro de `release/v2`

**Rama de este análisis:** `v2/auditoria-premerge` (creada desde `release/v2`, idéntica a su punta).
**Fecha:** 2026-11-05.
**Alcance:** análisis. No se tocó `src/`, no se hizo el merge, no se escribieron migraciones.

## Cómo se obtuvieron los datos

| Dato | Comando |
|---|---|
| merge-base | `git merge-base release/v2 main` → `1079c0b` |
| Commits que trae main | `git log --oneline release/v2..main` → **111 commits** |
| Diff de tres puntos | `git diff release/v2...main --stat` → **199 archivos, +19401 / −559** |
| Reparto | `api/observerrmm` 94 · **`web/app` 23** · `roles/*` 21 · `docs-site/*` 12 · resto (natsapi, scripts, release-notes, CI) 49 |
| Conflictos reales | `git merge-tree --write-tree --name-only release/v2 main` (**sólo lectura**, no toca el árbol de trabajo ni el índice) |
| Hunks de conflicto | `git merge-file` sobre las tres versiones de cada archivo, en el scratchpad de la sesión |

> **Nota de método.** No se ejecutó `git merge`. El inventario de conflictos sale de `git merge-tree`, que simula la fusión en memoria y devuelve el árbol y los conflictos sin modificar el repo. Los hunks se inspeccionaron copiando las tres versiones (base / main / v2) a un directorio temporal fuera del repo. El árbol de trabajo quedó limpio (`git status` vacío) salvo este archivo.

### El resultado de cabecera

`git merge main` produce **7 archivos en conflicto, todos en `web/app`**. Los 176 archivos restantes (backend Django, natsapi en Go, roles de Ansible, docs-site, CI) se fusionan solos: `release/v2` no tocó nada fuera del frontend.

```
CONFLICT (content): web/app/package.json
CONFLICT (content): web/app/src/components/agents/AssetsTab.vue
CONFLICT (content): web/app/src/components/agents/EraseCertificateDetailDialog.vue
CONFLICT (content): web/app/src/components/modals/coresettings/EditCoreSettings.vue
CONFLICT (content): web/app/src/i18n/en.json
CONFLICT (content): web/app/src/i18n/es.json
CONFLICT (content): web/app/src/views/EraseCertificatesView.vue
```

**Lo que más pesa no son los conflictos.** Son las tres cosas que el merge automático resuelve «bien» y deja la v2 rota o muda:

1. `routes.js` se auto-fusiona sin conflicto → las rutas `StorageMedia` y `VerifyCertificate` entran, pero **nadie las enlaza** (la v2 navega por `NavMenu.vue`, no por `FileBar.vue`).
2. En `EraseCertificatesView.vue`, el bloque completo de **Reconciliación** (`main:152-298`, 147 líneas) entra **fuera de todo marcador de conflicto**, bajo `v-show="tab === 'reconciliation'"`. En la v2 `tab` es `computed(() => props.mode)` y ninguna ruta pasa `mode: "reconciliation"` → **código muerto, invisible, que compila y pasa lint**.
3. Las 4 vistas/componentes nuevos de main llegan con el *chrome* v1 (`q-page.q-pa-md`, `div.text-h6`, `q-banner.bg-grey-3`) en vez del de la v2 (`q-page.obs-page`, `ObsPageHead`, `.obs-notice`).

---

## 1 · Pestañas nuevas en `SubTableTabs.vue` → `SECTIONS` + `SectionNav`

**No las encontré. `main` no toca `SubTableTabs.vue`.** Esto es lo que revisé:

| Verificación | Comando | Resultado |
|---|---|---|
| ¿main cambia `SubTableTabs.vue`? | `git diff $BASE main -- .../SubTableTabs.vue` | **vacío** |
| ¿la v2 lo cambia? | `git diff $BASE release/v2 -- .../SubTableTabs.vue` | **vacío** |
| ¿coinciden las listas? | `q-tab name=` en `SubTableTabs.vue:17-103` vs `SECTIONS` en `views/AgentWorkspace.vue:89-102` | **paridad 12/12** |
| ¿y `SectionNav`? | `components/agents/workspace/SectionNav.vue:31-54` | **12 claves, 3 grupos, paridad** |

Las 12 en los tres sitios: `summary`, `checks`, `tasks`, `patches`, `software`, `assets`, `history`, `actividad`, `notes`, `debug`, `audit`, `erase`.

**→ `SECTIONS` (`AgentWorkspace.vue:89`) y `SectionNav.vue:31` no necesitan ninguna entrada nueva. Trabajo: 0.**

### Pero sí hay dos pestañas nuevas, en otros dos sitios

Main no agregó secciones al espacio de trabajo; agregó pestañas **dentro** de dos pantallas. Las dos requieren adaptación manual porque la v2 reemplazó el contenedor de pestañas por otra cosa.

| # | Pestaña nueva (main) | Dónde nace en main | Qué hizo la v2 con ese contenedor | Adaptación en la v2 |
|---|---|---|---|---|
| 1a | `storage_media` — «Medios» | `components/agents/AssetsTab.vue:43` (`q-tab`) + `:95-96` (`q-tab-panel` + `StorageMediaDetail`) + `:111` (import) + `:115` (`components:`) | Cambió `q-tabs`/`q-tab-panels` por una lista de `q-expansion-item` sobre `assetOptions` | Agregar `["storage_media", "storageMedia"]` al array de `assetOptions` (**`AssetsTab.vue:83`**, tras `["encryption","encryption"]` en `:82`) y una tercera rama al `v-if/v-else-if` de **`AssetsTab.vue:28-35`** que monte `StorageMediaDetail`. Hoy la cadena es binaria (`encryption` / todo lo demás → `WmiDetail`), así que `storage_media` caería en `WmiDetail` y pintaría `undefined`. |
| 1b | `reconciliation` — «Reconciliación» | `views/EraseCertificatesView.vue:30` (`q-tab`) + `:152-298` (el panel completo, 147 líneas) | Borró el `q-tabs` entero: certificados e ingresos son dos rutas que comparten la vista vía `props.mode` (`routes.js:99` y `:110`) | Ruta nueva `EraseReconciliation` con `props: { mode: "reconciliation" }` tras **`routes.js:116`**, entrada en **`NavMenu.vue`**, y `erase.reconciliation.title` ya viene en i18n. **Si no se hace, el panel queda en el archivo y no se puede llegar a él.** |

**Conflicto de `AssetsTab.vue`:** 1 hunk, el `<template>` completo (v2 reescribió 92 líneas → 36). Resolución: **quedarse con el lado v2 íntegro** y reinyectar sólo `storage_media` en los dos puntos de arriba. No hay que mirar el lado main más allá de las 3 líneas que agrega.

**Estimación bloque 1:** 1a = 10 min (2 ediciones de una línea y media). 1b = **2–3 h**: hay que decidir si Reconciliación es una tercera ruta hermana o una sección, portar el panel al *chrome* de la v2, y arrastrar su cableado (`recLoading`, `recReport`, `recFilters`, `recPagination`, `recMetrics`, `recClientColumns`, `recMissingColumns`, `onRecRequest`, `loadReconciliation`, `clientOptions` + `fetchReconciliation` de `api/erase.js`).

---

## 2 · Destinos nuevos en `FileBar.vue` → `NavMenu.vue`

Main agrega **exactamente un** `q-item` a `FileBar.vue` (todo el diff del archivo son 6 líneas, `FileBar.vue:175-181`).

| # | Destino | Ruta nombrada | Clave i18n | En main | Dónde va en la v2 | Estado tras merge automático |
|---|---|---|---|---|---|---|
| 2a | Medios de almacenamiento | `StorageMedia` | `nav.storageMedia` | `FileBar.vue:176` (entre `nav.diskEncryption` y el bloque Erase) | **`NavMenu.vue:201`** — justo después del `q-item` de `DiskEncryption` (`:198-200`) y antes del comentario de Observer Erase (`:201-202`), para conservar el mismo orden que main | **Ruta viva, inalcanzable.** `routes.js` se auto-fusiona y la ruta existe; `NavMenu.vue` no la menciona. Sólo se llega escribiendo `/storage-media` a mano. |
| 2b | Portal público de verificación | `VerifyCertificate` | — | **no está en `FileBar.vue`** (es deliberado: ruta pública, `/verificar/:certificate_id?`, sin `meta.requireAuth`, fuera de `MainLayout`) | **nada en `NavMenu.vue`** | **Funciona.** `router/index.js` no lo toca ninguna de las dos ramas y la guardia sólo actúa sobre `meta.requireAuth`. Pero ver §3: es la única página que ve un auditor externo y llega con la piel v1. |

Revisado también: **`NavRail.vue`** sólo lleva gestores (`Scripts`, `Automation`, `Alerts`, `Settings`, líneas 79-81) — ningún destino de «Herramientas», así que no necesita nada.

**Estimación bloque 2:** 2a = **15 min** (3 líneas en `NavMenu.vue`, `nav.storageMedia` ya viene traducida en ambos idiomas). 2b = 0 min de navegación.

---

## 3 · Hex y `rgba()` hardcodeados que llegan de main

### 3.1 · La respuesta literal: dos ocurrencias, y **ninguna la trae main**

Busqué `#rrggbb`/`#rgb` y `rgba?(` en las 21 líneas de `web/app/src` que main modifica, sobre el lado `+` del diff (`git diff -U0 $BASE main`). **Cero resultados.** Grep directo sobre los blobs de main de los 13 componentes tocados:

| archivo:línea (en main) | Ocurrencia | base | main | v2 | Veredicto |
|---|---|---|---|---|---|
| `components/agents/EraseCertificateDetailDialog.vue:344` | `border-bottom: 1px solid rgba(128, 128, 128, 0.2)` | sí (`:292`) | sí | **no — ya tokenizado** (`var(--obs-border)`, `:368`) | **No lo trae main.** La v2 ya lo convirtió. El merge simulado conserva el token (`var(--obs-border)` en la línea 438 del archivo fusionado) porque el conflicto está en `<script>`, no en `<style>`. **Riesgo:** resolver el conflicto copiando el lado de main revertiría el token. Vigilar, no portar. |
| `components/modals/coresettings/EditCoreSettings.vue:1438` | `backgroundColor: "#027be3"` | sí (`:1376`) | sí | **sí (`:1455`)** | **PREEXISTENTE** en las tres ramas. La v2 nunca lo tokenizó. No es trabajo de este merge; se nombra y se deja. |

**→ Hex/rgba que haya que convertir por causa del merge: 0.**

### 3.2 · Lo que sí hay: 33 colores crudos de la paleta Material

El trabajo de color real no viene en hex, viene en clases y props de Quasar. Importa la distinción, porque `quasar.variables.sass:22-25` redefine `$primary/$positive/$negative/$warning` con la marca de la v2 → **`color="warning"`, `text-positive` y `text-negative` ya respetan el tema y no son deuda**. Lo que no la respeta es la paleta cruda (`grey-*`, `orange-*`, `deep-orange`, `black`, `white`), que ignora claro/oscuro.

Las 33 ocurrencias, en líneas **añadidas por main**, numeradas sobre la versión de main (`git show main:<archivo>`):

| # | archivo:línea | Ocurrencia | Token / clase de la v2 |
|---|---|---|---|
| 1 | `components/agents/AssetCustodyTimeline.vue:7` | `text-grey-7` | `var(--obs-muted)` |
| 2 | `components/agents/AssetCustodyTimeline.vue:20` | `color="white"` | `var(--obs-on-brand)` |
| 3 | `components/agents/AssetCustodyTimeline.vue:29` | `text-grey-7` | `var(--obs-muted)` |
| 4 | `components/agents/AssetCustodyTimeline.vue:37` | `bg-grey-2 text-grey-8` | `.obs-notice` |
| 5 | `components/agents/AssetCustodyTimeline.vue:46` | `text-grey-7` | `var(--obs-muted)` |
| 6 | `components/agents/AssetCustodyTimeline.vue:68` | `text-grey-7` | `var(--obs-muted)` |
| 7 | `components/agents/AssetCustodyTimeline.vue:71` | `text-grey-6` | `var(--obs-faint)` |
| 8 | `components/agents/EraseCertificateDetailDialog.vue:61` | `bg-orange-1 text-orange-9` | `.obs-notice--warning` ⚠ **no existe** |
| 9 | `components/agents/StorageMediaDetail.vue:6` | `text-grey` | `var(--obs-muted)` |
| 10 | `components/agents/StorageMediaDetail.vue:18` | `bg-orange-2 text-black` | `.obs-notice--warning` ⚠ |
| 11 | `components/agents/StorageMediaDetail.vue:20` | `color="orange"` | `color="warning"` |
| 12 | `components/agents/StorageMediaDetail.vue:29` | `bg-grey-3 text-black` | `.obs-notice` |
| 13 | `components/agents/StorageMediaDetail.vue:37` | `bg-grey-3 text-black` | `.obs-notice` |
| 14 | `components/agents/WipeOrderDialog.vue:43` | `bg-orange-1 text-orange-9` | `.obs-notice--warning` ⚠ |
| 15 | `components/agents/WipeOrderDialog.vue:53` | `bg-grey-3 text-black` | `.obs-notice` |
| 16 | `components/agents/WipeOrderDialog.vue:56` | `color="grey-7"` | `var(--obs-muted)` |
| 17 | `components/modals/coresettings/EditCoreSettings.vue:1035` | `text-grey` | `var(--obs-text-2)` |
| 18 | `components/modals/coresettings/EditCoreSettings.vue:1055` | `text-grey` | `var(--obs-text-2)` |
| 19 | `views/EraseCertificatesView.vue:153` | `text-grey-7` | `var(--obs-muted)` |
| 20 | `views/EraseCertificatesView.vue:218` | `text-grey-7` | `var(--obs-muted)` |
| 21 | `views/EraseCertificatesView.vue:240` | `text-grey-7` | `var(--obs-muted)` |
| 22 | `views/EraseCertificatesView.vue:261` | `text-grey-7` | `var(--obs-muted)` |
| 23 | `views/EraseCertificatesView.vue:265` | `text-grey-7` | `var(--obs-muted)` |
| 24 | `views/EraseCertificatesView.vue:273` | `color="deep-orange"` | `color="warning"` + `.obs-chip-neutral` si aplica |
| 25 | `views/EraseCertificatesView.vue:399` | `bg-orange-1 text-orange-9` | `.obs-notice--warning` ⚠ |
| 26 | `views/EraseCertificatesView.vue:629` | `clase: "text-deep-orange"` | `text-warning` |
| 27 | `views/StorageMediaView.vue:21` | `bg-grey-3 text-black` | `.obs-notice` |
| 28 | `views/VerifyCertificateView.vue:13` | `text-grey-7` | `var(--obs-muted)` |
| 29 | `views/VerifyCertificateView.vue:43` | `bg-orange-1` | `.obs-notice--warning` ⚠ |
| 30 | `views/VerifyCertificateView.vue:49` | `bg-grey-3` | `.obs-notice` |
| 31 | `views/VerifyCertificateView.vue:58` | `text-grey-7` | `var(--obs-muted)` |
| 32 | `views/VerifyCertificateView.vue:71` | `color="white"` | `var(--obs-on-brand)` |
| 33 | `views/VerifyCertificateView.vue:87` | `text-grey-7` | `var(--obs-muted)` |

Por archivo: `EraseCertificatesView.vue` 8 · `AssetCustodyTimeline.vue` 7 · `VerifyCertificateView.vue` 6 · `StorageMediaDetail.vue` 5 · `WipeOrderDialog.vue` 3 · `EditCoreSettings.vue` 2 · `StorageMediaView.vue` 1 · `EraseCertificateDetailDialog.vue` 1.

Las líneas de los 4 archivos que ya existen en la v2 se corren al fusionar; sobre el árbol fusionado simulado quedan en `WipeOrderDialog.vue:43,53,56` · `EraseCertificatesView.vue:164,177,242,264,285,289,297,423,669` · `EraseCertificateDetailDialog.vue:65` · `EditCoreSettings.vue:1073,1093`. Los 4 archivos nuevos entran enteros y conservan su numeración de main.

### 3.3 · Dos cosas que hay que construir antes de tokenizar

- **No existe `.obs-notice--warning`.** `css/app.sass:919` define `.obs-notice--info` y `:924` `.obs-notice--negative`, y nada más. Los 5 avisos ámbar de main (#8, #10, #14, #25, #29) no tienen a dónde ir. Hay que agregar la variante (4 líneas, calcada de `--negative` usando `var(--q-warning)`).
- **Los tokens semánticos están definidos y no expuestos.** `quasar.variables.sass:66-68` y `:106-108` definen `$obs-d-warning/-negative/-positive` y `$obs-l-*`, pero `css/app.sass` **no los publica** como `--obs-warning` / `--obs-negative` / `--obs-positive`, y ningún `.vue` los usa (grep en `web/app/src`: 0 resultados). O se exponen, o la conversión se apoya en `var(--q-warning)`.

### 3.4 · El bloque de color que más se nota

`views/StorageMediaView.vue` es la hermana literal de `views/DiskEncryptionView.vue`: misma forma, misma cabecera, mismo aviso «sólo Windows». La v2 ya convirtió `DiskEncryptionView.vue` (`git diff $BASE release/v2 --` = 25+/29−), y **ese diff es la receta exacta**:

```
q-page.q-pa-md                  → q-page.obs-page
div.row + div.text-h6 + q-space → <ObsPageHead :title :crumbs>  (+ import e components)
q-btn dense flat + q-tooltip    → q-btn outline no-caps .obs-page__btn :label
q-banner.bg-grey-3.text-black   → div.obs-notice[role=note]
div.row.q-col-gutter-md + col-* → div.obs-page__filters
q-select filled                 → q-select outlined .obs-page__field
q-badge :color                  → + :class="{ 'obs-chip-neutral': ... === 'grey' }"
q-td de un dato técnico         → q-td.mono
```

`VerifyCertificateView.vue` necesita lo mismo, y es **la más urgente de las dos**: es pública, sin sesión, y el destinatario es un cliente, un auditor o un tribunal. Es la única pantalla del producto que alguien de fuera va a ver, y llegaría con la piel v1 mientras el resto de la consola es v2.

**Estimación bloque 3:**

| Sub-bloque | Trabajo |
|---|---|
| `.obs-notice--warning` + exponer `--obs-warning/-negative/-positive` | **30 min** |
| `StorageMediaView.vue` y `VerifyCertificateView.vue` al *chrome* v2 (receta `DiskEncryptionView`) | **2 h** (1 h cada una) |
| `AssetCustodyTimeline.vue` + `StorageMediaDetail.vue` (7 + 5 ocurrencias, componentes embebidos, sin cabecera de página) | **1 h** |
| Las 14 restantes en los 4 archivos que ya existen en la v2 | **1 h** |
| **Total bloque 3** | **~4,5 h** |

---

## 4 · Claves de i18n: `es.json` y `en.json`

Análisis hecho aplanando los tres JSON a rutas con punto y comparando clave por clave (`base=1079c0b`, `main`, `release/v2`), para los dos idiomas.

### 4.1 · Los números

| | `es.json` | `en.json` |
|---|---|---|
| Claves en base | 3150 | 3150 |
| Claves en main | 3353 | 3353 |
| Claves en v2 | 3293 | 3293 |
| **main agrega** | **+203** | **+203** |
| **v2 agrega** | **+143** | **+143** |
| main borra | **0** | **0** |
| v2 borra | **0** | **0** |
| main modifica valor | 3 | 0 |
| v2 modifica valor | 5 | 2 |
| **Claves agregadas por AMBOS (colisión de nombre)** | **0** | **0** |

Los dos archivos están en conflicto, pero **el conflicto es textual, no semántico**: ninguna clave que agrega main existe en la v2, y al revés. Ningún borrado por ninguna de las dos partes. La resolución de fondo es **unión**.

### 4.2 · Qué agrega main (203 claves por idioma)

| Namespace | Claves | Para qué |
|---|---|---|
| `erase.*` | **129** | `custody` 27 · `reconciliation` 24 · `verify` 16 · `detail` 14 · `certify` 11 · `intakeForm` 9 · `disposition` 7 · `mediaType` 7 · `verificationMethod` 5 · `retention` 5 · `verificationResult` 2 · `intakeScanHint` 1 · `view` 1 |
| `storageMedia.*` | **64** | `detail` 17 · `busType` 9 · `verdict` 6 · `verdictHelp` 6 · `mediaType` 5 · `selfEncrypting` 4 · `warnings` 3 · `col*` 6 · `filter*` 3 · `title`/`refresh`/`loading`/`noData`/`windowsOnlyNotice` 5 |
| `editCoreSettings.*` | 6 | `eraseAttachmentRetentionDays(+Hint)`, `eraseAttachmentPruneEnabled(+Hint)`, `erasePublicVerifyEnabled(+Hint)` |
| `rolesForm.*` | 2 | `assignableRoles`, `assignableRolesHint` |
| `agentTabs.assets.storageMedia` | 1 | rótulo «Medios» de la pestaña de §1a |
| `nav.storageMedia` | 1 | rótulo del destino de §2a |

### 4.3 · Qué agrega la v2 (143 claves por idioma)

`agentWorkspace` 34 · `fleet` 27 · `automationManager` 21 · `scriptManager` 17 · `alertsManager` 14 · `navRail` 12 · `settingsPage` 10 · `erase` 2 · `lostEquipment` 2 · `reporting` 2 · `nav` 1 · `userPreferences` 1.

### 4.4 · Resolución por clave, a tres vías

| Caso | Claves | base | main | v2 | Resolución |
|---|---|---|---|---|---|
| **A. Sólo main agrega** | **203 × 2 idiomas** | ausente | nuevo | ausente | **Tomar main.** Unión. Sin decisión. |
| **B. Sólo v2 agrega** | **143 × 2 idiomas** | ausente | ausente | nuevo | **Tomar v2.** Unión. Sin decisión. |
| **C. Ambos modifican, cambio IDÉNTICO** | 3, sólo `es.json`: `activityMonitoring.globalOff`, `agentActivity.source_global`, `editCoreSettings.tabEmployeeMonitoring` | `… Employee Monitoring …` | `… Monitoreo de empleados …` | `… Monitoreo de empleados …` | **Cualquiera de los dos: el texto es byte a byte el mismo.** Es el mismo cambio hecho dos veces (main `f47eefe`, v2 `55f08d8`). Git lo resuelve solo y no aparece en ningún marcador. |
| **D. Sólo v2 modifica** | 2 por idioma: `alertTemplate.addNumberMessage`, `editCoreSettings.addNumberMessage` | `<span class='text-red'>` / `text-green` | = base | `<span class='mono'>` | **Tomar v2.** Es precisamente la des-paletización del §3 llevada a los textos. Main no los toca → auto-merge limpio, sin riesgo. |
| **E. Ambos agregan la misma clave con valor distinto** | **0** | — | — | — | **No existe.** Nada que decidir. |
| **F. main modifica / v2 borra, o al revés** | **0** | — | — | — | **No existe.** Ninguna rama borra claves. |

### 4.5 · Dónde choca el texto (es donde se trabaja a mano)

`git merge-file` da **exactamente 2 hunks por archivo**, iguales en `es.json` y `en.json`, y por la misma razón: las dos ramas **añadieron al final del mismo bloque**, así que la última clave de un lado lleva coma y la del otro no.

| Hunk | Líneas (archivo fusionado) | Namespace | Lado v2 | Lado main | Resolución |
|---|---|---|---|---|---|
| 1 | 3570–3752 | dentro de `erase.*` | 67 líneas: cierra `erase.orders` con `filterStatus`, `search`, y sigue con la escala de tiempo (`min`/`h`/`d`) | 113 líneas: abre `erase.disposition`, `mediaType`, `certify`, `custody`, `reconciliation`, `verify`, `retention`, `verificationMethod`, `verificationResult` | **Unión: pegar los dos bloques.** Único cuidado: la coma tras la última clave del bloque v2. |
| 2 | 3854–3948 | nivel raíz, tras `activityLive` | 13 líneas: abre `settingsPage` | 79 líneas: abre `storageMedia` completo | **Unión: pegar los dos bloques.** Misma coma. |

Namespaces de nivel 1 tocados por ambos: **`erase` y `nav`** — los dos únicos sitios de adyacencia textual. De nivel 2: **ninguno**. Por eso sólo hay 2 hunks y no 20.

Lo único que la v2 agrega en esas dos zonas: `nav.eraseIntake` («Ingresos de activos» / «Asset intake»), `erase.orders.filterStatus`, `erase.orders.search`.

**Estimación bloque 4:** **45 min** por los dos archivos. Son 4 hunks de «pegar los dos lados y arreglar una coma». Verificación obligatoria después — que los dos archivos sean JSON válido, queden con **3496 claves** (3150 + 203 + 143) y la **misma cuenta entre sí**; si `es` y `en` no empatan, falta una clave en un idioma:

```bash
python3 -c "
import json
def n(d): return sum(n(v) if isinstance(v, dict) else 1 for v in d.values())
for f in ['web/app/src/i18n/es.json', 'web/app/src/i18n/en.json']:
    print(f, n(json.load(open(f))))
"
```

---

## 5 · Conflictos en las listas de `lint:i18n` (resolución por unión)

Hay **dos** listas, no una, y se comportan distinto.

### 5.1 · `web/app/package.json` → `scripts.lint:i18n` — **CONFLICTO**

Es una **única línea** con 173 rutas separadas por espacios. Cualquier cambio en los dos lados choca por fuerza: git compara líneas enteras.

| | Entradas | Agrega vs base | Quita vs base |
|---|---|---|---|
| base | 173 | — | — |
| main | 177 | **+4** | **0** |
| v2 | 187 | **+14** | **0** |
| **unión** | **191** | | |

(Conteo de rutas de archivo, descartando los 6 tokens de cabecera del comando: `eslint --no-eslintrc -c .eslintrc.js --ext .vue`. Sin duplicados en ninguna de las tres ramas.)

**Las 4 de main:**

| # | Entrada |
|---|---|
| 1 | `src/components/agents/AssetCustodyTimeline.vue` |
| 2 | `src/components/agents/StorageMediaDetail.vue` |
| 3 | `src/views/StorageMediaView.vue` |
| 4 | `src/views/VerifyCertificateView.vue` |

**Las 14 de la v2:**

| # | Entrada | | # | Entrada |
|---|---|---|---|---|
| 1 | `src/components/agents/AgentLocationDialog.vue` | | 8 | `src/components/shell/ObsSectionNav.vue` |
| 2 | `src/components/agents/workspace/ActionBar.vue` | | 9 | `src/views/AgentWorkspace.vue` |
| 3 | `src/components/agents/workspace/AgentHeader.vue` | | 10 | `src/views/AlertsView.vue` |
| 4 | `src/components/agents/workspace/ContextColumn.vue` | | 11 | `src/views/AutomationView.vue` |
| 5 | `src/components/agents/workspace/SectionNav.vue` | | 12 | `src/views/PreferencesView.vue` |
| 6 | `src/components/shell/NavMenu.vue` | | 13 | `src/views/ScriptsView.vue` |
| 7 | `src/components/shell/NavRail.vue` | | 14 | `src/views/SettingsView.vue` |

**Resolución: unión de 191 entradas.** Ninguna rama quita nada, así que la unión es segura y no hay que elegir. Reconstruir la línea en vez de editarla a ojo:

```bash
python3 - <<'PY'
import json, subprocess
def lst(rev):
    s = json.loads(subprocess.run(["git","show",f"{rev}:web/app/package.json"],
                                  capture_output=True,check=True).stdout)["scripts"]["lint:i18n"]
    return s.split()
v2, main = lst("origin/release/v2"), lst("origin/main")
h = v2.index("src/views/LoginView.vue")   # 6: eslint --no-eslintrc -c .eslintrc.js --ext .vue
union = v2[h:] + [f for f in main[h:] if f not in v2[h:]]
assert len(union) == len(set(union)) == 191, len(union)
print(" ".join(v2[:h] + union))
PY
```

Además la v2 agrega dos dependencias (`@fontsource/archivo`, `@fontsource/jetbrains-mono`) en otra parte de `package.json`; main no toca esa zona y se auto-fusiona.

### 5.2 · `web/app/.eslintrc.js` → la otra lista — **SIN CONFLICTO**

El mismo allowlist existe también como `files:` override dentro de `.eslintrc.js`, pero ahí es **multilínea**, así que git lo fusiona solo. `git merge-tree` lo confirma: `Auto-merging web/app/.eslintrc.js`, sin `CONFLICT`.

| | Agrega | Dónde |
|---|---|---|
| main | **+4** (`StorageMediaView.vue` tras `.eslintrc.js:163`, `StorageMediaDetail.vue` tras `:165`, `VerifyCertificateView.vue` tras `:172`, `AssetCustodyTimeline.vue` tras `:177`) | bloque de Erase/cifrado |
| v2 | +14 | otra región del archivo |

**→ Trabajo manual: 0. Pero verificar que las dos listas quedan consistentes:** si `package.json` lista un archivo que `.eslintrc.js` no exceptúa (o al revés), `lint:i18n` falla o deja pasar texto crudo. Las dos deben terminar con las mismas 18 entradas nuevas (4 de main + 14 de la v2); `package.json` queda en 191 rutas.

**Estimación bloque 5:** **20 min** (reconstruir una línea con el script de arriba + comprobar paridad entre las dos listas).

---

## 6 · Los otros 3 conflictos de código

Los conflictos de `AssetsTab.vue` (§1a), `package.json` (§5.1) y los dos i18n (§4.5) ya están arriba. Faltan tres.

| Archivo | Hunks | Dónde | Qué pasa | Resolución | Trabajo |
|---|---|---|---|---|---|
| `views/EraseCertificatesView.vue` | **3** | 22–46, 152–165, 497–508 (archivo fusionado) | **H1:** main agrega la 3ª pestaña `reconciliation` al `q-tabs`; la v2 borró el `q-tabs` y usa `ObsPageHead` + rutas. **H2:** main agrega un botón «Ver custodia» (`erase.custody.view` → `openCustody`) a las acciones de fila, y pone `color="deep-orange"` donde la v2 tiene `color="primary"`. **H3:** en `setup()`, main agrega `const sep = "·"` y `tab = ref("certificates")`; la v2 tiene `tab = computed(() => props.mode)` + `pageTitle` + `intakeSearch`. | **H1:** quedarse con la v2 + ruta nueva (§1b). **H2:** quedarse con `color="primary"` y **sí** portar el botón de custodia (`AssetCustodyTimeline.vue` y `fetchCustodyEvents` llegan de main y se auto-fusionan — en el archivo fusionado: import en `:473`, `openCustody` en `:616`, ya expuesto en el `return` en `:940`; en main son `:448` y `:576`). **H3:** base la v2, agregar `sep`. | **2–3 h**, contando §1b |
| `components/agents/EraseCertificateDetailDialog.vue` | **1** | 199–309 | El array `rows` del detalle. Main le agrega **16 filas** (`equipment_make/model/hostname`, `media_type/origin/disposition/+detail`, `verification_method/evidence`, `concurrence_name/role/contact/at`, `document_hash`, `signature_alg`, `signing_key_id`) y usa `labelMediaType`/`labelDisposition`/`labelVerificationResult`/`labelVerificationMethod` de `utils/erase.ts` (archivo nuevo, se auto-fusiona: el import queda en `:153-157` del archivo fusionado). La v2 sólo reformateó el array con prettier (objetos multilínea). | **Tomar el conjunto de filas de main** — es el contrato de datos del Apéndice C, no estilo — y pasarle `npm run format`. El `<style>` no está en conflicto, así que `var(--obs-border)` sobrevive solo (línea 438 del archivo fusionado). **No copiar el lado main del `<style>`.** | **1 h** (mecánico, pero hay que leer 16 filas y no perder ninguna) |
| `components/modals/coresettings/EditCoreSettings.vue` | **2** | 971–1101, 1274–1323 | **H1:** main agrega 3 ajustes de Erase (`eraseAttachmentRetentionDays`, `eraseAttachmentPruneEnabled`, `erasePublicVerifyEnabled`) y cierra con `</q-tab-panel>`; la v2 convirtió los `q-tab-panels` en `<div>` de sección. **H2:** divergencia pura de envoltorio e indentación (`</div>` vs `</q-tab-panel>`), main no agrega nada. | **H1:** conservar los `<div>` de la v2 e insertar los 3 ajustes reindentados 2 espacios menos (las 6 claves i18n ya vienen, §4.2). **H2:** quedarse con el lado v2 tal cual. | **1 h** |

---

## 7 · Resumen de esfuerzo

| Bloque | Trabajo | Riesgo si se omite |
|---|---|---|
| §1a `storage_media` en `assetOptions` | 10 min | La subsección pinta `undefined` |
| §1b Reconciliación como ruta de la v2 | 2–3 h | 155 líneas de código muerto, invisible, que compila |
| §2a `StorageMedia` en `NavMenu.vue` | 15 min | Panel inalcanzable salvo por URL a mano |
| §3 color: variante `--warning` + 2 vistas al *chrome* v2 + 33 ocurrencias | 4,5 h | Pantallas con piel v1, una de ellas **pública** |
| §4 unión de i18n (4 hunks) | 45 min | JSON inválido → la app no arranca |
| §5 unión de `lint:i18n` (191 entradas) | 20 min | La compuerta deja pasar texto crudo |
| §6 `EraseCertificatesView` (3 hunks) | incluido en §1b | — |
| §6 `EraseCertificateDetailDialog` (16 filas) | 1 h | El certificado pierde el Apéndice C |
| §6 `EditCoreSettings` (2 hunks) | 1 h | Tres ajustes de Erase sin UI |
| **Total** | **~10–11 h** · **1,5 días de trabajo** | |

Supuestos de la estimación: una sola persona, que conoce las dos ramas, sin contar revisión de código ni prueba manual en navegador. **No incluye** verificar que `lint`, `lint:i18n` y `quasar build` pasan después: no se pudo medir la línea base (ver §8).

**Orden sugerido:** §4 y §5 primero (sin ellos la app no arranca y la compuerta no sirve) → §6 (que el merge quede compilando) → §1a y §2a (10 + 15 min que vuelven alcanzable lo que ya entró) → §1b → §3, dejando `VerifyCertificateView.vue` para el final pero **no fuera del merge**, por ser pública.

---

## 8 · Preexistentes: nombrados, no tocados

- **`#027be3` en `EditCoreSettings.vue:1455`** (v2) — hex crudo en las tres ramas. No lo trae el merge.
- **Deuda de color propia de la v2, ajena a main:** 7 archivos `.vue` con hex en `web/app/src` (`CheckGraph.vue` 7 ocurrencias, `ObserverTable.vue` 2, `RegistryManager.vue` 2, `EditCoreSettings.vue` 1, `AlertTemplateRelated.vue` 1, `CommandStream.vue` 1, `RelationsView.vue` 1) y 3 con `rgba(`. Ninguno tocado por main.
- **`$obs-*-warning/-negative/-positive` definidos y nunca expuestos** (`quasar.variables.sass:66-68`, `:106-108`) — hueco previo del sistema de tokens, que este merge saca a la luz (§3.3) pero no causa.
- **No se verificó `lint`, `lint:i18n` ni `quasar build`:** `web/app/node_modules` no está instalado en esta sesión. **No hay línea base**, así que cualquier fallo posterior al merge no se podrá atribuir sin medir antes. **Recomendación: correr `npm ci && npm run lint && npm run lint:i18n` en `release/v2` ANTES del merge y guardar la salida.** Sin eso no se distingue lo que rompió el merge de lo que ya estaba roto.
- **No hay suite de tests de frontend** en `web/app` (ningún `*.spec.js` / `*.test.js`, ningún directorio `test/`). La red de seguridad de este merge es `lint:i18n`, el build y la prueba manual. No hay más.

---

## 9 · Lo que elegí NO hacer, y por qué

| No hice | Por qué |
|---|---|
| **El merge.** Ni en esta rama ni en un *worktree* aparte. | Lo pediste explícitamente. Para los conflictos usé `git merge-tree --write-tree` (simula en memoria, no toca índice ni árbol) y `git merge-file` sobre copias en el scratchpad. El árbol de trabajo quedó limpio: `git status` sólo muestra este archivo. Lo digo porque «7 archivos en conflicto» es un dato medido, no estimado, y conviene que se sepa cómo. |
| **Tocar `src/`.** Ni una línea, ni siquiera las de 10 minutos del §1a y §2a. | Lo pediste. Por eso el informe da anclas (`NavMenu.vue:201`, `AssetsTab.vue:83`, `routes.js:116`) en vez de parches. |
| **Instalar `node_modules` para correr lint y build.** | Es un efecto secundario grande (red + disco) en una tarea de análisis, y el resultado sin línea base previa no sería interpretable (§8). Preferí nombrar el hueco y decir cómo cerrarlo. |
| **Inventar hallazgos en el punto 1.** | Main no toca `SubTableTabs.vue`: `SECTIONS` y `SectionNav` necesitan **cero** entradas nuevas. Dejé el «no lo encontré» con los cuatro comandos que lo comprueban (§1), y reporté aparte las dos pestañas que sí existen en otros archivos, diciendo claramente que no están donde preguntaste. |
| **Reportar los 2 hex/rgba como trabajo del merge.** | Los dos son preexistentes y lo verifiqué a tres vías (§3.1). Uno la v2 ya lo tokenizó. Contarlos como hallazgo habría inflado el informe con trabajo que no existe. A cambio reporté las 33 ocurrencias de paleta Material cruda, que sí llegan de main, marcando que van más allá de lo que preguntaste literalmente. |
| **Contar `color="warning"`, `text-positive` y `text-negative` como deuda.** | `quasar.variables.sass:22-25` redefine `$warning/$positive/$negative` con la marca de la v2: esas clases ya respetan el tema. Meterlas en la tabla habría generado trabajo falso. |
| **Auditar los 176 archivos de fuera de `web/app`.** | `release/v2` no toca nada fuera del frontend, y `git merge-tree` no reporta un solo conflicto ahí. 94 archivos de `api/observerrmm`, los roles de Ansible, `natsapi` y `docs-site` entran tal cual. Lo verifiqué (`Auto-merging` sin ninguna línea fuera de `web/app`) y no lo analicé más. |
| **Proponer la resolución del §1b.** | Reconciliación como tercera ruta hermana (`/erase-reconciliation`) o como sección dentro de otra pantalla es una decisión de producto sobre la navegación de la v2, no una adaptación mecánica. Documenté el costo de las dos y el cableado que arrastra; la elección es tuya. |
| **Tocar nada de las ramas hermanas** (`v2/auditoria-color`, `v2/t048-remotas`, `v2/t049-acceso`). | Hay tres sesiones trabajando en paralelo. Sólo las listé con `git ls-remote`; no las traje ni las leí. **Aviso:** `v2/auditoria-color` suena a que pisa el §3 de este informe. Vale cruzarlos antes de repartir trabajo. |
