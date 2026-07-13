# CDN propio de binarios del agente — `agents.observer.cl`

Solución definitiva de la faceta CDN de R-03: los binarios del agente Observer RMM
se sirven desde infra propia (`appserver 10.20.0.52`, Apache) en vez de depender de
`github.com/braincorp-cl/observer-agent-dist/releases`.

## Piezas

| Archivo | Rol |
|---|---|
| `agents.observer.cl.conf` | vhost Apache `:83`. **Lee** (público) por dos rutas y **recibe** (WebDAV autenticado) las subidas. Provenance del `/etc/apache2/sites-available/agents.observer.cl.conf` del appserver. |
| `observer-agents-cdn-publish.sh` | **Fallback manual** (control-plane → SSH). Ver más abajo. |

## Mecanismo de copia — push desde GitHub en cada release (primario)

El job **`publish-cdn`** del `release.yml` del agente (`observer-agent-dist`) sube los 8
binarios al CDN por **WebDAV autenticado sobre HTTPS** en cada release:

```
MKCOL https://agents.observer.cl/releases/download/v{ver}/
PUT   https://agents.observer.cl/releases/download/v{ver}/observeragent-...
```

No hay control-plane intermedio (sin SPOF) ni PAT de GitHub en el appserver: solo una
**credencial de subida dedicada** (Basic auth). El repo `observer-agent-dist` puede ser
**privado** — el job ya tiene los binarios que construyó, no los re-descarga.

**Configuración (una vez):**
1. Secrets del repo `observer-agent-dist`: `CDN_UPLOAD_USER` y `CDN_UPLOAD_PASSWORD`
   (valor de `htpasswd` en `/etc/apache2/observer-agents-cdn.htpasswd` del appserver).
2. `agents.observer.cl` publicado por el NPM (ver "Pendiente del usuario").
3. Tras cada release, fijar `LATEST_AGENT_VER` en `settings.py` a la versión servida.

El paso es `continue-on-error`: si el CDN falla, el release de GitHub igual se crea (fuente
de verdad) y se re-publica con el fallback.

## Fallback manual (control-plane, sin la credencial de subida)

Si el push de CI falla o hay que re-sembrar, desde el control-plane (donde `gh` está
autenticado con scope `repo`, funciona aunque el repo sea privado):

```bash
./scripts/appserver/observer-agents-cdn-publish.sh            # release 'latest'
./scripts/appserver/observer-agents-cdn-publish.sh v2.10.7    # versión concreta
# Destino por defecto observer@10.20.0.52; override con OBSERVER_APPSERVER=user@host.
```

Baja los assets con `gh` y los publica por `ssh`/`scp` (sudo NOPASS). No usa la credencial
WebDAV — usa SSH. Es una segunda vía, no la ruta normal.

## Rutas de lectura que sirve el vhost

Ambas resuelven al mismo binario (unsigned; firma diferida ADR-018):

- **(a) Estática** — espejo del path de GitHub, la usa `get_agent_url` hoy (rama sin `CodeSignToken`):
  `GET /releases/download/v{ver}/observeragent-v{ver}-{plat}-{arch}[.exe]`
- **(b) Por query params** — la usará `get_agent_url` cuando exista un `CodeSignToken`
  (`settings.AGENTS_URL`). Apache mapea la query al archivo estático e ignora el `token`:
  `GET /api/v2/agents/?version={ver}&arch={arch}&plat={plat}&token=...&api=...`

## Autorización (una sola `<Directory>`, método por método)

Para evitar ambigüedad de merge entre contenedores, todo se define por método:

- `GET`/`HEAD` — público, **solo** si el archivo resuelto matchea `observeragent-v[0-9]`
  (`Require expr %{REQUEST_FILENAME}`; cubre la ruta estática y la `/api/v2/agents/`
  reescrita). Sin listado; `403` a raíz/dir/no-binario.
- `PUT`/`MKCOL` — **`Require valid-user`** (Basic auth, `observer-agents-cdn.htpasswd`).
- Cualquier otro método (`PROPFIND`/`DELETE`/`MOVE`/`COPY`/`OPTIONS`/...) — `Require all denied`.

Verificado en `:83`: lectura pública 200, `/api/v2/agents/` 200, hardening 403, `PUT` sin
auth 401, `MKCOL`+`PUT` con auth 201, `PROPFIND`/`DELETE` 403.

## Cableado en el backend

`api/observerrmm/agents/utils.py::get_agent_url` (rama sin token) apunta a
`settings.AGENT_BASE_URL` (= `https://agents.observer.cl`, `settings.py`), no a GitHub.

## Fuera de alcance (requieren backend dinámico, hoy no cableados)

`/api/v2/checktoken`, `/api/v2/exe` (exe-gen on-demand), `/api/v2/webtar/`. Solo se
necesitan para firma/generación on-demand; devuelven `403/404`. Ver ADR-018.

## Pendiente del usuario (fuera del appserver)

DNS de `agents.observer.cl` + proxy host en el NPM corporativo (`→ 10.20.0.52:83`) + TLS.
Mismo patrón que `docs.observer.cl`. Necesario tanto para servir a los endpoints como para
que el job `publish-cdn` (GitHub Actions) alcance el CDN por HTTPS.
