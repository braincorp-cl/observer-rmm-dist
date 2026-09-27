#!/usr/bin/env python3
"""Genera la referencia pública de la API REST en docs-site/api/index.html.

Las rutas y los métodos HTTP se EXTRAEN del código (`api/observerrmm/<app>/urls.py`
y sus vistas, por análisis estático con `ast`: no hace falta levantar Django). Las
descripciones bilingües viven en `api_catalog.py`. El permiso de rol que exige
cada operación se deriva de la clase de permiso de la vista, y sus etiquetas se
toman de la propia consola (`RolesForm.vue` + `i18n/{es,en}.json`), para que la
página nombre los permisos exactamente como el operador los ve.

Falla (exit 1) si una ruta del código no está descrita ni excluida, o si el
catálogo describe una ruta o un método que el código ya no tiene: la página
pública no puede desfasarse del producto en silencio.

Solo stdlib. Uso:
    python3 scripts/docs/build_api_page.py [salida]
    (por defecto: docs-site/api/index.html)
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "api" / "observerrmm"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from api_catalog import DESC, EXCLUDED, GROUPS  # noqa: E402

APPS = {  # carpeta de la app -> prefijo público (observerrmm/urls.py)
    "agents": "agents", "clients": "clients", "software": "software", "winupdate": "winupdate",
    "services": "services", "checks": "checks", "autotasks": "tasks", "automation": "automation",
    "alerts": "alerts", "scripts": "scripts", "logs": "logs", "core": "core",
    "accounts": "accounts", "erase": "erase", "ee/reporting": "reporting",
}
HTTP = ("get", "post", "put", "patch", "delete")
# Listados que usan PATCH para mandar filtros en el cuerpo: son LECTURAS.
QUERY_PATCH = {"/alerts/", "/logs/audit/", "/logs/debug/", "/checks/{id}/history/",
               "/core/customfields/", "/core/urlaction/run/"}


# --------------------------------------------------------------------- extracción
def scan_views() -> tuple[dict, dict]:
    """Índice global nombre -> {methods, perms} de clases y funciones de vistas."""
    classes, funcs = {}, {}
    for app in APPS:
        base = API / app
        files = list(base.glob("views*.py")) + list((base / "views").glob("*.py"))
        for f in files:
            tree = ast.parse(f.read_text())
            for n in tree.body:
                if isinstance(n, ast.ClassDef):
                    meths = [m.name.upper() for m in n.body if isinstance(m, ast.FunctionDef) and m.name in HTTP]
                    perms = []
                    for m in n.body:
                        if isinstance(m, ast.Assign) and any(getattr(t, "id", "") == "permission_classes" for t in m.targets):
                            perms = [ast.unparse(e) for e in getattr(m.value, "elts", [])]
                    classes.setdefault(n.name, {"methods": meths, "perms": perms})
                elif isinstance(n, ast.FunctionDef):
                    meths, perms = [], []
                    for d in n.decorator_list:
                        s = ast.unparse(d)
                        if s.startswith("api_view"):
                            meths = re.findall(r"['\"](\w+)['\"]", s) or ["GET"]
                        if s.startswith("permission_classes"):
                            perms = [p.strip() for p in s[s.find("[") + 1:s.rfind("]")].split(",") if p.strip()]
                    funcs.setdefault(n.name, {"methods": meths, "perms": perms})
    return classes, funcs


def norm(route: str) -> str:
    route = re.sub(r"<agent:agent_id>", "{agent_id}", route)
    route = re.sub(r"<int:pk>", "{id}", route)
    route = re.sub(r"<uuid:pk>", "{uuid}", route)
    route = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", route)
    return route


def scan_routes(classes: dict, funcs: dict) -> list[dict]:
    out = []
    for app, prefix in APPS.items():
        tree = ast.parse((API / app / "urls.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "path":
                route = ast.literal_eval(node.args[0])
                view = re.sub(r"\.as_view\(.*\)$", "", ast.unparse(node.args[1])).split(".")[-1]
                info = classes.get(view) or funcs.get(view) or {"methods": [], "perms": []}
                out.append({"group": prefix, "path": "/" + prefix + "/" + norm(route), "view": view, **info})
    return out


# --------------------------------------------------------------------- permisos
def role_labels() -> dict:
    vue = (ROOT / "web/app/src/components/accounts/RolesForm.vue").read_text()
    pairs = re.findall(r'v-model="localRole\.(can_[a-z_]+)"\s*:label="\$t\(\'rolesForm\.(\w+)\'\)"', vue)
    es = json.loads((ROOT / "web/app/src/i18n/es.json").read_text())["rolesForm"]
    en = json.loads((ROOT / "web/app/src/i18n/en.json").read_text())["rolesForm"]
    return {p: (es[k], en[k]) for p, k in pairs}


def class_perms() -> dict:
    out = {}
    for app in APPS:
        f = API / app / "permissions.py"
        if not f.exists():
            continue
        for n in ast.parse(f.read_text()).body:
            if isinstance(n, ast.ClassDef):
                out[n.name] = sorted(set(re.findall(r"can_[a-z_]+", ast.unparse(n))))
    return out


def perm_for(path: str, method: str, perm_classes: list, cp: dict) -> list[str]:
    read = method == "GET" or (method == "PATCH" and path in QUERY_PATCH)
    need = []
    for pc in perm_classes:
        if pc in ("IsAuthenticated", "AllowAny"):
            continue
        cand = cp.get(pc, [])
        if pc == "AgentPerms":
            need.append("can_list_agents" if read else "can_uninstall_agents" if method == "DELETE" else "can_edit_agent")
        elif pc == "URLActionPerms":
            need.append("can_run_urlactions" if read or path.endswith("/run/test/") else "can_edit_core_settings")
        elif pc == "RetrieveFilesPerms":
            need.append("can_retrieve_files")
        elif pc == "AlertTemplatePerms":
            need.append("can_list_alerttemplates" if read else "can_manage_alerttemplates")
        elif len(cand) == 1:
            need.append(cand[0])
        elif len(cand) == 2 and pc in ("UninstallSoftwarePerms", "ViewLostEvidencePerms"):
            need.extend(cand)
        elif cand:
            rd = [c for c in cand if re.match(r"can_(list|view)_", c)]
            wr = [c for c in cand if c not in rd]
            need.extend((rd if read else wr) or cand)
    return list(dict.fromkeys(need))


# --------------------------------------------------------------------- render
def last_commit_date() -> str:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "scripts/docs/api_catalog.py", "scripts/docs/build_api_page.py"],
                           cwd=ROOT, capture_output=True, text=True, check=True)
        return r.stdout.strip() or date.today().isoformat()
    except Exception:
        return date.today().isoformat()


def bi(es: str, en: str, tag: str = "span", cls: str = "") -> str:
    c = f' {cls}' if cls else ""
    return f'<{tag} class="lang-es{c}">{es}</{tag}><{tag} class="lang-en{c}">{en}</{tag}>'


def main() -> int:
    outp = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs-site/api/index.html"
    classes, funcs = scan_views()
    routes = scan_routes(classes, funcs)
    cp, labels = class_perms(), role_labels()

    errors, seen = [], set()
    for r in routes:
        seen.add(r["path"])
        if r["path"] in EXCLUDED:
            continue
        if r["path"] not in DESC:
            errors.append(f"ruta sin descripcion en api_catalog.DESC: {r['path']} ({r['view']})")
            continue
        code_m = set(r["methods"])
        for m in DESC[r["path"]]:
            if code_m and m not in code_m:
                errors.append(f"{r['path']}: el catalogo describe {m} pero la vista {r['view']} solo tiene {sorted(code_m)}")
    for p in list(DESC) + list(EXCLUDED):
        if p not in seen:
            errors.append(f"el catalogo describe una ruta que el codigo ya no tiene: {p}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    by_path = {r["path"]: r for r in routes}
    n_ops = sum(len(v) for v in DESC.values())
    sections, toc_es, toc_en = [], [], []
    for g, (tes, ten, ies, ien) in GROUPS.items():
        rows = []
        for path, meths in DESC.items():
            if by_path[path]["group"] != g:
                continue
            for m, (des, den) in meths.items():
                req = perm_for(path, m, by_path[path]["perms"], cp)
                pe = ", ".join(labels.get(p, (p, p))[0] for p in req) or "Ninguno (basta la clave)"
                pn = ", ".join(labels.get(p, (p, p))[1] for p in req) or "None (a valid key suffices)"
                rows.append(
                    f'<tr><td><span class="m m-{m.lower()}">{m}</span></td>'
                    f'<td><code>{escape(path)}</code></td>'
                    f'<td>{bi(des, den)}</td><td class="perm">{bi(escape(pe), escape(pn))}</td></tr>')
        anchor = "ref-" + g
        toc_es.append(f'<li><a href="#{anchor}">{tes}</a></li>')
        toc_en.append(f'<li><a href="#{anchor}">{ten}</a></li>')
        sections.append(
            f'<h3 id="{anchor}">{bi(tes, ten)}</h3>\n'
            f'<p class="lang-es">{ies}</p><p class="lang-en">{ien}</p>\n'
            f'<div class="tbl"><table class="api"><thead><tr>'
            f'<th>{bi("Método", "Method")}</th><th>{bi("Ruta", "Path")}</th>'
            f'<th>{bi("Acción", "Action")}</th><th>{bi("Permiso del rol", "Role permission")}</th>'
            f'</tr></thead><tbody>\n' + "\n".join(rows) + "\n</tbody></table></div>")
    excl_rows = "\n".join(
        f'<tr><td><code>{escape(p)}</code></td><td>{bi(es, en)}</td></tr>' for p, (es, en) in EXCLUDED.items())

    page = TEMPLATE
    for k, v in {
        "{{N_OPS}}": str(n_ops), "{{N_ROUTES}}": str(len(DESC)),
        "{{REFERENCE}}": "\n\n".join(sections), "{{EXCLUDED}}": excl_rows,
        "{{TOC_ES}}": "\n".join(toc_es), "{{TOC_EN}}": "\n".join(toc_en),
        "{{DATE}}": last_commit_date(),
    }.items():
        page = page.replace(k, v)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(page)
    print(f"{outp}: {len(DESC)} rutas, {n_ops} operaciones, {len(EXCLUDED)} excluidas")
    return 0


TEMPLATE = (Path(__file__).resolve().parent / "api_page.template.html").read_text()

if __name__ == "__main__":
    sys.exit(main())
