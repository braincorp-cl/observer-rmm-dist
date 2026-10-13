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
    entrada = u.get("entrada") or {}
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
        # 049-E: teclas y eventos de mouse del tramo (presencia humana).
        e = entrada.get(str(i))
        k = mo = 0
        if isinstance(e, (list, tuple)) and len(e) == 2:
            k, mo = _minutos(e[0]), _minutos(e[1])
        out.append(
            {"t": _min_a_hhmm(i * 10), "pct": pct, "estado": estado, "k": k, "m": mo}
        )
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


CATEGORIAS = ("improductivo", "neutral", "productivo", "sin_categoria")


_EXT_PROCESO = {"exe", "app", "bin", "sh", "py", "jar", "appimage"}


def _es_dominio(nombre) -> bool:
    """ "youtube.com" o "docs.google.com/x" sí; "excel.exe" o "Zoho Mail" no."""
    n = str(nombre).strip().lower()
    if " " in n or "." not in n:
        return False
    tld = n.split("/")[0].split(":")[0].rsplit(".", 1)[-1]
    return tld.isalpha() and len(tld) >= 2 and tld not in _EXT_PROCESO


def _host(nombre) -> str:
    return str(nombre).strip().lower().split("/")[0]


def _actividad_categorias(categorias):
    """Clasificador por proceso y, desde la 049-E, por dominio web.

    Listas `productivo`, `improductivo` y `neutral`: un proceso ("chrome") o un
    dominio ("youtube.com", que cubre sus subdominios). Lo que no aparece cae en
    `por_defecto`; si no está configurado, en "sin_categoria".
    """
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
    procs, dominios = {}, {}
    for cat in ("productivo", "improductivo", "neutral"):
        for item in cats.get(cat, []) or []:
            if _es_dominio(item):
                dominios[_host(item).removeprefix("www.")] = cat
            else:
                # Sin el ".exe": "chrome.exe" (Windows) y "chrome" (Linux/macOS)
                # son la misma aplicación y caen en la misma categoría.
                procs[_sin_exe(item)] = cat
    defecto = cats.get("por_defecto", "sin_categoria")
    if defecto not in CATEGORIAS:
        defecto = "sin_categoria"

    def categoria(nombre):
        if _es_dominio(nombre):
            host = _host(nombre).removeprefix("www.")
            partes = host.split(".")
            for i in range(len(partes) - 1):
                cat = dominios.get(".".join(partes[i:]))
                if cat:
                    return cat
            return defecto
        return procs.get(_sin_exe(nombre), defecto)

    return categoria


_NAVEGADORES = {
    "chrome",
    "google chrome",
    "chromium",
    "edge",
    "microsoft edge",
    "firefox",
    "firefox-esr",
    "brave",
    "brave browser",
    "brave-browser",
    "opera",
    "vivaldi",
    "vivaldi-bin",
    "safari",
    "arc",
    "librewolf",
    "waterfox",
    "yandex",
}


def _combinado(procs, web):
    """Ranking único programas + sitios (049-E): el tiempo de navegador se
    reparte entre sus sitios/URL; lo que no se pudo atribuir sigue como navegador."""
    procs = {p: _minutos(m) for p, m in (procs or {}).items()}
    web = {k: _minutos(m) for k, m in (web or {}).items() if _minutos(m) > 0}
    navs = {p: m for p, m in procs.items() if p in _NAVEGADORES}
    if not web or not navs:
        return procs
    out = {p: m for p, m in procs.items() if p not in _NAVEGADORES}
    out.update(web)
    resto = sum(navs.values()) - sum(web.values())
    if resto > 0:
        out[max(navs, key=navs.get)] = resto
    return out


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


def _laboral_cfg(laboral):
    """(inicio_min, fin_min, días) si se pidió «solo horario laboral»; si no, None."""
    if str(laboral or "").strip().lower() not in ("1", "si", "sí", "true", "yes", "on"):
        return None
    from agents.activity import parse_work_days, parse_work_hours

    with suppress(Exception):
        from core.utils import get_core_settings

        core = get_core_settings()
        rango = parse_work_hours(core.activity_work_hours)
        dias = parse_work_days(core.activity_work_days)
        if rango and dias:
            return rango[0], rango[1], dias
    return 480, 1080, {0, 1, 2, 3, 4}


def _hosts(urls):
    out = {}
    for k, m in (urls or {}).items():
        h = _host(k)
        if h:
            out[h] = out.get(h, 0) + _minutos(m)
    return out


def _escalar(d, f):
    if f >= 1:
        return {k: _minutos(v) for k, v in (d or {}).items()}
    return {
        k: round(_minutos(v) * f)
        for k, v in (d or {}).items()
        if round(_minutos(v) * f) > 0
    }


def _metricas_usuario(u, fecha, huecos, categoria, lab=None):
    """Métricas de un usuario-día (049-E). Con `lab` (horario laboral) el día
    fuera de los días laborales se descarta (None) y el resto se recorta a la
    franja: activo/inactivo exactos por tramos de 10 min; procesos por hora; lo
    que no tiene hora (sitios, URL, inactivo por app) se prorratea."""
    activo = _minutos(u.get("activo_min"))
    inactivo = _minutos(u.get("inactivo_min"))
    procs = {p: _minutos(m) for p, m in (u.get("procs") or {}).items()}
    procs_i = {p: _minutos(m) for p, m in (u.get("procs_i") or {}).items()}
    sitios, urls, urls_i = (
        u.get("sitios") or {},
        u.get("urls") or {},
        u.get("urls_i") or {},
    )
    entrada = u.get("entrada") or {}
    pausas = _pausas(u)
    if lab:
        ini, fin, dias = lab
        with suppress(ValueError):
            if date.fromisoformat(fecha).weekday() not in dias:
                return None
        tramos = u.get("tramos") or {}
        act_s = tot_s = 0
        for i in range(ini // 10, (fin + 9) // 10):
            par = tramos.get(str(i))
            if isinstance(par, (list, tuple)) and len(par) == 2:
                act_s += _minutos(par[0])
                tot_s += _minutos(par[1])
        if tramos:
            f_act = (act_s / 60) / activo if activo else 0
            f_ina = ((tot_s - act_s) / 60) / inactivo if inactivo else 0
            activo, inactivo = round(act_s / 60), round((tot_s - act_s) / 60)
        else:
            f_act = f_ina = 1
        horas = u.get("horas") or {}
        lab_procs = {}
        for h in range(24):
            if h * 60 < fin and (h + 1) * 60 > ini:
                for p, m in ((horas.get(f"{h:02d}") or {}).get("p") or {}).items():
                    lab_procs[p] = lab_procs.get(p, 0) + _minutos(m)
        procs = lab_procs if horas else _escalar(procs, f_act)
        procs_i = _escalar(procs_i, f_ina)
        sitios, urls, urls_i = (
            _escalar(sitios, f_act),
            _escalar(urls, f_act),
            _escalar(urls_i, f_ina),
        )
        entrada = {
            k: v
            for k, v in entrada.items()
            if str(k).isdigit() and ini // 10 <= int(k) < (fin + 9) // 10
        }
        recortadas = []
        for p in pausas:
            a, b = max(_hhmm_a_min(p["desde"]), ini), min(_hhmm_a_min(p["hasta"]), fin)
            if b - a >= 10:
                recortadas.append(
                    {"desde": _min_a_hhmm(a), "hasta": _min_a_hhmm(b), "min": b - a}
                )
        pausas = recortadas
    web = (
        _hosts(urls)
        if urls
        else {_nombre_sitio(k): _minutos(v) for k, v in sitios.items()}
    )
    comb = _combinado(procs, web)
    por_cat = dict.fromkeys(CATEGORIAS, 0)
    for nombre, m in comb.items():
        por_cat[categoria(nombre)] += m
    # El navegador sin sitio atribuido y lo no medido por app quedan sin categoría
    # sólo si el total por app no cubre el activo (agentes viejos, top 25).
    falta = activo - sum(comb.values())
    if falta > 0:
        por_cat["sin_categoria"] += falta
    teclas = mouse = 0
    for par in entrada.values():
        if isinstance(par, (list, tuple)) and len(par) == 2:
            teclas += _minutos(par[0])
            mouse += _minutos(par[1])
    if not lab:
        teclas = _minutos(u.get("teclas")) or teclas
        mouse = _minutos(u.get("mouse")) or mouse
    total = activo + inactivo
    apps = sorted(
        set(procs) | set(procs_i),
        key=lambda p: (-(procs.get(p, 0) + procs_i.get(p, 0)), p),
    )
    return {
        "activo": activo,
        "inactivo": inactivo,
        "procs": procs,
        "procs_i": procs_i,
        "combinado": comb,
        "por_cat": por_cat,
        "web": web,
        "urls": urls,
        "urls_i": urls_i,
        "sitios": sitios,
        "pausas": pausas,
        "teclas": teclas,
        "mouse": mouse,
        "con_entrada": bool(u.get("entrada")) or "teclas" in u,
        "barra": _barra(por_cat, inactivo),
        "apps": [
            {
                "proceso": p,
                "min": procs.get(p, 0),
                "min_i": procs_i.get(p, 0),
                "pct": (
                    round(100 * (procs.get(p, 0) + procs_i.get(p, 0)) / total)
                    if total
                    else 0
                ),
                "cat": categoria(p),
            }
            for p in apps
        ],
    }


def _barra(por_cat, inactivo):
    """Segmentos de la barra apilada (minutos y % del tiempo medido)."""
    seg = [(c, por_cat.get(c, 0)) for c in CATEGORIAS] + [("inactivo", inactivo)]
    total = sum(m for _, m in seg)
    return [
        {"cat": c, "min": m, "pct": round(100 * m / total, 1) if total else 0}
        for c, m in seg
    ]


def _top_urls(urls, urls_i, top):
    claves = set(urls or {}) | set(urls_i or {})
    filas = [
        {
            "url": k,
            "min": _minutos((urls or {}).get(k)),
            "min_i": _minutos((urls_i or {}).get(k)),
        }
        for k in claves
    ]
    filas.sort(key=lambda f: (-(f["min"] + f["min_i"]), f["url"]))
    return filas[:top]


def actividad_dia(
    rows,
    fecha="",
    categorias=None,
    equipo="",
    usuario="",
    top=8,
    meta_min=None,
    laboral="",
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

    lab = _laboral_cfg(laboral)
    filas = []
    for r in registros:
        if r["fecha"] != fecha:
            continue
        u = r["u"]
        m49 = _metricas_usuario(u, r["fecha"], r["huecos"], categoria, lab)
        if m49 is None:
            continue
        procs = m49["procs"]
        por_cat = m49["por_cat"]
        activo = m49["activo"]
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
        pausas = m49["pausas"]
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
                "inactivo_min": m49["inactivo"],
                "huecos_min": _minutos(u.get("huecos_min")) or _huecos_min(r["huecos"]),
                "capturas": _minutos(u.get("capturas")),
                "productivo_min": por_cat["productivo"],
                "improductivo_min": por_cat["improductivo"],
                "neutral_min": por_cat["neutral"],
                "sin_categoria_min": por_cat["sin_categoria"],
                "pct_productivo": (
                    round(100 * por_cat["productivo"] / activo) if activo else 0
                ),
                # 049-E
                "barra": m49["barra"],
                "apps": m49["apps"][:top],
                "ranking": [
                    {"nombre": k, "min": v, "cat": categoria(k)}
                    for k, v in sorted(
                        m49["combinado"].items(), key=lambda x: (-x[1], x[0])
                    )[:top]
                ],
                "urls": _top_urls(m49["urls"], m49["urls_i"], top),
                "teclas": m49["teclas"],
                "mouse": m49["mouse"],
                "con_entrada": m49["con_entrada"],
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
                "sitios_web": _top_sitios(m49["sitios"], top),
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
            "neutral_min",
            "sin_categoria_min",
            "huecos_min",
            "teclas",
            "mouse",
        )
    }
    totales["barra"] = _barra(
        {c: totales[f"{c}_min"] for c in CATEGORIAS}, totales["inactivo_min"]
    )
    totales["laboral"] = bool(lab)
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
    hasta="",
    laboral="",
):
    """Agrega por usuario los dias en [desde, desde+dias). Sin desde: los ultimos `dias` con datos.

    `equipo` y `usuario` son filtros opcionales (ver _actividad_usuarios).
    049-E: `hasta` (inclusive) define un período libre (mes, trimestre...) y
    `laboral` recorta al horario laboral de la configuración global.
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
    with suppress(ValueError, TypeError):
        fin_libre = date.fromisoformat(str(hasta or "").strip())
        if inicio is None:
            inicio = fin_libre - timedelta(days=dias - 1)
        if fin_libre >= inicio:
            dias = min((fin_libre - inicio).days + 1, 366)
    if inicio is None and fechas:
        # sin desde: la ventana termina en el ultimo dia con datos
        inicio = date.fromisoformat(fechas[-1]) - timedelta(days=dias - 1)
    if inicio is None:
        ventana = []
    else:
        fin = (inicio + timedelta(days=dias)).isoformat()
        ventana = [f for f in fechas if inicio.isoformat() <= f < fin]
    ventana_set = set(ventana)
    lab = _laboral_cfg(laboral)

    usuarios = {}
    procesos = {}
    procesos_i = {}
    ranking = {}
    urls_g, urls_gi = {}, {}
    sitios_web = {}
    red = {}
    for r in registros:
        if r["fecha"] not in ventana_set:
            continue
        u = r["u"]
        m49 = _metricas_usuario(u, r["fecha"], r["huecos"], categoria, lab)
        if m49 is None:
            continue
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
                "neutral_min": 0,
                "sin_categoria_min": 0,
                "pausas_min": 0,
                "teclas": 0,
                "mouse": 0,
                "_inicios": [],
                "_fines": [],
            },
        )
        acc["dias"] += 1
        acc["pausas_min"] += sum(p["min"] for p in m49["pausas"])
        acc["teclas"] += m49["teclas"]
        acc["mouse"] += m49["mouse"]
        for c in CATEGORIAS:
            if c not in ("productivo", "improductivo"):
                acc[f"{c}_min"] += m49["por_cat"][c]
        ini = _hhmm_a_min(u.get("primer_activo"))
        fin = _hhmm_a_min(u.get("ultimo_activo"))
        if ini is not None:
            acc["_inicios"].append(ini)
        if fin is not None:
            acc["_fines"].append(fin)
        acc["activo_min"] += m49["activo"]
        acc["inactivo_min"] += m49["inactivo"]
        acc["huecos_min"] += _minutos(u.get("huecos_min")) or _huecos_min(r["huecos"])
        acc["productivo_min"] += m49["por_cat"]["productivo"]
        acc["improductivo_min"] += m49["por_cat"]["improductivo"]
        for p, m in m49["procs"].items():
            procesos[p] = procesos.get(p, 0) + m
        for p, m in m49["procs_i"].items():
            procesos_i[p] = procesos_i.get(p, 0) + m
        for k, m in m49["combinado"].items():
            ranking[k] = ranking.get(k, 0) + m
        for k, m in m49["urls"].items():
            urls_g[k] = urls_g.get(k, 0) + _minutos(m)
        for k, m in m49["urls_i"].items():
            urls_gi[k] = urls_gi.get(k, 0) + _minutos(m)
        for k, m in m49["sitios"].items():
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
        f["barra"] = _barra({c: f[f"{c}_min"] for c in CATEGORIAS}, f["inactivo_min"])
    filas.sort(key=lambda f: (-f["activo_min"], f["usuario"]))
    top_procs = [
        {"proceso": p, "min": m, "cat": categoria(p)}
        for p, m in sorted(procesos.items(), key=lambda x: (-x[1], x[0]))[:top]
    ]
    totales = {
        k: sum(f[k] for f in filas)
        for k in (
            "activo_min",
            "inactivo_min",
            "huecos_min",
            "teclas",
            "mouse",
        )
        + tuple(f"{c}_min" for c in CATEGORIAS)
    }
    totales["barra"] = _barra(
        {c: totales[f"{c}_min"] for c in CATEGORIAS}, totales["inactivo_min"]
    )
    totales["laboral"] = bool(lab)
    total_med = totales["activo_min"] + totales["inactivo_min"]
    apps = sorted(
        set(procesos) | set(procesos_i),
        key=lambda p: (-(procesos.get(p, 0) + procesos_i.get(p, 0)), p),
    )
    return {
        "totales": totales,
        # 049-E: aplicaciones con activo e inactivo, ranking combinado y URL.
        "apps": [
            {
                "proceso": p,
                "min": procesos.get(p, 0),
                "min_i": procesos_i.get(p, 0),
                "pct": (
                    round(100 * (procesos.get(p, 0) + procesos_i.get(p, 0)) / total_med)
                    if total_med
                    else 0
                ),
                "cat": categoria(p),
            }
            for p in apps[:top]
        ],
        "ranking": [
            {"nombre": k, "min": v, "cat": categoria(k)}
            for k, v in sorted(ranking.items(), key=lambda x: (-x[1], x[0]))[:top]
        ],
        "urls": _top_urls(urls_g, urls_gi, top),
        "desde": ventana[0] if ventana else "",
        "hasta": ventana[-1] if ventana else "",
        "fechas": ventana,
        "filas": filas,
        "meta_min": meta,
        "procesos": top_procs,
        "sitios_web": _top_sitios(sitios_web, top),
        "red": _top_red(red, top),
    }
