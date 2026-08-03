# Build del frontend — pin de reproducibilidad (D-04 / F008)

El artefacto en `web/dist/` se genera desde el fuente en `web/app/`:

| Componente | Versión pineada |
|---|---|
| Node.js | 22.x LTS (build F008: v22.22.2) |
| npm | 11.x (build F008: 11.12.1) |
| quasar | 2.18.5 (lockfile) |
| @quasar/app-vite | 1.10.2 (lockfile) |

## `web/dist/` NO se versiona — lo regenera el deploy

`web/dist/` está en `.gitignore` (no entra al repo). El playbook `install.yml`
lo **regenera automáticamente** en el control node, en un play dedicado
(`Build del frontend SPA en el control node`, `hosts: localhost`) que corre
ANTES de que el rol `observer_proxy` lo sincronice al servidor. No hay que
construir a mano ni commitear el artefacto.

- Omitir el build (re-deploy sin cambios de frontend, usando el `web/dist/` ya
  presente): `ansible-playbook install.yml ... -e observer_frontend_build=false`
- Construir solo el frontend: `ansible-playbook install.yml ... --tags frontend_build`

El control node (la máquina que corre `ansible-playbook`) necesita el toolchain
Node (referencia 22.22.2); el servidor destino NO requiere node — solo recibe el
`web/dist/` ya construido vía `synchronize` (decisión D-04, frontend híbrido:
fuente versionada + artefacto regenerado en deploy).

### Build manual (standalone / debug) — equivalente a lo que hace el play

```bash
cd web/app
npm ci          # respeta package-lock.json
npm run build   # quasar build → app/dist/ (distDir="dist/" en quasar.config.js)

# reconstituir el artefacto desplegable web/dist/ desde el output del build:
cd ..           # = web/
OUT=app/dist; [ -f app/dist/spa/index.html ] && OUT=app/dist/spa
rm -rf dist && cp -r "$OUT" dist
grep -q . dist/index.html && echo "OK: web/dist/ regenerado"
```

> Al commitear cambios de frontend, commitear solo el FUENTE (`web/app/`); `web/dist/`
> es gitignored. NO usar `git add -A` (ansible.cfg/inventory/staging.yml van excluidos).

Procedencia de la fuente:
- Build F008: 2026-06-11, fuente = working tree observer-rmm-web (features
  001-004, flag SSO_DISABLED, cleanup R-08). **Artefacto pre-rebrand.**
- Re-staging 2026-06-18: fuente actualizada a observer-rmm-web @ `23643ce`
  (incorpora el rebrand `ae485de` — los componentes del producto de origen
  → `Observer*`, 34 archivos — y discard Reports/SSO `23643ce`, ADR-010).
  Corrige el drift: `web/app/src` pasó de 146 hits legacy a 7, y esos 7 —URLs
  a la documentación del proyecto de origen— se cerraron después.
  **El artefacto `web/dist/` debe regenerarse con el comando de arriba**
  (Node 22.22.2) para reflejar esta fuente — hasta entonces queda stale.
