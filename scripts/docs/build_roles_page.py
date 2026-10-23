#!/usr/bin/env python3
"""Genera el catálogo público de perfiles en docs-site/administracion/roles/index.html.

La fuente es `api/observerrmm/accounts/role_catalog.py` —el mismo módulo que usa
el sembrador `seed_default_roles`—, de modo que la página publicada no pueda
desfasarse de los perfiles que la plataforma crea de verdad. Las etiquetas de
cada permiso se toman de la propia consola (`RolesForm.vue` + `i18n/{es,en}.json`)
para que la doc nombre los permisos exactamente como el operador los ve en
Configuración → Gestor de permisos.

La barra lateral se copia de `docs-site/functions/permissions/index.html`: es una
página escrita a mano, así que el rail generado sigue al del resto del sitio sin
tener que mantener dos copias.

Falla (exit 1) si un permiso del catálogo no tiene etiqueta en la consola: sería
un permiso nuevo sin traducir, y la página quedaría mostrando el nombre interno.

Solo stdlib. Uso:
    python3 scripts/docs/build_roles_page.py [salida]
    (por defecto: docs-site/administracion/roles/index.html)
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "api" / "observerrmm" / "accounts" / "role_catalog.py"
RAIL_SOURCE = ROOT / "docs-site" / "functions" / "permissions" / "index.html"
TEMPLATE = (Path(__file__).resolve().parent / "roles_page.template.html").read_text()

FAMILIES = [
    (
        "gobierno",
        ("Gobierno de la plataforma", "Platform governance"),
        (
            "Quién administra el sistema y a su propia gente. Son los perfiles con "
            "más alcance y los que conviene contar con los dedos de una mano.",
            "Who administers the system and their own people. These are the "
            "widest-reaching roles, and the ones you want to be able to count on one hand.",
        ),
    ),
    (
        "operacion",
        ("Operación y mesa de servicio", "Operations and service desk"),
        (
            "El día a día: atender incidentes, tomar control remoto, vigilar alertas "
            "y revisar lo que pasó.",
            "Day to day: handling incidents, taking remote control, watching alerts "
            "and reviewing what happened.",
        ),
    ),
    (
        "especialista",
        ("Especialistas", "Specialists"),
        (
            "Funciones que concentran una disciplina —parches, automatización, "
            "inventario, informes— sin necesitar el resto de la plataforma.",
            "Functions centred on one discipline —patching, automation, inventory, "
            "reporting— without needing the rest of the platform.",
        ),
    ),
    (
        "custodia",
        ("Custodia y respuesta", "Custody and response"),
        (
            "Capacidades irreversibles o sensibles para la privacidad. Se asignan de "
            "a una, a una persona concreta y por el tiempo que dure el caso.",
            "Irreversible or privacy-sensitive capabilities. Assigned one at a time, "
            "to a specific person, and for as long as the case lasts.",
        ),
    ),
]


def load_catalog():
    spec = importlib.util.spec_from_file_location("role_catalog", CATALOG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def perm_labels() -> dict:
    """permiso -> (etiqueta ES, etiqueta EN), tomadas de la consola."""
    vue = (ROOT / "web/app/src/components/accounts/RolesForm.vue").read_text()
    pairs = re.findall(
        r'v-model="localRole\.(can_[a-z_]+)"\s*:label="\$t\(\'rolesForm\.(\w+)\'\)"', vue
    )
    es = json.loads((ROOT / "web/app/src/i18n/es.json").read_text())["rolesForm"]
    en = json.loads((ROOT / "web/app/src/i18n/en.json").read_text())["rolesForm"]
    return {p: (es[k], en[k]) for p, k in pairs}


def rail() -> str:
    """Barra lateral del sitio, con el catálogo marcado como activo."""
    html = RAIL_SOURCE.read_text()
    inner = re.search(r'<nav class="rail"[^>]*>(.*?)</nav>', html, re.S).group(1)
    inner = inner.replace(' class="active"', "")
    inner = inner.replace(
        '<a href="/administracion/roles/">', '<a href="/administracion/roles/" class="active">'
    )
    return inner.strip("\n")


def last_commit_date() -> str:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(CATALOG)],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return out or date.today().isoformat()
    except Exception:
        return date.today().isoformat()


def bi(es: str, en: str) -> str:
    return f'<span class="lang-es">{es}</span><span class="lang-en">{en}</span>'


def anchor(name: str) -> str:
    slug = name.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        slug = slug.replace(a, b)
    return "rol-" + re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "docs-site/administracion/roles/index.html"
    cat = load_catalog()
    labels = perm_labels()

    missing = sorted(set(cat.MANAGED_PERMS) - set(labels))
    if missing:
        print(f"ERROR: permisos sin etiqueta en la consola: {', '.join(missing)}", file=sys.stderr)
        return 1

    fam_titles = {key: titles for key, titles, _ in FAMILIES}

    # ----------------------------------------------------------------- resumen
    rows = []
    for role in cat.STANDARD_ROLES:
        tes, ten = fam_titles[role["family"]]
        mark = ' <span class="perm-count">●</span>' if role["sensitive"] else ""
        rows.append(
            f'<tr><td><a href="#{anchor(role["name"])}"><strong>{escape(role["name"])}</strong></a>{mark}</td>'
            f'<td>{bi(escape(tes), escape(ten))}</td>'
            f'<td>{bi(escape(role["summary"]["es"]), escape(role["summary"]["en"]))}</td>'
            f'<td style="text-align:right">{len(role["perms"])}</td></tr>'
        )
    summary = (
        '      <div class="table-wrap"><table><thead><tr>'
        f'<th>{bi("Perfil", "Role")}</th><th>{bi("Familia", "Family")}</th>'
        f'<th>{bi("Para qué sirve", "What it is for")}</th>'
        f'<th style="text-align:right">{bi("Permisos", "Permissions")}</th>'
        "</tr></thead><tbody>\n" + "\n".join(rows) + "\n</tbody></table></div>\n"
        '      <p class="lang-es"><span class="perm-count">●</span> Perfiles con capacidades de alto impacto: revísalos en cada auditoría de accesos.</p>\n'
        '      <p class="lang-en"><span class="perm-count">●</span> Roles with high-impact capabilities: review them in every access audit.</p>'
    )

    # ---------------------------------------------------------------- familias
    blocks = []
    for key, (tes, ten), (ies, ien) in FAMILIES:
        members = [r for r in cat.STANDARD_ROLES if r["family"] == key]
        if not members:
            continue
        cards = []
        for role in members:
            perms_es = "".join(
                f"<li>{escape(labels[p][0])}</li>" for p in role["perms"]
            )
            perms_en = "".join(
                f"<li>{escape(labels[p][1])}</li>" for p in role["perms"]
            )
            warn = ""
            if role["sensitive"]:
                warn = (
                    '\n        <div class="callout warn lang-es"><span class="tag">Alto impacto</span>'
                    "<p>Este perfil otorga capacidades que conviene mantener acotadas a pocas personas y revisar periódicamente.</p></div>"
                    '\n        <div class="callout warn lang-en"><span class="tag">High impact</span>'
                    "<p>This role grants capabilities worth keeping limited to a few people and reviewing regularly.</p></div>"
                )
            n = len(role["perms"])
            cards.append(
                f'      <div class="role-card">\n'
                f'        <h3 id="{anchor(role["name"])}">{escape(role["name"])}</h3>\n'
                f'        <p class="who">{bi(escape(role["summary"]["es"]), escape(role["summary"]["en"]))}</p>\n'
                f'        <p class="perm-count">{bi(str(n) + " permisos", str(n) + " permissions")}</p>\n'
                f'        <ul class="perms lang-es">{perms_es}</ul>\n'
                f'        <ul class="perms lang-en">{perms_en}</ul>{warn}\n'
                f"      </div>"
            )
        blocks.append(
            f'      <h2 id="familia-{key}">{bi(escape(tes), escape(ten))}</h2>\n'
            f'      <p class="lang-es">{escape(ies)}</p>\n'
            f'      <p class="lang-en">{escape(ien)}</p>\n' + "\n".join(cards)
        )

    page = TEMPLATE
    for k, v in {
        "{{RAIL}}": rail(),
        "{{SUMMARY}}": summary,
        "{{FAMILIES}}": "\n\n".join(blocks),
        "{{N_ROLES}}": str(len(cat.STANDARD_ROLES)),
        "{{N_PERMS}}": str(len(cat.MANAGED_PERMS)),
        "{{DATE}}": last_commit_date(),
    }.items():
        page = page.replace(k, v)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    n_es = page.count("lang-es")
    n_en = page.count("lang-en")
    print(f"{out}: {len(cat.STANDARD_ROLES)} perfiles, {len(cat.MANAGED_PERMS)} permisos, "
          f"bilingüe {n_es}/{n_en}")
    return 0 if n_es == n_en else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
