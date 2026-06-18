# Build del frontend — pin de reproducibilidad (D-04 / F008)

El artefacto en `web/dist/` se genera desde el fuente en `web/app/`:

| Componente | Versión pineada |
|---|---|
| Node.js | 22.x LTS (build F008: v22.22.2) |
| npm | 11.x (build F008: 11.12.1) |
| quasar | 2.18.5 (lockfile) |
| @quasar/app-vite | 1.10.2 (lockfile) |

```bash
cd web/app
npm ci          # respeta package-lock.json (incluido en el squash)
npm run build   # quasar build → app/dist/ (distDir="dist/" en quasar.config.js)

# reconstituir el artefacto versionado web/dist/ desde el output del build:
cd ..           # = web/
OUT=app/dist; [ -f app/dist/spa/index.html ] && OUT=app/dist/spa
rm -rf dist && cp -r "$OUT" dist
grep -q . dist/index.html && echo "OK: web/dist/ regenerado"
# commitear web/ (NO usar git add -A: ansible.cfg/inventory/staging.yml van excluidos)
```

La instalación Ansible despliega `web/dist/` tal cual — el servidor NO
requiere node (decisión D-04, frontend híbrido: fuente + artefacto
versionado, precedente de los binarios nats-api).

Procedencia de la fuente:
- Build F008: 2026-06-11, fuente = working tree observer-rmm-web (features
  001-004, flag SSO_DISABLED, cleanup R-08). **Artefacto pre-rebrand.**
- Re-staging 2026-06-18: fuente actualizada a observer-rmm-web @ `23643ce`
  (incorpora rebrand cero-tactical `ae485de` — `TacticalDropdown/Table.vue`
  → `Observer*`, 34 archivos — y discard Reports/SSO `23643ce`, ADR-010).
  Corrige el drift: `web/app/src` pasó de 146 a 7 hits `tactical` (los 7 =
  URLs `docs.tacticalrmm.com`, excepción R-03 por diseño / `TODO F007.2`).
  **El artefacto `web/dist/` debe regenerarse con el comando de arriba**
  (Node 22.22.2) para reflejar esta fuente — hasta entonces queda stale.
