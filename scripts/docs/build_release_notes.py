#!/usr/bin/env python3
"""Genera la página pública de notas de versión: docs-site/release-notes/index.html.

Consolida los GitHub Releases de los DOS repos de producto —observer-rmm-dist
(servidor) y observer-agent-dist (agente)— en una sola página estática, con el
mismo chrome que el resto de docs-site (tema, selector ES/EN, SEO). Los repos son
privados; esta página es la copia PÚBLICA de sus notas, en docs.observer.cl.

Por qué acá y no colgado de WEB_VERSION: el viejo `get_webtar_url` armaba una URL a
un TARBALL de assets (código muerto, ya retirado), no a notas de versión. Las notas
son una página propia, desacoplada de cualquier número de versión.

Fuente: `gh api repos/<owner>/<repo>/releases --paginate` (usa el token de gh; los
repos son privados). El cuerpo de cada release ES el contenido de
release-notes/<tag>.md, escrito en es-CL. El chrome de la página es bilingüe; los
cuerpos se muestran en su idioma original (español).

Solo stdlib + el binario `gh`. Uso:
    python3 scripts/docs/build_release_notes.py [salida.html]
    (por defecto: docs-site/release-notes/index.html)
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

REPOS = [
    # (owner/repo, etiqueta ES, etiqueta EN, prefijo de ancla para desambiguar)
    ("braincorp-cl/observer-rmm-dist", "Servidor (producto)", "Server (product)", "srv"),
    ("braincorp-cl/observer-agent-dist", "Agente", "Agent", "agt"),
]

# ── Render de un subconjunto de Markdown → HTML ────────────────────────────────
# Deliberadamente acotado a lo que usan las notas: encabezados, viñetas, tablas,
# citas, negrita, `code` inline y enlaces. Nada de HTML crudo del origen se
# reinyecta sin escapar.

_BOLD = re.compile(r"\*\*(.+?)\*\*")  # no-greedy: tolera un *itálica* interior
_ITALIC = re.compile(r"\*([^*]+)\*")
_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    """Escapa HTML y aplica `code`, **negrita** y [enlaces](url).

    El `code` se aparta a placeholders ANTES de escapar, para que la negrita y los
    enlaces puedan cruzar por encima de un `code` inline (p.ej. **texto `x` más**),
    que era justo lo que se rompía al trocear el texto por los code spans."""
    codes: list[str] = []

    def _stash(m: "re.Match[str]") -> str:
        codes.append(html.escape(m.group(1)))
        return f"\x00{len(codes) - 1}\x00"

    tmp = _CODE.sub(_stash, text)
    esc = html.escape(tmp)  # escapa el resto; los placeholders \x00N\x00 sobreviven
    esc = _LINK.sub(lambda m: f'<a href="{m.group(2)}" rel="noopener">{m.group(1)}</a>', esc)
    esc = _BOLD.sub(r"<strong>\1</strong>", esc)
    esc = _ITALIC.sub(r"<em>\1</em>", esc)
    esc = re.sub(r"\x00(\d+)\x00", lambda m: "<code>" + codes[int(m.group(1))] + "</code>", esc)
    return esc


def _render_table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    # fila 0 = encabezado; fila 1 = separador |---|; resto = cuerpo
    body = [c for c in cells[2:]] if len(cells) > 2 else []
    thead = "".join(f"<th>{_inline(c)}</th>" for c in cells[0])
    tbody = "".join(
        "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>" for row in body
    )
    return f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>'


def md_to_html(md: str) -> str:
    """Convierte el cuerpo de una release (Markdown acotado) a HTML."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Encabezados: ## -> h3, ### -> h4 (h1/h2 los usa la estructura de la página)
        m = re.match(r"^(#{2,4})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)) + 1, 5)  # ## -> 3
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Tabla: bloque de líneas que empiezan con |
        if stripped.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            if len(block) >= 2:
                out.append(_render_table(block))
            continue

        # Cita
        if stripped.startswith(">"):
            block = []
            while i < n and lines[i].strip().startswith(">"):
                block.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote>" + _inline(" ".join(block)) + "</blockquote>")
            continue

        # Lista de viñetas
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < n and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append("<li>" + _inline(re.sub(r"^[-*]\s+", "", lines[i].strip())) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Párrafo (une líneas contiguas que no sean de otro bloque)
        para = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt.startswith(("#", "|", ">", "-", "*"))
            ):
                break
            para.append(nxt)
            i += 1
        out.append("<p>" + _inline(" ".join(para)) + "</p>")
    return "\n".join(out)


# ── Datos ──────────────────────────────────────────────────────────────────────

def fetch_releases(repo: str) -> list[dict]:
    """Trae los releases (no borradores) del repo vía gh, más nuevos primero."""
    raw = subprocess.run(
        ["gh", "api", f"repos/{repo}/releases", "--paginate"],
        check=True, capture_output=True, text=True,
    ).stdout
    rels = json.loads(raw)
    rels = [r for r in rels if not r.get("draft")]
    rels.sort(key=lambda r: r.get("published_at") or "", reverse=True)
    return rels


def fmt_date(iso: str) -> str:
    return (iso or "")[:10]


# ── Página ─────────────────────────────────────────────────────────────────────

HEAD = """<!DOCTYPE html>
<html lang="es" data-title-es="Notas de versión · Observer RMM" data-title-en="Release notes · Observer RMM">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Notas de versión · Observer RMM</title>
<meta name="description" content="Notas de versión de Observer RMM: cada release del servidor y del agente para Windows, Linux y macOS, con lo que cambió para el usuario y cómo actualizar.">
<!-- seo:start -->
<link rel="canonical" href="https://docs.observer.cl/release-notes/">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#0F1A2A">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Observer RMM">
<meta property="og:locale" content="es_CL">
<meta property="og:locale:alternate" content="en_US">
<meta property="og:url" content="https://docs.observer.cl/release-notes/">
<meta property="og:title" content="Notas de versión · Observer RMM">
<meta property="og:description" content="Cada release del servidor y del agente de Observer RMM, con lo que cambió para el usuario y cómo actualizar.">
<meta property="og:image" content="https://docs.observer.cl/assets/og-observer-rmm.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Observer RMM — monitoreo y administración remota de equipos">
<meta name="twitter:card" content="summary_large_image">
<!-- seo:end -->
<link rel="stylesheet" href="/assets/style.css?v=2">
<link href="/assets/favicon.png" rel="icon" type="image/png">
<style>
  .rn-toc{display:flex;flex-wrap:wrap;gap:.4rem;margin:.4rem 0 1.4rem}
  .rn-toc a{font-size:.82rem;padding:.15rem .5rem;border:1px solid var(--line,#2a3a52);border-radius:.4rem;text-decoration:none}
  .rn-rel{border-top:1px solid var(--line,#2a3a52);padding-top:1.1rem;margin-top:1.6rem}
  .rn-rel h2{margin:0 0 .1rem;scroll-margin-top:5rem}
  .rn-date{font-size:.8rem;opacity:.7;font-variant-numeric:tabular-nums}
  .rn-body h3{margin:1rem 0 .3rem;font-size:1.02rem}
  .rn-body h4{margin:.8rem 0 .2rem;font-size:.92rem;opacity:.85}
  .table-wrap{overflow-x:auto}
  .rn-body table{border-collapse:collapse;font-size:.86rem;margin:.5rem 0}
  .rn-body th,.rn-body td{border:1px solid var(--line,#2a3a52);padding:.3rem .55rem;text-align:left;vertical-align:top}
</style>
<script type="application/ld+json">
__JSONLD__
</script>
<script>
(function () {
  var d = document.documentElement;
  var t = localStorage.getItem('observer-docs-theme');
  if (t) d.setAttribute('data-theme', t);
  var l = localStorage.getItem('observer-docs-lang') || 'es';
  d.setAttribute('data-lang', l);
  d.setAttribute('lang', l);
  var tt = d.getAttribute('data-title-' + l);
  if (tt) document.title = tt;
})();
</script>
</head>
<body>
<header class="deck">
  <span class="signal" aria-hidden="true"></span>
  <a class="brand" href="/"><b>Observer RMM</b><span class="sub">Docs</span></a>
  <span class="spacer"></span>
  <div class="lang-toggle" role="group" aria-label="Idioma / Language">
    <button type="button" data-set-lang="es" aria-pressed="true">ES</button>
    <button type="button" data-set-lang="en" aria-pressed="false">EN</button>
  </div>
  <button class="theme-toggle" id="themeToggle" title="Cambiar tema / Toggle theme" aria-label="Cambiar tema / Toggle theme">◐</button>
</header>

<div class="shell">
  <nav class="rail" aria-label="Secciones / Sections">
    <p class="rail-label"><span class="lang-es">Documentación</span><span class="lang-en">Documentation</span></p>
    <a href="/"><span class="lang-es">Inicio</span><span class="lang-en">Home</span></a>
    <a href="/features/"><span class="lang-es">Características</span><span class="lang-en">Features</span></a>
    <a href="/release-notes/" class="active"><span class="lang-es">Notas de versión</span><span class="lang-en">Release notes</span></a>
    <a href="/guide_gettingstarted/"><span class="lang-es">Primeros pasos</span><span class="lang-en">Getting started</span></a>
    <a href="/guide_reports/"><span class="lang-es">Generar reportes</span><span class="lang-en">Generating reports</span></a>
    <a href="/functions/email_alerts/"><span class="lang-es">Alertas por correo</span><span class="lang-en">Email alerts</span></a>
    <a href="/functions/permissions/"><span class="lang-es">Permisos y seguridad</span><span class="lang-en">Permissions &amp; security</span></a>
    <a href="/uso_aceptable/"><span class="lang-es">Uso aceptable y privacidad</span><span class="lang-en">Acceptable use &amp; privacy</span></a>
    <a href="/faq/"><span class="lang-es">Preguntas frecuentes</span><span class="lang-en">FAQ</span></a>
  </nav>

  <main>
    <div class="content">
      <p class="eyebrow lang-es">Notas de versión</p>
      <p class="eyebrow lang-en">Release notes</p>
      <h1><span class="lang-es">Notas de versión</span><span class="lang-en">Release notes</span></h1>
      <p class="lead lang-es">El historial de versiones de Observer RMM, en dos pistas: el <strong>servidor</strong> (la plataforma) y el <strong>agente</strong> que corre en cada equipo Windows, Linux y macOS. Cada entrada describe lo que cambió para el usuario y cómo actualizar. Las notas están redactadas en español.</p>
      <p class="lead lang-en">The version history of Observer RMM, on two tracks: the <strong>server</strong> (the platform) and the <strong>agent</strong> that runs on each Windows, Linux, and macOS machine. Each entry describes what changed for the user and how to update. The notes are written in Spanish.</p>
"""

FOOT = """
      <footer>
        <span class="mono">Observer RMM</span><span class="lang-es"> — Documentación operativa y guías para clientes.</span><span class="lang-en"> — Operational documentation and guides for customers.</span>
      </footer>
    </div>
  </main>
</div>

<script>
(function () {
  var d = document.documentElement;
  var btns = document.querySelectorAll('.lang-toggle [data-set-lang]');
  function setPressed(l) {
    for (var i = 0; i < btns.length; i++) {
      btns[i].setAttribute('aria-pressed', btns[i].getAttribute('data-set-lang') === l ? 'true' : 'false');
    }
  }
  function apply(l) {
    d.setAttribute('data-lang', l);
    d.setAttribute('lang', l);
    localStorage.setItem('observer-docs-lang', l);
    var tt = d.getAttribute('data-title-' + l);
    if (tt) document.title = tt;
    setPressed(l);
  }
  for (var i = 0; i < btns.length; i++) {
    (function (b) { b.addEventListener('click', function () { apply(b.getAttribute('data-set-lang')); }); })(btns[i]);
  }
  setPressed(d.getAttribute('data-lang') || 'es');

  var tb = document.getElementById('themeToggle');
  tb.addEventListener('click', function () {
    var cur = d.getAttribute('data-theme');
    var isDark = cur ? cur === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    var next = isDark ? 'light' : 'dark';
    d.setAttribute('data-theme', next);
    localStorage.setItem('observer-docs-theme', next);
  });
})();
</script>
</body>
</html>
"""


def build() -> str:
    sections = []
    latest_for_jsonld = []
    for repo, es, en, prefix in REPOS:
        rels = fetch_releases(repo)
        cards = []
        for r in rels:
            tag = r["tag_name"]
            anchor = f"{prefix}-{tag}"
            date = fmt_date(r.get("published_at", ""))
            name = html.escape(r.get("name") or tag)
            body = md_to_html((r.get("body") or "").strip())
            cards.append(
                f'<article class="rn-rel">\n'
                f'  <h2 id="{html.escape(anchor)}">{name}</h2>\n'
                f'  <p class="rn-date">{html.escape(date)}</p>\n'
                f'  <div class="rn-body">{body}</div>\n'
                f'</article>'
            )
        if rels:
            latest_for_jsonld.append((es, rels[0]["tag_name"], fmt_date(rels[0].get("published_at", ""))))
        # índice de saltos rápidos por versión
        toc = "".join(
            f'<a href="#{html.escape(prefix)}-{html.escape(r["tag_name"])}">{html.escape(r["tag_name"])}</a>'
            for r in rels
        )
        sections.append(
            f'<h2 style="margin-top:2.2rem"><span class="lang-es">{html.escape(es)}</span>'
            f'<span class="lang-en">{html.escape(en)}</span></h2>\n'
            f'<div class="rn-toc">{toc}</div>\n' + "\n".join(cards)
        )

    jsonld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "inLanguage": "es-CL",
        "name": "Notas de versión · Observer RMM",
        "url": "https://docs.observer.cl/release-notes/",
        "about": {"@type": "SoftwareApplication", "name": "Observer RMM",
                  "applicationCategory": "Remote Monitoring and Management",
                  "operatingSystem": "Windows, Linux, macOS"},
    }
    head = HEAD.replace("__JSONLD__", json.dumps(jsonld, ensure_ascii=False, indent=1))
    return head + "\n".join(sections) + FOOT


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs-site/release-notes/index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    print(f"OK: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
