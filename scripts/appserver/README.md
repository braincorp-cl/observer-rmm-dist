# CDN propio de binarios del agente — `agents.observer.cl`

Solución definitiva de la faceta CDN de R-03: los binarios del agente Observer RMM
se sirven desde infra propia (`appserver 10.20.0.52`, Apache) en vez de depender de
`github.com/braincorp-cl/observer-agent-dist/releases`.

## Piezas

| Archivo | Rol |
|---|---|
| `agents.observer.cl.conf` | vhost Apache `:83`. Sirve los binarios por dos rutas hacia el mismo archivo. Provenance del `/etc/apache2/sites-available/agents.observer.cl.conf` del appserver. |
| `observer-agents-cdn-sync.sh` | Mecanismo de copia: baja el release de `observer-agent-dist` y lo publica en el docroot. Instalado en el appserver como `/usr/local/sbin/observer-agents-cdn-sync`. |

## Rutas que sirve el vhost

Ambas resuelven al mismo binario (unsigned; firma diferida ADR-018):

- **(a) Estática** — espejo del path de GitHub, la usa `get_agent_url` hoy (rama sin `CodeSignToken`):
  `GET /releases/download/v{ver}/observeragent-v{ver}-{plat}-{arch}[.exe]`
- **(b) Por query params** — la usará `get_agent_url` cuando exista un `CodeSignToken`
  (`settings.AGENTS_URL`). Apache mapea la query al archivo estático e ignora el `token`
  (binarios unsigned):
  `GET /api/v2/agents/?version={ver}&arch={arch}&plat={plat}&token=...&api=...`

Endurecimiento: sin listado de directorios; `403` a la raíz, al directorio y a cualquier
ruta que no sea un binario `observeragent-v*` (descarga solo por ruta exacta).

## Cableado en el backend

`api/observerrmm/agents/utils.py::get_agent_url` (rama sin token) apunta a
`settings.AGENT_BASE_URL` (= `https://agents.observer.cl`, `settings.py`), no a GitHub.

## Operación

Cada vez que se publique un nuevo release de binarios en `observer-agent-dist`:

```bash
# En el appserver (root/sudo). Sin argumento = release 'latest'.
sudo /usr/local/sbin/observer-agents-cdn-sync            # latest
sudo /usr/local/sbin/observer-agents-cdn-sync v2.10.7    # versión concreta

# Desde el control-plane:
ssh observer@10.20.0.52 'sudo /usr/local/sbin/observer-agents-cdn-sync'
```

Además hay que fijar `LATEST_AGENT_VER` en `settings.py` a la versión servida.

Opcional (no configurado): cron en el appserver para sincronizar `latest` periódicamente.

## Fuera de alcance (requieren backend dinámico, hoy no cableados)

`/api/v2/checktoken`, `/api/v2/exe` (exe-gen on-demand), `/api/v2/webtar/`. Solo se
necesitan para firma/generación on-demand; devuelven `403/404`. Ver ADR-018.

## Pendiente del usuario (fuera del appserver)

DNS de `agents.observer.cl` + proxy host en el NPM corporativo (`→ 10.20.0.52:83`) + TLS.
Mismo patrón que `docs.observer.cl`.
