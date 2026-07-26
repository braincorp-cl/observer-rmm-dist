# docs-site — Documentación propia de Observer RMM (`docs.observer.cl`)

Sitio estático que sirve la documentación enlazada desde la UI de Observer RMM.
Reemplaza los enlaces que antes salían a documentación de terceros (cierre de
R-03): la consola ya no envía usuarios fuera del dominio propio.

## Contenido

Páginas enlazadas desde la UI, más guías operativas independientes:

| Ruta | Enlazada desde |
|---|---|
| `/` | `FileBar.vue` — botón "Docs" |
| `/features/` | Página de resumen de características (no enlazada desde la UI): catálogo completo de features + plataformas soportadas |
| `/guide_gettingstarted/` | `InitialSetup.vue` — botón "Primeros pasos" |
| `/functions/email_alerts/` | Guía independiente (no enlazada desde la UI): configuración de correos de alerta |
| `/functions/permissions/#permisos-con-implicancias-de-seguridad` | `EditCoreSettings.vue` — ⚠ junto a "scripts de servidor" y "terminal web" |
| `/faq/#agentes-inesperados` | `installAgent.exeWarningMessage` (catálogos i18n en/es) |

Contenido **bilingüe español / inglés**, adaptado al entorno Observer. Sin
dependencias externas (CSS propio en `assets/style.css`, tema "Observation Deck"
espejando la UI).

## SEO — el sitio es público y se quiere encontrable

Este sitio es la documentación que consultan los clientes, y además la propiedad
que debe aparecer en búsquedas de **software RMM** y de **antirrobo /
geolocalización de equipos**. Lo que hay implementado:

- **`robots.txt`**: `Allow: /` + referencia al `sitemap.xml`.
- **`sitemap.xml`**: las 7 páginas con `lastmod` tomado del **último commit** que
  tocó cada archivo (no del `mtime`, que cambia al copiar al servidor). Al agregar
  o renombrar una página hay que actualizarlo a mano — no hay build.
- **Por página**: `<title>` y `description` orientados a búsqueda (título ≤ 62
  caracteres para que no lo truncen), `canonical`, `robots` con
  `max-image-preview:large`, Open Graph + Twitter card y `theme-color`.
- **Descripción en un solo idioma (español).** Antes eran bilingües separadas por
  " / ", lo que producía un snippet mezclado en los resultados. El HTML estático
  es el que indexan los rastreadores y el mercado primario es Chile.
- **Structured data** (JSON-LD): `SoftwareApplication` + `Organization` +
  `WebSite` en la portada, `FAQPage` en `/faq/`. Sin `aggregateRating` ni `offers`:
  no hay datos reales que respalden esas propiedades e inventarlas es incumplir las
  guías de Google además de mentir.
- **Imágenes en WebP** con `width`/`height` (evita el salto de layout) y
  `loading="lazy"` salvo la primera de cada página, que va `eager` +
  `fetchpriority="high"` porque es la del LCP. Las capturas pesaban 2,9 MB en PNG y
  quedaron en 645 KB (~22 %) a calidad 82.
- **`og-observer-rmm.png`** (1200×630) es una tarjeta de marca generada con
  ImageMagick, **sin datos de consola**: es la imagen que se ve al compartir el
  enlace en WhatsApp o LinkedIn.

**Lo que NO está resuelto:** el bilingüe es del lado del cliente, sin URLs
separadas, así que **solo se indexa el español**. Para posicionar en inglés harían
falta rutas propias (`/en/...`) con `hreflang`, que es duplicar las 7 páginas.

⚠️ **Corolario para las capturas:** el sitio es indexable, así que no se publican
datos que identifiquen el equipo de una persona. Las capturas de ubicación se toman
sobre **VMs del datacenter** (que además, al no tener radio WiFi, heredan las
coordenadas de su sitio y hacen visible el círculo de incertidumbre), nunca sobre
un notebook real, y se les recorta el bloque de serial e IPs del panel de hardware.

Y ojo con lo obvio: `robots.txt` no es ni fue un control de acceso. Si algún día
hay que restringir el sitio de verdad, el lugar es el **NPM** (allowlist o auth).

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
  parpadeo): usa el idioma guardado en `localStorage` (`observer-docs-lang`) y,
  si no hay, **siempre `es`**. También ajusta `document.title` y el atributo
  `lang` del `<html>`.
- **Por qué ya no se autodetecta con `navigator.language`** (se quitó al trabajar
  el SEO): los rastreadores se anuncian en inglés, así que renderizaban la página
  en inglés mientras el `<title>`, la descripción y el JSON-LD del HTML estático
  están en español — metadatos y contenido indexado en idiomas distintos. Con un
  default fijo, lo que rastrea Google coincide con lo que declara la página. El
  costo es que un visitante anglófono llega primero a español y tiene que usar el
  selector.
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
