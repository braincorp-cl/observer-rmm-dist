import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import cssWorker from "monaco-editor/esm/vs/language/css/css.worker?worker";
import htmlWorker from "monaco-editor/esm/vs/language/html/html.worker?worker";
import jsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";

import { Dark, LoadingBar } from "quasar";
import { watch } from "vue";

import { boot } from "quasar/wrappers";

import { aplicarTemaDeMonaco, definirTemas } from "@/utils/monaco-tema";

export default boot(() => {
  // V2-G02/G04 (2026-11-12): hasta hoy NINGUN editor reaccionaba al cambio de
  // tema. Los 8 sitios elegian vs-dark o vs-light al CREAR el editor y no habia
  // un solo setTheme ni un watcher del modo oscuro en el arbol, asi que al
  // cambiar de tema con un editor abierto Monaco se quedaba con el anterior
  // mientras las variables CSS ya habian cambiado. setTheme es GLOBAL, de modo
  // que una sola llamada alcanza para todos los editores vivos.
  // V2-G02 (2026-11-13): el color de la barra de carga se fija ACA y no en
  // `getDashInfo`. 🪤 Mi arreglo anterior lo saco de `if (edited)` —eso corrigio
  // SI corre— pero no CUANDO: `getDashInfo` es una accion async y la barra se
  // pinta durante la PRIMERA peticion, antes de que esa respuesta llegue. En una
  // ventana remota recien abierta (takecontrol, webterm, webvnc, que abren con
  // window.open y arrancan una instancia nueva) siempre ganaba el rojo de
  // fabrica de Quasar, #f44336, que no es token y ademas es color de ESTADO
  // usado para comunicar actividad. Medido en las tres superficies remotas en
  // las corridas de f1c251b y de 3de2fc0.
  //
  // `secondary` es el neutro que la ola 046 ya habia elegido. La preferencia del
  // usuario sigue pudiendo cambiarlo despues: `getDashInfo` llama a setDefaults
  // otra vez con el valor guardado, y gana la ultima llamada.
  LoadingBar.setDefaults({ color: "secondary" });

  definirTemas();
  watch(
    () => Dark.isActive,
    (oscuro) => aplicarTemaDeMonaco(oscuro),
    { immediate: true },
  );

  self.MonacoEnvironment = {
    getWorker(_: unknown, label: string) {
      if (label === "json") {
        return new jsonWorker();
      }
      if (label === "css" || label === "scss" || label === "less") {
        return new cssWorker();
      }
      if (label === "html" || label === "handlebars" || label === "razor") {
        return new htmlWorker();
      }
      return new editorWorker();
    },
  };
});
