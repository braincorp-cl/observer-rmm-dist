# T047 · Guion para hacer `git merge main` dentro de `release/v2`

**Qué es esto.** El guion para que otra persona ejecute el merge rápido y sin
equivocarse. **No contiene el merge hecho**: el árbol de este repositorio está
sin fusionar y ningún archivo de `src/` fue modificado.

**Revisión 2** — reescrito contra la punta actual de `release/v2`. La revisión 1
se escribió sobre `467d451`; desde entonces entraron 20 commits y 94 archivos.
Al final hay una sección de **qué quedó obsoleto** respecto de esa versión.

**Contra qué estado se escribió.**

| | |
|---|---|
| Repositorio | `braincorp-cl/observer-rmm-dist` |
| Rama de trabajo | `v2/guion-t047` = punta de `release/v2` + este documento |
| Punta de `release/v2` | `ae08aa7` |
| Punta de `main` | `da0e21b` |
| Base común | `1079c0b` — **sin cambios** desde la revisión 1 |
| `main` sobre la base | 199 archivos, +19 401 / −559 |
| `release/v2` sobre la base | 190 archivos, +12 982 / −3 947 |

**`main` no se movió donde importa.** Avanzó, pero sus commits recientes son
todos de ansible, despliegue y backend. Su último commit que toca
`web/app/src` es `ed3dbd6`, que ya estaba dentro del alcance de la revisión 1.
Los 7 archivos que llegan nuevos de `main` son exactamente los mismos.

**Cómo se verificó.** Igual que la revisión 1: el merge se hizo de verdad en un
**clon desechable** en `/tmp`, se aplicaron las resoluciones de la Parte 1, y se
corrieron los cinco comandos sobre el resultado. **Los cinco pasan.** El clon se
borró. Donde algo no se pudo verificar, lo digo.

---

## Parte 0 · Punto de partida

```bash
git fetch origin main release/v2
git checkout release/v2
git merge origin/main --no-commit
```

Resultado esperado: **7 archivos en conflicto, 12 hunks.** El conjunto no cambió
respecto de la revisión 1. Todo lo demás automergea, y ahí está el problema real
(Parte 2).

---

## Parte 1 · Los 12 hunks en conflicto

### Cuatro de los siete no hay que volver a mirarlos

Los 20 commits nuevos **no tocaron** `AssetsTab.vue`,
`EraseCertificateDetailDialog.vue`, `EditCoreSettings.vue` ni
`EraseCertificatesView.vue`. Eso no es una suposición: comparé los **blobs de
las tres etapas** del conflicto (base, nuestro lado, lado de `main`) entre la
revisión 1 y ahora, y los doce SHA son idénticos:

```
a84cdada / e3c62e17 / 0b6ede7b   AssetsTab.vue
1898a05d / c90b9ff7 / 6fa8d87a   EraseCertificateDetailDialog.vue
a1d372a5 / 4b76cb72 / 3e4040f4   EditCoreSettings.vue
7d8b35e9 / 6c7addbf / 9daf9b2a   EraseCertificatesView.vue
```

Mismos tres insumos ⇒ mismo conflicto, byte a byte. **Las resoluciones de la
revisión 1 para esos cuatro valen tal cual** y están más abajo sin un solo
cambio. Lo confirmé además aplicándolas: entraron sin un ajuste y el árbol
compila.

De los tres restantes, sólo cambió **nuestro** lado (etapa 2); base y `main`
siguen idénticos:

```
8d3bbd90 -> f1761977   package.json
62dbbceb -> 0c7e2595   i18n/en.json
e3548dac -> ca96e5ca   i18n/es.json
```

### Resumen

| # | Archivo | Hunks | Resolución | ¿Rehecha? |
|---|---|---|---|---|
| 1 | `web/app/package.json` | 1 | Unión: lista de la v2 + 4 archivos de `main` | Recalculada |
| 2 | `src/components/agents/AssetsTab.vue` | 1 | Estructura v2 + rama `storage_media` | Sin cambio |
| 3 | `src/components/agents/EraseCertificateDetailDialog.vue` | 1 | Tomar `main` y pasar prettier | Sin cambio |
| 4 | `src/components/modals/coresettings/EditCoreSettings.vue` | 2 | A: estructura v2 + 3 campos. B: tomar v2 | Sin cambio |
| 5 | `src/i18n/en.json` | 2 | Unión profunda por script | Recalculada |
| 6 | `src/i18n/es.json` | 2 | Unión profunda por script | Recalculada |
| 7 | `src/views/EraseCertificatesView.vue` | 3 | Ver detalle; uno deja código muerto | Sin cambio |

**Ninguno de los 12 exige una decisión de producto.**

---

### 1 · `web/app/package.json` — el gate `lint:i18n`

**🔎 Corrección a un dato de partida.** Se me indicó que la lista `lint:i18n`
venía más larga. **No creció**: la comparé entre `467d451` y la punta y es
**byte a byte idéntica**, 187 archivos. Lo que cambió en `package.json` son tres
scripts (`test`, `test:node`, `test:watch`) y cuatro devDependencies
(`vitest`, `jsdom`, `@vitejs/plugin-vue`, `@vue/test-utils`).

**Eso importa para la resolución**: los scripts nuevos **no entran en
conflicto**. El conflicto sigue siendo una sola línea, la de `lint:i18n`, porque
`main` no tocó esa zona del archivo. `git checkout --ours` conserva los scripts
de prueba sin más.

**Qué quiere cada lado.** La v2 agregó 14 archivos a la lista; `main` agregó 4.
Diferencia de conjuntos sobre las tres etapas: **nadie borró nada**, así que no
hay nada que decidir. Los 4 de `main`:

```
src/views/StorageMediaView.vue
src/views/VerifyCertificateView.vue
src/components/agents/StorageMediaDetail.vue
src/components/agents/AssetCustodyTimeline.vue
```

**Por qué importa.** Esos 4 son exactamente las vistas y componentes nuevos de
la Parte 2. Si se resuelve tomando el lado de la v2 (lo cómodo, porque su línea
es la más larga), **el gate deja de mirarlos** y cualquier texto sin traducir
que traigan pasa sin que nadie se entere. Y `lint:i18n` **sí es una compuerta de
CI**, así que el costo aparece tarde.

**Resolución** (la línea pesa ~11 KB; pegarla a mano es una mala idea):

```bash
git checkout --ours web/app/package.json
python3 -I scripts/t047-fix-lint-i18n.py
```

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

**Verificación:** imprime `lint:i18n: 191 archivos` (187 + 4), y el `git diff`
de `package.json` tiene exactamente **una** línea cambiada. Ejecutado: ✅.

---

### 2 · `AssetsTab.vue` — las pestañas de Activos

*(Resolución de la revisión 1, sin cambios: los tres insumos son idénticos.)*

**Qué quiere cada lado.**
- **v2**: borró las `q-tabs`/`q-tab-panels` y dejó bloques desplegables
  (`q-expansion-item`) recorriendo `assetOptions` — en la v2 la vista de agente
  no tiene pestañas (UI-E04).
- **`main`**: agregó una pestaña y un panel `storage_media` con
  `<StorageMediaDetail>`.

**Resolución: estructura de la v2, más una rama para `storage_media`.**

**🔴 La trampa.** El `<script>` **automergea sin conflicto**: el `import` de
`StorageMediaDetail` y su registro en `components:` ya quedan puestos. Pero
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

La clave `agentTabs.assets.storageMedia` llega con el i18n de `main`.

---

### 3 · `EraseCertificateDetailDialog.vue` — las filas del certificado

*(Sin cambios respecto de la revisión 1.)*

**Qué quiere cada lado.**
- **v2**: sólo reformateó (prettier pasó las filas de una línea a multilínea).
  **Cero cambios semánticos.**
- **`main`**: agregó 14 filas nuevas (equipo desglosado en marca/modelo/hostname,
  tipo y origen del medio, disposición, método y evidencia de verificación,
  bloque de "quien da fe") y pasó 4 valores por funciones de etiqueta.

**Resolución: el lado de `main`, y después prettier.**

```bash
git checkout --theirs web/app/src/components/agents/EraseCertificateDetailDialog.vue
cd web/app && npx prettier --write src/components/agents/EraseCertificateDetailDialog.vue
```

El resultado de prettier es idéntico al estilo de la v2. Además reparte en 3
líneas un `<td :class="{ mono: ... }">{{ field.value }}</td>` que `main` trae sin
partir — es correcto y deseable.

**⚠️ La red de seguridad NO está en CI.** `labelMediaType`, `labelDisposition`,
`labelVerificationResult`, `labelVerificationMethod` y las variables `d`, `eq`,
`conc` entran limpias por automerge. Si alguien toma el lado de la v2 por error,
quedan sin usar y **`npm run lint` lo caza**. Pero el job `frontend` de
`ci.yml` corre `lint:i18n`, `test` y `build` — **no corre `npm run lint`**. Es
el único de los 12 hunks con red, y hay que tenderla a mano:

```bash
cd web/app && npm run lint
```

---

### 4 · `EditCoreSettings.vue` — dos hunks

*(Sin cambios respecto de la revisión 1.)*

#### Hunk A · los campos de retención

**Qué quiere cada lado.**
- **v2**: sacó el envoltorio `<q-tab-panel>` y lo dejó como `<div>`
  (desindentado 2 espacios) — la v2 sirve esto como página `/settings/:section`
  con navegación lateral, no como pestañas.
- **`main`**: agregó **3 campos nuevos**: `erase_attachment_retention_days`,
  `erase_attachment_prune_enabled` y `erase_public_verify_enabled`.

**Resolución: la estructura de la v2 (cierre `</div>`), con los 3 campos de
`main` reindentados 2 espacios menos.**

**Comprobé que quedan alcanzables**: la sección `retention` está en
`SECTION_GROUPS` (grupo `platform`) y en `SAVABLE`, así que después del merge se
llega por **Ajustes → Plataforma → Retención** y el `PUT /core/settings/` los
guarda. Acá no hay hueco.

**El tercer campo enciende la ruta pública** (`/verificar`), que es la vista del
hueco D.

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
después de la misma línea. Recalculado contra la punta:

| | base | v2 (nuestro) | `main` | unión |
|---|---|---|---|---|
| claves | 3 150 | 3 301 | 3 353 | 3 505 |
| agregadas | — | +152 | +203 | |
| **borradas** | — | **1** | 0 | |

Las 152 de la v2 incluyen las 8 nuevas de las ventanas remotas
(`takeControl.*` y `remoteBackground.*`, de T048/T049). Verifiqué que
sobreviven a la unión.

**🔴 Lo que cambió respecto de la revisión 1: ahora hay un borrado.** El commit
`cf00224` quitó `takeControl.agentStatus`, huérfana tras T048. **`main` todavía
la tiene.** Una unión ingenua —o un `--theirs`— la **resucita**, y vuelve a
entrar una clave que la v2 borró a propósito. El resultado correcto tiene
**3 504** claves, no 3 505.

El resto sigue como antes:

- **colisiones reales: 0** — ninguna clave fue cambiada a valores distintos por
  los dos lados;
- `main` no borró nada.

Como no hay nada que decidir pero sí algo que es fácil romper, **no resolver
esto a mano**: son 4 hunks sobre ~3 500 claves.

```bash
python3 -I scripts/t047-union-i18n.py web/app/src/i18n/en.json
python3 -I scripts/t047-union-i18n.py web/app/src/i18n/es.json
```

```python
#!/usr/bin/env python3
# Une los i18n del merge: BASE/OURS/THEIRS -> union profunda, orden de OURS primero.
# Respeta los borrados de cualquiera de los dos lados y aborta ante una colision real.
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
            if k in b and k not in t:      # theirs la borro
                continue
            r[k] = o[k]
        else:
            if k in b and k not in o:      # ours la borro  <-- takeControl.agentStatus
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
alguien tocó la misma clave en los dos lados, se entera en vez de perderla.

**Verificación** — las dos deben quedar en **3 504** claves y
`takeControl.agentStatus` **no** debe existir:

```bash
python3 -c "
import json
f=lambda o: sum(map(f,o.values())) if isinstance(o,dict) else 1
for L in ('en','es'):
    d=json.load(open(f'web/app/src/i18n/{L}.json'))
    print(L, f(d), 'agentStatus' in d['takeControl'])"
```

Debe imprimir `en 3504 False` y `es 3504 False`. Ejecutado: ✅.

---

### 7 · `EraseCertificatesView.vue` — tres hunks

*(Sin cambios respecto de la revisión 1.)*

#### Hunk 1 · las `q-tabs` de la vista

- **v2**: borró las pestañas. Certificados e Ingresos son **dos rutas**
  (`/erase-certificates` y `/erase-intake`) que comparten la vista vía
  `props.mode`.
- **`main`**: agregó una **tercera** pestaña, `reconciliation`.

**Resolución: el lado de la v2** (sin `q-tabs`, cierre `</ObsPageHead>`).

**🔴 Pero eso deja código muerto.** El panel entero de Reconciliación automergea
limpio más abajo bajo `v-show="tab === 'reconciliation'"`. Reparación en la
Parte 2, hueco B. No se arregla dentro del conflicto.

#### Hunk 2 · los botones de la fila

- **v2**: cambió `color="deep-orange"` → `color="primary"` en el botón de
  certificar (pasada de color V2-G05, commit `c4b9674`).
- **`main`**: agregó un botón nuevo "Ver custodia" delante.

**Resolución: los dos.**

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

**Resolución: unión.**

**🔴 Trampa silenciosa.** `sep` lo usa la plantilla del panel de Reconciliación,
que automergea. Si se toma el lado de la v2 y se pierde `sep`, **no falla ni el
build, ni el lint, ni las pruebas**: Vue sólo emite un warning en consola y
renderiza vacío.

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
cd web/app && npm run lint && npm run lint:i18n && npm test && npm run build
```

Los cuatro pasan sobre el merge resuelto así — lo ejecuté contra la punta
actual. **Pero pasar no significa que el merge esté terminado**, y de eso trata
la Parte 2.

---

## Parte 2 · Lo que entra limpio y queda mudo

**Revisión contra la punta actual: siguen siendo los mismos seis. Ninguno
cambió y no apareció ninguno nuevo.** No lo asumí: lo verifiqué.

**Por qué se sostienen.** De los archivos de los que dependen los seis huecos,
los 20 commits nuevos tocaron exactamente **dos**:

| Archivo | Estado |
|---|---|
| `NavMenu.vue`, `NavRail.vue`, `FileBar.vue`, `MainLayout.vue` | intactos |
| `router/routes.js`, `DiskEncryptionView.vue` | intactos |
| `WipeOrderDialog.vue`, `NotFound.vue`, `store/index.js`, `quasar.config.js` | intactos |
| `css/app.sass` | **+8 líneas** |
| `views/LoginView.vue` | **+23 / −14** |

Y revisé las dos:

- **`app.sass`** sólo agrega el token `--obs-term-bg` para el terminal web. **No
  toca ningún remapeo de paleta** (siguen en las líneas 331-345 y 488) **ni
  agrega `obs-notice--warning`** (siguen existiendo sólo `--info` y
  `--negative`). Los huecos C, E y F se apoyan en eso y siguen en pie.
- **`LoginView.vue`** es T049, y **sí cambia algo del hueco D, para bien**: ver
  más abajo.

**Búsqueda de un hueco nuevo.** Crucé los archivos que tocan los **dos** lados y
que **automergean** —que es donde se esconde un conflicto semántico sin
marcador—: son los mismos cuatro de la revisión 1 (`AssetIntakeForm.vue`,
`WipeOrderDialog.vue`, `ClientsForm.vue`, `routes.js`). Ninguno de los 20
commits nuevos entra en esa intersección salvo `ClientsForm.vue`, donde la v2
sólo quitó un `bg-white` de un tooltip y `main` agrega el campo de retención más
abajo: no se rozan. **Sin hueco nuevo.**

---

### Hueco A · La ruta `StorageMedia` no la enlaza nadie

**Verificado contra la punta: sin cambios.**

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
`src/components/FileBar.vue`, la barra de menús de la v1. **En la v2 ese archivo
no se renderiza en ninguna parte**: `MainLayout.vue` monta `<NavRail />` y nada
más, y las únicas dos referencias a `FileBar` que quedan en el árbol fusionado
son **comentarios** (`NavMenu.vue:3` y `NavMenu.vue:490`). La v2 navega por
`NavMenu.vue`, que tiene el ítem de `DiskEncryption` pero no el de
`StorageMedia`.

La clave `nav.storageMedia` **sí llega** por la unión de i18n, traducida a los
dos idiomas. Falta sólo el ítem de menú.

**Qué hacer a mano.** En `src/components/shell/NavMenu.vue`, **después de la
línea 200** (el `</q-item>` que cierra el ítem de `DiskEncryption`, que abre en
la 198):

```vue
          <!-- inventario de medios de almacenamiento (feature 055) -->
          <q-item clickable v-close-popup :to="{ name: 'StorageMedia' }">
            <q-item-section>{{ $t("nav.storageMedia") }}</q-item-section>
          </q-item>
```

**Decisión pendiente (chica).** `main` lo puso en el menú **Ver**, junto a
Cifrado de disco. Dejarlo ahí es lo que dice el comentario de la ruta ("hermana
del panel de cifrado") y es lo que propongo; si el riel de la v2 tiene otro grupo
pensado para inventario, va ahí.

**Cómo comprobarlo abriendo la UI.**
1. Entrar a la consola. En el riel izquierdo, abrir el menú **Ver**.
2. **Antes**: aparece "Cifrado de disco" y no "Medios de almacenamiento". La
   única forma de llegar al panel es escribir `/storage-media` en la barra de
   direcciones — y si se escribe, **el panel carga perfecto**, que es lo que
   hace el hueco invisible.
3. **Después**: el ítem está y abre el mismo panel.

---

### Hueco B · El panel de Reconciliación entra completo y no se ve nunca

**Verificado contra la punta: sin cambios.** `EraseCertificatesView.vue` y
`routes.js` están intactos; el `v-show`, el `computed` y las dos únicas rutas con
`mode` siguen exactamente igual.

**Qué entra.** El panel de Reconciliación de `main` (RF-07) **automergea entero
y sin conflicto**: ~150 líneas de plantilla y ~150 de lógica — filtros de
cliente y período, el cálculo, la tabla por cliente, la tabla de activos sin
certificar, `loadReconciliation()`, sus columnas y el enlace a la cadena de
custodia. Más 68 claves de i18n bajo `erase.reconciliation.*`, ya traducidas.

**Por qué el merge no lo cablea.** Todo cuelga de
`v-show="tab === 'reconciliation'"`. En `main`, `tab` era un `ref("certificates")`
que movían las `q-tabs`. En la v2:

```js
const tab = computed(() => props.mode);
```

y `props.mode` lo fija la ruta. Las únicas rutas que lo pasan valen
`"certificates"` e `"intake"`. **No existe ninguna con `"reconciliation"`**, así
que la condición nunca es cierta.

El código es válido, está referenciado, compila y **pasa `lint`, `lint:i18n` y
`npm test` sin una sola queja** — porque `v-show` no exige que la condición pueda
ser cierta alguna vez.

**Qué hacer a mano.** Tres ediciones.

**1.** En `src/router/routes.js`, después del bloque de la ruta `EraseIntake`:

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
(abre en la línea 209, cierra en la 211):

```vue
          <q-item clickable v-close-popup :to="{ name: 'EraseReconciliation' }">
            <q-item-section>{{ $t("erase.reconciliation.title") }}</q-item-section>
          </q-item>
```

(No hace falta crear una clave `nav.*`: `erase.reconciliation.title` ya llega
traducida en los dos idiomas.)

**3.** En `src/views/EraseCertificatesView.vue`, el `pageTitle` sólo contempla
dos modos y con `reconciliation` mostraría "Certificados de borrado":

```js
    const pageTitle = computed(() => {
      if (tab.value === "intake") return t("nav.eraseIntake");
      if (tab.value === "reconciliation") return t("erase.reconciliation.title");
      return t("nav.eraseCertificates");
    });
```

**Cómo comprobarlo abriendo la UI.**
1. Ir a **Certificados de borrado** y mirar la cabecera: en la v1 había tres
   pestañas. **Después del merge sin arreglar no hay ninguna pestaña**, y sólo se
   llega a dos de los tres paneles, por el menú. Nada en pantalla insinúa que el
   tercero existe: por eso se escapa.
2. Escribir `/erase-reconciliation` en la barra de direcciones. **Antes**: cae en
   el 404 del producto. **Después**: abre el panel con sus filtros y el botón
   **Calcular**.
3. Confirmación de que funciona y no sólo aparece: elegir cliente y período y
   pulsar **Calcular**; deben salir las cuatro cifras (Ingresados / Certificados
   / Faltantes / Detenidos) y la tabla "Activos sin certificar".

---

### Hueco C · `StorageMediaView` llega con el chrome de la v1

**Verificado contra la punta: sin cambios.** `DiskEncryptionView.vue` está
intacto y el bloque `.obs-ws, .obs-page` de `app.sass` sigue donde estaba
(ahora en la línea 140).

**Qué entra.** `src/views/StorageMediaView.vue`, archivo nuevo (292 líneas).

**Por qué el merge no lo cablea.** Es un archivo nuevo: no hay con qué chocar.
Y `main` lo escribió copiando `DiskEncryptionView.vue` **anterior** a la
conversión de la v2. Las dos vistas son hermanas (lo dice el comentario de la
ruta) y hoy son visiblemente distintas:

| | `DiskEncryptionView` (v2) | `StorageMediaView` (de `main`) |
|---|---|---|
| Envoltorio | `<q-page class="obs-page">` | `<q-page class="q-pa-md">` (L2) |
| Cabecera | `<ObsPageHead :title :crumbs>` (L3) | `div.row` + `.text-h6` a mano (L4) |
| Botón refrescar | `outline no-caps .obs-page__btn` con rótulo | `dense flat` con tooltip (L6-15) |
| Aviso "sólo Windows" | `<div class="obs-notice" role="note">` (L18) | `<q-banner class="bg-grey-3 text-black">` (L21) |
| Filtros | `.obs-page__filters` + `.obs-page__field`, `outlined` (L23) | grilla `row q-col-gutter-md`, `filled` (L28-68) |
| `<q-table>` | — | **idéntica, no hay que tocarla** |

**🔑 Lo importante: la clase `obs-page` no es cosmética, es el gancho.** En
`src/css/app.sass:140` el bloque `.obs-ws, .obs-page` es el que convierte a
tokens los grises por defecto de Quasar: fondo y color de la tarjeta de tabla,
bordes de celdas, **color y fondo de la cabecera de la tabla**, los campos de
formulario y `.text-grey-8`. **Sin esa clase nada de eso se aplica.**

**Lo que NO es problema** (verificado selector por selector, y vuelto a verificar
contra la punta): `bg-grey-3` (L331), `text-black` (L335), `text-grey-6/7`
(L337), `bg-orange-1` (L339), `text-orange-9` (L341), `bg-orange-2` (L345) y
`text-grey` (L488) **sí están remapeados a tokens globalmente**. El color de
esos avisos no se rompe. El daño real es el de la clase `obs-page` y la
diferencia de forma con la vista hermana.

**Qué hacer a mano**, en `src/views/StorageMediaView.vue`:
- **L2**: `class="q-pa-md"` → `class="obs-page"`.
- **L3-16**: reemplazar el `div.row` + `text-h6` + botón por
  `<ObsPageHead :title="$t('storageMedia.title')" :crumbs="[$t('nav.agents')]">`
  con el botón de refrescar en el slot, copiando `DiskEncryptionView.vue:3-13`.
  Agregar el `import ObsPageHead` (ver `DiskEncryptionView.vue:122,130`).
- **L21-27**: el `q-banner` → `<div class="obs-notice" role="note">` con
  `<q-icon name="storage" />`, copiando `DiskEncryptionView.vue:18-21`.
- **L28-68**: la grilla → `<div class="obs-page__filters">` y los tres
  `q-select` de `filled` a `outlined class="obs-page__field"`, copiando
  `DiskEncryptionView.vue:23-51`.
- La `<q-table>` (L71+) **no se toca**.

**Cómo comprobarlo abriendo la UI.** Abrir **Cifrado de disco** y **Medios de
almacenamiento** en dos pestañas y alternar:
1. El título: una tiene miga de pan y título de página; la otra sólo un texto en
   negrita arriba a la izquierda.
2. El botón de refrescar: botón con borde y rótulo vs. sólo un ícono.
3. El aviso de "sólo Windows": recuadro con borde redondeado vs. franja.
4. Los filtros: campos con contorno vs. campos con fondo relleno.
5. **La prueba decisiva**: la **fila de encabezados de la tabla**. En Cifrado de
   disco tiene el fondo elevado y el texto atenuado del tema; en Medios de
   almacenamiento no. Si después del arreglo las dos se ven iguales, `obs-page`
   está haciendo su trabajo.

---

### Hueco D · `VerifyCertificateView`, la vista PÚBLICA

**Verificado contra la punta: el hueco sigue, y T049 mejoró el arreglo.**

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

**Esto lo pude abrir de verdad** (revisión 1), porque la ruta no pide
autenticación: compilé el merge resuelto, serví el `dist` y lo cargué en un
navegador. Medido, no deducido:

| Ruta | `body` | Fondo |
|---|---|---|
| `/login` | `body--dark` | `rgb(15, 26, 42)` |
| `/verificar` | `body--light` | `rgb(238, 242, 247)` |

**Por qué el merge no lo cablea.** Al vivir fuera de `MainLayout`, nadie le fija
el tema:

- `src/store/index.js` hace `Dark.set(data.dark_mode)` dentro de la carga de
  `dashinfo`, que **exige sesión iniciada**. Un tercero nunca pasa por ahí.
- `quasar.config.js` **no define `dark`**, así que el default de Quasar es claro.
- `LoginView.vue:112` resuelve esto **forzando** `$q.dark.set(true)`.

**🆕 Lo que cambió con T049, y mejora el arreglo.** Las tres pantallas de acceso
se rehicieron y dejaron un precedente que en la revisión 1 no existía:

- usan `class="flex flex-center obs-ws"` — y sus propios comentarios dicen que
  **`obs-ws` es el ámbito de tokens de las vistas** fuera de `MainLayout`. O sea
  que para una página así la clase correcta es `obs-ws`, no `obs-page`.
- el título de marca es `<h1 class="obs-page__title">Observer RMM</h1>` dentro de
  una `q-card` (`LoginView.vue:13`), con `obs-page__title` definido en
  `app.sass:530`.
- las acciones principales usan `unelevated no-caps color="primary"` +
  `obs-page__btn`.
- el tema lo sigue fijando **cada pantalla por su cuenta**: `LoginView.vue:112` y
  `TOTPSetup.vue:96`. **No se creó ningún helper compartido**, así que el arreglo
  del portal público mantiene la misma forma.

*(Observación al pasar, preexistente y ajena al merge: `InitialSetup.vue` **no**
fija el tema, aunque también vive fuera de `MainLayout`. No es consecuencia del
merge y no lo cuento como hueco; lo anoto porque muestra que "página fuera de
`MainLayout` que se olvida del tema" ya es un patrón en la v2.)*

**✅ Decisión de producto, ya tomada.** La revisión 1 dejaba abierto si el portal
llevaba marca. **Está decidido:**

> El portal público **lleva marca de producto** — logo y una línea que diga qué
> es la página — pero **NO** el nombre del tenant ni del cliente, porque cada
> instalación es un cliente y eso es justo lo que la decisión **L-02** prohíbe.
> **Tampoco lleva chrome de navegación.**

Eso cierra la pregunta y además encaja exactamente con el patrón T049: una
`q-card` centrada, con el `obs-page__title` de marca arriba y nada de riel ni
menús.

**Qué hacer a mano**, en `src/views/VerifyCertificateView.vue`:

1. **Tema.** En el `<script setup>`, fijarlo como las pantallas de acceso:
   ```js
   import { useQuasar } from "quasar";
   const $q = useQuasar();
   $q.dark.set(true);
   ```
2. **Ámbito de tokens.** En el `<div v-else class="q-pa-md">` (L7), pasar a
   `class="q-pa-md obs-ws"`, siguiendo a `LoginView.vue:4` y `TOTPSetup.vue:9`.
3. **Marca.** Agregar, como primera `q-card-section` de la tarjeta, el bloque de
   marca con la misma escala que el acceso:
   ```vue
         <q-card-section>
           <div class="text-center q-pt-md">
             <h1 class="obs-page__title ellipsis">Observer RMM</h1>
           </div>
         </q-card-section>
   ```
   El "qué es esta página" ya existe y está traducido: el subtítulo
   `erase.verify.subtitle`, que la vista ya pinta debajo del título. **No se
   agrega el nombre del tenant ni del cliente en ninguna parte** (L-02), y no se
   agrega riel, cabecera ni menús.
4. **`NotFound` en contexto público.** Cuando el tenant tiene la función apagada
   se renderiza `NotFound.vue` (L6), que trae un botón "Volver" que hace
   `$router.push("/")` y deja a un tercero sin cuenta en el login de una
   instalación ajena. **Ocultarlo en contexto público**: darle a `NotFound.vue`
   una prop tipo `:hide-back="true"` y pasarla desde acá, o envolver el botón en
   un `v-if`.
5. **Formato de fecha.** `formatearFecha` (L126) usa
   `new Date(valor).toLocaleString()`, que no es el formateo del resto del
   producto: la fecha de emisión saldrá distinta que en la consola. Usar el
   helper de `src/utils/format.ts`.

**Cómo comprobarlo abriendo la UI.**
1. En **Ajustes → Plataforma → Retención**, encender **"Exponer la verificación
   pública de certificados"** y guardar.
2. Abrir **una ventana de incógnito** (clave: sin sesión) y entrar a
   `https://<instalación>/verificar`.
3. **Antes**: sale en **claro**; `/login` en otra pestaña de la misma ventana
   sale en **oscuro**. Las dos son públicas, del mismo producto, y no coinciden.
   Y la página no dice en ninguna parte de qué producto es.
4. **Después**: las dos en oscuro, y el portal muestra "Observer RMM" con la
   misma tipografía y escala que el login, con su línea de qué es la página.
5. **Comprobación de L-02**: leer la página entera, incluido el resultado de una
   verificación real, y confirmar que **no aparece el nombre del tenant ni del
   cliente** en ningún lado.
6. Con un identificador real, verificar que la fecha "Emitido:" tenga el mismo
   formato que la columna de fecha en **Certificados de borrado**.
7. Apagar el toggle y recargar `/verificar`: debe salir el NotFound genérico
   **sin** el botón "Volver".

---

### Hueco E · Avisos de la v1 dentro de diálogos que la v2 ya había convertido

**Verificado contra la punta: sin cambios.** `WipeOrderDialog.vue` está intacto,
y `app.sass` sigue definiendo sólo `obs-notice--info` y `obs-notice--negative`.

**Qué entra.** `main` agrega avisos nuevos a archivos que **la v2 ya había
convertido al patrón `obs-notice`**:

- `src/components/agents/WipeOrderDialog.vue` (automergea): tras el merge el
  diálogo tiene **tres** avisos seguidos. El de arriba (L25) es el de la v2,
  `class="obs-notice q-ma-md"`. Los dos que agrega `main` justo debajo son
  `<q-banner class="bg-orange-1 text-orange-9 q-ma-md">` (L43) y
  `<q-banner class="bg-grey-3 text-black q-ma-md">` (L53).
- `src/components/agents/AssetCustodyTimeline.vue` (archivo nuevo, L37):
  `<q-banner dense class="bg-grey-2 text-grey-8 q-mb-md">`.

**Por qué el merge no lo cablea.** Nada que fusionar: uno automergea y el otro es
archivo nuevo. Y el color no avisa, porque `bg-orange-1`, `text-orange-9`,
`bg-grey-3` y `text-black` **sí están remapeados globalmente**. Lo que no se
remapea es la **forma**: `obs-notice` (`app.sass:551`) aporta borde de 1px, radio
de 8px, padding propio, `font-size: 13px` y el ícono atenuado a 18px. Un
`q-banner` pelado no tiene nada de eso. Quedan tres avisos pegados con dos formas
distintas.

Dos clases además **no están remapeadas en ninguna parte**, ni global ni dentro
de `.obs-page`: **`bg-grey-2`** y **`text-grey-8`** (ésta sólo existe dentro de
`.obs-ws`/`.obs-page`, y `AssetCustodyTimeline` se monta como diálogo, fuera de
ambas).

**✅ Decisión de producto, ya tomada.** La revisión 1 preguntaba si el aviso de
estado sólido debía reusar `--negative` o si se creaba `--warning`.
**Está decidido:**

> Se crea `obs-notice--warning` en vez de reusar `--negative`, **pero no ahora**:
> va en la tanda del sistema de diseño, junto con el anillo de foco.

**Eso cambia qué hacer en este merge.** El modificador **no se crea acá**, así
que los tres avisos quedan con `obs-notice` a secas, que ya los deja
consistentes entre sí y con el resto del producto. El matiz de severidad del
aviso de estado sólido llega después, cambiando una clase:

- `WipeOrderDialog.vue` **L43** y **L53**: `class="..."` → `class="obs-notice
  q-ma-md"`, quitando las clases de paleta.
- `AssetCustodyTimeline.vue` **L37**: → `class="obs-notice q-mb-md"`.

**Dejar anotado para la tanda del sistema de diseño**: cuando exista
`obs-notice--warning`, el aviso de `WipeOrderDialog.vue:43` ("la sobrescritura NO
es sanitización defendible sobre estado sólido") es uno de sus destinatarios.

**Cómo comprobarlo abriendo la UI.** Abrir una **orden de borrado** sobre un
equipo con disco de estado sólido inventariado (**Equipos perdidos** → caso
abierto → **Ordenar borrado**). Arriba del diálogo quedan dos o tres avisos
apilados: **antes** el primero tiene borde y esquinas redondeadas y los de abajo
son franjas rectangulares a todo el ancho; **después** los tres son iguales. Para
el de custodia: en **Certificados de borrado**, botón **Ver custodia** de
cualquier fila, y mirar el aviso "Un eslabón no se edita ni se borra".

---

### Hueco F · `verdictColor` trae la paleta cruda de la v1, con `teal` incluido

**Verificado contra la punta: sin cambios.** `utils/storageMedia.js` llega igual,
y `app.sass` no agregó remapeos para esos colores.

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

Lo consumen `StorageMediaView.vue` (badge de la columna "Categoría alcanzable") y
`StorageMediaDetail.vue` (badge del detalle, dentro de la pestaña Activos).

**Por qué el merge no lo cablea.** Archivo nuevo. Pero la v2 hizo dos pasadas de
color (V2-G05) cuyo criterio es el contrario:

- la vista hermana usa tokens semánticos —
  `{encrypted: "positive", unencrypted: "negative", unsupported: "grey",
  no_data: "warning"}` — y pinta el `grey` con la clase `obs-chip-neutral`
  (`DiskEncryptionView.vue:79`), que lo saca de `var(--obs-raised)`;
- **`teal` está explícitamente prohibido como color de dato**. El commit
  `cda299a` se titula, literalmente, "teal usado como dato", y `app.sass`
  lo deja por escrito: *"teal solo acción o navegación"*.

De `green`, `teal`, `blue`, `purple` y `orange` **ninguno está remapeado** (sólo
lo está `.bg-grey`). Entran como la paleta cruda de Quasar.

**✅ Decisión de producto, ya tomada.** La revisión 1 preguntaba cómo mapear 6
veredictos a 4 colores. **Está decidido:**

> **El color lleva la severidad y el rótulo del badge lleva el veredicto**, así
> que no se fuerzan 6 en 4 ni se amplía la paleta.

Es decir: que dos veredictos compartan color **no es pérdida de información**,
porque el texto del badge ya los distingue. El color sólo tiene que decir *qué
tan grave es*.

**Qué hacer a mano**, en `src/utils/storageMedia.js` L34-51, aplicando esa regla:

```js
// El color lleva la SEVERIDAD; el rótulo del badge lleva el veredicto, así que
// dos veredictos pueden compartir color sin que se pierda cuál es cuál.
export function verdictColor(veredicto) {
  switch (veredicto) {
    // Hay una vía de sanitización defendible.
    case "purge_remote":
    case "purge_live_image":
    case "clear_remote":
      return "positive";
    // Se midió y no hay categoría alcanzable: sólo queda sanitización parcial.
    case "no_category":
      return "warning";
    // No aplica ("el medio real está en otra parte") o no se sabe. Nunca rojo:
    // un equipo del que no sabemos nada no es un incumplidor.
    case "virtual_media":
    default:
      return "grey";      // + clase obs-chip-neutral en el badge
  }
}
```

**RN-02 queda respetada**: "sin dato" (`grey`) y "sin categoría alcanzable"
(`warning`) **no comparten color**, que es lo que la regla exige y lo que el
comentario original del archivo protege.

**La agrupación por severidad es mía, derivada de la regla y de los textos de
`verdictHelp` del propio `main`**: los tres primeros son los casos en que el
producto afirma que la sanitización es defendible. Si "severidad" para ustedes
separa `purge_live_image` (que exige arrancar el equipo fuera de su SO) del
resto, es mover un `case` de grupo y nada más.

Y en los dos badges que la usan, acompañar el gris con la clase neutra, igual que
`DiskEncryptionView.vue:79`:

```vue
<q-badge
  :color="verdictColor(row.verdict)"
  :class="{ 'obs-chip-neutral': verdictColor(row.verdict) === 'grey' }"
>
```

**Cómo comprobarlo abriendo la UI.** Ir a **Medios de almacenamiento** (después
del hueco A) y mirar la columna **Categoría alcanzable** junto a la columna
**Estado** de **Cifrado de disco** en otra pestaña. **Antes** los badges de
Medios salen verde/turquesa/azul/morado/naranjo — colores que no aparecen en
ninguna otra tabla de la consola; los de Cifrado usan los del tema. **Después**
las dos tablas usan la misma paleta, y el rótulo de cada badge sigue diciendo
cuál de los seis veredictos es. Comprobarlo **en tema claro y en oscuro**: el
`grey` crudo es el que peor se porta al cambiar de tema, y es lo que arregla
`obs-chip-neutral`.

---

### Resumen de la Parte 2

| # | Hueco | Archivos a tocar | ¿Decisión de producto? |
|---|---|---|---|
| A | Ruta `StorageMedia` sin enlace | `NavMenu.vue` | No (sólo en qué grupo del menú) |
| B | Panel Reconciliación muerto | `routes.js`, `NavMenu.vue`, `EraseCertificatesView.vue` | No |
| C | `StorageMediaView` con chrome v1 | `StorageMediaView.vue` | No |
| D | Portal público sin tema ni marca | `VerifyCertificateView.vue`, `NotFound.vue` | **Resuelta** (lleva marca, sin tenant ni chrome) |
| E | Avisos v1 junto a `obs-notice` | `WipeOrderDialog.vue`, `AssetCustodyTimeline.vue` | **Resuelta** (`obs-notice` ahora; `--warning` después) |
| F | `verdictColor` con paleta cruda | `utils/storageMedia.js` + 2 badges | **Resuelta** (color = severidad, rótulo = veredicto) |

Ninguno de los seis lo detecta `lint`, `lint:i18n`, `build` ni `npm test`. Los
seis se ven a simple vista abriendo la pantalla correspondiente.

---

## Parte 3 · Línea base, SIN fusionar

Rehecha sobre la punta actual (`ae08aa7`), sin merge. Ahora son **cinco**
comandos: existe `npm test`.

| Comando | Resultado |
|---|---|
| `npm ci` | ✅ **0** — 779 paquetes en 23 s |
| `npm run build` | ✅ **0** — "Build succeeded", SPA, 66 648 ms |
| `npm run lint` | ✅ **0** — **sin una sola advertencia** |
| `npm run lint:i18n` | ✅ **0** — **sin un solo hallazgo**, sobre 187 archivos |
| `npm test` | ✅ **0** — node:test 6/6 y vitest 22/22 en 3 archivos |

**La línea base está completamente limpia.** Cualquier cosa que salga roja
después del merge la rompió el merge, sin zona gris.

### Detalle de `npm test`

`npm test` encadena dos corredores: `test:node` (node:test, 6 pruebas sobre
`src/utils/coords.test.mjs`) y `vitest run` (22 pruebas en 3 archivos):

```
✓ test/styles/q-tooltip-bg-white.spec.js        (3 pruebas)
✓ test/components/agent-table-overdue-alert.spec.js (7 pruebas)
✓ test/components/agent-table-hostname.spec.js  (12 pruebas)
```

**El trinquete de tooltips y el merge.** `q-tooltip-bg-white.spec.js` es un
trinquete **en los dos sentidos** contra
`test/styles/q-tooltip-bg-white.baseline.json`, que hoy vale:

```json
{ "src/components/ui/DialogWrapper.vue": 1 }
```

Falla si alguien **reintroduce** un `bg-white` en un `q-tooltip`, y también si
hay **uno menos** sin actualizar el inventario. Lo verifiqué contra el merge:

- los 4 `.vue` nuevos que entran de `main` tienen **0** `bg-white` (sus tooltips
  son `<q-tooltip>` pelados, que es justo el patrón al que convergió la v2);
- el merge **no toca** `DialogWrapper.vue`, así que el inventario tampoco baja.

**El trinquete queda verde después del merge.** Es la primera red automática que
este merge tiene y conviene saber que no se dispara, para no perder tiempo
interpretándola.

### ⚠️ `npm run lint` NO está en CI

El job `frontend` de `.github/workflows/ci.yml` corre, en este orden:

```
npm ci  →  npm run lint:i18n  →  npm test  →  npm run build
```

**No corre `npm run lint`**, y no lo corre ningún otro job. O sea que la red de
seguridad del hunk 3 (imports y variables que quedan sin usar si se resuelve
mal) **sólo existe si alguien corre el lint a mano**. Está en el comando de
cierre de la Parte 1 por eso.

### Ruido preexistente que NO hay que atribuirle al merge

Todos estos salen con los comandos en 0, y son previos al merge:

- **`npm ci`**: `49 vulnerabilities (18 moderate, 27 high, 4 critical)` en
  `npm audit`, y tres `npm warn deprecated glob@…`. Subió desde 43 al entrar las
  dependencias de prueba; es previo al merge igual.
- **`build`**: `<script src="/env-config.js"> in "/index.html" can't be bundled
  without type="module"`.
- **`build` y `test`**: `Browserslist: browsers data (caniuse-lite) is 6 months
  old`.
- **`build`**, dos avisos de minificado de CSS, **con número de línea del CSS
  concatenado, no de un archivo fuente**:
  ```
  ▲ [WARNING] Expected identifier but found "." [css-syntax-error]   <stdin>:…   .gutterItem {
  ▲ [WARNING] Expected identifier but found ">" [css-syntax-error]   <stdin>:…   > div {
  ```
- **`build`**: `(!) Some chunks are larger than 1600 KiB after minification`.

### Números para comparar después

| Medida | Base (sin fusionar) | Tras el merge resuelto (medido) |
|---|---|---|
| Claves i18n (`en` / `es`) | 3 301 / 3 301 | **3 504 / 3 504** |
| Archivos en el gate `lint:i18n` | 187 | **191** |
| Inventario del trinquete de tooltips | 1 | **1** (sin cambio) |
| Pruebas | 6 + 22 | **6 + 22** (sin cambio) |

### Lo mismo, corrido sobre el merge YA resuelto

En el clon desechable, con los 7 conflictos resueltos como dice la Parte 1 **y
sin ninguno de los arreglos de la Parte 2**:

| Comando | Resultado |
|---|---|
| `npm run lint` | ✅ **0** |
| `npm run lint:i18n` | ✅ **0** — ahora sobre 191 archivos |
| `npm test` | ✅ **0** — 6 + 22, trinquete incluido |
| `npm run build` | ✅ **0** — mismos avisos preexistentes |

**Las cuatro en verde con los seis huecos de la Parte 2 abiertos.** Ése sigue
siendo el dato más útil del documento, y ahora vale también para `npm test` y
para la CI: **el verde de CI no es evidencia de que el merge esté terminado.**

---

## Qué quedó obsoleto de la revisión 1

- **La advertencia sobre la rama.** La revisión 1 avisaba que los bloques estaban
  sacados contra `HEAD` y no contra `release/v2` puro, porque la rama de trabajo
  iba 5 commits adelante. Ya no aplica: esos 5 commits están dentro de
  `release/v2`, y esta revisión se escribió contra su punta.
- **La línea base entera.** Los números de la revisión 1 (697 paquetes, 43
  vulnerabilidades, build de 52 550 ms, 3 294 claves i18n) eran de otro árbol.
  Reemplazados. Y le faltaba un comando: `npm test` no existía.
- **"Los i18n no tienen borrados."** Era cierto entonces y **ya no**: la v2 borró
  `takeControl.agentStatus`. La unión ahora da 3 504 claves, no 3 505, y una
  resolución descuidada resucita la clave.
- **Las tres preguntas de producto abiertas.** Las tres están respondidas en los
  huecos D, E y F.
- **El plan del hueco E.** La revisión 1 proponía *o* reusar `--negative` *o*
  crear `--warning` ahora. Ya no: se usa `obs-notice` a secas y `--warning` llega
  en la tanda del sistema de diseño.
- **El plan del hueco F.** La revisión 1 proponía colapsar 6 veredictos en 4
  colores y lo marcaba como pregunta abierta. La regla decidida (color =
  severidad, rótulo = veredicto) cambia el mapeo y cierra la pregunta.
- **El plan del hueco D.** La revisión 1 no sabía si el portal llevaba marca y no
  tenía un patrón al que apuntar. Ahora lleva marca, y T049 dejó el patrón exacto
  (`obs-ws`, `obs-page__title`, la `q-card` centrada del acceso).
- **Números de línea de `app.sass`.** Se corrieron 8 líneas al entrar
  `--obs-term-bg`. Todos los que cita esta revisión están verificados contra la
  punta.
- **Un dato de partida que no se sostuvo.** Se me indicó que la lista `lint:i18n`
  venía más larga; es idéntica (187). Lo que creció en `package.json` son los
  scripts de prueba y las devDependencies, que automergean.

---

## Qué elegí NO hacer

- **No ejecuté el merge en este repositorio.** El árbol está sin fusionar, ningún
  archivo de `src/` fue tocado, y lo único que toco es este `.md`. Lo que sí hice
  fue poner la rama al día con `release/v2` (un merge de nuestra propia rama
  base, no el de `main`), porque la tarea pedía trabajar contra la punta actual y
  la línea base de la Parte 3 tiene que salir de ese árbol.
- **No rehice las resoluciones de los cuatro archivos intactos**, como se pidió.
  Pero tampoco las di por buenas a ojo: comparé los doce SHA de las tres etapas
  del conflicto contra la revisión 1 y son idénticos, y además las apliqué en el
  clon desechable para confirmar que entran sin ajustes. La confirmación es una
  prueba, no una suposición.
- **Sí volví a hacer el merge en un clon desechable en `/tmp`**, ya borrado. Lo
  digo porque cambia cuánto vale este documento: las resoluciones de la Parte 1
  están aplicadas y compiladas contra la punta actual, no deducidas.
- **No apliqué ninguno de los seis arreglos de la Parte 2**, aunque ahora los
  seis tienen el camino completo y ninguno espera una decisión. Siguen siendo
  trabajo de cableado posterior al merge, y mezclarlos con la resolución de
  conflictos haría imposible revisar ninguna de las dos cosas.
- **No creé `obs-notice--warning`**, siguiendo la decisión (b): va en la tanda
  del sistema de diseño junto con el anillo de foco, no acá. Dejé anotado cuál es
  su destinatario para cuando esa tanda ocurra.
- **No reabrí las tres decisiones ya tomadas.** En el hueco F derivé una
  agrupación concreta de los 6 veredictos a partir de la regla decidida, y la
  marqué como derivación mía para que corregirla sea mover un `case`; no la
  presenté como una pregunta nueva.
- **No verifiqué en navegador los huecos A, B, C, E ni F.** Todos cuelgan de
  rutas con `requireAuth` y este entorno no tiene backend. El hueco D sí está
  medido en un navegador real (revisión 1), porque la ruta pública no pide
  sesión. Los otros cinco están sostenidos en lectura del árbol ya fusionado —
  que `FileBar.vue` no lo renderiza nadie, que `tab` sale de `props.mode`, que
  las rutas y claves existen o faltan, que `app.sass` remapea unos selectores y
  no otros— y cada uno lleva su receta de comprobación visual.
- **No investigué por qué `npm run lint` no está en CI.** Lo verifiqué, lo digo
  y lo compenso poniéndolo en el comando de cierre de la Parte 1; si debería
  estar en el job `frontend` es una decisión que no me corresponde tomar acá.
- **No toqué `InitialSetup.vue`**, aunque tampoco fija el tema y vive fuera de
  `MainLayout`. Es un defecto preexistente de la v2, no lo causa el merge, y
  arreglarlo desde este trabajo sería ensanchar el alcance sin que nadie lo haya
  pedido. Queda anotado en el hueco D.
- **No toqué `release/v2` ni abrí un pull request.** El commit va a
  `v2/guion-t047`.
- **No estimé de nuevo las 10-11 horas.** No tengo con qué contrastar la medición
  previa. Dónde está el costo no cambió: los 12 hunks son mecánicos y 4 de ellos
  se resuelven con dos scripts; las horas se van en los seis huecos de la Parte
  2, que no los encuentra ninguna herramienta.
