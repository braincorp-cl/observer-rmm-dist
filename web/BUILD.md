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
npm run build   # quasar build → dist/
# copiar el output a web/dist/ y commitear
```

La instalación Ansible despliega `web/dist/` tal cual — el servidor NO
requiere node (decisión D-04, frontend híbrido: fuente + artefacto
versionado, precedente de los binarios nats-api).

Build F008: 2026-06-11, fuente = working tree observer-rmm-web (incluye
features 001-004, flag SSO_DISABLED, cleanup R-08).
