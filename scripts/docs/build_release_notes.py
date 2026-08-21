#!/usr/bin/env python3
"""Genera las páginas públicas de notas de versión en docs-site/release-notes/.

Consolida los GitHub Releases de los DOS repos de producto en **dos pistas
separadas**, cada una en su propia URL:

    docs-site/release-notes/index.html         -> landing con las dos pistas
    docs-site/release-notes/server/index.html  -> servidor (observer-rmm-dist)
    docs-site/release-notes/agent/index.html   -> agente  (observer-agent-dist)

El historial combinado era una sola página gigante e ilegible; separarlo por
servidor y agente deja cada pista corta y navegable en su propia dirección.

Los repos son privados: esta página es la copia PÚBLICA de sus notas en
docs.observer.cl. Por eso **ningún enlace a github.com sobrevive al render** —
serían enlaces rotos para cualquiera que no tenga acceso al repo. Los cruces
entre versiones (\"acompaña al Agent vX\") se reescriben a anclas del propio sitio;
el resto de los enlaces a github (README, compare, commits) se des-enlazan a
texto plano, y las líneas \"Full Changelog\" que GitHub agrega solo se eliminan.

Fuente: `gh api repos/<owner>/<repo>/releases --paginate` (usa el token de gh;
los repos son privados). El cuerpo de cada release ES el contenido de
release-notes/<tag>.md, escrito en es-CL. El chrome de la página es bilingüe; los
cuerpos se muestran en su idioma original (español).

Solo stdlib + el binario `gh`. Uso:
    python3 scripts/docs/build_release_notes.py [dir_salida]
    (por defecto: docs-site/release-notes)
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

# clave -> (owner/repo, etiqueta ES, etiqueta EN, prefijo de ancla, ruta pública)
TRACKS = {
    "server": (
        "braincorp-cl/observer-rmm-dist",
        "Servidor (plataforma)",
        "Server (platform)",
        "srv",
        "/release-notes/server/",
    ),
    "agent": (
        "braincorp-cl/observer-agent-dist",
        "Agente",
        "Agent",
        "agt",
        "/release-notes/agent/",
    ),
}

# ── Saneo de enlaces a github.com ────────────────────────────────────────────
# Los repos son privados; cualquier enlace a github.com es roto de nacimiento
# para el público. Se eliminan ANTES de renderizar el Markdown.

# Enlace markdown a un tag de release de nuestros repos -> se reescribe a un
# ancla del propio sitio, en la pista que corresponda.
_GH_TAG = re.compile(
    r"https?://github\.com/braincorp-cl/observer-(rmm|agent)-dist/releases/tag/([^)\s]+)"
)
# Cualquier enlace markdown [texto](url-github) -> ver _rewrite_md_link.
_MD_GH_LINK = re.compile(r"\[([^\]]+)\]\((https?://github\.com/[^)]+)\)")
# URL de github suelta (sin envolver en enlace markdown), p.ej. la línea
# \"Full Changelog: https://github.com/...\".
_BARE_GH = re.compile(r"https?://github\.com/\S+")
# Línea autogenerada por GitHub que no aporta nada en la copia pública.
_FULL_CHANGELOG = re.compile(r"^\s*\*{0,2}Full Changelog\*{0,2}\s*:", re.IGNORECASE)


def _onsite_anchor(kind: str, tag: str) -> str:
    """Ancla del propio sitio para un tag de release, según la pista."""
    if kind == "rmm":
        return f"/release-notes/server/#srv-{tag}"
    return f"/release-notes/agent/#agt-{tag}"


def _rewrite_md_link(m: "re.Match[str]") -> str:
    text, url = m.group(1), m.group(2)
    tag = _GH_TAG.match(url)
    if tag:
        # Cruce entre versiones -> enlace interno vivo, no a github.
        return f"[{text}]({_onsite_anchor(tag.group(1), tag.group(2))})"
    # README / compare / commits / etc. -> se conserva el texto, sin enlace roto.
    return text


def sanitize_github(md: str) -> str:
    """Deja el Markdown sin ninguna referencia a github.com."""
    lines = [
        ln
        for ln in md.replace("\r\n", "\n").split("\n")
        if not _FULL_CHANGELOG.match(ln)
    ]
    text = "\n".join(lines)
    text = _MD_GH_LINK.sub(_rewrite_md_link, text)
    # Cualquier URL de github que haya quedado suelta se elimina (deja el resto
    # de la frase intacto).
    text = _BARE_GH.sub("", text)
    return text


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
<html lang="es" data-title-es="__TITLE_ES__" data-title-en="__TITLE_EN__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE_ES__</title>
<meta name="description" content="__DESC__">
<!-- seo:start -->
<link rel="canonical" href="__CANON__">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#0F1A2A">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Observer RMM">
<meta property="og:locale" content="es_CL">
<meta property="og:locale:alternate" content="en_US">
<meta property="og:url" content="__CANON__">
<meta property="og:title" content="__TITLE_ES__">
<meta property="og:description" content="__DESC__">
<meta property="og:image" content="https://docs.observer.cl/assets/og-observer-rmm.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Observer RMM — monitoreo y administración remota de equipos">
<meta name="twitter:card" content="summary_large_image">
<!-- seo:end -->
<link rel="stylesheet" href="/assets/style.css?v=2">
<link href="/assets/favicon.png" rel="icon" type="image/png">
<style>
  .rn-tracks{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));margin:1.2rem 0}
  .rn-track{border:1px solid var(--line,#2a3a52);border-radius:.6rem;padding:1.1rem 1.2rem;text-decoration:none;display:block}
  .rn-track h2{margin:.1rem 0 .3rem;font-size:1.1rem}
  .rn-track .rn-latest{font-size:.85rem;opacity:.8;font-variant-numeric:tabular-nums}
  .rn-track .rn-go{margin-top:.6rem;font-size:.85rem;font-weight:600}
  .rn-toc{display:flex;flex-wrap:wrap;gap:.4rem;margin:.4rem 0 1.4rem}
  .rn-toc a{font-size:.82rem;padding:.15rem .5rem;border:1px solid var(--line,#2a3a52);border-radius:.4rem;text-decoration:none}
  .rn-rel{border-top:1px solid var(--line,#2a3a52);padding-top:1.1rem;margin-top:1.6rem}
  .rn-rel h2{margin:0 0 .1rem;scroll-margin-top:5rem}
  .rn-date{font-size:.8rem;opacity:.7;font-variant-numeric:tabular-nums}
  .rn-body h3{margin:1rem 0 .3rem;font-size:1.02rem}
  .rn-body h4{margin:.8rem 0 .2rem;font-size:.92rem;opacity:.85}
  .rn-switch{display:flex;gap:.5rem;margin:.2rem 0 1rem}
  .rn-switch a{font-size:.85rem;padding:.25rem .7rem;border:1px solid var(--line,#2a3a52);border-radius:.4rem;text-decoration:none}
  .rn-switch a[aria-current="page"]{background:var(--line,#2a3a52)}
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


def _head(title_es: str, title_en: str, desc: str, canon: str, jsonld: dict) -> str:
    return (
        HEAD.replace("__TITLE_ES__", html.escape(title_es))
        .replace("__TITLE_EN__", html.escape(title_en))
        .replace("__DESC__", html.escape(desc))
        .replace("__CANON__", canon)
        .replace("__JSONLD__", json.dumps(jsonld, ensure_ascii=False, indent=1))
    )


def _switch(active: str) -> str:
    """Barra para saltar entre las dos pistas y volver al índice."""
    def link(href, es, en, key):
        cur = ' aria-current="page"' if key == active else ""
        return (
            f'<a href="{href}"{cur}>'
            f'<span class="lang-es">{es}</span><span class="lang-en">{en}</span></a>'
        )

    return (
        '<div class="rn-switch">'
        + link("/release-notes/", "Todo", "Overview", "index")
        + link("/release-notes/server/", "Servidor", "Server", "server")
        + link("/release-notes/agent/", "Agente", "Agent", "agent")
        + "</div>"
    )


def build_track(key: str) -> str:
    """Página de una pista (servidor o agente)."""
    repo, es, en, prefix, path = TRACKS[key]
    rels = fetch_releases(repo)

    cards = []
    for r in rels:
        tag = r["tag_name"]
        anchor = f"{prefix}-{tag}"
        date = fmt_date(r.get("published_at", ""))
        name = html.escape(r.get("name") or tag)
        body = md_to_html(sanitize_github((r.get("body") or "").strip()))
        cards.append(
            f'<article class="rn-rel">\n'
            f'  <h2 id="{html.escape(anchor)}">{name}</h2>\n'
            f'  <p class="rn-date">{html.escape(date)}</p>\n'
            f'  <div class="rn-body">{body}</div>\n'
            f'</article>'
        )
    toc = "".join(
        f'<a href="#{html.escape(prefix)}-{html.escape(r["tag_name"])}">{html.escape(r["tag_name"])}</a>'
        for r in rels
    )

    title_es = f"Notas de versión · {es} · Observer RMM"
    title_en = f"Release notes · {en} · Observer RMM"
    if key == "server":
        desc = ("Notas de versión del servidor (plataforma) de Observer RMM: cada release "
                "con lo que cambió para el usuario y cómo actualizar.")
        lead_es = ("El historial de versiones del <strong>servidor</strong> —la plataforma de "
                   "Observer RMM—. Cada entrada describe lo que cambió para el usuario y cómo "
                   "actualizar. Las notas del <strong>agente</strong> que corre en cada equipo "
                   'están en su propia página: <a href="/release-notes/agent/">Notas del agente</a>.')
        lead_en = ("The version history of the <strong>server</strong> —the Observer RMM "
                   "platform—. Each entry describes what changed for the user and how to update. "
                   "The notes for the <strong>agent</strong> that runs on each machine live on "
                   'their own page: <a href="/release-notes/agent/">Agent release notes</a>.')
    else:
        desc = ("Notas de versión del agente de Observer RMM para Windows, Linux y macOS: cada "
                "release con lo que cambió y cómo actualiza la flota.")
        lead_es = ("El historial de versiones del <strong>agente</strong> que corre en cada equipo "
                   "Windows, Linux y macOS. Cada entrada describe lo que cambió y cómo se actualiza "
                   "la flota. Las notas del <strong>servidor</strong> están en su propia página: "
                   '<a href="/release-notes/server/">Notas del servidor</a>.')
        lead_en = ("The version history of the <strong>agent</strong> that runs on each Windows, "
                   "Linux, and macOS machine. Each entry describes what changed and how the fleet "
                   "updates. The <strong>server</strong> notes live on their own page: "
                   '<a href="/release-notes/server/">Server release notes</a>.')

    jsonld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "inLanguage": "es-CL",
        "name": title_es,
        "url": f"https://docs.observer.cl{path}",
        "isPartOf": {"@type": "CollectionPage", "name": "Notas de versión · Observer RMM",
                     "url": "https://docs.observer.cl/release-notes/"},
        "about": {"@type": "SoftwareApplication", "name": "Observer RMM",
                  "applicationCategory": "Remote Monitoring and Management",
                  "operatingSystem": "Windows, Linux, macOS"},
    }

    head = _head(title_es, title_en, desc, f"https://docs.observer.cl{path}", jsonld)
    body = (
        '<p class="eyebrow lang-es">Notas de versión</p>\n'
        '<p class="eyebrow lang-en">Release notes</p>\n'
        f'<h1><span class="lang-es">{html.escape(es)}</span>'
        f'<span class="lang-en">{html.escape(en)}</span></h1>\n'
        + _switch(key)
        + f'<p class="lead lang-es">{lead_es}</p>\n'
        + f'<p class="lead lang-en">{lead_en}</p>\n'
        + f'<div class="rn-toc">{toc}</div>\n'
        + "\n".join(cards)
    )
    return head + body + FOOT


def build_landing() -> str:
    """Índice: dos tarjetas, servidor y agente, con la última versión de cada una."""
    cards = []
    jsonld_parts = []
    for key in ("server", "agent"):
        repo, es, en, prefix, path = TRACKS[key]
        rels = fetch_releases(repo)
        latest = rels[0] if rels else None
        if latest:
            tag = html.escape(latest["tag_name"])
            date = html.escape(fmt_date(latest.get("published_at", "")))
            latest_es = f'Última versión: <strong>{tag}</strong> · {date}'
            latest_en = f'Latest: <strong>{tag}</strong> · {date}'
        else:
            latest_es = latest_en = ""
        desc_es = ("La plataforma: consola, API, monitoreo, alertas, modo perdido."
                   if key == "server"
                   else "El programa que corre en cada equipo Windows, Linux y macOS.")
        desc_en = ("The platform: console, API, monitoring, alerts, lost mode."
                   if key == "server"
                   else "The program that runs on each Windows, Linux, and macOS machine.")
        cards.append(
            f'<a class="rn-track" href="{path}">'
            f'<h2><span class="lang-es">{html.escape(es)}</span>'
            f'<span class="lang-en">{html.escape(en)}</span></h2>'
            f'<p><span class="lang-es">{desc_es}</span><span class="lang-en">{desc_en}</span></p>'
            f'<p class="rn-latest"><span class="lang-es">{latest_es}</span>'
            f'<span class="lang-en">{latest_en}</span></p>'
            f'<p class="rn-go"><span class="lang-es">Ver notas →</span>'
            f'<span class="lang-en">View notes →</span></p>'
            f'</a>'
        )
        if latest:
            jsonld_parts.append({
                "@type": "CollectionPage",
                "name": f"Notas de versión · {es}",
                "url": f"https://docs.observer.cl{path}",
            })

    title_es = "Notas de versión · Observer RMM"
    title_en = "Release notes · Observer RMM"
    desc = ("Notas de versión de Observer RMM en dos pistas: el servidor (la plataforma) y el "
            "agente para Windows, Linux y macOS, con lo que cambió y cómo actualizar.")
    jsonld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "inLanguage": "es-CL",
        "name": title_es,
        "url": "https://docs.observer.cl/release-notes/",
        "hasPart": jsonld_parts,
        "about": {"@type": "SoftwareApplication", "name": "Observer RMM",
                  "applicationCategory": "Remote Monitoring and Management",
                  "operatingSystem": "Windows, Linux, macOS"},
    }

    head = _head(title_es, title_en, desc, "https://docs.observer.cl/release-notes/", jsonld)
    body = (
        '<p class="eyebrow lang-es">Notas de versión</p>\n'
        '<p class="eyebrow lang-en">Release notes</p>\n'
        '<h1><span class="lang-es">Notas de versión</span><span class="lang-en">Release notes</span></h1>\n'
        '<p class="lead lang-es">El historial de Observer RMM va en dos pistas separadas: el '
        '<strong>servidor</strong> (la plataforma) y el <strong>agente</strong> que corre en cada '
        'equipo. Elige una pista. Las notas están redactadas en español.</p>\n'
        '<p class="lead lang-en">The Observer RMM history runs on two separate tracks: the '
        '<strong>server</strong> (the platform) and the <strong>agent</strong> that runs on each '
        'machine. Pick a track. The notes are written in Spanish.</p>\n'
        + '<div class="rn-tracks">' + "".join(cards) + "</div>"
    )
    return head + body + FOOT


def main() -> None:
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs-site/release-notes")
    targets = {
        base / "index.html": build_landing,
        base / "server" / "index.html": lambda: build_track("server"),
        base / "agent" / "index.html": lambda: build_track("agent"),
    }
    for out, builder in targets.items():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(builder(), encoding="utf-8")
        print(f"OK: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
