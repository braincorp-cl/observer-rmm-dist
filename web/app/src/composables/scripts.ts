import { ref, watch, computed, onMounted, onBeforeUnmount } from "vue";
import { useStore } from "vuex";
import { useQuasar } from "quasar";
import { useI18n } from "vue-i18n";
import { fetchScripts } from "@/api/scripts";
import {
  formatScriptOptions,
  removeExtraOptionCategories,
} from "@/utils/format";
import type { Script } from "@/types/scripts";
import { AgentPlatformType } from "@/types/agents";

export interface ScriptOption extends Script {
  label: string;
  value: number;
}

export interface useScriptDropdownParams {
  script?: number; // set a selected script on init
  plat?: AgentPlatformType; // set a platform for filterByPlatform
  onMount?: boolean; // loads script options on mount
}

// script dropdown
export function useScriptDropdown(opts?: useScriptDropdownParams) {
  const scriptOptions = ref([] as ScriptOption[]);
  const defaultTimeout = ref(30);
  const defaultArgs = ref([] as string[]);
  const defaultEnvVars = ref([] as string[]);
  const script = ref(opts?.script);
  const scriptName = ref("");
  const syntax = ref<string | undefined>("");
  const plat = ref<AgentPlatformType | undefined>(opts?.plat);

  // specify parameters to filter out the product's script templates
  async function getScriptOptions() {
    scriptOptions.value = Object.freeze(
      formatScriptOptions(
        // `showCommunityScripts` es el nombre del query param que espera el
        // backend (scripts/views.py): se manda tal cual a propósito.
        await fetchScripts({
          showCommunityScripts: showScriptTemplates.value,
        }),
      ),
    ) as ScriptOption[];
  }

  // watch scriptPk for changes and update the default timeout and args
  watch([script, scriptOptions], () => {
    if (script.value && scriptOptions.value.length > 0) {
      const tmpScript = scriptOptions.value.find(
        (i) => i.value === script.value,
      );

      if (tmpScript) {
        defaultTimeout.value = tmpScript.default_timeout;
        defaultArgs.value = tmpScript.args;
        defaultEnvVars.value = tmpScript.env_vars;
        syntax.value = tmpScript.syntax;
        scriptName.value = tmpScript.label;
      }
    }
  });

  // vuex show script templates
  const store = useStore();
  const showScriptTemplates = computed(() => store.state.showScriptTemplates);

  // filter for only getting server tasks
  const serverScriptOptions = computed(
    () =>
      removeExtraOptionCategories(
        scriptOptions.value.filter(
          (script) =>
            script.category ||
            !script.supported_platforms ||
            script.supported_platforms.length === 0 ||
            script.supported_platforms.includes("linux"),
        ),
      ) as ScriptOption[],
  );

  const filterByPlatformOptions = computed(() => {
    if (!plat.value) {
      return scriptOptions.value;
    } else {
      return removeExtraOptionCategories(
        scriptOptions.value.filter(
          (script) =>
            script.category ||
            !script.supported_platforms ||
            script.supported_platforms.length === 0 ||
            script.supported_platforms.includes(plat.value!),
        ),
      ) as ScriptOption[];
    }
  });

  function reset() {
    defaultTimeout.value = 30;
    defaultArgs.value = [];
    defaultEnvVars.value = [];
    script.value = undefined;
    syntax.value = "";
  }

  if (opts?.onMount) onMounted(() => getScriptOptions());

  return {
    //data
    script,
    defaultTimeout,
    defaultArgs,
    defaultEnvVars,
    scriptName,
    syntax,
    plat,

    scriptOptions, // unfiltered options
    serverScriptOptions, // only scripts that can run on server
    filterByPlatformOptions, // use the returned plat to change options

    //methods
    getScriptOptions,
    reset, // resets dropdown selection state
  };
}

// Indicador de espera del borrador con IA.
//
// El backend le da al proveedor hasta 120 s, y hay modelos gratuitos que se
// acercan a ese techo. Una rueda muda durante dos minutos se lee como una
// consola colgada, así que el contador va mostrando los segundos transcurridos:
// es la única señal de que la petición sigue viva.
export function useAiDraftLoader() {
  const $q = useQuasar();
  const { t } = useI18n();

  let timer: ReturnType<typeof setInterval> | undefined;

  function start() {
    const startedAt = Date.now();

    const render = () =>
      $q.loading.show({
        message: t("scriptsCommon.generatingScript", {
          secs: Math.round((Date.now() - startedAt) / 1000),
        }),
      });

    render();
    timer = setInterval(render, 1000);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = undefined;
    $q.loading.hide();
  }

  // Si el modal se destruye con la petición en vuelo (cerrar la consola, por
  // ejemplo) el intervalo quedaría corriendo contra un `$q.loading` huérfano.
  onBeforeUnmount(stop);

  return { start, stop };
}

export const shellOptions = [
  { label: "Powershell", value: "powershell" },
  { label: "Batch", value: "cmd" },
  { label: "Python", value: "python" },
  { label: "Shell", value: "shell" },
  { label: "Nushell", value: "nushell" },
  { label: "Deno", value: "deno" },
];
