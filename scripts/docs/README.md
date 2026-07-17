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

`--steps` es un JSON: lista de `{name, actions}`; acciones `get`/`click`/`tab`/
`esc`/`sleep`/`shot`. Ver `STEPS_EXAMPLE` en el `.py`.

**Gotchas descubiertos:**
- En **staging** suelen estar **vacías** las pestañas *Chequeos, Tareas, Historial*
  (sin datos) → malas para docs. Usar un entorno con datos o descartarlas.
- Menú **Reportes → "Gestor de reportes"** (texto exacto del item).
- Pestañas *Auditoría/Depuración* pueden requerir scroll de la barra de tabs.
- Consola en español; el idioma se ve arriba a la derecha.

## 2) Elegir + optimizar

Revisar (una hoja de contactos ayuda) y quedarse con las **ricas en contenido**,
1 representativa por sección de docs. Optimizar a ~1400px:

```bash
convert origen.png -resize 1400 -strip docs-site/assets/shots/<nombre>.png
# si hay pngquant: pngquant --force --quality=65-85 --output <f> <f>
```

Guardar en `docs-site/assets/shots/` (nombres descriptivos: `dashboard.png`,
`parches.png`, `software.png`, `reportes.png`, …).

## 3) Embeber en la página de docs

CSS ya presente en `docs-site/assets/style.css` (clase `.doc-shot`, theme-aware).
En la página (`docs-site/<pagina>/index.html`) insertar tras el `<h2>` de la
sección, **con caption bilingüe** (mantener paridad `lang-es`/`lang-en`):

```html
<figure class="doc-shot">
  <img src="/assets/shots/parches.png" alt="Gestión de parches de Windows">
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

```bash
H=observer@10.20.0.52; DR=/var/www/html/observer-docs
ssh $H "sudo cp -p $DR/<pagina>/index.html $DR/<pagina>/index.html.bak-$(date +%Y%m%d)"
scp docs-site/<pagina>/index.html docs-site/assets/style.css $H:/tmp/
scp docs-site/assets/shots/*.png $H:/tmp/shots/    # crear /tmp/shots antes
ssh $H "sudo install -o www-data -g www-data -m 644 /tmp/index.html $DR/<pagina>/index.html
        sudo install -o www-data -g www-data -m 644 /tmp/style.css $DR/assets/style.css
        sudo mkdir -p $DR/assets/shots && sudo chown www-data:www-data $DR/assets/shots
        sudo install -o www-data -g www-data -m 644 /tmp/shots/*.png $DR/assets/shots/
        sudo systemctl reload apache2"
```

**Verificar en vivo:**
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://docs.observer.cl/<pagina>/
for i in dashboard parches software reportes; do
  curl -s -o /dev/null -w "$i %{http_code} %{content_type}\n" https://docs.observer.cl/assets/shots/$i.png; done
# y opcional: Selenium sobre la página pública → document.images sin naturalWidth===0 (0 rotas)
```

## Registro

- Memoria: `reference_docs_screenshots_selenium` (índice en MEMORY.md).
- Feature docs: `feature_docs_site_observer_cl` (actualizaciones 2026-07-16b).
