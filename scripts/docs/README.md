# scripts/docs — Capturas de la consola para docs.observer.cl

Procedimiento para tomar pantallazos reales de la consola Observer RMM e
integrarlos en `docs.observer.cl` (páginas de `docs-site/`). Herramienta de
operador; **no se despliega** (vive fuera del docroot del sitio).

> Establecido 2026-07-16 al documentar las primeras features. Se reutiliza para
> documentar las features restantes. Detalle histórico: cross-repo CHANGELOG.

## Requisitos (estación gráfica del operador)

- Sesión **X11** (`echo $DISPLAY`, p.ej. `:0` o `:11.0`).
- **Firefox ESR** (`/usr/bin/firefox-esr`), **geckodriver** (`/usr/bin/geckodriver`),
  **selenium** Python (`python3 -c "import selenium"`).
- Haber **iniciado sesión** en la consola (staging `rmm.observer.cl`) en el
  Firefox normal al menos una vez → deja el token en el perfil.

## Por qué así (decisiones clave)

- **Modo Selenium/geckodriver headed** (no headless): rinde igual que el navegador
  real y el operador puede mirar. (También hay `xdotool` para manejar la ventana
  real, pero Selenium es más confiable y reproducible.)
- **Auth por inyección de token, NO login**: la consola es una SPA que guarda el
  token DRF en `localStorage` (no en cookies). El script lo **lee de la sesión ya
  abierta** del operador (`storage/default/https+++<dominio>/ls/data.sqlite`) y lo
  inyecta en un **perfil Selenium limpio**. Ventajas: sin credenciales, sin 2FA, y
  el perfil Selenium **no arrastra** las otras sesiones del operador (privacidad).
- **La consola es una SPA**: la mayoría de las "interfaces" son paneles/diálogos,
  no URLs. Se navega por **clicks de texto** (`click_text`), robusto en Quasar.

## 1) Capturar

```bash
DISPLAY=:0 python3 scripts/docs/console_screenshots.py \
    --base https://rmm.observer.cl --out /tmp/shots
# set propio de pasos:
DISPLAY=:0 python3 scripts/docs/console_screenshots.py --steps mis_pasos.json --out /tmp/shots
```

`--steps` es un JSON: lista de `{name, actions}`. Acciones disponibles:

| Acción | Para qué |
|---|---|
| `["get", "/", 6]` | navegar y esperar N s |
| `["click", "texto"]` · `["clickc", "subcadena"]` | clic por texto exacto / por subcadena |
| `["dblclick", "texto"]` | abrir el editor de una fila |
| `["rclick", "HOSTNAME"]` | **clic derecho**: el menú de acciones del equipo sólo se abre así |
| `["tab", "Parches"]` | pestaña de agente |
| `["type", "textarea", "lo que se pide"]` | escribir en un campo **del diálogo de encima** |
| `["keys", "control", "\ue007"]` | combinación de teclas (`\ue007` = Enter ⇒ Ctrl+Enter) |
| `["scroll", 330]` | desplazar el contenido del diálogo de encima |
| `["maximize"]` | maximizar el diálogo |
| `["away"]` | alejar el puntero antes de capturar |
| `["esc"]` · `["sleep", 3]` · `["shot", "nombre"]` | cerrar / esperar / capturar |

Ver `STEPS_EXAMPLE` en el `.py`.

**Gotchas descubiertos:**
- En **staging** suelen estar **vacías** las pestañas *Chequeos, Tareas, Historial*
  (sin datos) → malas para docs. Usar un entorno con datos o descartarlas.
- Menú **Reportes → "Gestor de reportes"** (texto exacto del item).
- Pestañas *Auditoría/Depuración* pueden requerir scroll de la barra de tabs.
- Consola en español; el idioma se ve arriba a la derecha.
- **El menú de Quasar necesita ~2 s de animación** entre abrir el menú padre y
  clicar su ítem. Con 1 s el clic se pierde y el menú se cierra: parece que el
  ítem no existiera.
- **`maximize` es medida de privacidad, no de encuadre.** El diálogo normal deja
  ver el panel de hardware de atrás (IP pública, IP LAN, UUID del equipo) y la
  tabla de agentes con la columna *Usuario*. Maximizado, el diálogo tapa todo.
- **El corrector de Firefox subraya en rojo** todo lo que se escriba en español
  (no hay diccionario es instalado) y eso sale en la captura. `type` lo apaga con
  `spellcheck=false`; si se escribe por otra vía, hay que apagarlo a mano.
- **El tooltip del botón recién clicado aparece en la captura** y tapa el campo de
  al lado. Poner `["away"]` antes de cada `shot`.
- **Elegir el contenido para que quepa en el cuadro.** Una salida de 44 líneas no
  entra: el formulario del diálogo se lleva los primeros ~520 px. Se probaron
  varias plantillas por API antes de capturar y se eligió una de 23 líneas, que
  entra completa **con su veredicto final**. Sale más barato que recortar.
- Si el modelo del asistente IA **filtra su razonamiento** (`<think>`) o repite el
  script, el borrador no se publica: hay que regenerar. Conviene automatizar el
  descarte (líneas de más, bloques repetidos) en vez de mirar cada corrida.

## 2) Elegir + optimizar

Revisar (una hoja de contactos ayuda) y quedarse con las **ricas en contenido**,
1 representativa por sección de docs. El sitio sirve **WebP** (el PNG pesaba ~5×):

```bash
# recorte + escala + WebP en un paso
convert origen.png -crop 1632x715+0+0 +repage -resize 1400 \
        -quality 82 -define webp:method=6 docs-site/assets/shots/<nombre>.webp
```

Guardar en `docs-site/assets/shots/` (nombres descriptivos: `dashboard.webp`,
`parches.webp`, `ubicacion-mapa.webp`, …). El `-crop` de arriba es el que **deja
fuera el bloque de serial e IPs** del panel de hardware; ajustar la geometría a la
captura, pero no publicarla con esos datos.

⚠️ **El sitio está indexado** (`robots.txt` con `Allow`), así que la captura es
contenido público: no debe identificar el equipo de una persona. Las de ubicación
van sobre **VMs del datacenter**, no sobre notebooks reales — detalle y razones en
`docs-site/README.md`.

## 3) Embeber en la página de docs

CSS ya presente en `docs-site/assets/style.css` (clase `.doc-shot`, theme-aware).
En la página (`docs-site/<pagina>/index.html`) insertar tras el `<h2>` de la
sección, **con caption bilingüe** (mantener paridad `lang-es`/`lang-en`):

```html
<figure class="doc-shot">
  <img src="/assets/shots/parches.webp" width="1400" height="613"
       loading="lazy" decoding="async" alt="Gestión de parches de Windows">
  <figcaption><span class="lang-es">Texto ES.</span><span class="lang-en">EN text.</span></figcaption>
</figure>
```

Chequear paridad antes de commitear:
`grep -o lang-es features/index.html | wc -l` == `grep -o lang-en …`

## 4) Commit + push (repo de distribución)

```bash
git add docs-site/assets/shots/ docs-site/assets/style.css docs-site/<pagina>/index.html
git commit -m "feat(docs): capturas de la consola en <sección>"
git push origin main   # observer-rmm-dist = repo de distribución (push permitido)
```

## 5) Deploy al appserver + verificar

Appserver `10.20.0.52` (Apache), docroot `/var/www/html/observer-docs/`.

🔴 **El respaldo va FUERA del docroot.** Un `index.html.bak-…` al lado del original
**se sirve por HTTP** (responde 200): queda una copia vieja de la página, pública e
indexable. Ya pasó —13 `.bak` públicos— y el vhost hoy los deniega, pero la regla es
no crearlos ahí. Respaldar en `/var/www/backups/observer-docs/<timestamp>/`.

```bash
H=observer@10.20.0.52; DR=/var/www/html/observer-docs; TS=$(date +%Y%m%d-%H%M%S)
# 1) subir en un tar (preserva rutas relativas; nada suelto en /tmp del server)
cd docs-site && tar cf - <pagina>/index.html sitemap.xml assets/shots/<nuevas>.webp \
  | ssh $H "mkdir -p /tmp/docs-nuevo && tar xf - -C /tmp/docs-nuevo"
# 2) respaldar SOLO lo que se va a pisar, FUERA del docroot
ssh $H "B=/var/www/backups/observer-docs/$TS
        sudo mkdir -p \$B/<pagina> \$B/assets/shots
        sudo cp -p $DR/<pagina>/index.html \$B/<pagina>/
        sudo cp -p $DR/sitemap.xml \$B/"
# 3) instalar con dueño y permisos explícitos + recargar
ssh $H "sudo install -o www-data -g www-data -m 644 /tmp/docs-nuevo/<pagina>/index.html $DR/<pagina>/index.html
        sudo install -o www-data -g www-data -m 644 /tmp/docs-nuevo/assets/shots/*.webp $DR/assets/shots/
        sudo systemctl reload apache2; rm -rf /tmp/docs-nuevo"
```

**Verificar en vivo** (no basta el 200: este vhost tuvo WebP servido **sin**
`Content-Type`, y con el `nosniff` del proxy el navegador se niega a renderizarlo →
200 del tamaño correcto y la imagen invisible):

```bash
curl -sk -o /tmp/p.html -w "%{http_code}\n" https://docs.observer.cl/<pagina>/
md5sum /tmp/p.html docs-site/<pagina>/index.html      # deben coincidir
for i in <nuevas>; do
  curl -sk -o /tmp/x.webp -w "$i %{http_code} %{content_type}\n" \
       https://docs.observer.cl/assets/shots/$i.webp
  md5sum /tmp/x.webp docs-site/assets/shots/$i.webp; done   # también deben coincidir
ssh $H "find $DR -name '*.bak' | wc -l"               # tiene que dar 0
```

Y el chequeo en navegador sobre la página **pública**: render exclusivo por idioma,
ids duplicados, anclas internas, scroll horizontal y **0 imágenes rotas
scrolleando la página entera** — la mayoría son `loading="lazy"` y sin scroll
reportan `naturalWidth=0`, o sea rotas sin estarlo.

⚠️ **Si un archivo se reemplaza con el MISMO nombre, hay que bustear la caché**
(`?v=N` en la página): el proxy de adelante cachea assets ~6 h. Y el cache-buster
se **mide** en la respuesta viva antes de publicar: acá el HTML no se cachea y el
CSS sí, así que no se puede asumir por tipo de archivo.

## Registro

- Memoria: `reference_docs_screenshots_selenium` (índice en MEMORY.md).
- Feature docs: `feature_docs_site_observer_cl` (actualizaciones 2026-07-16b).

## Notas de versión públicas (docs.observer.cl/release-notes/)

`build_release_notes.py` consolida los GitHub Releases de **observer-rmm-dist**
(servidor) y **observer-agent-dist** (agente) en `docs-site/release-notes/index.html`.
Los repos son privados; esta es la copia pública de sus notas. Regenerar y publicar:

```bash
python3 scripts/docs/build_release_notes.py     # usa `gh api` (token de gh)
# publicar al appserver igual que el resto de docs (sección 5 de este README)
```

Se desacopló a propósito de `WEB_VERSION`: esa variable ya no arma ninguna URL
(el `get_webtar_url` del tarball de assets se retiró por muerto).
