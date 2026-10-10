import json
from contextlib import suppress
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import validators


def as_tz(date_obj, tz, format="%b %d %Y, %I:%M %p"):
    return date_obj.astimezone(ZoneInfo(tz)).strftime(format)


def local_ips(wmi_detail):
    ret = []
    with suppress(Exception):
        ips = wmi_detail["network_config"]
        for i in ips:
            try:
                addr = [x["IPAddress"] for x in i if "IPAddress" in x][0]
            except:
                continue

            if addr is None:
                continue

            for ip in addr:
                if validators.ipv4(ip):
                    ret.append(ip)

    return ret


def from_json(value):
    """Parsea un string JSON dentro de una plantilla. Nunca levanta: lo ilegible da {}."""
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# Feature 048 · Observer Actividad. El recolector del endpoint imprime por stdout
# un JSON con los dias cerrados; cada corrida queda en AgentHistory (task_run).
# Estos filtros normalizan esas filas para las plantillas, que asi no hacen
# aritmetica en Jinja.
# ---------------------------------------------------------------------------


def _actividad_categorias(categorias):
    # Acepta el JSON tal cual o la fuente de datos del Key Store
    # (lista de filas {"value": "<json>"}).
    if isinstance(categorias, (list, tuple)):
        categorias = (
            categorias[0].get("value", "")
            if categorias and isinstance(categorias[0], dict)
            else ""
        )
    cats = from_json(categorias) if categorias else {}
    if not isinstance(cats, dict):
        cats = {}
    prod = {str(p).lower() for p in cats.get("productivo", [])}
    improd = {str(p).lower() for p in cats.get("improductivo", [])}
    defecto = cats.get("por_defecto", "neutral")
    if defecto not in ("productivo", "improductivo", "neutral"):
        defecto = "neutral"

    def categoria(proc):
        nombre = str(proc).lower()
        if nombre in prod:
            return "productivo"
        if nombre in improd:
            return "improductivo"
        return defecto

    return categoria


def _actividad_usuarios(rows):
    """Recorre las filas de AgentHistory y produce (equipo, sitio, cliente, dia, usuario).

    Si un mismo dia de un mismo usuario aparece en dos corridas (recolector
    re-ejecutado, o -Hoy y despues la corrida final), gana la mas reciente.
    """
    filas = [r for r in (rows or []) if isinstance(r, dict)]
    filas.sort(key=lambda r: str(r.get("time", "")))
    vistos = {}
    for row in filas:
        resultados = from_json(row.get("script_results"))
        if not isinstance(resultados, dict):
            continue
        doc = from_json(resultados.get("stdout"))
        if not isinstance(doc, dict):
            continue
        equipo = row.get("agent__hostname", "")
        for dia in doc.get("dias", []) or []:
            if not isinstance(dia, dict):
                continue
            for usuario in dia.get("usuarios", []) or []:
                if not isinstance(usuario, dict):
                    continue
                clave = (equipo, dia.get("fecha", ""), usuario.get("usuario", ""))
                vistos[clave] = {
                    "equipo": equipo,
                    "sitio": row.get("agent__site__name", ""),
                    "cliente": row.get("agent__site__client__name", ""),
                    "so": doc.get("so", ""),
                    "fecha": dia.get("fecha", ""),
                    "u": usuario,
                }
    return list(vistos.values())


def _minutos(valor):
    try:
        return max(int(valor), 0)
    except (TypeError, ValueError):
        return 0


def actividad_dia(rows, fecha="", categorias=None, top=8):
    """Resumen de un dia por usuario. Sin fecha (o con una que no esta) usa el ultimo dia con datos."""
    categoria = _actividad_categorias(categorias)
    registros = _actividad_usuarios(rows)
    fechas = sorted({r["fecha"] for r in registros if r["fecha"]})
    fecha = str(fecha or "").strip()
    if fecha not in fechas:
        fecha = fechas[-1] if fechas else ""

    filas = []
    for r in registros:
        if r["fecha"] != fecha:
            continue
        u = r["u"]
        procs = {p: _minutos(m) for p, m in (u.get("procs") or {}).items()}
        por_cat = {"productivo": 0, "improductivo": 0, "neutral": 0}
        for p, m in procs.items():
            por_cat[categoria(p)] += m
        activo = _minutos(u.get("activo_min"))
        horas = []
        for h in range(24):
            celda = (u.get("horas") or {}).get(f"{h:02d}") or {}
            hp = {p: _minutos(m) for p, m in (celda.get("p") or {}).items()}
            principal = max(hp, key=hp.get) if hp else ""
            horas.append(
                {
                    "h": f"{h:02d}",
                    "a": min(_minutos(celda.get("a")), 60),
                    "i": min(_minutos(celda.get("i")), 60),
                    "principal": principal,
                    "cat": categoria(principal) if principal else "",
                }
            )
        filas.append(
            {
                "equipo": r["equipo"],
                "sitio": r["sitio"],
                "cliente": r["cliente"],
                "so": r["so"],
                "usuario": u.get("usuario", ""),
                "primero": u.get("primero", ""),
                "ultimo": u.get("ultimo", ""),
                "activo_min": activo,
                "inactivo_min": _minutos(u.get("inactivo_min")),
                "huecos_min": _minutos(u.get("huecos_min")),
                "capturas": _minutos(u.get("capturas")),
                "productivo_min": por_cat["productivo"],
                "improductivo_min": por_cat["improductivo"],
                "neutral_min": por_cat["neutral"],
                "pct_productivo": (
                    round(100 * por_cat["productivo"] / activo) if activo else 0
                ),
                "horas": horas,
                "procs": [
                    {"proceso": p, "min": m, "cat": categoria(p)}
                    for p, m in sorted(procs.items(), key=lambda x: (-x[1], x[0]))[:top]
                ],
                "titulos": [
                    {"titulo": t[0], "min": _minutos(t[1])}
                    for t in (u.get("titulos_top") or [])[:top]
                    if isinstance(t, (list, tuple)) and len(t) == 2
                ],
                "nota": u.get("nota", ""),
            }
        )
    filas.sort(key=lambda f: (f["cliente"], f["sitio"], f["equipo"], f["usuario"]))
    totales = {
        k: sum(f[k] for f in filas)
        for k in (
            "activo_min",
            "inactivo_min",
            "productivo_min",
            "improductivo_min",
            "huecos_min",
        )
    }
    totales["usuarios"] = len(filas)
    totales["pct_productivo"] = (
        round(100 * totales["productivo_min"] / totales["activo_min"])
        if totales["activo_min"]
        else 0
    )
    return {"fecha": fecha, "fechas": fechas, "filas": filas, "totales": totales}


def actividad_rango(rows, desde="", dias=7, categorias=None, top=10):
    """Agrega por usuario los dias en [desde, desde+dias). Sin desde: los ultimos `dias` con datos."""
    categoria = _actividad_categorias(categorias)
    registros = _actividad_usuarios(rows)
    fechas = sorted({r["fecha"] for r in registros if r["fecha"]})
    dias = _minutos(dias) or 7
    desde = str(desde or "").strip()
    try:
        inicio = date.fromisoformat(desde) if desde else None
    except ValueError:
        inicio = None
    if inicio is None and fechas:
        # sin desde: la ventana termina en el ultimo dia con datos
        inicio = date.fromisoformat(fechas[-1]) - timedelta(days=dias - 1)
    if inicio is None:
        ventana = []
    else:
        fin = (inicio + timedelta(days=dias)).isoformat()
        ventana = [f for f in fechas if inicio.isoformat() <= f < fin]
    ventana_set = set(ventana)

    usuarios = {}
    procesos = {}
    for r in registros:
        if r["fecha"] not in ventana_set:
            continue
        u = r["u"]
        clave = (r["cliente"], r["sitio"], r["equipo"], u.get("usuario", ""))
        acc = usuarios.setdefault(
            clave,
            {
                "cliente": r["cliente"],
                "sitio": r["sitio"],
                "equipo": r["equipo"],
                "usuario": u.get("usuario", ""),
                "dias": 0,
                "activo_min": 0,
                "inactivo_min": 0,
                "huecos_min": 0,
                "productivo_min": 0,
                "improductivo_min": 0,
            },
        )
        acc["dias"] += 1
        acc["activo_min"] += _minutos(u.get("activo_min"))
        acc["inactivo_min"] += _minutos(u.get("inactivo_min"))
        acc["huecos_min"] += _minutos(u.get("huecos_min"))
        for p, m in (u.get("procs") or {}).items():
            m = _minutos(m)
            cat = categoria(p)
            if cat == "productivo":
                acc["productivo_min"] += m
            elif cat == "improductivo":
                acc["improductivo_min"] += m
            procesos[p] = procesos.get(p, 0) + m

    filas = list(usuarios.values())
    for f in filas:
        f["pct_productivo"] = (
            round(100 * f["productivo_min"] / f["activo_min"]) if f["activo_min"] else 0
        )
        f["activo_prom_min"] = round(f["activo_min"] / f["dias"]) if f["dias"] else 0
    filas.sort(key=lambda f: (-f["activo_min"], f["usuario"]))
    top_procs = [
        {"proceso": p, "min": m, "cat": categoria(p)}
        for p, m in sorted(procesos.items(), key=lambda x: (-x[1], x[0]))[:top]
    ]
    return {
        "desde": ventana[0] if ventana else "",
        "hasta": ventana[-1] if ventana else "",
        "fechas": ventana,
        "filas": filas,
        "procesos": top_procs,
    }
