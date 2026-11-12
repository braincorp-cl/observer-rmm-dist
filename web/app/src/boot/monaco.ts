import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import cssWorker from "monaco-editor/esm/vs/language/css/css.worker?worker";
import htmlWorker from "monaco-editor/esm/vs/language/html/html.worker?worker";
import jsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";

import { Dark } from "quasar";
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
