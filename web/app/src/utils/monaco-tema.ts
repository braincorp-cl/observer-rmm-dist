// Tema de Monaco construido con los tokens del proyecto (V2-G02 / V2-G04).
//
// POR QUE EXISTE
//
// 1. Los 8 sitios que crean un editor elegian `vs-dark` o `vs-light` UNA SOLA
//    VEZ, al construirlo, y no habia un solo `setTheme` ni un watcher del modo
//    oscuro en todo el arbol. Si el usuario cambia de tema con el editor ya
//    abierto, Monaco se queda con el anterior mientras las variables CSS del
//    documento ya cambiaron. Medido el 2026-11-12: axe reporto 2,74:1 con
//    `fg #52647a` -el valor CLARO de --obs-faint- sobre `bg #1e1e1e`, que es el
//    fondo de `vs-dark`. Un arreglo por CSS no podia funcionar: mezclaba un
//    token que reacciona al tema con un editor que no.
//
// 2. El cromo del editor -fondo, canaleta, numeros de linea, seleccion, regla-
//    son superficies y texto, asi que tienen token propio y se pueden mapear
//    sin inventar colores.
//
// 3. LA SINTAXIS (decidido el 2026-11-14, antes era un LIMITE DELIBERADO)
//
//    El limite anterior decia que no se tocaban los `rules` y que el minimo de
//    la sintaxis heredada quedaba en 4,75 sobre `--obs-deep`. Eso era FALSO, y
//    el error era de muestreo: 4,75 se calculo sobre las SEIS clases `mtk` que
//    el script de ejemplo alcanzaba a renderizar. `vs_dark` declara 42 scopes,
//    y el minimo real sobre `--obs-deep` es 3,28 (`variable.predefined`
//    #4864aa). Dos scopes violaban G04 sobre el fondo propio del editor, sin
//    ningun velo de por medio.
//
//    Peor: el 13-11 agregue velos (linea actual `--obs-hover`, seleccion
//    `--obs-selected`) para cerrar un residuo de V2-G02, y esos velos son mas
//    CLAROS que `--obs-deep`, asi que hundieron la sintaxis heredada. El
//    arreglo de G02 fabrico el rojo de G04: `comment` #608b4e pasa de 4,73
//    sobre el fondo a 3,89 sobre la linea actual y 3,76 sobre la seleccion.
//    El techo es duro: para que #608b4e llegue a 4,5 el fondo necesita
//    luminancia <= 0,00888, y `--obs-hover` tiene 0,01813. Ningun velo visible
//    cabe debajo de la paleta heredada.
//
//    DECISION: se mantiene `inherit: true` y se sobreescriben por `rules` SOLO
//    los scopes que no llegan a 4,8 sobre la PEOR capa donde se pinta texto
//    (oscuro `--obs-selected` #132A34, claro `--obs-surface` #FFFFFF),
//    subiendoles la luminosidad en HSL y dejando H y S intactos. No se agrega
//    ningun matiz nuevo, asi que no choca con G05 -que ademas ya exime a la
//    sintaxis-. 15 scopes en oscuro y 18 en claro, mas el nivel 2 de corchete de
//    claro; el resto sigue heredado. Comprobado cerrando el ciclo sobre este
//    mismo archivo -45 y 46 primeros planos por 4 capas = 364 pares-: CERO
//    pares bajo 4,5, con minimo 5,00 en oscuro (`metatag` sobre #132A34) y
//    4,96 en claro (`keyword.flow` #AF00DB sobre #F2F4F7, que se hereda).
//
//    🪤 `editor.selectionForeground` NO es una salida: `selections.js` registra
//    la regla CSS, pero `viewLine.js` solo agrega la clase
//    `inline-selected-text` que la lleva `if (isHighContrast(themeType))`. Un
//    tema con `base: "vs-dark"` nunca la recibe.
import * as monaco from "monaco-editor";

export const TEMA_CLARO = "obs-claro";
export const TEMA_OSCURO = "obs-oscuro";

// Lee un token del documento. Se lee en caliente y no se cachea: el valor
// cambia con el tema, y es justo el cambio lo que este modulo existe para
// seguir.
function token(nombre: string, respaldo: string): string {
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(nombre)
    .trim();
  return v || respaldo;
}

function cromo(oscuro: boolean): monaco.editor.IStandaloneThemeData["colors"] {
  return {
    // 🔑 El fondo OSCURO es --obs-deep y no --obs-field, y la razon es medida:
    // con inherit:true los colores de sintaxis vienen de vs-dark, que los
    // diseno contra SU fondo (#1e1e1e). Poner --obs-field (#273447), que es mas
    // CLARO, les quitaba contraste: .mtk9 (#569cd6) caia de 5,65 a 4,27 y axe
    // lo marco en 4,26 — la violacion la introduje yo al cambiar el fondo y
    // heredar los primeros planos. El fondo y los primeros planos de un tema
    // son un PAR; no se puede tomar uno del sistema de diseno y el otro de
    // vs-dark. --obs-deep (#0A1220) es mas oscuro que #1e1e1e, asi que lo
    // heredado GANA contraste: el minimo de los seis tokens de sintaxis pasa de
    // 4,22 (sobre el propio fondo de vs-dark) a 4,75. En claro no hay problema:
    // --obs-field claro (#F2F4F7) deja el minimo en 4,66.
    "editor.background": token(
      oscuro ? "--obs-deep" : "--obs-field",
      oscuro ? "#0A1220" : "#F2F4F7",
    ),
    "editor.foreground": token("--obs-text", oscuro ? "#E6EDF5" : "#16202E"),
    // Los numeros de linea: el inactivo es el que axe marcaba a 1,75 y luego a
    // 2,74. Con --obs-muted sobre --obs-field queda sobre 4,5:1 en los dos temas.
    "editorLineNumber.foreground": token(
      "--obs-muted",
      oscuro ? "#8FA3BC" : "#52647A",
    ),
    "editorLineNumber.activeForeground": token(
      "--obs-text",
      oscuro ? "#E6EDF5" : "#16202E",
    ),
    "editorLineNumber.dimmedForeground": token(
      "--obs-muted",
      oscuro ? "#8FA3BC" : "#52647A",
    ),
    "editorIndentGuide.background": token(
      "--obs-border",
      oscuro ? "#1E2D42" : "#D3DCE7",
    ),
    "editorIndentGuide.activeBackground": token(
      "--obs-muted",
      oscuro ? "#8FA3BC" : "#52647A",
    ),
    // 🪤 V2-G04 (2026-11-14): esta clave decia `editorLineHighlightBorder`, SIN
    // el punto. Los ids de color de Monaco son punteados; `editor.lineHighlightBorder`
    // existe en el registro y `editorLineHighlightBorder` NO, asi que Monaco la
    // descartaba en silencio y el borde de la linea actual era el #282828 de
    // vs-dark -que no es ningun token-. Nadie lo midio porque el relleno opaco
    // que puse el 13-11 lo tapaba: un arreglo escondiendo al de al lado.
    // V2-G02 (2026-11-19): el contorno del editor enfocado tomaba el
    // focusBorder por defecto de vs/vs-dark (rgb(0,127,212) / rgb(0,144,241)),
    // fuera del set. Pasa al token de foco del proyecto.
    focusBorder: token("--obs-focus", oscuro ? "#E6EDF5" : "#16202E"),
    "editor.lineHighlightBorder": token(
      "--obs-border",
      oscuro ? "#1E2D42" : "#D3DCE7",
    ),
    // V2-G02 (2026-11-13): claves que el primer tema no puso y que el censo
    // midió fuera del set de tokens: la línea actual, la selección y el
    // resaltado de coincidencias. Medidas como `current-line-exact` y
    // `rgba(121,121,121,…)` en 16 bloques de 8 superficies.
    "editor.lineHighlightBackground": token(
      "--obs-hover",
      oscuro ? "#17253A" : "#F6F8FB",
    ),
    "editor.selectionBackground": token(
      "--obs-selected",
      oscuro ? "#132A34" : "#EEF8FA",
    ),
    "editor.inactiveSelectionBackground": token(
      "--obs-raised",
      oscuro ? "#17253A" : "#F6F8FB",
    ),
    "editor.selectionHighlightBackground": token(
      "--obs-selected",
      oscuro ? "#132A34" : "#EEF8FA",
    ),
    "editor.wordHighlightBackground": token(
      "--obs-selected",
      oscuro ? "#132A34" : "#EEF8FA",
    ),
    "editorCursor.foreground": token(
      "--obs-text",
      oscuro ? "#E6EDF5" : "#16202E",
    ),
    // 🔴 V2-G02 (2026-11-15): sin esta clave Monaco la DERIVA como la inversa
    // por canal del foreground del caret, y ese valor derivado no pertenece a
    // ningun token: --obs-text oscuro es rgb(230,237,245) y el `color` medido
    // del nodo `.monaco-editor .cursor` salia rgb(25,18,10) -255 menos cada
    // canal-, con su simetrico en claro. Por eso ningun grep lo encontraba:
    // nadie lo habia escrito. Es el color del GLIFO bajo el caret de bloque, o
    // sea el fondo del editor, y la enmienda del 2026-11-12 dice que en el
    // cromo cualquier color fuera del set sigue violando.
    "editorCursor.background": token(
      oscuro ? "--obs-deep" : "--obs-field",
      oscuro ? "#0A1220" : "#F2F4F7",
    ),
    "editorWidget.background": token(
      "--obs-surface",
      oscuro ? "#131F31" : "#FFFFFF",
    ),
    "editorWidget.border": token(
      "--obs-border",
      oscuro ? "#1E2D42" : "#D3DCE7",
    ),
    "input.background": token("--obs-field", oscuro ? "#273447" : "#F2F4F7"),
    "editorGutter.background": token(
      "--obs-deep",
      oscuro ? "#0A1220" : "#F6F8FB",
    ),
    "input.foreground": token("--obs-text", oscuro ? "#E6EDF5" : "#16202E"),
    // V2-G02 (2026-11-14): el residuo `rgba(121,121,121,0.2 / 0.4)` que el censo
    // midio fuera del set de tokens NO era la linea actual ni la seleccion -esa
    // atribucion mia del 13-11 estaba equivocada-: son los DESLIZADORES.
    // `scrollbarSlider.background` vale #797979 al 40 % en vs-dark y
    // `minimapSlider.background` se deriva de el al 50 % (de ahi el 0,2), asi que
    // definir solo el primero dejaria el segundo en un rgba compuesto que
    // tampoco es token. Se definen los seis, opacos, sobre la rampa neutra:
    // borde en reposo, muted al pasar por encima, texto al arrastrar.
    "scrollbarSlider.background": token(
      "--obs-border",
      oscuro ? "#1E2D42" : "#D3DCE7",
    ),
    "scrollbarSlider.hoverBackground": token(
      "--obs-muted",
      oscuro ? "#8FA3BC" : "#52647A",
    ),
    "scrollbarSlider.activeBackground": token(
      "--obs-text",
      oscuro ? "#E6EDF5" : "#16202E",
    ),
    "minimapSlider.background": token(
      "--obs-border",
      oscuro ? "#1E2D42" : "#D3DCE7",
    ),
    "minimapSlider.hoverBackground": token(
      "--obs-muted",
      oscuro ? "#8FA3BC" : "#52647A",
    ),
    "minimapSlider.activeBackground": token(
      "--obs-text",
      oscuro ? "#E6EDF5" : "#16202E",
    ),
    // 🪤 V2-G04 + V2-G02: los velos del buscador venian heredados
    // (`findMatchBackground` #515C6A deja la sintaxis en 1,19 y
    // `findMatchHighlightBackground` #EA5C0055 ni es token). Mi primer intento
    // los bajo a `--obs-border`, y eso REPITIO el error que este archivo
    // documenta: agregar un fondo sin recalcular el par. En claro
    // `--obs-border` #D3DCE7 deja `comment` #008000 en 3,7, y en oscuro
    // #1E2D42 es mas claro que `--obs-selected`, o sea movia la peor capa.
    // 🔑 Los dos rellenos van a `--obs-selected`, que YA esta dentro de la
    // envolvente contra la que se calcularon las reglas, y la coincidencia
    // actual se distingue por BORDE. El borde va en `--obs-muted` y no en el
    // teal de `--obs-primary` para no abrir una discusion de G05 por un color
    // de accion donde no hay accion.
    "editor.findMatchBackground": token(
      "--obs-selected",
      oscuro ? "#132A34" : "#EEF8FA",
    ),
    "editor.findMatchBorder": token(
      "--obs-muted",
      oscuro ? "#8FA3BC" : "#52647A",
    ),
    "editor.findMatchHighlightBackground": token(
      "--obs-selected",
      oscuro ? "#132A34" : "#EEF8FA",
    ),
    "editor.findMatchHighlightBorder": token(
      "--obs-muted",
      oscuro ? "#8FA3BC" : "#52647A",
    ),
    // El velo del buscador que SI se midio: #141B29 son 2 nodos a 4,34, y es
    // `rangeHighlightBackground`, que en vs-dark vale #ffffff0b -blanco al
    // 4,31 % sobre --obs-deep-. Heredado, nunca definido. Va a `--obs-hover`,
    // que es la capa de linea actual y ya esta en la envolvente.
    "editor.rangeHighlightBackground": token(
      "--obs-hover",
      oscuro ? "#17253A" : "#F6F8FB",
    ),
    // Los corchetes NO salen de `rules` sino de `colors`, y por eso no los
    // cubria la tabla de arriba: son el `mtk10` que mi evidencia midio como
    // rgb(255,215,0) en oscuro y rgb(4,49,250) en claro. De los 6 niveles solo
    // 3 son visibles (4, 5 y 6 valen #00000000). El unico que no pasa es el
    // nivel 2 en claro: #319331 da 3,56 sobre --obs-field.
    "editorBracketHighlight.foreground1": oscuro ? "#FFD700" : "#0431FA",
    "editorBracketHighlight.foreground2": oscuro ? "#DA70D6" : "#287828",
    "editorBracketHighlight.foreground3": oscuro ? "#179FFF" : "#7B3814",
    // 🪤 Y el SEPTIMO color de corchete, que no esta numerado y por eso se me
    // paso: `unexpectedBracket.foreground` -el corchete sin par-. En vs-dark y
    // en vs vale `rgba(255,18,18,0.8)`, y COMPUESTO sobre cada capa da 3,32 /
    // 2,82 / 2,71 en oscuro y 3,56 / 3,69 / 3,64 / 3,93 en claro: los SEIS
    // cruces violan 4,5. Aparece cada vez que alguien teclea un corchete que
    // todavia no cierra, o sea casi siempre mientras se escribe codigo.
    // Se le dan los mismos valores que a la regla `invalid`, porque es la misma
    // semantica -un corchete sin par ES un token invalido- y ya estan medidos
    // en 5,01 y 5,02 sobre la peor capa de cada tema.
    "editorBracketHighlight.unexpectedBracket.foreground": oscuro
      ? "#F66767"
      : "#C42F2F",
  };
}

/**
 * Scopes de sintaxis que se sobreescriben. Solo los que no llegan a 4,8 sobre
 * la PEOR capa donde se pinta texto; H y S intactos, se mueve la luminosidad.
 * El resto los hereda del tema base (`inherit: true`).
 *
 * 🪤 La primera version de esta tabla uso #FFFFFF como peor capa del tema
 * CLARO, y eso esta AL REVES: con primeros planos oscuros el blanco es el
 * MEJOR fondo, no el peor. La peor capa clara es `--obs-field` #F2F4F7, que es
 * el fondo propio del editor. Con la referencia correcta no son 13 scopes sino
 * 19: `predefined.sql` #C700C7 daba 4,48 y `metatag.content.html` #FF0000
 * daba 3,63. El mismo error de direccion ya me habia costado G04 dos veces.
 *
 * Capas consideradas, y son las unicas que el tema pinta debajo de sintaxis:
 *   oscuro  deep #0A1220 (editor) · hover #17253A (linea actual) ·
 *           selected #132A34 (seleccion, resaltes y buscador) · surface #131F31
 *   claro   field #F2F4F7 (editor) · raised #F6F8FB · selected #EEF8FA ·
 *           surface #FFFFFF
 * Peor: oscuro la MAS CLARA (#132A34), claro la MAS OSCURA (#F2F4F7).
 */
function reglas(oscuro: boolean): monaco.editor.ITokenThemeRule[] {
  return oscuro
    ? [
        { token: "invalid", foreground: "F66767" }, // #f44747 daba 4.15
        { token: "variable.predefined", foreground: "8095C9" }, // #4864AA daba 2.61
        { token: "comment", foreground: "70A35B" }, // #608B4E daba 3.76
        { token: "regexp", foreground: "C282A8" }, // #B46695 daba 3.75
        { token: "annotation", foreground: "D47E7E" }, // #cc6666 daba 4.02
        { token: "delimiter.html", foreground: "969696" }, // #808080 daba 3.78
        { token: "delimiter.xml", foreground: "969696" }, // #808080 daba 3.78
        { token: "tag.id.pug", foreground: "7998C2" }, // #4F76AC daba 3.21
        { token: "tag.class.pug", foreground: "7998C2" }, // #4F76AC daba 3.21
        { token: "metatag", foreground: "E0767B" }, // #DD6A6F daba 4.52
        { token: "string.sql", foreground: "FF5F5F" }, // #FF0000 daba 3.73
        { token: "operator.scss", foreground: "969696" }, // #909090 daba 4.67
        { token: "operator.sql", foreground: "8998A6" }, // #778899 daba 4.09
        { token: "operator.swift", foreground: "969696" }, // #909090 daba 4.67
        { token: "predefined.sql", foreground: "FF2CFF" }, // #FF00FF daba 4.75
      ]
    : [
        { token: "invalid", foreground: "C42F2F" }, // #cd3131 daba 4.67
        { token: "constant", foreground: "D40000" }, // #dd0000 daba 4.68
        { token: "comment", foreground: "007A00" }, // #008000 daba 4.66
        { token: "number", foreground: "08784F" }, // #098658 daba 4.18
        { token: "annotation", foreground: "686868" }, // #808080 daba 3.58
        { token: "type", foreground: "007575" }, // #008080 daba 4.33
        { token: "tag.id.pug", foreground: "476A9B" }, // #4F76AC daba 4.22
        { token: "tag.class.pug", foreground: "476A9B" }, // #4F76AC daba 4.22
        { token: "metatag", foreground: "D40000" }, // #e00000 daba 4.57
        { token: "metatag.content.html", foreground: "D40000" }, // #FF0000 daba 3.63
        { token: "metatag.html", foreground: "686868" }, // #808080 daba 3.58
        { token: "metatag.xml", foreground: "686868" }, // #808080 daba 3.58
        { token: "attribute.name", foreground: "D40000" }, // #FF0000 daba 3.63
        { token: "attribute.value.number", foreground: "08784F" }, // #098658 daba 4.18
        { token: "attribute.value.unit", foreground: "08784F" }, // #098658 daba 4.18
        { token: "string.sql", foreground: "D40000" }, // #FF0000 daba 3.63
        { token: "operator.sql", foreground: "5B6A7A" }, // #778899 daba 3.31
        { token: "predefined.sql", foreground: "BA00BA" }, // #C700C7 daba 4.48
      ];
}

let definidos = false;

/** Define los dos temas. Idempotente: Monaco acepta redefinir con el mismo nombre. */
export function definirTemas() {
  monaco.editor.defineTheme(TEMA_OSCURO, {
    base: "vs-dark",
    inherit: true, // el resto de la sintaxis se hereda: ver el punto 3 arriba
    rules: reglas(true),
    colors: cromo(true),
  });
  monaco.editor.defineTheme(TEMA_CLARO, {
    base: "vs",
    inherit: true,
    rules: reglas(false),
    colors: cromo(false),
  });
  definidos = true;
}

/** El nombre del tema que corresponde al modo actual. */
export function temaDeMonaco(oscuro: boolean): string {
  if (!definidos) definirTemas();
  return oscuro ? TEMA_OSCURO : TEMA_CLARO;
}

/**
 * Aplica el tema a TODOS los editores vivos. Se llama cuando el modo cambia:
 * `monaco.editor.setTheme` es global, no por instancia, asi que una sola
 * llamada alcanza y no hace falta que cada componente se entere.
 *
 * Se redefinen los temas antes de aplicarlos porque sus colores salen de las
 * variables CSS, que acaban de cambiar de valor.
 */
export function aplicarTemaDeMonaco(oscuro: boolean) {
  definirTemas();
  monaco.editor.setTheme(oscuro ? TEMA_OSCURO : TEMA_CLARO);
}
