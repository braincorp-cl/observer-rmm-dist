# Guion de re-captura de docs.observer.cl sobre la UI v2

> Escrito el **2026-11-05**, al retirar del sitio las 21 figuras de la consola v1.

> Las capturas v1 y los bloques `<figure>` exactos están en `docs-site-fuera-de-linea/`.


## Por qué se retiraron en vez de reemplazarlas


La cobertura **está completa**: se verificó por render, no por grep, que las 19 superficies
que ilustraba el sitio existen y se dibujan en la UI v2 (`rmm-v2.observer.cl`, `release/v2`
`254d9f8`, 0 errores severos de consola y sonda de consola positiva). Lo que falta no es UI:

1. La cabecera de la v2 todavía dice **v1.4.42**. El bump a **2.0.0** es la ola 10 de la 050.
2. Falta la **tanda del sistema de diseño** (anillo de foco V2-G15, `obs-notice--warning`,
   radio de los campos de `LoginView`): todas tocan `app.sass`, o sea, el aspecto de todas
   las superficies.

Capturar antes de eso obliga a capturar dos veces. **Decisión del usuario (5-nov): retirar
ahora y reponer con la 2.0.0.**

## Decisiones ya tomadas para esa pasada

| Decisión | Valor |
|---|---|
| Flota que sale en las capturas | **La sintética**: «Universal Retail», `BOG-CAJA-01`, `cajero01`. Son datos ficticios ⇒ nada que difuminar, tablas llenas y creíbles. 🔴 Esconder el cliente de andamiaje «Canario 050 - Cliente W» antes de capturar. |
| Las tres capturas que exigen una acción real | Ejecutar un script de **sólo lectura** y generar un borrador con la IA sobre una VM de laboratorio; para «equipo perdido» **sembrar la fila en la BD de staging**, nunca marcar un equipo vivo (enciende bloqueo de pantalla, cámara y alarma). |
| Privacidad | Sigue mandando el corolario del `docs-site/README.md`: el sitio es indexable, no se publican datos que identifiquen el equipo de una persona. Ubicación sólo sobre VMs del datacenter; recortar el bloque de serial, IP pública, IP LAN y UUID. |

## Cómo se capturó para verificar (y cómo repetirlo)

Dos vías probadas:

- **`scripts/docs/console_screenshots.py`** — la herramienta de operador. Firefox ESR +
  geckodriver con `DISPLAY=:0`, lee el token de la sesión ya iniciada en el perfil del
  operador. Es la vía oficial y la que trae el motor de pasos (`get/click/tab/type/maximize/…`).
- **El arnés del gauntlet 046** (`_reversa_forward/046-ui-v2-piloto-agente-1c/instrumento/sesion.py`,
  en el repo `observer-rmm`) — Chromium headless con el token del canario `gauntlet046`
  y **cerrojo de escritura**: toda petición no-GET se registra y no se envía. Es con lo que se
  hizo esta verificación. Útil para encuadrar sin riesgo; inútil para las tres capturas que
  necesitan una escritura de verdad.

Encuadre: viewport **1400×758** (las de diálogo quedaron en 1400×613 tras recorte).
Esconder el banner de mantenimiento antes de disparar:

```js
document.querySelectorAll('.q-banner').forEach(b => {
  if (/mantenimiento|maintenance/i.test(b.textContent)) b.style.display = 'none';
});
```

## El anillo de foco y el halo accidental — medido, no supuesto

La tanda del sistema de diseño añade un **anillo de foco** que hoy no existe: `app.sass`
no tiene **ni una** regla de foco en sus 968 renglones, Quasar hace `outline: 0` y lo
sustituye por un velo de 1,33–1,46:1. Parámetros ya decididos por el usuario el 4-nov
(viven en el `ui-watch.md` de la 050):

| | |
|---|---|
| token | `--obs-focus`, **neutro propio, no el teal de marca**: `#E6EDF5` en oscuro, `#16202E` en claro — los mismos neutros de texto de cada tema, para que sea inequívocamente «ni color de marca ni de estado» |
| disparador | `:focus-visible` — se ve al **tabular**, no al hacer clic con el ratón |
| forma | `outline: 2px solid var(--obs-focus)` + `outline-offset: 2px`, siguiendo el radio del control |
| dónde | regla global sobre `:focus-visible` en `css/app.sass`, más las excepciones de los componentes que Quasar pinta aparte |

El color y el disparador son decisión expresa; la forma y la ubicación van por default
convencional y son discutibles si al capturar estorban.

### Lo que esto le hace a las capturas

El arnés **hace clic** para llegar a los diálogos, así que puede dejar el foco puesto sin
que hoy se note —con `outline: 0` el foco es invisible—. Cuando el anillo exista, esa
misma captura saldría con un halo de 2 px que nadie pidió, y se leería como **defecto del
producto** en vez de como artefacto del instrumento.

**Medido el 5-nov sobre las superficies del barrido**, en vez de suponerlo:

| superficie | cómo se llega | `document.activeElement` | `:focus-visible` |
|---|---|---|---|
| dashboard, panel de agente | sólo URL | `BODY` | 0 |
| ubicación, menú de respuesta, mensaje en pantalla, modo perdido | tras 1–3 clics | `DIV` (el contenedor del diálogo, que Quasar enfoca para que ESC funcione) | **0** |

🔑 **El riesgo es menor de lo que parecía, y por una razón concreta:** el foco que deja el
arnés es **programático**, así que `:focus-visible` **no lo matchea** —son 0 en las cuatro—.
Un anillo definido sobre `:focus-visible`, como el decidido, **no pinta** sobre esos
contenedores. El halo no aparece solo.

🪤 **Dónde sí reaparece**, y hay que vigilarlo al capturar:

1. Cualquier **excepción de componente escrita con `:focus` a secas** en vez de
   `:focus-visible` sí pinta sobre un foco programático. Si la tanda deja alguna, el halo
   vuelve justo en los diálogos.
2. Si el arnés **toca el teclado** antes de disparar (el barrido usa `ESC` para cerrar
   diálogos), el navegador pasa a modalidad teclado y el foco siguiente **sí** cuenta como
   `:focus-visible`.

### Regla para capturar

Quitar el foco antes de disparar y **probar que se quitó**, en vez de suponerlo — es el
equivalente de teclado del `mouse_away()` que `console_screenshots.py` ya hace por los
tooltips:

```python
# antes de cada captura
s.js("if (document.activeElement && document.activeElement !== document.body) "
     "document.activeElement.blur();")
sonda = s.js("return {es_body: document.activeElement === document.body, "
             "focus_visible: document.querySelectorAll(':focus-visible').length};")
assert sonda["es_body"] and sonda["focus_visible"] == 0, sonda
```

Guardar esa sonda **junto a la captura**: así la ausencia de halo queda **probada y no
supuesta**, con la misma lógica que la sonda de consola del gauntlet. Verificado que el
`blur()` devuelve `activeElement` a `BODY` en las cuatro superficies de diálogo.

## Las tres cifras, que no son la misma

Se confunden fácil y conviene tenerlas claras antes de empezar:

| cifra | qué es |
|---|---|
| **23** | archivos `.webp` que había en `assets/shots/` y que se movieron a `docs-site-fuera-de-linea/assets-shots-v1/` |
| **21** | bloques `<figure class="doc-shot">` retirados: **17** de `/features/` y **4** de `/guide_reports/` |
| **19** | superficies distintas de la consola, que son los archivos efectivamente referenciados |

Cuadran así: **19 + 4 huérfanas = 23** archivos, y **19 + 2 repeticiones = 21** figuras.
Las dos repeticiones son `reportes-preview-html.webp` y `reportes-preview-pdf.webp`, que
aparecen **en las dos páginas** (`/features/#reporteria` y `/guide_reports/`) con
figcaption distinto cada vez. Al reponer: **una captura, dos `<figure>`**; no hay que
capturar dos veces ni duplicar el archivo.

## Lo que la ola 8 NO invalida de este guion

**Ninguna de las 19 superficies es una pantalla de acceso ni una ventana remota.** Las 19
son: flota; panel, parches y software de agente; biblioteca de scripts, prompt y borrador
de IA, y ejecución de script; menú de respuesta rápida y mensaje en pantalla; mapa e
histórico de ubicación; diálogo y lista de modo perdido; y las cinco de reportes (gestor,
previa HTML, previa PDF, programaciones, historial).

Así que el trabajo de la ola 8 del 5-nov —el `AccessLayout.vue` nuevo que heredan las cinco
pantallas de acceso (`6139945` + `13ef6f3`), la cabecera que ganaron `WebVNC` y
`WebTerminal` (`1bb7c9b`) y el arreglo del `|` de i18n que devuelve el sufijo a los títulos
de las ventanas remotas— **no toca ninguna de estas 19**. La verificación por render se hizo
contra `254d9f8` y sigue valiendo para este conjunto.

Lo que sí las mueve a todas es la **tanda del sistema de diseño** (`app.sass`), y por eso
este guion se ejecuta después de ella.

## Las 21 figuras, con su superficie en la v2

Estado: ✅ = se renderizó y se capturó en la verificación del 5-nov · 🟡 = existe, falta capturarla
· 🔶 = existe pero la captura exige una acción o datos que hoy no hay.


| Archivo | Página | Ancla | Tamaño | Cómo llegar en la v2 | Estado | Nota |
|---|---|---|---|---|---|---|
| `dashboard.webp` | `/features/` | `—` | 1400×758 | `/` | ✅ renderizada | Vista Flota. Esconder el banner de mantenimiento antes de capturar. |
| `agente-panel.webp` | `/features/` | `#acceso-remoto` | 1400×758 | `/agents/<id>/summary` | ✅ renderizada | AgentWorkspace. 🔴 Recortar el bloque de IP pública, IP LAN y UUID del panel de hardware. |
| `script-ia-prompt.webp` | `/features/` | `#ejecucion-automatizacion` | 1400×583 | `/scripts` → «Nuevo script» → «Generar borrador con IA» | ✅ renderizada | El cuadro trae los tres ejemplos y el contador 0/2000. |
| `script-ia-borrador.webp` | `/features/` | `#ejecucion-automatizacion` | 1400×583 | ídem, tras pulsar «Generar borrador» | 🔶 acción pendiente | 🔶 Exige una llamada real a la IA (POST): el arnés del gauntlet la bloquea. |
| `plantillas-biblioteca.webp` | `/features/` | `#plantillas-scripts` | 1400×718 | `/scripts` | ✅ renderizada | Hoy son **50** scripts, no 44: hay que reescribir el alt y el figcaption. |
| `script-ejecucion-windows.webp` | `/features/` | `#plantillas-scripts` | 1400×923 | agente → «Ejecutar script» | 🔶 acción pendiente | 🔶 Exige ejecutar un script de verdad en un equipo y esperar la salida. |
| `parches.webp` | `/features/` | `#gestion-equipos` | 1400×758 | `/agents/<id>/patches` | ✅ renderizada | Sección Parches del workspace (32 actualizaciones en el equipo de laboratorio). |
| `software.webp` | `/features/` | `#gestion-equipos` | 1400×758 | `/agents/<id>/software` | ✅ renderizada | Sección Software del workspace. |
| `ubicacion-mapa.webp` | `/features/` | `#ubicacion` | 1400×613 | agente → ícono `place` de la cabecera | ✅ renderizada | Leaflet + círculo de incertidumbre. Usar una **VM del datacenter**, nunca un notebook real. |
| `ubicacion-historico.webp` | `/features/` | `#ubicacion` | 1400×613 | ídem → «Histórico» | 🔶 datos pendientes | 🔶 Necesita un equipo con trayectoria: la VM de laboratorio hereda un solo punto del sitio. |
| `respuesta-menu.webp` | `/features/` | `#respuesta-endpoint` | 1400×613 | agente → «Más acciones» → «Respuesta rápida» | ✅ renderizada | Submenú con las cuatro acciones. |
| `respuesta-mensaje.webp` | `/features/` | `#respuesta-endpoint` | 1400×613 | ídem → «Mensaje en pantalla» | ✅ renderizada | Diálogo con Título, Mensaje y el aviso de que el texto va sin traducir. |
| `modo-perdido-dialogo.webp` | `/features/` | `#modo-perdido` | 1400×758 | `/lost-equipment` → «Marcar como perdido» | ✅ renderizada | Diálogo con Equipo, Motivo, Cadencia y Contramedidas (avanzado). |
| `modo-perdido-lista.webp` | `/features/` | `#modo-perdido` | 1400×758 | `/lost-equipment` | 🔶 acción pendiente | 🔶 La tabla está **vacía** en staging. Sembrar una fila en la BD; NO marcar un equipo vivo (dispara bloqueo de pantalla, cámara y alarma). |
| `reportes-gestor.webp` | `/features/` | `#reporteria` | 1400×758 | riel → Reportes → «Gestor de reportes» → «Plantillas base» | ✅ renderizada | Administrador de reportes con las plantillas curadas. |
| `reportes-preview-html.webp` | `/features/` | `#reporteria` | 1400×758 | Gestor → plantilla «Estado de la Flota» → vista previa HTML | 🟡 por capturar | Se puede re-renderizar un reporte ya guardado. |
| `reportes-preview-pdf.webp` | `/features/` | `#reporteria` | 1400×758 | ídem, selector PDF | 🟡 por capturar | Mismo reporte, paginado. |
| `reportes-preview-html.webp` | `/guide_reports/` | `#dependencias` | 1400×758 | ídem | 🟡 por capturar | (segunda aparición) |
| `reportes-preview-pdf.webp` | `/guide_reports/` | `#dependencias` | 1400×758 | ídem | 🟡 por capturar | (segunda aparición) |
| `reportes-programacion.webp` | `/guide_reports/` | `#programaciones` | 1400×758 | Gestor → «Programaciones de reportes» | ✅ renderizada |  |
| `reportes-historial.webp` | `/guide_reports/` | `#historial` | 1400×758 | Gestor → «Historial de ejecución de reportes» | ✅ renderizada | Con datos reales en staging (Inventario de Agentes, Actividad, Panorama de Parches…). |

### Las 4 huérfanas: cuatro superficies distintas, ninguna duplicada

`reportes-consulta`, `reportes-consultas`, `reportes-editor` y `reportes-recursos` estaban
publicadas pero **ninguna página las referenciaba**.

Se sospechó que `consulta`/`consultas` —singular y plural— fueran una **renombrada a
medias**, con el archivo viejo publicado de más. **No lo son**: se abrieron las cuatro y
cada una muestra una superficie distinta del módulo de reportes.

| archivo | qué muestra de verdad | ¿sirve para docs? |
|---|---|---|
| `reportes-consultas` (plural) | la **lista** de consultas de datos del gestor: 2 filas, botón «Nueva» | flojo: casi vacío |
| `reportes-consulta` (singular) | el **editor de UNA consulta**: el JSON con `only`, `model: agent`, `filter` y `order_by` | sí, explica el modelo de consulta |
| `reportes-editor` | el **editor de plantillas**: Jinja + barra de formato, selector HTML/PDF/Depuración, pestañas HTML/CSS/VISTA PREVIA y el panel de Variables | **la más rica de las cuatro** |
| `reportes-recursos` | **Activos de reporte**: un único archivo, `observer-logo.png` | flojo: casi vacío |

Las cuatro siguen existiendo y son alcanzables en la v2 (pestañas del Administrador de
reportes, y el editor al abrir una plantilla). Así que son cuatro capturas **que nunca se
embebieron**, no cuatro archivos muertos — probablemente porque dos de ellas se ven vacías.

**Decisión para T062:** si se reponen, que sea con un `<figure>` que las use. La candidata
que vale la pena es `reportes-editor`; `consultas` y `recursos` no aportan con los datos de
staging. Y ninguna vuelve «por si acaso»: un archivo publicado sin `<figure>` es
exactamente lo que dejó este desorden.

## Cómo reponer

1. Capturar sobre `rmm-v2.observer.cl` (o ya sobre la 2.0.0 en staging) siguiendo la tabla.
2. Optimizar a WebP calidad 82 (`cwebp -q 82`): las PNG pesaban 2,9 MB y quedaron en 645 KB.
3. Devolver los archivos a `docs-site/assets/shots/`:
   `git mv docs-site-fuera-de-linea/assets-shots-v1 docs-site/assets/shots` y reemplazar.
4. Reponer los bloques `<figure class="doc-shot">` desde
   `docs-site-fuera-de-linea/capturas-v1-bloques.html`, en su ancla, **subiendo el `?v=N`**
   de cada `src` para saltar la caché del NPM.
5. Revisar los textos que el cambio de UI invalida. Al menos: el figcaption de
   `plantillas-biblioteca` dice «44 plantillas» y hoy son **50**.
6. La primera imagen de cada página va `loading="eager" fetchpriority="high"` (es la del LCP);
   el resto `loading="lazy" decoding="async"`.

## `/videos/` vuelve — decisión del usuario, 2026-11-05

La sección **no** está dada de baja para siempre: se repone **cuando la UI v2 esté
operativa**, con los dos videos (antirrobo 25 s, modo perdido 31 s) **regrabados** sobre
ella. Hoy muestran la consola v1 de punta a punta, y eso —no el corte de versión— es lo
que bloquea su regreso: regrabarlos es producción audiovisual, no trabajo de la ola 10.

Consecuencias prácticas:

- El `RedirectMatch 302 ^/videos/?$ → /features/` del vhost **tiene fecha de vencimiento**.
  No debe convertirse en 301 por antigüedad. Al reponer la sección se borra la línea.
- La página y toda su media siguen en `docs-site-fuera-de-linea/`: `videos/index.html` con
  su JSON-LD `VideoObject`, y `assets-videos/` con MP4 + WebM 1080p, pósters WebP/JPG y
  subtítulos VTT ES/EN de ambos. Se reponen con `git mv`, y hay que **reponer también** el
  enlace del riel en las 17 páginas, las dos tarjetas del inicio, los cuatro párrafos
  «Míralo en acción» de `/features/` y la entrada del sitemap — el detalle está en
  `docs-site-fuera-de-linea/README.md`.
- Los videos nuevos reemplazan los archivos de media, pero el `index.html` y su JSON-LD se
  reaprovechan salvo por la duración, que hay que corregir si los cortes cambian de largo.
