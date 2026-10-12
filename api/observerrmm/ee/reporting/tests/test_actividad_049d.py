"""049-D · jornada, pausas, meta, tramos de 10 min y procesos unificados en los
reportes de actividad. Incluye el render de las dos plantillas curadas."""

import datetime
from zoneinfo import ZoneInfo

from jinja2.sandbox import SandboxedEnvironment

from ee.reporting import custom_filters
from ee.reporting.custom_filters import actividad_dia, actividad_rango


def _fila(data, host="PC-01"):
    return {
        "agent__hostname": host,
        "agent__site__name": "Casa Matriz",
        "agent__site__client__name": "ACME",
        "data": data,
    }


def _usuario(**extra):
    u = {
        "usuario": "ana",
        "primero": "08:00",
        "ultimo": "18:00",
        "activo_min": 240,
        "inactivo_min": 30,
        "procs": {"chrome.exe": 60, "chrome": 30, "msedge.exe": 10, "excel.exe": 140},
        "horas": {"08": {"a": 50, "i": 10, "p": {"chrome.exe": 20, "chrome": 30}}},
    }
    u.update(extra)
    return u


def _doc(fecha, huecos=None, **extra):
    dia = {"fecha": fecha, "usuarios": [_usuario(**extra)]}
    if huecos is not None:
        dia["huecos"] = huecos
    return {"v": 1, "so": "windows", "dias": [dia]}


DOC_049D = dict(
    primer_activo="08:12",
    ultimo_activo="17:48",
    pausas=[["10:00", "10:15"], ["13:00", "13:45"]],
    tramos={"48": [600, 600], "49": [0, 600], "50": [300, 600]},
)


class TestProcesosUnificados:
    def test_chrome_exe_y_chrome_suman_y_categorizan_igual(self):
        cats = '{"productivo": ["Excel.exe"], "improductivo": ["chrome"]}'
        f = actividad_dia([_fila(_doc("2026-10-12"))], "", cats, meta_min=480)["filas"][
            0
        ]
        procs = {p["proceso"]: (p["min"], p["cat"]) for p in f["procs"]}
        assert procs["chrome"] == (90, "improductivo")
        assert procs["edge"][0] == 10  # alias msedge
        assert procs["excel"] == (140, "productivo")
        assert "chrome.exe" not in procs
        assert f["improductivo_min"] == 90

    def test_no_altera_la_fila_original(self):
        doc = _doc("2026-10-12")
        actividad_dia([_fila(doc)], "", None, meta_min=480)
        assert "chrome.exe" in doc["dias"][0]["usuarios"][0]["procs"]


class TestJornadaPausasMeta:
    def test_dia(self):
        f = actividad_dia([_fila(_doc("2026-10-12", **DOC_049D))], meta_min=480)[
            "filas"
        ][0]
        assert (f["jornada_inicio"], f["jornada_fin"]) == ("08:12", "17:48")
        assert f["pausas_n"] == 2 and f["pausas_min"] == 60
        assert f["pct_meta"] == 50  # 240 / 480
        assert f["con_tramos"]

    def test_meta_explicita_y_totales(self):
        r = actividad_dia(
            [_fila(_doc("2026-10-12")), _fila(_doc("2026-10-12"), host="PC-02")],
            meta_min=240,
        )
        assert r["totales"]["pct_meta"] == 100
        assert r["totales"]["meta_min"] == 240

    def test_agente_anterior_sin_campos_nuevos(self):
        f = actividad_dia([_fila(_doc("2026-10-12"))], meta_min=480)["filas"][0]
        assert f["jornada_inicio"] == "" and f["pausas"] == []
        assert not f["con_tramos"]
        assert all(t["estado"] == "sin_datos" for t in f["tramos"])

    def test_rango_promedia_inicio_fin_y_meta_por_dia_con_actividad(self):
        filas = [
            _fila(_doc("2026-10-12", **DOC_049D)),
            _fila(
                _doc(
                    "2026-10-13",
                    primer_activo="08:48",
                    ultimo_activo="18:12",
                    pausas=[["12:00", "12:30"]],
                )
            ),
        ]
        r = actividad_rango(filas, "2026-10-12", 7, meta_min=480)
        f = r["filas"][0]
        assert (f["inicio_prom"], f["fin_prom"]) == ("08:30", "18:00")
        assert f["pausas_min"] == 90
        assert f["meta_min"] == 960 and f["pct_meta"] == 50
        assert r["meta_min"] == 480


class TestTramos:
    def test_estados(self):
        huecos = [
            {"desde": "00:00", "hasta": "07:55", "motivo": "apagado"},
            {"desde": "12:00", "hasta": "12:30", "motivo": "suspendido"},
        ]
        f = actividad_dia(
            [_fila(_doc("2026-10-12", huecos=huecos, **DOC_049D))], meta_min=480
        )["filas"][0]
        t = f["tramos"]
        assert len(t) == 144
        assert t[0]["estado"] == "apagado" and t[47]["estado"] == "apagado"
        assert t[48] == {"t": "08:00", "pct": 100, "estado": "medido"}
        assert t[49]["pct"] == 0 and t[50]["pct"] == 50
        assert [t[i]["estado"] for i in (72, 73, 74)] == ["suspendido"] * 3
        assert t[100]["estado"] == "sin_datos"
        # 475 min apagado + 30 suspendido, del día del equipo
        assert f["huecos_min"] == 505


def _render(template):
    from ee.reporting.management.commands.load_curated_reports import END

    env = SandboxedEnvironment(
        comment_start_string="{=",
        comment_end_string="=}",
        extensions=["jinja2.ext.do", "jinja2.ext.loopcontrols"],
    )
    env.globals.update(
        {
            "datetime": datetime,
            "ZoneInfo": ZoneInfo,
        }
    )
    for name in dir(custom_filters):
        obj = getattr(custom_filters, name)
        if callable(obj) and not name.startswith("_"):
            env.filters[name] = obj
    body = template.replace("{% block content %}", "").replace(END, "")
    return env.from_string(body)


class TestPlantillasCuradas:
    def _ctx(self):
        huecos = [{"desde": "00:00", "hasta": "07:55", "motivo": "apagado"}]
        return {
            "data_sources": {
                "corridas": [
                    _fila(_doc("2026-10-12", huecos=huecos, **DOC_049D)),
                    _fila(_doc("2026-10-13", **DOC_049D)),
                ],
                "categorias": [],
            },
            "fecha": "2026-10-12",
            "desde": "2026-10-12",
        }

    def test_diario_muestra_jornada_pausas_meta_y_tramos(self, monkeypatch):
        from ee.reporting.management.commands.load_curated_reports import (
            ACTIVIDAD_DIA,
        )

        monkeypatch.setattr(custom_filters, "_meta_min", lambda meta_min=None: 480)
        html = _render(ACTIVIDAD_DIA).render(**self._ctx())
        assert "jornada 08:12&ndash;17:48" in html
        assert "10:00&ndash;10:15 (15 min)" in html
        assert "50%" in html
        assert "#9e9e9e" in html  # tramo apagado

    def test_semanal_muestra_promedios_y_meta(self, monkeypatch):
        from ee.reporting.management.commands.load_curated_reports import (
            ACTIVIDAD_SEMANA,
        )

        monkeypatch.setattr(custom_filters, "_meta_min", lambda meta_min=None: 480)
        html = _render(ACTIVIDAD_SEMANA).render(**self._ctx())
        assert "Inicio prom." in html and "08:12" in html
        assert "8:00 por cada d&iacute;a" in html
