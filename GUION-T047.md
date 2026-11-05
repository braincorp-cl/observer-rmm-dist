# T047 · Guion para hacer `git merge main` dentro de `release/v2`

**Qué es esto.** El guion para que otra persona ejecute el merge rápido y sin
equivocarse. **No contiene el merge hecho**: el árbol de este repositorio está
sin fusionar y ningún archivo de `src/` fue modificado.

**Contra qué estado se escribió.**

| | |
|---|---|
| Repositorio | `braincorp-cl/observer-rmm-dist` |
| Rama de trabajo | `v2/guion-t047` (= `origin/release/v2` + 5 commits) |
| `main` | `origin/main` |
| Base común | `1079c0b9e92f5aa4741713929a562cbea3369ba5` |
| `main` sobre la base | 199 archivos, +19 401 / −559 |
| `release/v2` sobre la base | 147 archivos, +9 521 / −3 392 |

**Advertencia sobre la rama.** El enunciado pedía simular
`git merge-tree release/v2 main`. Lo hice, y además contra `HEAD`
(`v2/guion-t047`), que va 5 commits adelante. **Los conflictos son los mismos 7
archivos en ambos casos**, pero 3 de esos archivos
(`EditCoreSettings.vue`, `en.json`, `es.json`) fueron tocados por esos 5
commits, así que **los bloques finales de este guion están sacados contra
`HEAD`**, que es el árbol real sobre el que se va a trabajar. Si alguien fusiona
parado en `release/v2` puro, los conflictos de esos tres archivos tendrán un
lado "nuestro" distinto.

**Cómo se verificó.** Todo lo que sigue se ejecutó en un **clon desechable** en
`/tmp`, no acá: se hizo el merge de verdad, se aplicaron las resoluciones de la
Parte 1, y se corrieron `lint`, `lint:i18n` y `build` sobre el resultado. **Las
cuatro pasan.** El clon se borró. Donde algo no se pudo verificar, lo digo.

---

## Parte 0 · Punto de partida

```bash
git fetch origin main release/v2
git checkout v2/guion-t047
git merge origin/main --no-commit
```

Resultado esperado: **7 archivos en conflicto, 12 hunks.** Nada más entra en
conflicto; todo lo demás automergea, y ahí está el problema real (Parte 2).

---

## Parte 1 · Los 12 hunks en conflicto

| # | Archivo | Hunks | Resolución en una línea |
|---|---|---|---|
| 1 | `web/app/package.json` | 1 | Unión: lista de la v2 + 4 archivos de `main` |
| 2 | `src/components/agents/AssetsTab.vue` | 1 | Estructura v2 + rama `storage_media` (y agregarla a `assetOptions`) |
| 3 | `src/components/agents/EraseCertificateDetailDialog.vue` | 1 | Tomar `main` y pasar prettier |
| 4 | `src/components/modals/coresettings/EditCoreSettings.vue` | 2 | A: estructura v2 + 3 campos de `main`. B: tomar v2 |
| 5 | `src/i18n/en.json` | 2 | Unión profunda por script |
| 6 | `src/i18n/es.json` | 2 | Unión profunda por script |
| 7 | `src/views/EraseCertificatesView.vue` | 3 | Ver detalle; uno deja código muerto (→ Parte 2, hueco B) |

**Ninguno de los 12 exige una decisión de producto.** Las preguntas abiertas que
sí encontré están en la Parte 2, y ninguna bloquea el merge.

---

### 1 · `web/app/package.json` — el gate `lint:i18n`

**Qué quiere cada lado.** Es una sola línea con la lista de archivos del gate de
traducciones. La v2 agregó 14 archivos (el shell `NavMenu`/`NavRail`, el
`AgentWorkspace` y sus piezas, y las vistas `Alerts`/`Automation`/`Scripts`/
`Settings`/`Preferences`). `main` agregó 4.

**Resolución: unión.** Lo comprobé por diferencia de conjuntos: **nadie borró
nada**, así que no hay nada que decidir. Los 4 de `main` son:

```
src/views/StorageMediaView.vue
src/views/VerifyCertificateView.vue
src/components/agents/StorageMediaDetail.vue
src/components/agents/AssetCustodyTimeline.vue
```

**Por qué importa.** Esos 4 archivos son exactamente las vistas y componentes
nuevos de la Parte 2. Si se resuelve tomando el lado de la v2 (lo cómodo, porque
la línea de la v2 es la más larga), **el gate deja de mirarlos** y cualquier
texto sin traducir que traigan pasa sin que nadie se entere.

**Bloque listo para pegar.** La línea tiene ~11 KB, pegarla a mano es una mala
idea. Usar esto, que es determinista:

```bash
git checkout --ours web/app/package.json
python3 -I scripts/t047-fix-lint-i18n.py
```

Con `scripts/t047-fix-lint-i18n.py`:

```python
#!/usr/bin/env python3
# package.json: toma la lista lint:i18n de la v2 (OURS) y le agrega los 4
# archivos nuevos de main, cada uno junto a su vecino natural.
import json, collections, sys
P = "web/app/package.json"
d = json.load(open(P), object_pairs_hook=collections.OrderedDict)
xs = d["scripts"]["lint:i18n"].split()
NUEVOS = [
    ("src/views/StorageMediaView.vue",                 "src/views/DiskEncryptionView.vue"),
    ("src/components/agents/StorageMediaDetail.vue",   "src/components/agents/DiskEncryptionDetail.vue"),
    ("src/views/VerifyCertificateView.vue",            "src/views/EraseCertificatesView.vue"),
    ("src/components/agents/AssetCustodyTimeline.vue", "src/components/agents/AssetIntakeForm.vue"),
]
for nuevo, vecino in NUEVOS:
    if nuevo in xs:
        continue
    if vecino not in xs:
        sys.exit(f"vecino ausente: {vecino}")
    xs.insert(xs.index(vecino) + 1, nuevo)
d["scripts"]["lint:i18n"] = " ".join(xs)
json.dump(d, open(P, "w"), indent=2)
open(P, "a").write("\n")
print("lint:i18n:", len(xs) - 6, "archivos")
```

**Verificación:** debe imprimir `lint:i18n: 191 archivos` (187 + 4). El `git
diff` de `package.json` debe tener exactamente **una** línea cambiada.

---

### 2 · `AssetsTab.vue` — las pestañas de Activos

**Qué quiere cada lado.**
- **v2**: borró las `q-tabs`/`q-tab-panels` y dejó bloques desplegables
  (`q-expansion-item`) recorriendo `assetOptions` — en la v2 la vista de agente
  no tiene pestañas (UI-E04).
- **`main`**: agregó una pestaña y un panel `storage_media` con
  `<StorageMediaDetail>`.

**Resolución: estructura de la v2, más una rama para `storage_media`.**

**🔴 La trampa.** El `<script>` **automergeó sin conflicto**: el `import` de
`StorageMediaDetail` y su registro en `components:` ya están puestos. Pero
`assetOptions` es del lado de la v2 y **no lista `storage_media`**. Si se
resuelve tomando el lado de la v2 tal cual, el componente queda importado,
registrado y jamás renderizado: la subsección "Medios de almacenamiento"
desaparece del detalle de equipo sin que nada falle.

**Bloque final (reemplaza el hunk completo):**

```vue
    <q-list separator class="obs-assets">
      <q-expansion-item
        v-for="opt in assetOptions"
        :key="opt.value"
        dense
        dense-toggle
        :default-opened="opt.value === 'os'"
        :label="opt.label"
        :data-asset="opt.value"
        header-class="obs-assets__hdr"
      >
        <div class="q-px-md q-pb-sm">
          <DiskEncryptionDetail
            v-if="opt.value === 'encryption' && selectedAgent"
            :agent-id="selectedAgent"
            :status="agentStatus"
          />
          <StorageMediaDetail
            v-else-if="opt.value === 'storage_media' && selectedAgent"
            :agent-id="selectedAgent"
          />
          <WmiDetail
            v-else-if="!['encryption', 'storage_media'].includes(opt.value)"
            :info="assets[opt.value]"
          />
        </div>
      </q-expansion-item>
    </q-list>
```

**Y además**, en `assetOptions` (fuera del hunk, hay que editarlo a mano),
agregar la entrada después de `["encryption", "encryption"],`:

```js
        ["storage_media", "storageMedia"],
```

La clave `agentTabs.assets.storageMedia` ya llega con el i18n de `main`.

---

### 3 · `EraseCertificateDetailDialog.vue` — las filas del certificado

**Qué quiere cada lado.**
- **v2**: sólo reformateó (prettier pasó las filas de una línea a multilínea).
  **Cero cambios semánticos.**
- **`main`**: agregó 14 filas nuevas (equipo desglosado en marca/modelo/hostname,
  tipo y origen del medio, disposición, método y evidencia de verificación,
  bloque de "quien da fe") y pasó 4 valores por funciones de etiqueta.

**Resolución: el lado de `main`, y después prettier.** Todo el contenido es de
`main`; lo único que aporta la v2 es el formato, y prettier lo reproduce exacto.

```bash
git checkout --theirs web/app/src/components/agents/EraseCertificateDetailDialog.vue
cd web/app && npx prettier --write src/components/agents/EraseCertificateDetailDialog.vue
```

Lo verifiqué: el resultado de prettier es idéntico al estilo de la v2. Prettier
además reparte en 3 líneas un `<td :class="{ mono: ... }">{{ field.value }}</td>`
que `main` trajo sin partir — es correcto y deseable.

**Red de seguridad.** Acá el lint protege: `labelMediaType`, `labelDisposition`,
`labelVerificationResult`, `labelVerificationMethod` y las variables `d`, `eq`,
`conc` ya entraron limpias por automerge. Si alguien toma el lado de la v2 por
error, quedan sin usar y **`npm run lint` lo caza**. Es el único de los 7 donde
pasa eso; en los demás el error es silencioso.

---

### 4 · `EditCoreSettings.vue` — dos hunks

#### Hunk A · los campos de retención

**Qué quiere cada lado.**
- **v2**: sacó el envoltorio `<q-tab-panel>` y lo dejó como `<div>`
  (desindentado 2 espacios) — la v2 sirve esto como página
  `/settings/:section` con navegación lateral, no como pestañas.
- **`main`**: agregó **3 campos nuevos** dentro del `<q-tab-panel>`:
  `erase_attachment_retention_days`, `erase_attachment_prune_enabled` y
  `erase_public_verify_enabled`.

**Resolución: la estructura de la v2 (cierre `</div>`), con los 3 campos de
`main` reindentados 2 espacios menos.**

**Comprobé que sí quedan alcanzables**: la sección `retention` está en
`SECTION_GROUPS` (grupo `platform`) y en `SAVABLE`, así que después del merge se
llega por **Ajustes → Plataforma → Retención** y el `PUT /core/settings/` los
guarda. Acá no hay hueco.

**El tercer campo enciende la ruta pública** (`/verificar`), que es la vista de
la que habla el hueco D.

**Bloque final** — va **antes** del `</div>` que cierra el panel, después del
`q-card-section` de `lost_mode_evidence_closed_case_days`:

```vue
              <!-- Feature 053 ola 3 (RNF-06/L-04). Hasta esta ola el plazo
                   existia en la API y no se mostraba NI se leia: se podia
                   configurar, recibir 200 y no configurar nada. -->
              <q-card-section class="row">
                <div class="col-4">
                  {{ $t("editCoreSettings.eraseAttachmentRetentionDays") }}
                </div>
                <div class="col-2"></div>
                <q-input
                  dense
                  outlined
                  type="number"
                  min="366"
                  v-model.number="settings.erase_attachment_retention_days"
                  class="col-6"
                  :hint="
                    $t('editCoreSettings.eraseAttachmentRetentionDaysHint')
                  "
                />
              </q-card-section>
              <q-card-section class="row">
                <div class="col-4">
                  {{ $t("editCoreSettings.eraseAttachmentPruneEnabled") }}
                </div>
                <div class="col-2"></div>
                <div class="col-6">
                  <q-toggle
                    v-model="settings.erase_attachment_prune_enabled"
                    :label="$t('editCoreSettings.eraseAttachmentPruneEnabled')"
                  />
                  <div class="text-caption text-grey">
                    {{ $t("editCoreSettings.eraseAttachmentPruneEnabledHint") }}
                  </div>
                </div>
              </q-card-section>

              <!-- Feature 053 ola 4 (RF-08). Nace apagado: enciende una ruta
                   SIN autenticacion en el dominio de esta instalacion. -->
              <q-card-section class="row">
                <div class="col-4">
                  {{ $t("editCoreSettings.erasePublicVerifyEnabled") }}
                </div>
                <div class="col-2"></div>
                <div class="col-6">
                  <q-toggle
                    v-model="settings.erase_public_verify_enabled"
                    :label="$t('editCoreSettings.erasePublicVerifyEnabled')"
                  />
                  <div class="text-caption text-grey">
                    {{ $t("editCoreSettings.erasePublicVerifyEnabledHint") }}
                  </div>
                </div>
              </q-card-section>
            </div>
```

Después, `npx prettier --write` sobre el archivo: al desindentar, tres
expresiones vuelven a caber en una línea.

#### Hunk B · el bloque de `activity_prune_days`

**Sólo formato.** La v2 desindentó (mismo cambio `q-tab-panel` → `div`) y
prettier repartió la arrow function de `:rules`. `main` no aporta nada
semántico. **Tomar el lado de la v2 tal cual.**

---

### 5 y 6 · `i18n/en.json` y `i18n/es.json`

**Qué quiere cada lado.** El conflicto clásico de JSON: ambos agregaron claves
después de la misma línea. La v2 sumó 144 claves (`navRail`, `agentWorkspace`,
`settingsPage`); `main` sumó 203 (`erase.custody`, `erase.reconciliation`,
`erase.verify`, `erase.retention`, `storageMedia`, los enums de disposición y
verificación).

**Resolución: unión profunda.** Lo verifiqué clave por clave sobre los tres
estados (base / v2 / main):

- **colisiones reales: 0** — ninguna clave fue cambiada a valores distintos por
  los dos lados;
- **borrados: 0** — ninguno de los dos quitó una clave;
- unión: **3 497 claves** en cada idioma (desde 3 150 en la base).

Como no hay nada que decidir, **no resolver esto a mano**: son 4 hunks sobre
~3 500 claves y un error acá es una clave perdida que nadie nota hasta que un
usuario ve un identificador crudo en pantalla.

```bash
python3 -I scripts/t047-union-i18n.py web/app/src/i18n/en.json
python3 -I scripts/t047-union-i18n.py web/app/src/i18n/es.json
```

Con `scripts/t047-union-i18n.py`:

```python
#!/usr/bin/env python3
# Une los i18n del merge: BASE/OURS/THEIRS -> union profunda, orden de OURS primero.
# Uso: python3 -I union-i18n.py <ruta.json>   (con el merge en conflicto)
import json, subprocess, sys, collections

ruta = sys.argv[1]

def etapa(n):
    out = subprocess.run(["git", "show", f":{n}:{ruta}"], capture_output=True, check=True)
    return json.loads(out.stdout, object_pairs_hook=collections.OrderedDict)

base, ours, theirs = etapa(1), etapa(2), etapa(3)

def unir(b, o, t, camino=""):
    if not (isinstance(o, dict) and isinstance(t, dict)):
        # Hoja. Si ambos lados cambiaron distinto respecto de base -> colision real.
        if o != t and o != b and t != b:
            raise SystemExit(f"COLISION REAL en {camino}:\n  base={b!r}\n  ours={o!r}\n  theirs={t!r}")
        return o if o != b else t
    b = b if isinstance(b, dict) else {}
    r = collections.OrderedDict()
    for k in list(o) + [k for k in t if k not in o]:
        if k in o and k in t:
            r[k] = unir(b.get(k), o[k], t[k], f"{camino}.{k}")
        elif k in o:
            if k in b and k not in t:      # theirs lo borro
                continue
            r[k] = o[k]
        else:
            if k in b and k not in o:      # ours lo borro
                continue
            r[k] = t[k]
    return r

res = unir(base, ours, theirs)
with open(ruta, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"{ruta}: {len(json.dumps(res))} bytes, listo")
```

El script **aborta si encuentra una colisión real**, así que si el día del merge
alguien tocó la misma clave en los dos lados, se entera en vez de perderla en
silencio.

**Verificación:** las dos deben quedar en 3 497 claves.

```bash
python3 -c "
import json
f=lambda o: sum(map(f,o.values())) if isinstance(o,dict) else 1
for L in ('en','es'): print(L, f(json.load(open(f'web/app/src/i18n/{L}.json'))))"
```

---

### 7 · `EraseCertificatesView.vue` — tres hunks

#### Hunk 1 · las `q-tabs` de la vista

- **v2**: borró las pestañas. Certificados e Ingresos son **dos rutas**
  (`/erase-certificates` y `/erase-intake`) que comparten la vista vía
  `props.mode`.
- **`main`**: agregó una **tercera** pestaña, `reconciliation`.

**Resolución: el lado de la v2** (sin `q-tabs`, cierre `</ObsPageHead>`).

**🔴 Pero eso deja código muerto.** El panel entero de Reconciliación
automergeó limpio más abajo bajo `v-show="tab === 'reconciliation'"`, y en la v2
`tab` es `computed(() => props.mode)`, alimentado por la ruta, que sólo vale
`"certificates"` o `"intake"`. **Compila, pasa lint y no se ve nunca.** La
reparación está en la Parte 2, hueco B. No se arregla dentro del conflicto.

#### Hunk 2 · los botones de la fila

- **v2**: cambió `color="deep-orange"` → `color="primary"` en el botón de
  certificar (pasada de color V2-G05, commit `c4b9674`: fuera los colores fuera
  de paleta).
- **`main`**: agregó un botón nuevo "Ver custodia" delante.

**Resolución: los dos.** El botón de `main` tal cual (sin color explícito, que
es lo que corresponde a un control sin estado en la v2) y el de certificar con
el `primary` de la v2.

```vue
        <template v-slot:body-cell-actions="props">
          <q-td :props="props" auto-width>
            <q-btn
              dense
              flat
              no-caps
              size="sm"
              icon="timeline"
              :label="$t('erase.custody.view')"
              @click="openCustody(props.row)"
            />
            <q-btn
              dense
              flat
              no-caps
              size="sm"
              color="primary"
              icon="delete_forever"
              :label="$t('erase.view.certifyDestruction')"
              @click="askCertify(props.row)"
            />
          </q-td>
        </template>
```

#### Hunk 3 · la cabecera del `setup()`

- **v2**: `tab` computado desde `props.mode`, más `pageTitle` e `intakeSearch`.
- **`main`**: una constante `sep = "·"`.

**Resolución: unión.** Hay que quedarse con las dos cosas.

**🔴 Trampa silenciosa.** `sep` lo usa la plantilla del panel de Reconciliación,
que automergeó. Si se toma el lado de la v2 y se pierde `sep`, **no falla ni el
build ni el lint**: Vue sólo emite un warning en consola y renderiza vacío.

```js
    const dash = "—";
    // Separador de texto: va por variable y no literal en la plantilla, porque
    // el gate `lint:i18n` trata cualquier texto crudo como falta de traducción.
    const sep = "·";
    const tab = computed(() => props.mode);
    const pageTitle = computed(() =>
      tab.value === "intake"
        ? t("nav.eraseIntake")
        : t("nav.eraseCertificates"),
    );
    const intakeSearch = ref("");
```

---

### Cierre de la Parte 1

```bash
git add -A
cd web/app && npm run lint && npm run lint:i18n && npm run build
```

Las tres pasan sobre el merge resuelto así — lo ejecuté. **Pero pasar las tres
no significa que el merge esté terminado**, y de eso trata la Parte 2.

---

## Parte 2 · Lo que entra limpio y queda mudo

Esta es la parte cara. El merge no deja ni un marcador de conflicto en nada de
lo que sigue, y nada de esto lo detecta `lint`, `lint:i18n` ni `build`.

**Verificación de los tres casos de la medición anterior:**

| Caso reportado | ¿Sigue siendo cierto? |
|---|---|
| Rutas nuevas que nadie enlaza (v2 navega por `NavMenu.vue`, no `FileBar.vue`) | **Sí, pero una sola ruta, no varias** (hueco A) |
| Panel entero bajo un `v-show` que ninguna ruta alimenta | **Sí, exacto** (hueco B) |
| Vistas nuevas con el chrome de la v1, una pública | **Parcialmente** — el problema es más chico de lo que suena (huecos C y D) |

Y aparecieron **dos huecos más** del mismo tipo que no estaban en la lista
(huecos E y F).

---

### Hueco A · La ruta `StorageMedia` no la enlaza nadie

**Qué entra.** Una ruta nueva, limpia, en `router/routes.js`:

```js
      {
        path: "storage-media",
        name: "StorageMedia",
        component: () => import("@/views/StorageMediaView.vue"),
        meta: { requireAuth: true },
      },
```

**Por qué el merge no lo cablea.** `main` sí agregó el enlace — pero en
`src/components/FileBar.vue` (línea 176 post-merge), que es la barra de menús de
la v1. **En la v2 ese archivo no se renderiza en ninguna parte.** Lo comprobé:
`MainLayout.vue` monta `<NavRail />` y nada más; las únicas referencias a
`FileBar` que quedan en el árbol fusionado son **comentarios** (en `NavMenu.vue`
y en `store/index.js`, explicando que la barra se eliminó). La v2 navega por
`src/components/shell/NavMenu.vue`, que tiene el ítem de `DiskEncryption` pero
no el de `StorageMedia`.

La clave `nav.storageMedia` **sí llega** por la unión de i18n, lista y traducida
a los dos idiomas. Lo único que falta es el ítem de menú.

**Qué hacer a mano.** En `src/components/shell/NavMenu.vue`, **después de la
línea 200** (el `</q-item>` que cierra el ítem de `DiskEncryption`, que abre en
la línea 198):

```vue
          <!-- inventario de medios de almacenamiento (feature 055) -->
          <q-item clickable v-close-popup :to="{ name: 'StorageMedia' }">
            <q-item-section>{{ $t("nav.storageMedia") }}</q-item-section>
          </q-item>
```

**Decisión pendiente (chica).** `main` lo puso en el menú **Ver**, junto a
Cifrado de disco. En la v2 el riel tiene grupos distintos. Dejarlo junto a
Cifrado de disco es lo que dice el comentario de la ruta ("hermana del panel de
cifrado") y es lo que propongo; si el riel de la v2 tiene otro grupo pensado para
inventario, va ahí.

**Cómo comprobarlo abriendo la UI.**
1. Entrar a la consola. En el riel izquierdo, abrir el menú **Ver**.
2. **Antes del arreglo**: aparece "Cifrado de disco" y no aparece "Medios de
   almacenamiento". La única forma de llegar al panel es escribir
   `/storage-media` en la barra de direcciones — y si se escribe, **el panel
   carga perfecto**, que es lo que hace el hueco invisible.
3. **Después**: el ítem está, y al hacer clic abre el mismo panel.

---

### Hueco B · El panel de Reconciliación entra completo y no se ve nunca

Éste es el caso del enunciado, y es el más caro de los seis.

**Qué entra.** El panel de Reconciliación de `main` (RF-07) **automergea
entero y sin conflicto**: ~150 líneas de plantilla y ~150 de lógica —
filtros de cliente y período, el cálculo, la tabla por cliente, la tabla de
activos sin certificar, `loadReconciliation()`, sus columnas y el enlace a la
cadena de custodia. Más 68 claves de i18n bajo `erase.reconciliation.*`, ya
traducidas.

**Por qué el merge no lo cablea.** Todo cuelga de
`v-show="tab === 'reconciliation'"`. En `main`, `tab` era un
`ref("certificates")` que movían las `q-tabs`. En la v2, `tab` es:

```js
const tab = computed(() => props.mode);
```

y `props.mode` lo fija la ruta: sólo existen `/erase-certificates`
(`mode: "certificates"`) y `/erase-intake` (`mode: "intake"`). **No hay ninguna
ruta que ponga `mode: "reconciliation"`**, así que la condición nunca es cierta.

El código es válido, está referenciado, compila y **pasa `lint` y `lint:i18n`
sin una sola queja** — justamente porque `v-show` no exige que la condición
pueda ser cierta alguna vez.

**Qué hacer a mano.** Tres ediciones.

**1.** En `src/router/routes.js`, después del bloque de la ruta `EraseIntake`
(el que cierra tras `props: { mode: "intake" }`):

```js
      {
        // 050 (V2-S02) · la reconciliación tenía pestaña propia en la v1;
        // en la v2 cada panel de esta vista es una ruta.
        path: "erase-reconciliation",
        name: "EraseReconciliation",
        component: () => import("@/views/EraseCertificatesView.vue"),
        props: { mode: "reconciliation" },
        meta: {
          requireAuth: true,
        },
      },
```

**2.** En `src/components/shell/NavMenu.vue`, después del ítem `EraseOrders`
(línea ~211 post-merge):

```vue
          <q-item clickable v-close-popup :to="{ name: 'EraseReconciliation' }">
            <q-item-section>{{ $t("erase.reconciliation.title") }}</q-item-section>
          </q-item>
```

(No hace falta crear una clave `nav.*`: `erase.reconciliation.title` ya llega
traducida en los dos idiomas.)

**3.** En `src/views/EraseCertificatesView.vue`, el `pageTitle` del `setup()`
sólo contempla dos modos y con `reconciliation` mostraría "Certificados de
borrado". Reemplazar por:

```js
    const pageTitle = computed(() => {
      if (tab.value === "intake") return t("nav.eraseIntake");
      if (tab.value === "reconciliation") return t("erase.reconciliation.title");
      return t("nav.eraseCertificates");
    });
```

**Cómo comprobarlo abriendo la UI.**
1. Ir a **Certificados de borrado**. Mirar la cabecera de la página: en la v1
   había tres pestañas (Certificados / Ingresos / Reconciliación). **Después del
   merge sin arreglar no hay ninguna pestaña**, y sólo se llega a dos de los tres
   paneles, por el menú. No hay nada en pantalla que insinúe que el tercero
   existe: ésa es exactamente la razón por la que se escapa.
2. Prueba directa: escribir `/erase-reconciliation` en la barra de direcciones.
   **Antes del arreglo** cae en el 404 del producto. **Después** abre el panel
   con sus filtros de cliente y fechas y el botón **Calcular**.
3. Confirmación de que el panel funciona de verdad y no sólo aparece: elegir un
   cliente y un período y pulsar **Calcular**; tienen que salir las cuatro cifras
   (Ingresados / Certificados / Faltantes / Detenidos) y la tabla "Activos sin
   certificar". Si salen, el cableado está completo.

---

### Hueco C · `StorageMediaView` llega con el chrome de la v1

**Qué entra.** `src/views/StorageMediaView.vue`, archivo nuevo (292 líneas).

**Por qué el merge no lo cablea.** Es un archivo nuevo: no hay con qué chocar,
entra tal cual lo escribió `main`. Y `main` lo escribió copiando
`DiskEncryptionView.vue` **anterior** a la conversión de la v2. Las dos vistas
son hermanas (lo dice el comentario de la ruta) y hoy son visiblemente distintas:

| | `DiskEncryptionView` (v2) | `StorageMediaView` (de `main`) |
|---|---|---|
| Envoltorio | `<q-page class="obs-page">` | `<q-page class="q-pa-md">` (L2) |
| Cabecera | `<ObsPageHead :title :crumbs>` | `div.row` + `.text-h6` a mano (L4) |
| Botón refrescar | `outline no-caps .obs-page__btn` con rótulo | `dense flat` con tooltip (L6-15) |
| Aviso "sólo Windows" | `<div class="obs-notice" role="note">` | `<q-banner class="bg-grey-3 text-black">` (L21) |
| Filtros | `.obs-page__filters` + `.obs-page__field`, `outlined` | grilla `row q-col-gutter-md`, `filled` (L28-68) |
| `<q-table>` | — | **idéntica, no hay que tocarla** |

**🔑 Lo importante: la clase `obs-page` no es cosmética, es el gancho.** En
`src/css/app.sass:132` el bloque `.obs-ws, .obs-page` es el que convierte a
tokens los grises por defecto de Quasar: fondo y color de la tarjeta de tabla,
bordes de celdas, **color y fondo de la cabecera de la tabla**, los campos de
formulario y `.text-grey`/`.text-grey-8`. **Sin esa clase nada de eso se
aplica.** No es que se vea "un poco distinto": la cabecera de la tabla y los
campos quedan con la paleta de Quasar mientras la vista hermana de al lado usa
tokens.

**Lo que NO es problema** (lo verifiqué antes de reportarlo): `bg-grey-3`,
`text-black`, `text-grey-7`, `bg-orange-1/2`, `text-orange-9` y `text-grey`
**sí están remapeados a tokens globalmente** en `app.sass:320-340` y `470-480`.
O sea que el color de esos avisos no se rompe. El daño real es el de la clase
`obs-page` y la diferencia de forma con la vista hermana.

**Qué hacer a mano**, en `src/views/StorageMediaView.vue`:
- **L2**: `class="q-pa-md"` → `class="obs-page"`.
- **L3-16**: reemplazar el `div.row` + `text-h6` + botón por
  `<ObsPageHead :title="$t('storageMedia.title')" :crumbs="[$t('nav.agents')]">`
  con el botón de refrescar en el slot, copiando `DiskEncryptionView.vue:3-13`.
  Agregar el `import ObsPageHead` y registrarlo.
- **L21-27**: el `q-banner` → `<div class="obs-notice" role="note">` con
  `<q-icon name="storage" />`, copiando `DiskEncryptionView.vue:18-21`.
- **L28-68**: la grilla `row q-col-gutter-md` → `<div class="obs-page__filters">`
  y los tres `q-select` de `filled` a `outlined class="obs-page__field"`,
  copiando `DiskEncryptionView.vue:23-51`.
- La `<q-table>` (L71+) **no se toca**.

**Cómo comprobarlo abriendo la UI.** Abrir **Cifrado de disco** y **Medios de
almacenamiento** en dos pestañas del navegador y alternar entre ellas:
1. El título: una tiene miga de pan y título de página; la otra sólo un texto en
   negrita pegado arriba a la izquierda.
2. El botón de refrescar: en una es un botón con borde y la palabra
   "Actualizar"; en la otra es sólo un ícono.
3. El aviso de "sólo Windows": en una es un recuadro con borde redondeado; en la
   otra es una franja.
4. Los filtros: en una los campos tienen contorno; en la otra tienen fondo
   relleno.
5. **La prueba decisiva**: mirar la **fila de encabezados de la tabla** en las
   dos. En Cifrado de disco tiene el fondo elevado y el texto atenuado del tema;
   en Medios de almacenamiento no. Si después del arreglo las dos se ven iguales,
   `obs-page` está haciendo su trabajo.

---

### Hueco D · `VerifyCertificateView`, la vista PÚBLICA

**Qué entra.** `src/views/VerifyCertificateView.vue` (167 líneas) y su ruta,
**fuera de `MainLayout` y sin `requireAuth`**:

```js
  {
    path: "/verificar/:certificate_id?",
    name: "VerifyCertificate",
    component: () => import("@/views/VerifyCertificateView.vue"),
  },
```

La abre un tercero sin cuenta: el cliente, un auditor, un tribunal. Se enciende
con el toggle `erase_public_verify_enabled` del hunk A de `EditCoreSettings`.

**Esta sí la pude abrir de verdad**, porque no pide autenticación: compilé el
merge resuelto, serví el `dist` y la cargué en un navegador. Lo que sigue está
medido, no deducido.

**Por qué el merge no lo cablea.** Archivo nuevo otra vez. Y al vivir fuera de
`MainLayout`, **nadie le fija el tema**:

- `src/store/index.js:266` hace `Dark.set(data.dark_mode)` — pero dentro de la
  carga de `dashinfo`, que **exige sesión iniciada**. Un tercero nunca pasa por
  ahí.
- `LoginView.vue:102`, la otra página fuera de `MainLayout`, resuelve esto
  **forzando** `$q.dark.set(true)`.
- `quasar.config.js` **no define `dark`**, así que el default de Quasar es claro.

**Medido en el navegador, sobre el merge resuelto:**

| Ruta | `body` | Fondo |
|---|---|---|
| `/login` | `body--dark` | `rgb(15, 26, 42)` |
| `/verificar` | `body--light` | `rgb(238, 242, 247)` |

Dos páginas públicas del mismo producto, con el tema opuesto. Nadie eligió eso:
es lo que queda cuando una vista nueva no pasa por el único lugar que fija el
tema.

También confirmé que **no tiene** `.obs-page` ni `ObsPageHead`, y que **sí**
hereda las fuentes del producto (`Archivo`) y los remapeos de color globales,
porque `app.sass` es global. Visualmente: una tarjeta blanca sobre fondo pálido,
**sin logo ni nombre del producto en ninguna parte**.

**Qué hacer a mano:**

1. **El tema (objetivo, hay que arreglarlo).** En
   `src/views/VerifyCertificateView.vue`, dentro del `<script setup>` (empieza en
   L102), fijar el tema explícitamente como hace `LoginView`:
   ```js
   import { useQuasar } from "quasar";
   const $q = useQuasar();
   $q.dark.set(true);
   ```
2. **`formatearFecha` (L126)** usa `new Date(valor).toLocaleString()`, que no es
   el formateo de fechas del resto del producto. La fecha de emisión del
   certificado va a salir con otro formato que en el resto de la consola. Usar el
   helper de `src/utils/format.ts`.
3. **El `NotFound` del portal apagado (L6)**: cuando el tenant tiene la función
   apagada, se renderiza `NotFound.vue`, que trae un botón "Volver" que hace
   `$router.push("/")`. Para un tercero sin cuenta eso lo deja en la pantalla de
   login de una instalación ajena. Conviene ocultar ese botón en el contexto
   público.

**❓ Pregunta de producto, no la invento.** ¿El portal público debe llevar el
chrome de la v2 (logo Observer, cabecera de producto) o quedarse neutro a
propósito? Hay un argumento real para cada lado:
- **A favor de ponerle marca**: el destinatario necesita saber de qué
  instalación es el certificado que está verificando; hoy la página no lo dice.
- **A favor de dejarlo neutro**: `erasePublicVerifyEnabledHint` subraya que la
  página "no muestra cliente, equipo ni serie", y la decisión de diseño L-02
  prohíbe convertirla en un oráculo. Poner marca completa empuja en la dirección
  contraria.

No la resuelvo. Lo que sí hay que arreglar pase lo que pase es el tema (punto 1):
hoy no es una decisión de nadie, es un accidente.

**Cómo comprobarlo abriendo la UI.**
1. En **Ajustes → Plataforma → Retención**, encender **"Exponer la verificación
   pública de certificados"** y guardar.
2. Abrir **una ventana de incógnito** (clave: sin sesión) y entrar a
   `https://<instalación>/verificar`.
3. **Antes del arreglo**: la página sale en **claro**. Abrir `/login` en otra
   pestaña de la misma ventana de incógnito: sale en **oscuro**. Las dos son
   públicas, del mismo producto, y no coinciden.
4. **Después**: las dos en oscuro.
5. Con un identificador real de certificado, verificar también que la fecha
   "Emitido:" tenga el mismo formato que la columna de fecha en
   **Certificados de borrado**.

---

### Hueco E · Avisos de la v1 dentro de diálogos que la v2 ya había convertido

**No estaba en la lista de los tres.** Es el mismo mecanismo y lo encontré
barriendo el resto del diff.

**Qué entra.** `main` agrega avisos nuevos a archivos que **la v2 ya había
convertido al patrón `obs-notice`**:

- `src/components/agents/WipeOrderDialog.vue` (automergea limpio): tras el merge
  el diálogo tiene **tres** avisos seguidos. El de arriba (~L25) es el de la v2,
  `class="obs-notice q-ma-md"`. Los dos que agrega `main` justo debajo (L43 y
  L53) son `<q-banner class="bg-orange-1 text-orange-9 q-ma-md">` y
  `<q-banner class="bg-grey-3 text-black q-ma-md">`.
- `src/components/agents/AssetCustodyTimeline.vue` (archivo nuevo, L37):
  `<q-banner dense class="bg-grey-2 text-grey-8 q-mb-md">`.

**Por qué el merge no lo cablea.** Nada que fusionar: uno automergea y el otro es
archivo nuevo. Y el color no avisa, porque `bg-orange-1`, `text-orange-9`,
`bg-grey-3` y `text-black` **sí están remapeados globalmente**. Lo que no se
remapea es la **forma**: `obs-notice` aporta borde de 1px, radio de 8px, padding
propio, `font-size: 13px` y el ícono atenuado a 18px. Un `q-banner` pelado no
tiene nada de eso. Quedan tres avisos pegados con dos formas distintas.

Dos clases además **no están remapeadas en ninguna parte**, ni global ni dentro
de `.obs-page`: **`bg-grey-2`** y **`text-grey-8`** (ésta sólo existe dentro de
`.obs-ws`/`.obs-page`, y `AssetCustodyTimeline` se monta como diálogo, fuera de
ambas). Ahí el color tampoco sale de tokens.

**Qué hacer a mano:**
- `WipeOrderDialog.vue` **L43** y **L53**: `class="..."` → `class="obs-notice
  q-ma-md"`, quitando las clases de paleta.
- `AssetCustodyTimeline.vue` **L37**: → `class="obs-notice q-mb-md"`.

**❓ Pregunta de producto (chica).** El aviso de L43 ("la sobrescritura NO es
sanitización defendible sobre estado sólido") es una **advertencia**, y hoy
`app.sass` sólo define `obs-notice--info` y `obs-notice--negative`; **no existe
`obs-notice--warning`**. Dos opciones: usar `--negative` (defendible: es un
aviso de cumplimiento legal, no un matiz), o agregar un modificador
`--warning` en `app.sass` con `var(--q-warning)`. La segunda es más limpia pero
toca el sistema de diseño. Lo dejo planteado; el aviso neutro de L53 ("no se
sabe qué medio hay") va con `obs-notice` a secas en cualquier caso.

**Cómo comprobarlo abriendo la UI.** Abrir una **orden de borrado** sobre un
equipo con disco de estado sólido inventariado (**Equipos perdidos** → caso
abierto → **Ordenar borrado**). En la parte de arriba del diálogo quedan dos o
tres avisos apilados: **antes del arreglo** el primero tiene borde y esquinas
redondeadas y los de abajo son franjas rectangulares a todo el ancho; **después**
los tres son iguales. Para el de custodia: en **Certificados de borrado**, botón
**Ver custodia** de cualquier fila, y mirar el aviso "Un eslabón no se edita ni
se borra".

---

### Hueco F · `verdictColor` trae la paleta cruda de la v1, con `teal` incluido

**Tampoco estaba en la lista.**

**Qué entra.** `src/utils/storageMedia.js` (archivo nuevo), L34-51:

```js
export function verdictColor(veredicto) {
  switch (veredicto) {
    case "purge_remote":     return "green";
    case "purge_live_image": return "teal";
    case "clear_remote":     return "blue";
    case "virtual_media":    return "purple";
    case "no_category":      return "orange";
    default:                 return "grey";
  }
}
```

Lo consumen `StorageMediaView.vue` (badge de la columna "Categoría alcanzable")
y `StorageMediaDetail.vue` (badge del detalle, dentro de la pestaña Activos).

**Por qué el merge no lo cablea.** Archivo nuevo; nada con qué chocar. Pero la
v2 hizo dos pasadas de color (V2-G05) cuyo criterio es el contrario:

- la vista hermana usa tokens semánticos —
  `{encrypted: "positive", unencrypted: "negative", unsupported: "grey",
  no_data: "warning"}` — y pinta el `grey` con la clase `obs-chip-neutral`,
  que lo saca de `var(--obs-raised)`;
- **`teal` está explícitamente prohibido como color de dato** en la v2. El commit
  `cda299a` de esta misma rama se titula, literalmente, "teal usado como dato", y
  `app.sass:487` lo deja por escrito: *"teal solo acción o navegación"*.

De `green`, `teal`, `blue`, `purple` y `orange` **ninguno está remapeado** (sólo
lo está `.bg-grey`). Entran como la paleta cruda de Quasar.

**Qué hacer a mano.** En `src/utils/storageMedia.js` L34-51, pasar a tokens
semánticos. Hay que preservar la regla que el propio comentario del archivo
protege — que `no_data` y `no_category` **no compartan color** (RN-02):

```js
export function verdictColor(veredicto) {
  switch (veredicto) {
    case "purge_remote":
      return "positive";
    case "purge_live_image":
    case "clear_remote":
      return "info";
    case "virtual_media":
      return "grey";      // + clase obs-chip-neutral en el badge
    case "no_category":
      return "warning";
    default:
      return "grey";      // + clase obs-chip-neutral en el badge
  }
}
```

Y en los dos badges que la usan, acompañar el gris con la clase neutra, igual que
`DiskEncryptionView.vue:79`:

```vue
<q-badge
  :color="verdictColor(row.verdict)"
  :class="{ 'obs-chip-neutral': verdictColor(row.verdict) === 'grey' }"
>
```

**❓ Pregunta de producto.** Mi propuesta colapsa `purge_live_image` y
`clear_remote` en un mismo `info`, y `virtual_media` y `no_data` en gris. **Eso
pierde distinciones que `main` hacía a propósito**: el comentario de la función
dice que "sin dato" y "sin categoría alcanzable" no deben compartir color, y ahí
lo respeto (gris vs. `warning`), pero `virtual_media` y `no_data` sí quedan
iguales. La v2 tiene 4 colores semánticos y acá hay 6 veredictos, así que **no
hay un mapeo 1:1 y la decisión es de producto**: ¿cuáles de los 6 pueden
compartir color? La alternativa es ampliar la paleta de datos de la v2, que es
una decisión de diseño más grande. No la tomo.

**Cómo comprobarlo abriendo la UI.** Ir a **Medios de almacenamiento** (después
del hueco A) y mirar la columna **Categoría alcanzable** junto a la columna
**Estado** de **Cifrado de disco** en otra pestaña. **Antes del arreglo** los
badges de Medios salen verde/turquesa/azul/morado/naranjo —
colores que no aparecen en ninguna otra tabla de la consola; los de Cifrado usan
los cuatro del tema. **Después** las dos tablas usan la misma paleta.
Comprobarlo **en tema claro y en oscuro**: el `grey` crudo es el que peor se
porta al cambiar de tema, y es lo que arregla `obs-chip-neutral`.

---

### Resumen de la Parte 2

| # | Hueco | Archivos a tocar | ¿Decisión de producto? |
|---|---|---|---|
| A | Ruta `StorageMedia` sin enlace | `NavMenu.vue` | No (sólo en qué grupo del menú) |
| B | Panel Reconciliación muerto | `routes.js`, `NavMenu.vue`, `EraseCertificatesView.vue` | No |
| C | `StorageMediaView` con chrome v1 | `StorageMediaView.vue` | No |
| D | Portal público sin tema | `VerifyCertificateView.vue` | Sí, para la marca; **no** para el tema |
| E | Avisos v1 junto a `obs-notice` | `WipeOrderDialog.vue`, `AssetCustodyTimeline.vue` | Sí, chica (`--warning`) |
| F | `verdictColor` con paleta cruda | `utils/storageMedia.js` + 2 badges | Sí (mapeo 6→4) |

Ninguno de los seis lo detecta `lint`, `lint:i18n` ni `build`. Los seis se ven a
simple vista abriendo la pantalla correspondiente — por eso cada uno trae su
receta de comprobación visual.

---

## Parte 3 · Línea base, SIN fusionar

Corrida en este árbol (`v2/guion-t047`, sin merge), para poder distinguir después
qué rompió el merge y qué ya estaba roto.

| Comando | Resultado |
|---|---|
| `npm ci` | ✅ **0** — 697 paquetes en 39 s |
| `npm run build` | ✅ **0** — "Build succeeded", SPA, 52 550 ms |
| `npm run lint` | ✅ **0** — **sin una sola advertencia** |
| `npm run lint:i18n` | ✅ **0** — **sin un solo hallazgo**, sobre 187 archivos |

**La línea base está completamente limpia.** Es la mejor noticia de este
documento: **cualquier cosa que salga roja después del merge la rompió el
merge**, sin excepciones y sin zona gris.

### Ruido preexistente que NO hay que atribuirle al merge

`npm ci` y `npm run build` terminan en 0 pero imprimen cosas. Todas son
previas al merge:

- **`npm ci`**: `43 vulnerabilities (14 moderate, 27 high, 2 critical)` en
  `npm audit`. Preexistente, no lo toca el merge.
- **`build`**: `<script src="/env-config.js"> in "/index.html" can't be bundled
  without type="module"`.
- **`build`**: `Browserslist: browsers data (caniuse-lite) is 6 months old`.
- **`build`**, dos avisos de minificado de CSS, **con número de línea del CSS
  concatenado, no de un archivo fuente** — no confundirlos con un error nuevo:
  ```
  ▲ [WARNING] Expected identifier but found "." [css-syntax-error]   <stdin>:3437:1   .gutterItem {
  ▲ [WARNING] Expected identifier but found ">" [css-syntax-error]   <stdin>:3600:1   > div {
  ```
- **`build`**: `(!) Some chunks are larger than 1600 KiB after minification`.

### Otros números de la base, para comparar después

| Medida | Antes | Después del merge (medido) |
|---|---|---|
| Claves i18n (`en.json` / `es.json`) | 3 294 / 3 294 | **3 497 / 3 497** |
| Archivos en el gate `lint:i18n` | 187 | **191** |
| Quasar / `@quasar/app-vite` / Vite | 2.18.5 / 1.10.2 / 2.9.18 | sin cambio |

### Lo mismo, corrido sobre el merge YA resuelto

Como la Parte 1 se verificó de verdad, también tengo este lado de la
comparación. En el clon desechable, con los 7 conflictos resueltos como dice la
Parte 1 **y sin ninguno de los arreglos de la Parte 2**:

| Comando | Resultado |
|---|---|
| `npm run lint` | ✅ **0** |
| `npm run lint:i18n` | ✅ **0** — ahora sobre 191 archivos |
| `npm run build` | ✅ **0** — "Build succeeded", mismos avisos preexistentes |

**Las tres en verde con los seis huecos de la Parte 2 abiertos.** Ése es el dato
más útil del documento: el verde de la Parte 3 **no es evidencia de que el merge
esté terminado**, y quien lo ejecute no debería cerrarlo basándose en eso.

---

## Qué elegí NO hacer

- **No ejecuté el merge en este repositorio.** El árbol está sin fusionar, ningún
  archivo de `src/` fue tocado, y lo único que agrego es este `.md` en la raíz.
  La tarea era de preparación. Quedan `web/app/node_modules/` y `web/app/dist/`
  como residuo de la Parte 3, que pedía correr `npm ci` y `npm run build`; los dos
  están en `.gitignore` y no entran al commit.
- **Sí hice el merge en un clon desechable en `/tmp`**, y lo digo explícitamente
  porque cambia cuánto vale este documento. Preferí eso a entregar bloques
  plausibles sin probar: las resoluciones de la Parte 1 están aplicadas y
  compiladas, no deducidas. El clon ya no existe.
- **No apliqué ninguno de los seis arreglos de la Parte 2**, aunque los tengo
  especificados con archivo y línea. Tres de los seis tienen una pregunta de
  producto adentro (la marca del portal público, el modificador `--warning`, el
  mapeo de 6 veredictos a 4 colores), y aplicarlos ahora habría significado
  responderlas por mi cuenta y dejarlas enterradas en un diff.
- **No respondí esas tres preguntas.** Las dejé planteadas con el argumento de
  cada lado, que era lo pedido.
- **No reporté como defecto el color de los avisos de la v1 que entran de
  `main`.** Era mi primera lectura y era incorrecta: `app.sass:320-340` ya
  remapea globalmente `bg-grey-3`, `bg-orange-1/2`, `text-black`, `text-grey-6/7`
  y `text-grey`. Verifiqué selector por selector antes de escribir, y el hueco E
  quedó reducido a lo que de verdad falla (la forma de `obs-notice`, más
  `bg-grey-2` y `text-grey-8`, que son las dos únicas clases sin remapeo). El
  hueco C también se encogió: el problema no es la paleta sino la clase
  `obs-page`.
- **No verifiqué en navegador los huecos A, B, C, E ni F.** Todos cuelgan de
  rutas con `requireAuth` y este entorno no tiene backend. Sí verifiqué el hueco
  D en un navegador de verdad, porque la ruta pública no pide sesión, y de ahí
  salen las medidas de `body--light` vs `body--dark`. Los otros cinco están
  sostenidos en lectura del árbol ya fusionado, no del árbol de `main`: comprobé
  que `FileBar.vue` no lo renderiza nadie, que `tab` sale de `props.mode`, y que
  las rutas y claves i18n existen o faltan. Cada uno lleva su receta de
  comprobación visual para que quien tenga una instalación cierre el circuito en
  un par de minutos.
- **No toqué `release/v2` ni abrí un pull request.** El commit va a
  `v2/guion-t047`, como corresponde.
- **No estimé de nuevo las 10-11 horas.** No tenía con qué contrastar la medición
  previa. Lo que sí puedo decir es dónde está el costo: los 12 hunks son
  mecánicos y 4 de ellos (i18n y `package.json`) se resuelven con dos scripts;
  las horas se van en los seis huecos de la Parte 2, que no los encuentra ninguna
  herramienta y hay que ir a buscar a mano.
