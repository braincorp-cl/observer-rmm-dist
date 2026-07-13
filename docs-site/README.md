# docs-site — Documentación propia de Observer RMM (`docs.observer.cl`)

Sitio estático que sirve la documentación enlazada desde la UI de Observer RMM.
Reemplaza los enlaces que antes salían a documentación de terceros (cierre de
R-03): la consola ya no envía usuarios fuera del dominio propio.

## Contenido

Páginas enlazadas desde la UI, más guías operativas independientes:

| Ruta | Enlazada desde |
|---|---|
| `/` | `FileBar.vue` — botón "Docs" |
| `/guide_gettingstarted/` | `InitialSetup.vue` — botón "Primeros pasos" |
| `/functions/email_alerts/` | Guía independiente (no enlazada desde la UI): configuración de correos de alerta |
| `/functions/permissions/#permisos-con-implicancias-de-seguridad` | `EditCoreSettings.vue` — ⚠ junto a "scripts de servidor" y "terminal web" |
| `/faq/#agentes-inesperados` | `installAgent.exeWarningMessage` (catálogos i18n en/es) |

Contenido **bilingüe español / inglés**, adaptado al entorno Observer. Sin
dependencias externas (CSS propio en `assets/style.css`, tema "Observation Deck"
espejando la UI).

## i18n (bilingüe en el cliente)

El sitio es bilingüe **sin duplicar URLs ni tocar la UI**: los enlaces que la
consola llama son estáticos y sus anclas (`#agentes-inesperados`,
`#permisos-con-implicancias-de-seguridad`) se mantienen en español. El idioma se
resuelve en el navegador:

- Cada texto visible existe en dos variantes marcadas con la clase `lang-es` o
  `lang-en`. El CSS muestra solo la del idioma activo
  (`html[data-lang="es"] .lang-en { display:none }` y viceversa).
- Los `id` de los encabezados **no cambian** (siguen en español) para no romper
  las anclas que llama la UI; solo se intercambia el texto visible (spans
  `lang-es`/`lang-en` dentro del mismo `<h_>`). Regla: nunca duplicar un `id`.
- Un script en `<head>` fija `data-lang` **antes del primer render** (sin
  parpadeo): usa el idioma guardado en `localStorage` (`observer-docs-lang`) o,
  si no hay, autodetecta con `navigator.language` (`en*` → inglés; resto →
  español, default del producto). También ajusta `document.title` y el atributo
  `lang` del `<html>`.
- El selector **ES / EN** del header permite forzar el idioma; la elección se
  persiste en `localStorage`.

Al agregar contenido: por cada bloque en español, agregar su gemelo `lang-en`
(mismo elemento/estructura). El chequeo `grep -c lang-es` vs `grep -c lang-en`
debe dar igual por archivo.

## Despliegue

Servido por Apache en **appserver (`10.20.0.52`)**:

- DocumentRoot: `/var/www/html/observer-docs/`
- vhost: `/etc/apache2/sites-available/docs.observer.cl.conf` (escucha en `:82`;
  `Options -Indexes`, sin listado de directorios)
- TLS y exposición pública: los termina el NPM corporativo
  (`docs.observer.cl` → `10.20.0.52:82`).

Para actualizar el sitio, copiar el contenido de este directorio al DocumentRoot
(propietario `www-data`, archivos `644`, directorios `755`) y recargar Apache.
