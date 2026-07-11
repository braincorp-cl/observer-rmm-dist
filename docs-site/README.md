# docs-site — Documentación propia de Observer RMM (`docs.observer.cl`)

Sitio estático que sirve la documentación enlazada desde la UI de Observer RMM.
Reemplaza los enlaces que antes salían a documentación de terceros (cierre de
R-03): la consola ya no envía usuarios fuera del dominio propio.

## Contenido

Solo se documentan las páginas que la UI enlaza:

| Ruta | Enlazada desde |
|---|---|
| `/` | `FileBar.vue` — botón "Docs" |
| `/guide_gettingstarted/` | `InitialSetup.vue` — botón "Primeros pasos" |
| `/functions/permissions/#permisos-con-implicancias-de-seguridad` | `EditCoreSettings.vue` — ⚠ junto a "scripts de servidor" y "terminal web" |
| `/faq/#agentes-inesperados` | `installAgent.exeWarningMessage` (catálogos i18n en/es) |

Contenido en español, adaptado al entorno Observer. Sin dependencias externas
(CSS propio en `assets/style.css`, tema "Observation Deck" espejando la UI).

## Despliegue

Servido por Apache en **appserver (`10.20.0.52`)**:

- DocumentRoot: `/var/www/html/observer-docs/`
- vhost: `/etc/apache2/sites-available/docs.observer.cl.conf` (escucha en `:82`;
  `Options -Indexes`, sin listado de directorios)
- TLS y exposición pública: los termina el NPM corporativo
  (`docs.observer.cl` → `10.20.0.52:82`).

Para actualizar el sitio, copiar el contenido de este directorio al DocumentRoot
(propietario `www-data`, archivos `644`, directorios `755`) y recargar Apache.
