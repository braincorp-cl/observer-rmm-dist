# Arquitectura — Observer RMM Distributed

## Topología multi-host

```
┌─────────────────────────────────────────────────────────────┐
│  INTERNET / Red interna MINSAL 10.50.0.0/24                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ :80, :443
                 ┌─────────▼──────────┐
                 │  observer_proxy    │  10.50.0.10
                 │  nginx (apt)       │
                 │  TLS termination   │
                 └────┬─────────┬─────┘
                      │         │
              :8000   │         │  :4430
    ┌─────────────────▼──┐  ┌───▼────────────────┐
    │  observer_api       │  │  observer_mesh      │
    │  10.50.0.14         │  │  10.50.0.13         │
    │  rmm.service (uWSGI)│  │  meshcentral.service│
    │  daphne.service     │  │  Node.js 20 / npm   │
    │  nats.service       │  └────────┬────────────┘
    │  nats-api.service   │           │
    │  celery.service     │           │  :5432
    │  celerybeat.service │  ┌────────▼────────────┐
    └──────┬──────┬───────┘  │  observer_db        │
           │      │          │  10.50.0.11         │
     :5432 │      │ :6379    │  PostgreSQL 18       │
           │  ┌───▼──────────┐  DB: observerrmm    │
           │  │ observer_redis│  DB: meshcentral    │
           │  │ 10.50.0.12   │└─────────────────────┘
           │  │ Redis 7.x    │
           │  └──────────────┘
           │
           └───────────────────────────────────────────┐
                                                       │ :5432
                                            ┌──────────▼──────────┐
                                            │  observer_db (mismo)│
                                            └─────────────────────┘
```

## Puertos requeridos entre grupos

| Origen | Destino | Puerto | Protocolo | Servicio |
|--------|---------|--------|-----------|---------|
| observer_proxy | observer_api | 8000 | TCP | uWSGI HTTP |
| observer_proxy | observer_api | 9235 | TCP | NATS WebSocket |
| observer_proxy | observer_mesh | 4430 | TCP | MeshCentral HTTPS |
| observer_api | observer_db | 5432 | TCP | PostgreSQL |
| observer_api | observer_redis | 6379 | TCP | Redis |
| observer_api | observer_mesh | 4430 | TCP | MeshCentral API |
| observer_mesh | observer_db | 5432 | TCP | PostgreSQL (meshcentral DB) |
| agentes Windows/Linux | observer_proxy | 443 | TCP | HTTPS API + WS |
| agentes Windows/Linux | observer_proxy | 443 | TCP | MeshCentral remoto |
| todos | todos | 22 | TCP | SSH (administración) |

## All-in-one vs multi-host

| Aspecto | All-in-one | Multi-host |
|---------|-----------|-----------|
| Inventario | `inventory/all-in-one.yml` | `inventory/production.yml` |
| Playbook | `install.yml` (mismo) | `install.yml` (mismo) |
| Hosts | 1 (localhost) | 4-5 hosts separados |
| Uso recomendado | Dev / staging | Producción |
| Tiempo de deploy | ~30 min | ~60 min |
| Aislamiento de fallas | No | Sí (fallo de MeshCentral no afecta API) |

## Decisiones de diseño

| ID | Decisión |
|----|---------|
| D-01 | Sin Docker en producción — systemd directo en OS |
| D-02 | ansible-vault para secretos — nativo, versionable |
| D-03 | PostgreSQL single-node v1 — Patroni HA reservado para v2 |
| D-04 | Un rol por grupo de servicio |
| D-08 | Ubuntu 22.04/24.04 LTS — Debian excluido |
| D-09 | CHECKIN_SYNCMESH 3600-7200s (upstream 200-400s causó crash en MINSAL) |
