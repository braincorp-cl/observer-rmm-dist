# Procedencia de componentes (RF-11 / RN-02)

> F008 `consolidacion-dist` — 2026-06-11
> Decisión marco: `D-2026-06-10-CONSOLIDACION-DIST` (copia limpia sin historia,
> squash por componente, naming canónico `observerrmm`).

Este repositorio es el punto de consolidación del sistema Observer RMM de
BrainCorp. El código de producto NO se desarrolla aquí: se desarrolla y valida
en los forks de trabajo (local-only) y se consolida vía commits squash únicos,
de modo que **ningún commit del upstream original (TacticalRMM / Amidaware) es
alcanzable desde `main`** (criterio de aceite RN-02).

## Tabla de procedencia

| Componente | Path en dist | Fork de origen | Commit de origen | Commit squash en dist | Confianza Reversa |
|------------|--------------|----------------|------------------|----------------------|-------------------|
| Backend Django (18 apps) | `api/observerrmm/` | `observer-rmm` (hub) | hub `099cc1a0` | `328d2f3` | ~98% |
| Capa Go (natsapi) | `natsapi/` + `main.go` + `go.mod`/`go.sum` | `observer-rmm` (hub) | hub `099cc1a0` | `328d2f3` (mismo squash backend) | ~98% |
| Binario nats-api (artefacto Go) | `roles/observer_api/files/nats-api{,-arm64}` | compilado de `natsapi/` (este repo) | — | `bafa5bf` (recompilado) | — (derivado) |
| Frontend Vue/Quasar (fuente) | `web/app/` | `observer-rmm-web` | web `fe91b2d` | `09ecf3f` | ~87% |
| Frontend (artefacto build) | `web/dist/` | build local desde `web/app/` (pins en `web/BUILD.md`) | — | `09ecf3f` | — (derivado) |
| Despliegue Ansible (6 roles + playbooks) | `roles/`, `*.yml`, `group_vars/` | nativo del dist (scaffold F001 + endurecimiento F008) | — | historia propia del dist | — (nativo) |
| Agente | **NO consolidado** (ver abajo) | `observer-agent` | — | — | ~89–91% |

Confianzas según `confidence-report.md` del hub (re-extracción 5 hub /
re-extracción 7 web / re-extracción 5 agent, 2026-06).

> **Nota nats-api (staging E2E, `bafa5bf`):** los binarios `roles/observer_api/files/nats-api{,-arm64}`
> versionados en el primer commit del dist estaban **stale** (build del 26-may pre-rebrand: embebían
> el user NATS `observer` y el path `/rmm/api/observer/`), lo que provocaba `nats: Authorization Violation`
> contra `nats-rmm.conf` (user `observerrmm`). Se **recompilaron desde el fuente `natsapi/` de este repo**
> (`go build`, amd64+arm64) → embeben `observerrmm-nats-api`. **Regla:** estos artefactos deben
> reconstruirse desde `natsapi/` ante cualquier cambio del fuente; un binario stale tras un rebrand es
> un fallo silencioso (el `.go` correcto no garantiza el binario correcto).

## Upstream original

Los tres forks derivan de **TacticalRMM** (Amidaware LLC/Inc.). El trabajo de
las features F001–F008 eliminó las dependencias funcionales hacia la
infraestructura del upstream (sin llamadas HTTP salientes a Amidaware desde el
hub, `SharedTemplatesRepo` eliminada, SSO providers deshabilitados, headers EE
removidos con autorización legal BrainCorp 2026-05-28, LICENSE propietario
BrainCorp en los 4 repos). Las menciones residuales al upstream que persisten
en el código (links `docs.tacticalrmm.com`, nombre de servicio Windows del
agente) están inventariadas y justificadas en el gate CI
`.github/workflows/no-legacy-strings.yml`, y su cierre depende de R-03
(CDN/documentación BrainCorp, único riesgo cross-repo abierto).

## Agente (D-05): no consolidado por diseño

El agente multiplataforma vive en el repo `observer-agent` y **no se copia a
este repo**:

- Los binarios se producen con el workflow `release.yml` del repo agente:
  `observeragent-v{version}-{goos}-{goarch}` (con `.exe` para Windows),
  metadata BrainCorp en `versioninfo.json`.
- Distribución: GitHub Releases del repo agente; a futuro, CDN BrainCorp
  (riesgo R-03 abierto — el hub tiene `get_latest_trmm_ver` stubbeado a
  `settings.TRMM_VERSION` hasta que exista el CDN, regla RN-028).
- Excepción acotada a la política de push: el repo agente puede pushear
  **tags de release** para alimentar `release.yml`; el resto del trabajo en
  forks sigue siendo local-only.

## Especificaciones de referencia

La fuente de verdad documental del sistema vive en el hub `observer-rmm`:

- `_reversa_sdd/cross-repo/README.md` — estado global de los 3 repos + dist
- `_reversa_sdd/cross-repo/spec-impact-matrix-global.md` — matriz de impacto global
- `_reversa_sdd/confidence-report.md` — confianzas y gaps vigentes
- `_reversa_forward/008-consolidacion-dist/` — requirements, roadmap, actions
  y bitácora (`progress.jsonl`) de la consolidación que produjo este repo

## Baseline de tests

Ver `docs/PYTEST-BASELINE.md` (D-09) para el baseline pytest oficial del dist
y su trazabilidad al gate Fase 0 (RN-04).
