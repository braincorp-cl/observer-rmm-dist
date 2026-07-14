# Changelog — Observer RMM

Notas de versión del producto Observer RMM. Es la **fuente de verdad**: el sitio
público `https://agents.observer.cl/changelog/` se genera a partir de este archivo
en cada push a `main` (workflow `publish-changelog.yml`). La consola enlaza aquí
desde el aviso de "versión disponible" (`MainLayout.vue`, ancla `#v{versión}`).

Formato de cada entrada: `## vX.Y.Z — YYYY-MM-DD` (el token `vX.Y.Z` se usa tal cual
como ancla HTML `id`, así que debe coincidir con `TRMM_VERSION`). Viñetas con `-`.

## v1.4.0 — 2026-07-13

- Correos de alerta por SMTP con TLS implícito en el puerto 465 (`SMTP_SSL`), además de STARTTLS en 587/25.
- Distribución de los agentes desde un CDN propio en `agents.observer.cl` (descarga directa, sin depender de terceros).
- Consola internacionalizada en español e inglés, con idioma por defecto configurable en la instalación.
- Tema visual "Observation Deck" (navy profundo + cian de señal).
- Conexión cifrada del servicio `nats-api` hacia PostgreSQL.
- Todos los enlaces de documentación y ayuda apuntan a `docs.observer.cl`.
- Endurecimiento del registro de auditoría (límite de tamaño configurable) y del rate-limit de inicio de sesión.
- Comandos de mantenimiento del backend (inventario WMI y limpieza de nodos huérfanos de MeshCentral).
