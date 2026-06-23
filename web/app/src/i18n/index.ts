import en from "./en.json";
import es from "./es.json";

// Catálogos agregados que consume el boot de vue-i18n (src/boot/i18n.ts).
// Fuente única en JSON: la usan el runtime y el gate i18n de ESLint
// (@intlify/eslint-plugin-vue-i18n, ver .eslintrc.js → settings.vue-i18n.localeDir).
export default {
  en,
  es,
};
