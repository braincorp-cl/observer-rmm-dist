import json
import re
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
# Actividad de usuarios (048/049). El agente sube por día un JSON con los
# usuarios (AgentActivityDaily.data). Estos filtros normalizan esas filas para
# las plantillas, que asi no hacen aritmetica en Jinja.
# ---------------------------------------------------------------------------


def _sin_exe(proc) -> str:
    # 049-D: nombre canónico (sin ".exe", sin ruta y con alias: msedge = edge).
    from agents.activity import canon_process

    return canon_process(proc)


def _meta_min(meta_min=None) -> int:
    """Jornada esperada por día (049-D). Sin valor explícito, la de CoreSettings."""
    with suppress(TypeError, ValueError):
        if meta_min not in (None, ""):
            return max(int(meta_min), 0)
    with suppress(Exception):
        from core.utils import get_core_settings

        return int(get_core_settings().activity_expected_min)
    return 480


def _hhmm_a_min(hhmm) -> int | None:
    with suppress(AttributeError, ValueError, TypeError):
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    return None


def _min_a_hhmm(minutos) -> str:
    if minutos is None:
        return ""
    minutos = int(round(minutos))
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _pausas(u) -> list:
    out = []
    for p in u.get("pausas") or []:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            continue
        a, b = _hhmm_a_min(p[0]), _hhmm_a_min(p[1])
        if a is None or b is None or b < a:
            continue
        out.append({"desde": p[0], "hasta": p[1], "min": b - a})
    return out


def _huecos_min(huecos) -> int:
    total = 0
    for h in huecos or []:
        if not isinstance(h, dict):
            continue
        a, b = _hhmm_a_min(h.get("desde")), _hhmm_a_min(h.get("hasta"))
        if a is not None and b is not None and b > a:
            total += b - a
    return total


def _tramos(u, huecos) -> list:
    """144 tramos de 10 min con % activo y estado (049-D).

    Estado: "medido" (hay muestras), "apagado"/"suspendido" (hueco del equipo)
    o "sin_datos" (sin muestras ni hueco: sin sesión, monitoreo apagado o agente
    anterior a la 049-D).
    """
    crudos = u.get("tramos") or {}
    motivo = {}
    for h in huecos or []:
        if not isinstance(h, dict):
            continue
        a, b = _hhmm_a_min(h.get("desde")), _hhmm_a_min(h.get("hasta"))
        if a is None or b is None:
            continue
        for i in range(a // 10, min((b + 9) // 10, 144)):
            motivo.setdefault(i, h.get("motivo") or "apagado")
    out = []
    for i in range(144):
        par = crudos.get(str(i))
        total = act = 0
        if isinstance(par, (list, tuple)) and len(par) == 2:
            act, total = _minutos(par[0]), _minutos(par[1])
        if total > 0:
            estado, pct = "medido", min(round(100 * act / total), 100)
        else:
            estado, pct = motivo.get(i, "sin_datos"), None
        out.append({"t": _min_a_hhmm(i * 10), "pct": pct, "estado": estado})
    return out


_RE_CORREO_ENTRE_PARENTESIS = re.compile(r"\s*\([^()]*@[^()]*\)")


def _nombre_sitio(nombre) -> str:
    # "Zoho Mail (persona@dominio)" -> "Zoho Mail": el sitio no necesita la cuenta.
    return _RE_CORREO_ENTRE_PARENTESIS.sub("", str(nombre)).strip()


def _top_sitios(sitios, top):
    sumados = {}
    for k, v in (sitios or {}).items():
        n = _nombre_sitio(k)
        if n:
            sumados[n] = sumados.get(n, 0) + _minutos(v)
    return [
        {"sitio": k, "min": v}
        for k, v in sorted(sumados.items(), key=lambda x: (-x[1], x[0]))[:top]
    ]


def _top_red(red, top):
    filas = []
    for app, d in (red or {}).items():
        if not isinstance(d, dict):
            continue
        filas.append(
            {
                "app": app,
                "min": _minutos(d.get("min")),
                "conex_max": _minutos(d.get("conex_max")),
                "destinos": _minutos(d.get("destinos")),
            }
        )
    filas.sort(key=lambda f: (-f["min"], f["app"]))
    return filas[:top]


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
    # Sin el ".exe": "chrome.exe" (Windows) y "chrome" (Linux/macOS) son la
    # misma aplicación y caen en la misma categoría.
    prod = {_sin_exe(p) for p in cats.get("productivo", [])}
    improd = {_sin_exe(p) for p in cats.get("improductivo", [])}
    defecto = cats.get("por_defecto", "neutral")
    if defecto not in ("productivo", "improductivo", "neutral"):
        defecto = "neutral"

    def categoria(proc):
        nombre = _sin_exe(proc)
        if nombre in prod:
            return "productivo"
        if nombre in improd:
            return "improductivo"
        return defecto

    return categoria


def _canon_usuario(u) -> dict:
    """Copia del usuario con los procesos unificados (chrome.exe = chrome)."""
    from agents.activity import canon_activity_day

    copia = json.loads(json.dumps(u))
    return canon_activity_day({"usuarios": [copia]})["usuarios"][0]


def _actividad_usuarios(rows, equipo="", usuario=""):
    """Recorre las filas de AgentActivityDaily y produce (equipo, sitio, cliente, dia, usuario).

    Si un mismo dia de un mismo usuario aparece en dos filas, gana la ultima.

    `equipo` y `usuario` son filtros OPCIONALES (vienen del prompt de dependencias
    como texto, pueden llegar vacios = sin filtrar): equipo compara el hostname
    exacto sin distinguir mayusculas; usuario es una coincidencia parcial sobre el
    nombre registrado en la actividad, tambien sin distinguir mayusculas.
    """
    equipo = str(equipo or "").strip().lower()
    usuario = str(usuario or "").strip().lower()
    filas = [r for r in (rows or []) if isinstance(r, dict)]
    filas.sort(key=lambda r: str(r.get("time", "")))
    vistos = {}
    for row in filas:
        host = row.get("agent__hostname", "") or ""
        if equipo and host.lower() != equipo:
            continue
        # Fuente: AgentActivityDaily (campo `data`), que sube el módulo nativo del
        # agente. El camino por AgentHistory de los scripts de la 048 se retiró.
        doc = row.get("data")
        if not isinstance(doc, dict):
            doc = from_json(doc)
        if not isinstance(doc, dict):
            continue
        for dia in doc.get("dias", []) or []:
            if not isinstance(dia, dict):
                continue
            for u in dia.get("usuarios", []) or []:
                if not isinstance(u, dict):
                    continue
                nombre = u.get("usuario", "") or ""
                if usuario and usuario not in nombre.lower():
                    continue
                clave = (host, dia.get("fecha", ""), nombre)
                u = _canon_usuario(u)
                vistos[clave] = {
                    "equipo": host,
                    "sitio": row.get("agent__site__name", ""),
                    "cliente": row.get("agent__site__client__name", ""),
                    "so": doc.get("so", ""),
                    "fecha": dia.get("fecha", ""),
                    "huecos": dia.get("huecos") or [],
                    "u": u,
                }
    return list(vistos.values())


def _minutos(valor):
    try:
        return max(int(valor), 0)
    except (TypeError, ValueError):
        return 0


def actividad_dia(
    rows, fecha="", categorias=None, equipo="", usuario="", top=8, meta_min=None
):
    """Resumen de un dia por usuario. Sin fecha (o con una que no esta) usa el ultimo dia con datos.

    `equipo` y `usuario` son filtros opcionales (ver _actividad_usuarios).
    `meta_min`: jornada esperada; sin valor, la de la configuración global.
    """
    categoria = _actividad_categorias(categorias)
    meta = _meta_min(meta_min)
    registros = _actividad_usuarios(rows, equipo, usuario)
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
        pausas = _pausas(u)
        filas.append(
            {
                "equipo": r["equipo"],
                "sitio": r["sitio"],
                "cliente": r["cliente"],
                "so": r["so"],
                "usuario": u.get("usuario", ""),
                "primero": u.get("primero", ""),
                "ultimo": u.get("ultimo", ""),
                # 049-D: jornada por entrada real, pausas, meta y tramos.
                "jornada_inicio": u.get("primer_activo", ""),
                "jornada_fin": u.get("ultimo_activo", ""),
                "pausas": pausas,
                "pausas_n": len(pausas),
                "pausas_min": sum(p["min"] for p in pausas),
                "meta_min": meta,
                "pct_meta": round(100 * activo / meta) if meta else 0,
                "tramos": _tramos(u, r["huecos"]),
                "con_tramos": bool(u.get("tramos")),
                "huecos": r["huecos"],
                "activo_min": activo,
                "inactivo_min": _minutos(u.get("inactivo_min")),
                "huecos_min": _minutos(u.get("huecos_min")) or _huecos_min(r["huecos"]),
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
                # 049-C (agente 2.17.6+): sitios web por título y red por app.
                "sitios_web": _top_sitios(u.get("sitios"), top),
                "red": _top_red(u.get("red"), top),
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
    totales["meta_min"] = meta
    totales["pct_meta"] = (
        round(100 * totales["activo_min"] / (meta * len(filas)))
        if meta and filas
        else 0
    )
    totales["pct_productivo"] = (
        round(100 * totales["productivo_min"] / totales["activo_min"])
        if totales["activo_min"]
        else 0
    )
    return {"fecha": fecha, "fechas": fechas, "filas": filas, "totales": totales}


def actividad_rango(
    rows,
    desde="",
    dias=7,
    categorias=None,
    equipo="",
    usuario="",
    top=10,
    meta_min=None,
):
    """Agrega por usuario los dias en [desde, desde+dias). Sin desde: los ultimos `dias` con datos.

    `equipo` y `usuario` son filtros opcionales (ver _actividad_usuarios).
    """
    categoria = _actividad_categorias(categorias)
    meta = _meta_min(meta_min)
    registros = _actividad_usuarios(rows, equipo, usuario)
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
    sitios_web = {}
    red = {}
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
                "pausas_min": 0,
                "_inicios": [],
                "_fines": [],
            },
        )
        acc["dias"] += 1
        acc["pausas_min"] += sum(p["min"] for p in _pausas(u))
        ini = _hhmm_a_min(u.get("primer_activo"))
        fin = _hhmm_a_min(u.get("ultimo_activo"))
        if ini is not None:
            acc["_inicios"].append(ini)
        if fin is not None:
            acc["_fines"].append(fin)
        acc["activo_min"] += _minutos(u.get("activo_min"))
        acc["inactivo_min"] += _minutos(u.get("inactivo_min"))
        acc["huecos_min"] += _minutos(u.get("huecos_min")) or _huecos_min(r["huecos"])
        for p, m in (u.get("procs") or {}).items():
            m = _minutos(m)
            cat = categoria(p)
            if cat == "productivo":
                acc["productivo_min"] += m
            elif cat == "improductivo":
                acc["improductivo_min"] += m
            procesos[p] = procesos.get(p, 0) + m
        for k, m in (u.get("sitios") or {}).items():
            sitios_web[k] = sitios_web.get(k, 0) + _minutos(m)
        for app, d in (u.get("red") or {}).items():
            if not isinstance(d, dict):
                continue
            acc_red = red.setdefault(app, {"min": 0, "conex_max": 0, "destinos": 0})
            acc_red["min"] += _minutos(d.get("min"))
            acc_red["conex_max"] = max(
                acc_red["conex_max"], _minutos(d.get("conex_max"))
            )
            acc_red["destinos"] = max(acc_red["destinos"], _minutos(d.get("destinos")))

    filas = list(usuarios.values())
    for f in filas:
        f["pct_productivo"] = (
            round(100 * f["productivo_min"] / f["activo_min"]) if f["activo_min"] else 0
        )
        f["activo_prom_min"] = round(f["activo_min"] / f["dias"]) if f["dias"] else 0
        # 049-D: contra la jornada esperada de los días con actividad, y hora
        # promedio de inicio y fin.
        f["meta_min"] = meta * f["dias"]
        f["pct_meta"] = round(100 * f["activo_min"] / f["meta_min"]) if meta else 0
        inicios, fines = f.pop("_inicios"), f.pop("_fines")
        f["inicio_prom"] = _min_a_hhmm(sum(inicios) / len(inicios)) if inicios else ""
        f["fin_prom"] = _min_a_hhmm(sum(fines) / len(fines)) if fines else ""
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
        "meta_min": meta,
        "procesos": top_procs,
        "sitios_web": _top_sitios(sitios_web, top),
        "red": _top_red(red, top),
    }
