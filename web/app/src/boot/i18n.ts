import { boot } from "quasar/wrappers";
import { createI18n } from "vue-i18n";
import { Lang } from "quasar";
import langEn from "quasar/lang/en-US";
import langEs from "quasar/lang/es";
import messages from "@/i18n";

// Idiomas soportados en v1 (RN-02). Cualquier otro valor degrada a "en" (RN-08).
export const SUPPORTED_LOCALES = ["en", "es"] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

declare global {
  interface Window {
    _env_?: { PROD_URL?: string; DEFAULT_LANG?: string };
  }
}

function isSupported(value: unknown): value is AppLocale {
  return (
    typeof value === "string" &&
    (SUPPORTED_LOCALES as readonly string[]).includes(value)
  );
}

// Resolución inicial (pre-login, RN-01): el idioma por defecto del servidor llega por
// env-config.js (window._env_.DEFAULT_LANG, generado por observer_proxy / GAP-045).
// En dev (sin env-config.js) y ante valor no soportado, cae a "en".
function resolveInitialLocale(): AppLocale {
  const envLang =
    typeof window !== "undefined" && window._env_
      ? window._env_.DEFAULT_LANG
      : undefined;
  return isSupported(envLang) ? envLang : "en";
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: resolveInitialLocale(),
  fallbackLocale: "en",
  messages,
});

// Aplica un locale a vue-i18n y mantiene sincronizado el language pack de Quasar
// (componentes nativos: date pickers, paginación, diálogos). Robusto: idioma no
// soportado -> "en" sin romper la UI.
export function applyLocale(locale: unknown): void {
  const lang: AppLocale = isSupported(locale) ? locale : "en";
  i18n.global.locale.value = lang;
  Lang.set(lang === "es" ? langEs : langEn);
}

export default boot(({ app }) => {
  app.use(i18n);
  applyLocale(i18n.global.locale.value);
});
