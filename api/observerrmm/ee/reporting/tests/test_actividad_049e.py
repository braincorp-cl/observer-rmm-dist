"""049-E · brechas KeepActive: categorías por dominio y «sin categoría», ranking
combinado programas + sitios, activo/inactivo por aplicación, URL, teclas/mouse,
período libre, horario laboral y render de las tres plantillas curadas."""

from unittest.mock import patch

from ee.reporting.custom_filters import (
    _actividad_categorias,
    _combinado,
    actividad_dia,
    actividad_rango,
)
from ee.reporting.tests.test_actividad_049d import _render


def _fila(fecha, host="PC-01", **extra):
    u = {
        "usuario": "ana",
        "primero": "07:00",
        "ultimo": "20:00",
        "activo_min": 120,
        "inactivo_min": 60,
        "procs": {"chrome": 80, "excel": 40},
        "procs_i": {"chrome": 50, "excel": 10},
        "urls": {"www.youtube.com/watch": 50, "docs.google.com/document/d/x/edit": 20},
        "urls_i": {"www.youtube.com/watch": 30},
        "teclas": 900,
        "mouse": 400,
        "entrada": {"48": [500, 100], "120": [400, 300]},
        "horas": {
            "07": {"a": 20, "i": 0, "p": {"chrome": 20}},
            "08": {"a": 60, "i": 30, "p": {"chrome": 40, "excel": 20}},
            "20": {"a": 40, "i": 30, "p": {"chrome": 20, "excel": 20}},
        },
        # 07:00 fuera del horario 08-18: 20 min activos; 08:00-08:59: 60/30; 20:00 fuera.
        "tramos": {
            "42": [1200, 1200],
            "48": [3600, 5400],
            "120": [2400, 4200],
        },
    }
    u.update(extra)
    return {
        "agent__hostname": host,
        "agent__site__name": "Casa Matriz",
        "agent__site__client__name": "ACME",
        "data": {"v": 1, "so": "windows", "dias": [{"fecha": fecha, "usuarios": [u]}]},
    }


CATS = '{"productivo": ["excel", "google.com"], "improductivo": ["youtube.com"]}'


class TestCategorias:
    def test_dominio_cubre_subdominios_y_sin_categoria_por_omision(self):
        cat = _actividad_categorias(CATS)
        assert cat("www.youtube.com") == "improductivo"
        assert cat("docs.google.com") == "productivo"
        assert cat("excel.exe") == "productivo"  # proceso, no dominio
        assert cat("notepad") == "sin_categoria"
        assert cat("ejemplo.cl") == "sin_categoria"

    def test_por_defecto_explicito_se_respeta(self):
        cat = _actividad_categorias('{"por_defecto": "neutral"}')
        assert cat("notepad") == "neutral"


def test_combinado_reparte_el_navegador_entre_sitios():
    comb = _combinado({"chrome": 80, "excel": 40}, {"youtube.com": 50, "a.cl": 20})
    assert comb == {"excel": 40, "youtube.com": 50, "a.cl": 20, "chrome": 10}
    # Sin datos web, queda igual.
    assert _combinado({"chrome": 80}, {}) == {"chrome": 80}


class TestDia:
    def test_barra_apps_urls_y_entrada(self):
        f = actividad_dia([_fila("2026-10-13")], "2026-10-13", CATS)["filas"][0]
        assert f["improductivo_min"] == 50  # youtube
        assert f["productivo_min"] == 60  # excel 40 + docs.google 20
        assert f["sin_categoria_min"] == 10  # resto de chrome sin sitio
        barra = {s["cat"]: s["min"] for s in f["barra"]}
        assert barra["inactivo"] == 60 and sum(barra.values()) == 180
        apps = {a["proceso"]: (a["min"], a["min_i"]) for a in f["apps"]}
        assert apps["chrome"] == (80, 50)
        assert f["urls"][0] == {"url": "www.youtube.com/watch", "min": 50, "min_i": 30}
        assert (f["teclas"], f["mouse"]) == (900, 400)
        assert f["tramos"][48]["k"] == 500 and f["tramos"][120]["m"] == 300
        assert f["ranking"][0]["nombre"] == "www.youtube.com"

    @patch(
        "ee.reporting.custom_filters._laboral_cfg",
        return_value=(480, 1080, {0, 1, 2, 3, 4}),
    )
    def test_horario_laboral_recorta_por_tramos_y_horas(self, _cfg):
        f = actividad_dia([_fila("2026-10-13")], "2026-10-13", CATS, laboral="si")[
            "filas"
        ][0]
        assert (f["activo_min"], f["inactivo_min"]) == (60, 30)
        apps = {a["proceso"]: a["min"] for a in f["apps"]}
        assert apps == {"chrome": 40, "excel": 20}
        # Fuera de la franja no hay teclas (tramo 120 = 20:00).
        assert (f["teclas"], f["mouse"]) == (500, 100)

    @patch(
        "ee.reporting.custom_filters._laboral_cfg",
        return_value=(480, 1080, {0, 1, 2, 3, 4}),
    )
    def test_horario_laboral_descarta_fin_de_semana(self, _cfg):
        res = actividad_dia([_fila("2026-10-11")], "2026-10-11", CATS, laboral="si")
        assert res["filas"] == []  # domingo


class TestRango:
    def test_periodo_libre_con_hasta(self):
        filas = [_fila(f"2026-10-{d:02d}") for d in (1, 15, 31)] + [_fila("2026-11-01")]
        r = actividad_rango(filas, "2026-10-01", 7, CATS, hasta="2026-10-31")
        assert r["desde"] == "2026-10-01" and r["hasta"] == "2026-10-31"
        assert r["filas"][0]["dias"] == 3
        assert r["totales"]["teclas"] == 2700
        assert {a["proceso"] for a in r["apps"]} == {"chrome", "excel"}
        assert r["urls"][0]["url"] == "www.youtube.com/watch"

    def test_sin_hasta_sigue_siendo_semanal(self):
        filas = [_fila(f"2026-10-{d:02d}") for d in range(1, 15)]
        r = actividad_rango(filas, "2026-10-01", 7, CATS)
        assert r["filas"][0]["dias"] == 7


class TestPlantillas:
    def _ctx(self, **extra):
        ctx = {
            "data_sources": {"corridas": [_fila("2026-10-13")], "categorias": CATS},
            "fecha": "2026-10-13",
            "desde": "2026-10-01",
            "hasta": "2026-10-31",
        }
        ctx.update(extra)
        return ctx

    def test_las_tres_plantillas_muestran_lo_nuevo(self):
        from ee.reporting.management.commands.load_curated_reports import (
            ACTIVIDAD_DIA,
            ACTIVIDAD_PERIODO,
            ACTIVIDAD_SEMANA,
        )

        for plantilla, desde in (
            (ACTIVIDAD_DIA, ""),
            (ACTIVIDAD_SEMANA, "2026-10-10"),
            (ACTIVIDAD_PERIODO, "2026-10-01"),
        ):
            html = _render(plantilla).render(**self._ctx(desde=desde))
            assert "Toda la empresa" in html
            assert "www.youtube.com/watch" in html
            assert "Sin categor" in html
            assert "900 / 400" in html
        html = _render(ACTIVIDAD_PERIODO).render(**self._ctx())
        assert "2026-10-13 a 2026-10-13" in html
