#!/usr/bin/env python3
"""Genera el changelog público de Observer RMM (HTML autocontenido) desde CHANGELOG.md.

El HTML resultante se publica en https://agents.observer.cl/changelog/index.html
(workflow publish-changelog.yml, por WebDAV). La consola lo enlaza desde el aviso de
"versión disponible" (MainLayout.vue) con el ancla #v{TRMM_VERSION}.

CLAVE: cada entrada `## vX.Y.Z — fecha` produce un encabezado con `id="vX.Y.Z"` EXACTO
(el token tal cual, con los puntos), para que el ancla de la UI resuelva. No se slugifica.

Solo stdlib (corre en el runner de CI sin dependencias). Cero strings de terceros:
el contenido viene de CHANGELOG.md, que pasa por el gate no-legacy-strings.

Uso:  python3 scripts/build_changelog.py [CHANGELOG.md] [salida.html]
      (por defecto: CHANGELOG.md -> stdout)
"""
from __future__ import annotations

import html
import re
import sys

VERSION_RE = re.compile(r"^##\s+(v\d+\.\d+\.\d+[^\s]*)\s*[—-]\s*(.*)$")
BULLET_RE = re.compile(r"^\s*-\s+(.*)$")
CODE_RE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    """Escapa HTML y renderiza `code` inline. Nada más (formato deliberadamente simple)."""
    out, last = [], 0
    for m in CODE_RE.finditer(text):
        out.append(html.escape(text[last : m.start()]))
        out.append("<code>" + html.escape(m.group(1)) + "</code>")
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


def parse(md: str):
    """CHANGELOG.md -> [(version, fecha, [items])] en orden de aparición."""
    entries, cur = [], None
    in_intro = True
    for line in md.splitlines():
        mver = VERSION_RE.match(line)
        if mver:
            in_intro = False
            cur = {"ver": mver.group(1), "date": mver.group(2).strip(), "items": []}
            entries.append(cur)
            continue
        if in_intro:
            continue  # título + párrafo introductorio del .md no van al HTML
        mb = BULLET_RE.match(line)
        if mb and cur is not None:
            cur["items"].append(mb.group(1).strip())
    return entries


def render(entries) -> str:
    sections = []
    for e in entries:
        lis = "\n".join(f"      <li>{_inline(i)}</li>" for i in e["items"])
        ver = html.escape(e["ver"])
        date = html.escape(e["date"])
        sections.append(
            f'  <section>\n'
            f'    <h2 id="{ver}">{ver} <span class="date">{date}</span></h2>\n'
            f"    <ul>\n{lis}\n    </ul>\n"
            f"  </section>"
        )
    body = "\n".join(sections)
    return TEMPLATE.format(body=body)


# Autocontenido: CSS inline, paleta "Observation Deck" espejando la UI. Sin recursos externos.
TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Changelog — Observer RMM</title>
<style>
  :root {{ --navy:#0F1A2A; --surface:#17253A; --primary:#0E8FA8; --accent:#22C3D6; --text:#E8EEF4; --muted:#8AA0B8; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--navy); color:var(--text); font:16px/1.6 system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
  header {{ background:var(--surface); border-bottom:3px solid var(--primary); padding:24px 20px; }}
  header h1 {{ margin:0; font-size:22px; }} header p {{ margin:6px 0 0; color:var(--muted); font-size:14px; }}
  main {{ max-width:820px; margin:0 auto; padding:24px 20px 64px; }}
  section {{ background:var(--surface); border:1px solid #23364e; border-radius:10px; padding:16px 20px; margin:18px 0; }}
  h2 {{ font-size:18px; margin:4px 0 12px; color:var(--accent); scroll-margin-top:16px; }}
  h2 .date {{ color:var(--muted); font-size:13px; font-weight:400; margin-left:8px; }}
  h2:target {{ outline:2px solid var(--primary); outline-offset:6px; border-radius:4px; }}
  ul {{ margin:0; padding-left:20px; }} li {{ margin:6px 0; }}
  code {{ background:#0b1420; color:var(--accent); padding:1px 6px; border-radius:4px; font-size:13px; }}
  a {{ color:var(--primary); }}
</style>
</head>
<body>
<header>
  <h1>Observer RMM — Changelog</h1>
  <p>Notas de versión del producto.</p>
</header>
<main>
{body}
</main>
</body>
</html>
"""


def main(argv):
    src = argv[1] if len(argv) > 1 else "CHANGELOG.md"
    with open(src, encoding="utf-8") as fh:
        entries = parse(fh.read())
    if not entries:
        sys.stderr.write(f"error: no se hallaron entradas '## vX.Y.Z' en {src}\n")
        return 1
    out = render(entries)
    if len(argv) > 2:
        with open(argv[2], "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
