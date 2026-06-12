# Changelog — observer-rmm-web (BrainCorp Spa)

Formato: las entradas más recientes arriba. Cada entrada cita la feature del ciclo forward (`_reversa_forward/NNN-<short-name>/`), la decisión que la origina y, cuando corresponda, los hallazgos cross-repo del hub `observer-rmm`.

## 2026-06-02 — Feature `004-revoke-pdf-object-urls` (cierra WI-DECISION-02 / Q-REP-07)

**Resumen:** corregir memory leak en el módulo Reportes EE. Tres funciones del factory `useReportTemplates()` (`runReportPreview`, `runReport`) y `useReportingHistory()` (`runReportHistory`) creaban `URL.createObjectURL(data)` para PDFs sin revocar el URL anterior, acumulando blobs en sesiones largas. Cierre del watch item registrado en `_reversa_sdd/watch-items.md#wi-decision-02`.

**Disparador:** Q-REP-07 / Reviewer 2026-05-20 — "memory leak progresivo en sesiones largas con muchas previews PDF".

**Mecanismo:** revocación inline guardada por `value.startsWith("blob:")` antes de cada asignación, más `onBeforeUnmount` en los 3 componentes consumidores (`ReportTemplateForm.vue`, `ReportView.vue`, `ReportHistoryView.vue`) para liberar el último blob al desmontaje.

**Archivos tocados:**

- `src/ee/reporting/api/reporting.ts` — guard + `URL.revokeObjectURL` al inicio de `runReportPreview` (L123-124), `runReport` (L148-149) y `runReportHistory` (L721-722)
- `src/ee/reporting/components/ReportTemplateForm.vue` — import `onBeforeUnmount`, hook que revoca `renderedPreview` si es blob
- `src/ee/reporting/views/ReportView.vue` — import `onBeforeUnmount`, hook que revoca `reportData` si es blob
- `src/ee/reporting/views/ReportHistoryView.vue` — import `onBeforeUnmount`, hook que revoca `reportData` si es blob
- `CHANGELOG.md` — esta entrada

**Hallazgo durante el coding:** `RunReportDialog.vue` **NO** desestructura `reportData` ni `renderedPreview` (sólo `reportTemplates`, `isLoading`, `getReportTemplates`, `openReport`, `downloadReport`); el plan original lo incluía como consumidor pero la inspección en disco confirmó que NO lo es. Los consumidores reales son los 3 archivos tocados.

**Verificación:**

- `grep -c "URL.revokeObjectURL" src/ee/reporting/` → **6 invocaciones** (3 en factory + 3 en `onBeforeUnmount` de componentes)
- `npm run lint` exit 0; `npx vue-tsc --noEmit` sin errores nuevos; `npm run build` exit 0
- Comportamiento observable de la SPA sin cambios (RF-07)

**Referencias:**

- `_reversa_forward/004-revoke-pdf-object-urls/{requirements,roadmap,actions,legacy-impact,regression-watch}.md`
- Watch item original: `_reversa_sdd/watch-items.md#wi-decision-02`

## 2026-06-01 — Feature `002-remove-shared-templates` (BrainCorp 2026-06-01)

**Resumen:** la funcionalidad "Importar templates compartidos" se elimina físicamente del frontend del módulo Reportes EE. El componente Vue dialog, el botón en `ReportsManager`, las funciones `getSharedTemplates`/`importSharedTemplates` del factory, el ref reactivo `sharedTemplates` y el tipo `SharedTemplate` se borran de raíz. **Sin reactivación contemplada** (RNF Reversibilidade = `Won't`).

**Disparador:** re-extracción 4 del hub `observer-rmm` (2026-06-01) confirmó que el backend consumía hardcoded `https://raw.githubusercontent.com/amidaware/reporting-templates/master/` (supply-chain risk, GAP-027 / WI-HUB-01 / Q-REP-04 / R-10). BrainCorp decidió eliminación explícita frontend + backend; el hub aplicó cleanup backend en commit `7a6e789a` (2026-06-01 06:00Z).

**Mecanismo:** eliminación quirúrgica bottom-up. El factory `useReportTemplates()` y la singleton `useSharedReportTemplates` (8 consumidores activos en el módulo Reportes) se preservan intactos en su esqueleto; sólo se quitan 3 miembros internos específicos (1 ref + 2 funciones) más el tipo. La asimetría con la feature 001 (SSO) es deliberada: SSO debe poder reactivarse, shared templates no.

**Compatibilidad con datos existentes:** los registros `ReportTemplate` que fueron importados vía Shared Templates en el pasado siguen accesibles, editables y ejecutables. Son indistinguibles de los creados manualmente (RN-NEW-06 del requirements).

**Si BrainCorp quisiera repoblar templates pre-instalados en el futuro:** será nueva implementación desde cero (ADR-014 del hub, deferido — management command con fixtures locales, o fork BrainCorp del repo upstream).

**Archivos tocados:**

- `src/ee/reporting/components/SharedTemplatesImport.vue` — **eliminado** (`git rm`)
- `src/ee/reporting/components/ReportsManager.vue` — eliminados botón "Shared Templates", import del componente y función `openSharedTemplates`
- `src/ee/reporting/api/reporting.ts` — eliminados del factory `useReportTemplates()`: ref `sharedTemplates`, funciones `getSharedTemplates`/`importSharedTemplates`, las 3 entries del return statement, y el import del tipo `SharedTemplate`. Singleton `useSharedReportTemplates` preservada (8 consumidores)
- `src/ee/reporting/types/reporting.ts` — eliminada `interface SharedTemplate`
- `CHANGELOG.md` — esta entrada

**Verificación (`npm run build` + `vue-tsc`):**

- `grep -rE "SharedTemplate|SharedTemplatesImport|getSharedTemplates|importSharedTemplates|useSharedTemplatesStore" src/` → **0 ocurrencias**
- `npx vue-tsc --noEmit` → sin errores nuevos (sólo 2 deprecation warnings pre-existentes del tsconfig)
- `npm run build` → exit 0, dist/ 18MB
- `grep -rE "SharedTemplate|SharedTemplatesImport|getSharedTemplates|importSharedTemplates|templates/shared" dist/` → **0 ocurrencias** (eliminación más radical que el flag de feature 001)

**Referencias cross-repo:**

- Hub `observer-rmm` commit `7a6e789a` (2026-06-01 06:00Z) — cleanup backend correspondiente
- Hub `observer-rmm` ADR-014 (deferido) — política sobre dependencia de template repo upstream
- `_reversa_forward/002-remove-shared-templates/{requirements,roadmap,actions,investigation,data-delta,onboarding,legacy-impact,regression-watch}.md` — artefactos del ciclo forward
- Memoria local: `acciones-pendientes-re-extraccion-4-hub` cierra la decisión 2 con esta feature

## 2026-06-01 — Feature `001-disable-sso-ui` (BrainCorp 2026-06-01)

**Resumen:** la UI de Single Sign-On queda deshabilitada en este repo hasta nuevo aviso. La interfaz de login, las opciones de Core Settings y las rutas SSO no se renderizan ni se invocan. El módulo `src/ee/sso/` se preserva sin modificaciones (excepto un comentario JSDoc en `ProviderCallback.vue`).

**Disparador:** re-extracción 4 del hub `observer-rmm` (2026-06-01) confirmó leak de OAuth `client_secret` en texto plano en 3 serializers backend (GAP-024 / Q-SSO-03 / R-07). BrainCorp decidió deshabilitar la UI mientras el hub planifica mitigaciones (ADR-013 deferido) o se materializa F008 (greenfield `observer-rmm-dist`).

**Mecanismo:** flag de build `SSO_DISABLED` (default `"true"`) declarado en `quasar.config.js#build.env`. Vite evalúa el flag en tiempo de build; el tree-shake elimina el chunk SSO del bundle cuando está activo.

**Cómo reactivar SSO en el futuro:**

```bash
export SSO_DISABLED=false
npm run build
# Verificar antes con el equipo del hub que ADR-013 esté aplicado.
```

**Archivos tocados:**

- `quasar.config.js` — nueva variable en `build.env`
- `.env.example` — documentación de la variable
- `src/router/routes.js` — entrada `/account/provider/callback` con `beforeEnter` → `Login`
- `src/views/LoginView.vue` — import estático SSO → dynamic import condicional dentro de `onMounted`
- `src/components/modals/coresettings/EditCoreSettings.vue` — import estático `SSOProvidersTable` → `defineAsyncComponent` condicional; tab y panel "sso" bajo `v-if="ssoEnabled"`
- `src/ee/sso/views/ProviderCallback.vue` — comentario JSDoc marcando huérfano (única modificación dentro de `src/ee/sso/`)
- `CHANGELOG.md` — archivo creado (esta entrada)

**Referencias cross-repo:**

- Hub `observer-rmm` commit `7a6e789a` (cleanup backend de templates compartidos, 2026-06-01) — feature hermana, no incluida en este commit.
- Hub `observer-rmm` ADR-013 (política de secrets SSO) — diferido.
- `_reversa_forward/001-disable-sso-ui/{requirements,roadmap,actions,legacy-impact,regression-watch}.md` — artefactos del ciclo forward.
- Memoria local: `acciones-pendientes-re-extraccion-4-hub` registra la decisión BrainCorp 2026-06-01.

**Watch items abiertos:** 8 (W001–W008) en `_reversa_forward/001-disable-sso-ui/regression-watch.md`. La próxima re-extracción reversa (`/reversa`) debe verificarlos.

**Próxima feature en serie:** `002-remove-shared-templates` (eliminar UI de templates compartidos en reporting, espejo del cleanup backend del hub).
