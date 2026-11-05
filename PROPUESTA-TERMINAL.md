# Propuesta: tokens de color para el terminal web (`WebTerminal.vue`)

**Estado:** propuesta, sin implementar. Ningún archivo de `web/app/src/` fue modificado por este
documento.
**Hallazgo que cierra:** `web/app/src/views/WebTerminal.vue:54` pasa `theme: { background: "#333" }`
a xterm — un hex a mano (viola `UI-D02` / `V2-G02`) que además nunca sigue al tema, y sin
`foreground` fijado en ninguna parte.
**Fecha de medición:** 2026-11-05.

---

## 0. Método (qué medí y con qué)

Nada acá viene de memoria. Las dos fuentes son:

1. **El CSS compilado del proyecto.** Compilé `src/css/quasar.variables.sass` +
   `src/css/app.sass` con `sass 1.80.6` (quitando solo los `@import` de `@fontsource`, que no
   aportan color) y leí los valores resueltos de los bloques `body.body--dark` / `body.body--light`.
   Confirmé además que **nadie más redefine** `--obs-deep` ni `--obs-text` en un scope más
   estrecho: en las 1224 líneas de CSS compilado cada uno aparece exactamente dos veces, una por
   tema.
2. **El código fuente de `@xterm/xterm@6.0.0`**, la versión exacta que fija `web/app/package.json:22`.
   El paquete publicado en npm trae los `.ts` originales; leí
   `src/browser/services/ThemeService.ts`, `src/browser/Types.ts`, `src/common/Color.ts`,
   `src/common/services/OptionsService.ts`, `src/browser/Viewport.ts`,
   `src/browser/renderer/dom/DomRendererRowFactory.ts` y `css/xterm.css`.

Los ratios los calculé con una réplica exacta de `src/common/Color.ts` de xterm
(`relativeLuminance2`, `contrastRatio`, `ensureContrastRatio`, `reduceLuminance`,
`increaseLuminance`, `blend`), no con una implementación propia de WCAG. Eso importa para la
sección 3: así los valores "después de corregir" son los que xterm realmente va a pintar, con su
algoritmo de pasos del 10 %, no un ideal teórico.

Valores de token resueltos (del CSS compilado):

| token | `body--dark` | `body--light` |
|---|---|---|
| `--obs-page` | `#0F1A2A` | `#EEF2F7` |
| `--obs-surface` | `#131F31` | `#FFFFFF` |
| `--obs-raised` | `#17253A` | `#F6F8FB` |
| `--obs-rail` | `#0B1523` | `#E3E9F1` |
| **`--obs-deep`** | **`#0A1220`** | **`#DCE3EC`** |
| `--obs-border` | `#1E2D42` | `#D3DCE7` |
| `--obs-selected` | `#132A34` | `#EEF8FA` |
| **`--obs-text`** | **`#E6EDF5`** | **`#16202E`** |
| `--obs-text-2` | `#C3D2E3` | `#33445A` |
| **`--obs-on-dark`** | **`#E6EDF5`** | **`#E6EDF5`** (invariante) |
| `--obs-paper` | `#FFFFFF` | `#FFFFFF` (invariante) |

---

## 1. Qué par usa HOY el terminal, de verdad

### Fondo

`theme.background = "#333"`. `css.toColor()` (`src/common/Color.ts:151-156`) toma la rama
`case 4: // #rgb` y lo expande repitiendo cada dígito: **`#333333`**.

### Primer plano

No se fija en ninguna parte. `ThemeService` lo resuelve con
`parseColor(theme.foreground, DEFAULT_FOREGROUND)` (`ThemeService.ts:83`), y
`DEFAULT_FOREGROUND = css.toColor('#ffffff')` (`ThemeService.ts:23`). El primer plano efectivo es
**`#FFFFFF`**.

Lo mismo pasa con tres colores más que el componente tampoco fija y que sí se ven:

| color | de dónde sale hoy | valor efectivo |
|---|---|---|
| `foreground` | `DEFAULT_FOREGROUND` | `#FFFFFF` |
| `cursor` | `DEFAULT_CURSOR`, mezclado con el fondo | `#FFFFFF` |
| `cursorAccent` | `DEFAULT_CURSOR_ACCENT` = `DEFAULT_BACKGROUND` | `#000000` |
| `selectionBackground` | `DEFAULT_SELECTION` = `rgba(255,255,255,0.3)` sobre `#333333` | `#707070` |
| barra de scroll | `opacity(foreground, 0.2 / 0.4 / 0.5)` | blanco al 20/40/50 % |

### El par efectivo y su contraste

| | fondo | primer plano | ratio | AA texto normal (4,5:1) |
|---|---|---|---|---|
| **HOY, ambos temas** | `#333333` | `#FFFFFF` | **12,63:1** | pasa |

El par de hoy **no es el problema de contraste**: 12,63:1 es holgado. Los dos problemas reales son
otros:

1. **No sigue al tema.** `#333333` es el mismo en claro y en oscuro, y no corresponde a ninguna
   superficie de la paleta 1c. Su luminancia relativa es `0.0331`, contra `0.0060` de
   `--obs-deep` oscuro: visiblemente más claro y más gris (sin el tinte navy) que cualquier
   superficie del tema oscuro, y obviamente fuera de lugar en el claro.
2. **El primer plano es el default de xterm, no una decisión del proyecto.** Que hoy funcione es
   suerte: el par es "blanco puro sobre gris medio", que no es el par de ningún tema de Observer.

### Detalle de implementación que conviene saber

`css/xterm.css` del paquete trae `.xterm .xterm-viewport { background-color: #000; }` (línea 95).
No se ve, porque `Viewport.ts:74` escribe
`this._scrollableElement.getDomNode().style.backgroundColor = themeService.colors.background.css`
en estilo inline, que gana a la hoja de estilos. O sea: el `#000` del CSS vendido queda tapado por
el `#333333` del `theme`. Si algún día se quita `background` del `theme`, no queda `#333` ni
transparente: queda **negro**.

---

## 2. Par de tokens propuesto

### Qué usan hoy las superficies parecidas

Busqué el precedente antes de proponer:

| superficie | archivo | fondo | primer plano |
|---|---|---|---|
| **salida de comando en vivo** (`.command-stream`) | `src/components/agents/CommandStream.vue:97-104` | `var(--obs-deep)` | `var(--obs-text)` |
| editor de scripts (Monaco) | `src/components/scripts/ScriptFormModal.vue:495` | temas propios de Monaco `vs-dark` / `vs-light` | ídem |
| `<pre>` de stdout/stderr | `RunScript.vue`, `ScriptOutput.vue`, `TestScriptModal.vue`, `SendCommand.vue`, `AuditLogDetailModal.vue`, `PreDialog.vue` | heredan la superficie del diálogo (`q-card`), sin fondo propio | heredan `--obs-text` |
| **cabecera de la app** | `app.sass:282` y `--obs-hdr-*` | tokens **oscuros fijos en ambos temas** | `--obs-on-dark` |
| lienzo de reporte renderizado | `--obs-paper` | **blanco fijo en ambos temas** | — |

`--obs-deep` es el único token que el proyecto ya usa como fondo de una superficie de consola
(`CommandStream.vue`), así que el valor es el correcto. La pregunta que queda es **si debe
re-tematizarse**, y la respuesta la fuerzan los 16 colores ANSI (sección 3).

### Opción A — recomendada: el terminal es una superficie oscura invariante

```
background: var(--obs-term-bg)   // nuevo token, = $obs-d-deep en ambos temas → #0A1220
foreground: var(--obs-on-dark)   // token existente, invariante → #E6EDF5
cursor:     var(--obs-on-dark)
cursorAccent: var(--obs-term-bg)
```

| tema | fondo | primer plano | ratio | AA |
|---|---|---|---|---|
| oscuro | `#0A1220` | `#E6EDF5` | **15,89:1** | pasa |
| claro | `#0A1220` | `#E6EDF5` | **15,89:1** | pasa |

**Por qué un token nuevo, habiendo pedido reusar.** El proyecto ya tiene dos superficies que
deliberadamente **no** se re-tematizan, y cada una tiene su token con la justificación escrita en
`quasar.variables.sass`:

- `$obs-paper` — *"el lienzo de un reporte renderizado es papel. El documento se compone en blanco
  con tinta oscura y no se re-tematiza, así que su fondo es el mismo en ambos temas; queda como
  token para que ningún `.vue` tenga que escribir el color a mano (V2-G02)"*.
- `--obs-hdr-*` — *"Encabezado: siempre navy (bg-dark) en ambos temas ⇒ tokens oscuros fijos"*.

Un terminal es el mismo caso, y por una razón medible, no estética: **los 16 colores ANSI que
xterm trae por defecto son la paleta Tango, calibrada para fondo oscuro. Sobre `--obs-deep` claro,
11 de 16 no llegan a 4,5:1** (sección 3). Si el terminal sigue al tema, el tema claro obliga a
inventar 16 tokens ANSI nuevos por tema (32 valores) o a aceptar que la salida con color sea
ilegible. El token nuevo es uno; la alternativa son 32.

El token nuevo **no introduce ningún hex nuevo**: es un alias de `$obs-d-deep`, que ya existe.
Y el primer plano es reuso puro: `--obs-on-dark` ya vale `#E6EDF5` en los dos temas y ya es el
primer plano de la cabecera, que es exactamente "texto sobre superficie oscura fija".

**Ventaja secundaria, y no menor:** la opción A es **estática**. No necesita leer el tema, ni
reaccionar a un cambio de tema, ni arreglar el bug de la sección 5.1.

### Opción B — alternativa: el terminal sigue al tema

```
background: var(--obs-deep)   // #0A1220 oscuro / #DCE3EC claro
foreground: var(--obs-text)   // #E6EDF5 oscuro / #16202E claro
```

| tema | fondo | primer plano | ratio | AA |
|---|---|---|---|---|
| oscuro | `#0A1220` | `#E6EDF5` | **15,89:1** | pasa |
| claro | `#DCE3EC` | `#16202E` | **12,69:1** | pasa |

Cero tokens nuevos, y es consistente con `CommandStream.vue`. El par base pasa AA en los dos
temas. **Pero** arrastra tres costos que la opción A no tiene:

1. Obliga a resolver los 16 ANSI (sección 3): sobre `#DCE3EC`, 11 de 16 fallan.
2. Obliga a arreglar el bug de la sección 5.1 primero, o el token resuelve **siempre al tema
   claro** aunque el usuario tenga el oscuro.
3. Obliga a reaplicar el tema cuando el usuario cambia de tema con el terminal abierto, y a
   resolver la selección: `DEFAULT_SELECTION` es `rgba(255,255,255,0.3)`, que sobre `#DCE3EC` da
   `#E7EBF2` — **1,08:1 contra el fondo, o sea invisible**.

En oscuro A y B son idénticas. Toda la diferencia está en el tema claro.

**Mi recomendación es A.** Un terminal es un terminal, no una tarjeta ni un `<pre>`; es el único
widget de la webUI cuyo contenido trae sus propios colores desde el otro lado del cable, y esos
colores asumen fondo oscuro. Dicho eso: si la dirección de diseño es que *nada* escapa al tema,
B es defendible, y la sección 3 dice exactamente cuánto cuesta.

---

## 3. Los 16 colores ANSI

### ¿Se fija alguno hoy?

**No. Ninguno.** El `theme` del componente trae solo `background`.
`ThemeService._setTheme()` (`ThemeService.ts:113-120`) resuelve cada slot con
`parseColor(theme.black, DEFAULT_ANSI_COLORS[0])`, etc., así que los 16 quedan en
`DEFAULT_ANSI_COLORS` (`src/browser/Types.ts:181-201`): la **paleta Tango**.

Importante: tampoco está activa la red de seguridad de xterm.
`minimumContrastRatio` vale **`1`** por defecto (`OptionsService.ts:42`), y `1` significa
*desactivado* — `DomRendererRowFactory.ts:481` sale de inmediato con ese valor. Los 16 colores
caen crudos sobre el fondo.

### ¿Son legibles? Ratios medidos

`AA` = ≥ 4,5:1 (texto normal). `grande` = ≥ 3:1 (solo válido para texto ≥ 18,66 px bold o ≥ 24 px;
el terminal corre a 15 px, así que para este caso **"grande" es falla**).

| # | nombre | hex | sobre HOY `#333333` | sobre `#0A1220` (A y B-oscuro) | sobre `#DCE3EC` (B-claro) |
|---|---|---|---|---|---|
| 0 | black | `#2e3436` | 1,00 ✗ | 1,48 ✗ | 9,78 ✓ |
| 1 | red | `#cc0000` | 2,15 ✗ | 3,18 grande | 4,55 ✓ |
| 2 | green | `#4e9a06` | 3,58 grande | 5,31 ✓ | 2,73 ✗ |
| 3 | yellow | `#c4a000` | 5,04 ✓ | 7,48 ✓ | 1,94 ✗ |
| 4 | blue | `#3465a4` | 2,13 ✗ | 3,16 grande | 4,58 ✓ |
| 5 | magenta | `#75507b` | 1,92 ✗ | 2,85 ✗ | 5,09 ✓ |
| 6 | cyan | `#06989a` | 3,59 grande | 5,33 ✓ | 2,72 ✗ |
| 7 | white | `#d3d7cf` | 8,66 ✓ | 12,85 ✓ | 1,13 ✗ |
| 8 | brBlack | `#555753` | 1,73 ✗ | 2,57 ✗ | 5,65 ✓ |
| 9 | brRed | `#ef2929` | 3,02 grande | 4,48 grande | 3,24 grande |
| 10 | brGreen | `#8ae234` | 7,83 ✓ | 11,61 ✓ | 1,25 ✗ |
| 11 | brYellow | `#fce94f` | 10,17 ✓ | 15,09 ✓ | 1,04 ✗ |
| 12 | brBlue | `#729fcf` | 4,56 ✓ | 6,76 ✓ | 2,14 ✗ |
| 13 | brMagenta | `#ad7fa8` | 3,84 grande | 5,69 ✓ | 2,55 ✗ |
| 14 | brCyan | `#34e2e2` | 7,90 ✓ | 11,71 ✓ | 1,24 ✗ |
| 15 | brWhite | `#eeeeec` | 10,88 ✓ | 16,14 ✓ | 1,11 ✗ |
| | **AA (≥4,5)** | | **7 / 16** | **10 / 16** | **5 / 16** |

Tres lecturas:

- **Hoy el terminal es peor de lo que parece.** El par base da 12,63:1, pero **9 de 16 colores ANSI
  no llegan a 4,5:1 sobre `#333333`**, y `ansi 0` (negro) está en **1,00:1 — literalmente
  invisible**. Cualquier `ls --color`, `systemctl status`, `git diff` o salida con `\e[31m` ya está
  parcialmente ilegible en producción. Esta es la parte del hallazgo que el par fondo/primer plano
  escondía.
- **Cambiar el fondo a `--obs-deep` oscuro mejora los 16 sin tocar la paleta**, de 7 a 10 sobre AA,
  porque el fondo es más oscuro (luminancia `0.0060` contra `0.0331`). Es mejora gratis.
- **El tema claro es el escenario malo:** `#DCE3EC` deja 11 de 16 bajo AA, y los peores son
  justamente los más usados (`white` 1,13 · `brWhite` 1,11 · `brYellow` 1,04 · `brGreen` 1,25 ·
  `brCyan` 1,24). Todos los *bright*, que es lo que usan los prompts y los logs con color.

### ¿Hay que fijarlos?

**No fijarlos a mano. Activar `minimumContrastRatio: 4.5`.**

xterm ya resuelve esto, y lo resuelve mejor que una paleta escrita a mano:
`DomRendererRowFactory._applyMinimumContrast()` (líneas 480-507) corrige el color del texto **en
tiempo de render, celda por celda, contra el fondo real de esa celda**. O sea que también cubre
video inverso, `\e[4Xm` (fondo ANSI) y 256/truecolor — casos que una paleta de 16 valores fijos no
cubre. Detalles del mecanismo, verificados en el código:

- Las celdas `dim` piden la mitad del ratio (`ratio / (cell.isDim() ? 2 : 1)`, línea 496), para que
  sigan distinguiéndose de las normales.
- Los glifos de bloque están exentos (`treatGlyphAsBackgroundColor`, línea 481), así que el arte
  con `░▒▓█` y las barras de progreso no se alteran.
- El resultado se memoriza en `contrastCache` / `halfContrastCache`, por lo que no hay costo por
  celda repetida.

Esto es lo que xterm pintaría **sobre el fondo propuesto `#0A1220`** con `minimumContrastRatio: 4.5`
(solo los 6 que cambian; los otros 10 quedan intactos):

| # | nombre | antes | ratio antes | después | ratio después |
|---|---|---|---|---|---|
| 0 | black | `#2e3436` | 1,48 | `#858a8a` | **5,36** |
| 1 | red | `#cc0000` | 3,18 | `#df5959` | **5,10** |
| 4 | blue | `#3465a4` | 3,16 | `#5c83b7` | **4,81** |
| 5 | magenta | `#75507b` | 2,85 | `#9c81a0` | **5,41** |
| 8 | brBlack | `#555753` | 2,57 | `#848683` | **5,10** |
| 9 | brRed | `#ef2929` | 4,48 | `#f13f3f` | **4,93** |

**Resultado: 16 de 16 ≥ 4,5:1, con dos tokens tocados y una línea de opción.**

Variante conservadora, si 4,5 se considera demasiada intervención sobre los colores que eligió el
programa remoto: con `minimumContrastRatio: 3` solo cambian **tres** colores sobre `#0A1220`
(`black` → `#676d6e` 3,56 · `magenta` → `#836289` 3,64 · `brBlack` → `#666865` 3,33) y los
`red`/`blue`/`brRed` quedan tal cual. Es menos fiel a AA y más fiel a la salida original. Mi
recomendación es 4,5, porque a 15 px la excepción de "texto grande" no aplica.

**Para la opción B hace falta lo mismo, y encima cubre más casos.** Sobre `#DCE3EC`, el mismo
mecanismo corrige los 11 que fallan (p. ej. `brWhite #eeeeec` → `#636363`, `brYellow #fce94f` →
`#696220`, `brCyan #34e2e2` → `#166969`). Funciona, pero conviene saber que en tema claro la
corrección es **agresiva**: `brWhite`, `brYellow`, `brGreen` y `brCyan` quedan prácticamente
irreconocibles como "el color que mandó el programa". Es otro argumento a favor de A.

### Un caso más que suele olvidarse: video inverso

Ya con `minimumContrastRatio` activo esto queda cubierto, porque la corrección es contra el fondo
real de la celda. Lo dejo medido para que se vea por qué **no** alcanza con fijar los 16 colores de
primer plano y nada más. Primer plano por defecto sobre fondo ANSI, sin corrección:

- Opción A (`fg #E6EDF5`): fallan 11 de 16 fondos. Los peores: `brWhite` 1,02 · `brYellow` 1,05 ·
  `white` 1,24 · `brCyan` 1,36 · `brGreen` 1,37.
- Opción B claro (`fg #16202E`): fallan 6 de 16. Los peores: `black` 1,30 · `brBlack` 2,25 ·
  `magenta` 2,49.

---

## 4. Diff propuesto (no aplicado)

Dos archivos, 31 líneas agregadas y 1 eliminada; 21 de las 31 son comentarios que dejan la
medición en el código. **Corresponde a la opción A + `minimumContrastRatio: 4.5`.**

```diff
diff --git a/web/app/src/css/app.sass b/web/app/src/css/app.sass
index 75dd3e9..02571cd 100644
--- a/web/app/src/css/app.sass
+++ b/web/app/src/css/app.sass
@@ -9,6 +9,14 @@
 
 body
   font-variant-numeric: tabular-nums
+  // Lienzo de un terminal: oscuro en ambos temas, por la misma razón por la que
+  // $obs-paper es papel en ambos. Los 16 colores ANSI que xterm trae por defecto
+  // son la paleta Tango, calibrada para fondo oscuro: sobre --obs-deep claro
+  // (#DCE3EC) 11 de los 16 no llegan a 4,5:1, y los peores son justamente los
+  // bright que usan los prompts y los logs. Alias de $obs-d-deep: no agrega
+  // ningún hex nuevo, y existe para que WebTerminal.vue no escriba el color a
+  // mano (V2-G02). El primer plano reusa --obs-on-dark, ya invariante.
+  --obs-term-bg: #{$obs-d-deep}
 
 // Datos (IP, MAC, versiones, conteos, rutas): monoespaciada.
 .mono
diff --git a/web/app/src/views/WebTerminal.vue b/web/app/src/views/WebTerminal.vue
index 3290b87..ddbb8b8 100644
--- a/web/app/src/views/WebTerminal.vue
+++ b/web/app/src/views/WebTerminal.vue
@@ -9,6 +9,7 @@
   height: 100vh;
   display: flex;
   flex-direction: column;
+  background: var(--obs-term-bg);
 }
 
 .xterm-container {
@@ -30,6 +31,20 @@ const xtermContainer = ref<HTMLElement | null>(null);
 let term: Terminal;
 const fit = new FitAddon();
 
+// Resuelve un token --obs-* a su hex. xterm NO acepta "var(--obs-term-bg)":
+// css.toColor() prueba el string contra el fillStyle de un canvas sembrado con un
+// CanvasGradient (Color.ts:194-198); un valor inválido deja el gradiente puesto,
+// toColor lanza, y parseColor() (ThemeService.ts:186-198) cae al default EN
+// SILENCIO — el fondo quedaría negro #000000 sin ningún error en consola.
+// Devolver undefined cuando el token no resuelve es deliberado: es el contrato de
+// parseColor para "usa tu default", y evita escribir un hex de respaldo acá
+// (V2-G02).
+function obsToken(name: string): string | undefined {
+  return (
+    getComputedStyle(document.body).getPropertyValue(name).trim() || undefined
+  );
+}
+
 const { data, send, close } = useCliWSConnection();
 
 onMounted(() => {
@@ -50,8 +65,16 @@ function setupXTerm() {
     fontSize: 15,
     fontWeight: 400,
     cursorBlink: true,
+    // Los 16 ANSI quedan en el default de xterm (Tango). Esta opción los corrige
+    // a 4,5:1 contra el fondo real de cada celda en tiempo de render, así que
+    // cubre también el video inverso y el 256/truecolor, que una paleta fija de
+    // 16 valores no cubriría. 1 = desactivado, que es el default.
+    minimumContrastRatio: 4.5,
     theme: {
-      background: "#333",
+      background: obsToken("--obs-term-bg"),
+      foreground: obsToken("--obs-on-dark"),
+      cursor: obsToken("--obs-on-dark"),
+      cursorAccent: obsToken("--obs-term-bg"),
     },
   });
 
```

Verificado sobre una copia del checkout en el scratchpad, no sobre `src/`:

- `git apply --check -p1` contra el árbol actual: **aplica limpio**. El diff de arriba es el
  que generó `git diff` sobre esa copia, no uno escrito a mano, así que los encabezados de
  hunk y el contexto son exactos.
- `prettier 3.3.3` con el `.prettierrc` del proyecto: **`WebTerminal.vue` queda formateado**
  (`All matched files use Prettier code style!`).
- `sass 1.80.6` sobre el `app.sass` mutado: compila, y el bloque `body` resuelve a
  `--obs-term-bg: #0A1220`, sin depender de la clase de tema.

### Lo que este diff NO toca, a propósito

- **`selectionBackground`**: queda en el default `rgba(255,255,255,0.3)`, que sobre `#0A1220` da
  `#545963` — **2,67:1 contra el fondo**, y el texto `#E6EDF5` encima queda en **5,96:1**. Es
  suficiente y no requiere token. (Con la opción B sí haría falta: en claro el default da 1,08:1.)
  No propuse `--obs-selected` para esto: medido, da **1,26:1** en oscuro y **1,20:1** en claro
  contra su fondo — peor que el default de xterm.
- **La paleta de 16 ANSI**, que queda en el default de xterm por diseño: `minimumContrastRatio`
  resuelve el problema sin agregar 16 o 32 tokens nuevos.
- **`quasar.variables.sass`**: no hace falta ninguna variable Sass nueva, porque `$obs-d-deep` y
  `$obs-d-text` ya existen.

### Cómo verificar después de aplicar

1. `cd web/app && npx quasar build` (o `npx vue-tsc --noEmit`) debe pasar. `obsToken` devuelve
   `string | undefined` y `ITheme` declara `foreground?: string` / `background?: string`
   (`typings/xterm.d.ts:343-351`), así que encaja. El único riesgo de tipos sería
   `exactOptionalPropertyTypes`, que **no** está en `web/app/tsconfig.json` pero sí podría venir
   de `@quasar/app-vite/tsconfig-preset`, que no pude leer sin `node_modules`. Si estuviera
   activo, la firma pasa a `string` y los `obsToken(...)` se envuelven en un objeto armado
   condicionalmente.
2. Abrir el terminal con el tema **claro** activo y confirmar que el fondo sigue siendo navy
   oscuro, no `#DCE3EC` — si sale claro, `obsToken` devolvió vacío.
3. Correr algo con color en el agente (`ls --color=always /`, `systemctl status`) y confirmar que
   ningún color desaparece. En particular `printf '\e[30mnegro\e[0m\n'`: hoy es invisible (1,00:1
   sobre `#333333`), después debe leerse gris (`#858a8a`, 5,36:1).
4. Si el fondo sale **negro puro** (`#000000`), es la falla silenciosa de `parseColor`: el token no
   resolvió.

---

## 5. Preguntas abiertas

### 5.1 (Bloquea la opción B) El popup del terminal nunca aplica el tema del usuario

Hallazgo aparte, encontrado mientras medía, y que cambia la decisión: **`/webterm` se abre como
ventana nueva** (`src/api/core.ts:86-91`, `openURL`), es una ruta de nivel superior sin
`MainLayout` (`src/router/routes.js:170-177`), y **`WebTerminal.vue` nunca llama a
`$q.dark.set()`**.

`Dark.set(data.dark_mode)` vive en `src/store/index.js:266`, dentro de `getDashInfo`, que
`WebTerminal.vue` no despacha. Los **otros dos popups hacen exactamente eso y el terminal es el
único que no**:

- `src/views/TakeControl.vue:110-114` → `const { dark_mode } = await fetchDashboardInfo(); $q.dark.set(dark_mode);`
- `src/views/RemoteBackground.vue:176-180` → idem.

Consecuencia: en la ventana del terminal el `body` queda en `body--light` siempre, y **cualquier**
`var(--obs-*)` leído ahí resuelve a los valores del tema claro, aunque el usuario tenga el oscuro.
Para la opción A no importa (los dos tokens son invariantes, y el diff define `--obs-term-bg` en
`body` sin depender de la clase de tema). Para la opción B es bloqueante: habría que agregar el
`getDashInfo` que ya tienen sus dos hermanas **antes** de tematizar el terminal.

**Pregunta:** ¿se arregla igual, como consistencia con `TakeControl` / `RemoteBackground`, aunque la
opción A no lo necesite? Es un `await` y dos líneas, y hoy es una inconsistencia real entre los tres
popups.

### 5.2 Cambio de tema con el terminal abierto

Si se elige B, el tema de xterm habría que reaplicarlo cuando cambia `$q.dark.isActive`. Es
soportado: `ThemeService` escucha `onSpecificOptionChange('theme', ...)` (`ThemeService.ts:73`), así
que basta `term.options.theme = { ... }`. Con la opción A no aplica, porque los tokens no cambian.
**Pregunta:** ¿vale la pena el watcher, o se acepta que el terminal se abre con el tema que tenía al
abrirse?

### 5.3 ¿`minimumContrastRatio` es aceptable para los operadores?

La opción corrige colores que el programa remoto eligió a propósito. Para un sysadmin que lee
`git diff` o `kubectl` por color, un rojo que pasa de `#cc0000` a `#df5959` sigue leyéndose como
rojo, pero es otro rojo. **Pregunta:** ¿4,5 (AA estricto, 6 colores alterados sobre `#0A1220`), 3
(3 colores alterados) o 1 (desactivado, 6 de 16 bajo AA)? Mi recomendación es 4,5. Este es un
cambio de comportamiento visible, no solo de tokens, y es la decisión que menos puedo tomar yo.

### 5.4 ¿`CommandStream.vue` debería alinearse?

`CommandStream.vue:97` usa `font-family: monospace` en vez de `$obs-font-mono` / `OBS_FONT_MONO`, y
es la otra superficie de consola. No es color, así que queda fuera del hallazgo. **Pregunta:** ¿se
anota como hallazgo aparte?

### 5.5 El `#000` de `css/xterm.css`

`.xterm .xterm-viewport { background-color: #000 }` es hex a mano, pero vive en el CSS vendido de
`@xterm/xterm`, no en `src/`. Hoy queda tapado por el estilo inline de `Viewport.ts:74`.
**Pregunta:** ¿se considera que la regla de color aplica solo a `src/`, o conviene dejarlo anotado
como deuda conocida de dependencia?

### 5.6 Nombre del token

Propuse `--obs-term-bg`. Los tokens invariantes existentes no tienen un prefijo común
(`--obs-paper` no lo tiene, `--obs-hdr-*` usa el de su componente). `--obs-term` o
`--obs-terminal` servirían igual. **Pregunta:** ¿nombre preferido?

---

## 6. Qué quedó sin medir

- **No corrí la webUI.** No hay `node_modules` instalado en el checkout y este es un trabajo de
  propuesta, así que no hay captura de pantalla ni medición de píxeles renderizados. Todos los
  ratios salen del CSS compilado y del código de xterm, no del DOM vivo. Lo que no verifiqué en
  pantalla es que el `fit()` no deje una franja del `body` visible al borde (por eso el diff agrega
  `background: var(--obs-term-bg)` a `.full-page-terminal`, que es preventivo, no medido).
- **No evalué los 240 colores restantes** de la paleta de 256 (índices 16-255), generados
  programáticamente en `Types.ts:203-223`. Son demasiados para tabular y `minimumContrastRatio` los
  cubre por el mismo mecanismo de render.
- **No revisé el lado servidor** (`natsapi`, `ormmcli`): qué secuencias de color emite realmente el
  CLI. Si emite un subconjunto acotado, la tabla de la sección 3 se podría reducir a los colores que
  de verdad se usan.
