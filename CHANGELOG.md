# Changelog — Observer RMM

Notas de versión del producto Observer RMM. Es la **fuente de verdad**: el sitio
público `https://agents.observer.cl/changelog/` se genera a partir de este archivo
en cada push a `main` (workflow `publish-changelog.yml`). La consola enlaza aquí
desde el aviso de "versión disponible" (`MainLayout.vue`, ancla `#v{versión}`).

Formato de cada entrada: `## vX.Y.Z — YYYY-MM-DD` (el token `vX.Y.Z` se usa tal cual
como ancla HTML `id`, así que debe coincidir con `TRMM_VERSION`). Viñetas con `-`.

## v1.4.2 — 2026-07-26

- Respuesta rápida en el equipo: **bloqueo remoto de pantalla**, **mensaje en pantalla** y **alarma sonora**, disponibles equipo por equipo o como acción masiva.
- Las tres acciones tienen permiso propio por rol (se otorgan por separado) y quedan registradas en el log de auditoría, tanto si se ejecutan como si fallan.
- Geolocalización de activos: mapa con la ubicación de cada equipo y trayectoria histórica de posiciones.
- Ubicación por redes WiFi cercanas, con precisión típica de unos 20 metros, en vez de solo por dirección IP. En macOS se usa la ubicación nativa del sistema operativo.
- Coordenadas declarables por sitio, que se usan como respaldo cuando el equipo no puede resolver su posición.
- Geocerca opcional por equipo, con alerta por correo y aviso en la consola cuando un activo sale del perímetro de su sitio.
- Control remoto compatible con doble proxy inverso.

## v1.4.1 — 2026-07-22

- Reportería: 19 plantillas curadas, 4 de ellas con gráficos, y el módulo completo internacionalizado en español e inglés.
- El instalador del agente en Linux ya no se detiene en equipos sin entorno de escritorio.
- Favicon de Observer en la consola.
- Documentación: guía "Generar reportes" y capturas de la consola en `docs.observer.cl`.

## v1.4.0 — 2026-07-13

- Correos de alerta por SMTP con TLS implícito en el puerto 465 (`SMTP_SSL`), además de STARTTLS en 587/25.
- Distribución de los agentes desde un CDN propio en `agents.observer.cl` (descarga directa, sin depender de terceros).
- Consola internacionalizada en español e inglés, con idioma por defecto configurable en la instalación.
- Tema visual "Observation Deck" (navy profundo + cian de señal).
- Conexión cifrada del servicio `nats-api` hacia PostgreSQL.
- Todos los enlaces de documentación y ayuda apuntan a `docs.observer.cl`.
- Endurecimiento del registro de auditoría (límite de tamaño configurable) y del rate-limit de inicio de sesión.
- Comandos de mantenimiento del backend (inventario WMI y limpieza de nodos huérfanos de MeshCentral).
