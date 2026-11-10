# Fuera de línea — no se publica

Lo que vive acá **no lo sube** `scripts/docs/publish_docs.py`: ese script sincroniza
sólo `docs-site/`. Por eso basta mover una carpeta aquí para darla de baja del sitio,
y un `git mv` de vuelta para reponerla.

| Carpeta | Era | Dada de baja | Motivo |
|---|---|---|---|
| `videos/` | `docs-site/videos/` → `https://docs.observer.cl/videos/` | 2026-11-05 | Baja **temporal**: los dos videos (antirrobo 25 s, modo perdido 31 s) muestran la consola **v1**. 🔑 **Vuelve** — decisión del usuario del 5-nov: se repone cuando la **UI v2 esté operativa**, con los dos videos **regrabados** sobre ella. Mientras tanto la URL sale por `RedirectMatch 302 → /features/`. |
| `assets-videos/` | `docs-site/assets/videos/` | 2026-11-05 | Media de esa sección: MP4 + WebM 1080p, pósters WebP/JPG y subtítulos VTT ES/EN de ambos videos. |
| `assets-shots-v1/` | `docs-site/assets/shots/` | 2026-11-05 | Las **23 capturas de la consola v1** (19 usadas + 4 huérfanas). Se retiraron junto con sus 21 bloques `<figure>` de `/features/` y `/guide_reports/`: la UI v2 ya cubre las 19 superficies, pero su cabecera todavía dice v1.4.42 y falta la tanda del sistema de diseño ⇒ se reponen con la **2.0.0**. Guion de re-captura: `scripts/docs/GUION-RECAPTURA-UI-V2.md` |
| `capturas-v1-bloques.html` | — | 2026-11-05 | Los 21 bloques `<figure class="doc-shot">` tal cual estaban, con su ancla, para reponerlos sin reescribir los figcaption. |

## Para reponer `/videos/`

1. `git mv docs-site-fuera-de-linea/videos docs-site/videos`
2. `git mv docs-site-fuera-de-linea/assets-videos docs-site/assets/videos`
3. Reponer en las 17 páginas el enlace del riel
   `<a href="/videos/"><span class="lang-es">Videos</span><span class="lang-en">Videos</span></a>`,
   entre «Catálogo de perfiles» y «Notas de versión».
4. Reponer las dos tarjetas de `docs-site/index.html` (ES y EN) y los cuatro párrafos
   «Míralo en acción» de `docs-site/features/index.html` (`#respuesta-endpoint` y `#modo-perdido`).
5. Reponer la entrada `<url>` de `docs-site/sitemap.xml`.

El commit que dio de baja la sección tiene todo eso junto; `git revert` de ese commit
es el camino corto.

## Para reponer las capturas

No basta con mover la carpeta: hay que **volver a capturar** sobre la UI v2 y reponer los
bloques `<figure>`. Todo el procedimiento, con la tabla superficie por superficie y las
decisiones ya tomadas (flota sintética, las tres capturas que exigen una acción real,
privacidad), está en **`scripts/docs/GUION-RECAPTURA-UI-V2.md`**.
