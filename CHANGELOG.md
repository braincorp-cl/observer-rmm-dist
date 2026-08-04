# Changelog — Observer RMM

Notas de versión del producto Observer RMM. Es la **fuente de verdad**: el sitio
público `https://agents.observer.cl/changelog/` se genera a partir de este archivo
en cada push a `main` (workflow `publish-changelog.yml`). La consola enlaza aquí
desde el aviso de "versión disponible" (`MainLayout.vue`, ancla `#v{versión}`).

Formato de cada entrada: `## vX.Y.Z — YYYY-MM-DD` (el token `vX.Y.Z` se usa tal cual
como ancla HTML `id`, así que debe coincidir con `ORMM_VERSION`). Viñetas con `-`.

## v1.4.3 — 2026-08-04

- Biblioteca de 44 **plantillas de scripts** propias del producto para Windows, Linux y macOS, listas para ejecutar o clonar, sin depender de repositorios externos.
- Las plantillas se distinguen con su propio isotipo en el Administrador de scripts, y sus argumentos y variables de entorno se pueden revisar y ajustar para una prueba puntual sin tener que clonarlas.
- **Asistente IA** con pestaña propia en Configuración global: funciona con cualquier proveedor de API estilo OpenAI, con URL base, modelo, límite de tokens y temperatura configurables.
- Redacción de un **borrador de script con IA** desde el Administrador de scripts, describiendo en lenguaje natural lo que se necesita.
- Alerta por correo y baja del equipo en la consola cuando alguien **desinstala el agente a mano**, con una ventana de gracia de 10 minutos que se puede cancelar si la desinstalación era parte de una reinstalación.
- La alarma antirrobo suena al volumen máximo del equipo y no se detiene bajando el volumen.
- Geolocalización y su forzado activados por omisión en instalaciones nuevas.
- Documentación pública en `docs.observer.cl`, indexable y con la tabla de funciones soportadas por plataforma.
- Corregido: el cuadro para pedirle el borrador a la IA mostraba una sola línea, así que no se alcanzaba a leer lo que uno mismo estaba escribiendo. Ahora es un campo amplio, con ejemplos y contador.
- Corregido: la espera por la respuesta del proveedor de IA pasa de 60 a 120 segundos, y la consola muestra los segundos transcurridos en vez de una rueda muda. Antes se descartaban modelos que responden bien pero lento.
- Corregido: el desinstalador del agente en Linux se quedaba esperando una confirmación en pantalla que nadie iba a dar.
- Corregido: el respaldo programado reportaba éxito sin haber escrito el archivo.
- Corregido: la hora de las alertas se informa en la zona horaria del producto.
- Corregido: la desinstalación en macOS ya no queda colgada cuando MeshCentral no responde.

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
