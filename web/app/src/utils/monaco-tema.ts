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
// LIMITE DELIBERADO: aqui NO se tocan los colores de SINTAXIS (`rules`), y se
// deja `inherit: true` para que los herede del tema base. Motivo: V2-G02 pide
// que todo color computado sea un token del proyecto, pero V2-G05 dice que rojo,
// ambar y verde SOLO significan estado y que el teal SOLO marca accion o
// navegacion. La paleta no tiene ningun hue decorativo, y pintar una cadena de
// verde o un numero de ambar seria exactamente el uso decorativo que G05
// prohibe. Los dos criterios no se pueden satisfacer a la vez para la sintaxis
// con la paleta actual: hace falta decidir si se agrega una paleta de sintaxis
// al sistema de diseno o si la sintaxis queda exenta de G02, como ya lo esta en
// G05. Mientras eso no se decida, el cromo cumple y la sintaxis queda declarada.
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
    "editor.background": token("--obs-field", oscuro ? "#273447" : "#F2F4F7"),
    "editor.foreground": token("--obs-text", oscuro ? "#E6EDF5" : "#16202E"),
    "editorGutter.background": token(
      "--obs-raised",
      oscuro ? "#17253A" : "#F6F8FB",
    ),
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
    editorLineHighlightBorder: token(
      "--obs-border",
      oscuro ? "#1E2D42" : "#D3DCE7",
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
    "input.foreground": token("--obs-text", oscuro ? "#E6EDF5" : "#16202E"),
  };
}

let definidos = false;

/** Define los dos temas. Idempotente: Monaco acepta redefinir con el mismo nombre. */
export function definirTemas() {
  monaco.editor.defineTheme(TEMA_OSCURO, {
    base: "vs-dark",
    inherit: true, // la sintaxis se hereda: ver LIMITE DELIBERADO arriba
    rules: [],
    colors: cromo(true),
  });
  monaco.editor.defineTheme(TEMA_CLARO, {
    base: "vs",
    inherit: true,
    rules: [],
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
