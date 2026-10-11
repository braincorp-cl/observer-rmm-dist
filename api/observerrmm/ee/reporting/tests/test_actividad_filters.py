import json

from ee.reporting.custom_filters import actividad_dia, actividad_rango, from_json


def _fila(stdout, host="PC-01", sitio="Casa Matriz", cliente="ACME"):
    if not isinstance(stdout, str):
        stdout = json.dumps(stdout)
    return {
        "agent__hostname": host,
        "agent__site__name": sitio,
        "agent__site__client__name": cliente,
        "script_results": {"stdout": stdout, "stderr": "", "retcode": 0},
    }


def _doc(fecha, usuario="DOM\\jperez", activo=120, procs=None, horas=None):
    return {
        "v": 1,
        "so": "windows",
        "dias": [
            {
                "fecha": fecha,
                "usuarios": [
                    {
                        "usuario": usuario,
                        "primero": "08:00",
                        "ultimo": "18:00",
                        "activo_min": activo,
                        "inactivo_min": 30,
                        "huecos_min": 5,
                        "capturas": 12,
                        "procs": procs or {"excel.exe": 90, "chrome.exe": 30},
                        "horas": horas
                        or {"08": {"a": 50, "i": 10, "p": {"excel.exe": 50}}},
                        "titulos_top": [["Informe.xlsx", 60]],
                    }
                ],
            }
        ],
    }


CATS = json.dumps({"productivo": ["EXCEL.EXE"], "improductivo": ["chrome.exe"]})


class TestFromJson:
    def test_parsea_string(self):
        assert from_json('{"a": 1}') == {"a": 1}

    def test_basura_devuelve_dict_vacio(self):
        assert from_json("no es json") == {}
        assert from_json(None) == {}

    def test_dict_pasa_tal_cual(self):
        assert from_json({"a": 1}) == {"a": 1}


class TestActividadDia:
    def test_categoriza_sin_distinguir_mayusculas(self):
        res = actividad_dia([_fila(_doc("2026-10-10"))], "2026-10-10", CATS)
        f = res["filas"][0]
        assert f["productivo_min"] == 90
        assert f["improductivo_min"] == 30
        assert f["pct_productivo"] == 75
        assert f["procs"][0] == {"proceso": "excel.exe", "min": 90, "cat": "productivo"}

    def test_mapa_de_24_horas(self):
        f = actividad_dia([_fila(_doc("2026-10-10"))], "2026-10-10")["filas"][0]
        assert len(f["horas"]) == 24
        assert f["horas"][8]["a"] == 50
        assert f["horas"][8]["principal"] == "excel.exe"
        assert f["horas"][9]["a"] == 0

    def test_sin_fecha_usa_el_ultimo_dia(self):
        rows = [_fila(_doc("2026-10-09")), _fila(_doc("2026-10-10", activo=200))]
        res = actividad_dia(rows)
        assert res["fecha"] == "2026-10-10"
        assert res["filas"][0]["activo_min"] == 200

    def test_dia_repetido_gana_la_ultima_corrida(self):
        rows = [
            _fila(_doc("2026-10-10", activo=10)),
            _fila(_doc("2026-10-10", activo=99)),
        ]
        res = actividad_dia(rows, "2026-10-10")
        assert len(res["filas"]) == 1
        assert res["filas"][0]["activo_min"] == 99

    def test_stdout_ilegible_no_rompe(self):
        rows = [_fila("ERROR: algo"), {"script_results": None}, "basura"]
        res = actividad_dia(rows, "2026-10-10")
        assert res["filas"] == []
        assert res["totales"]["usuarios"] == 0

    def test_categoria_por_defecto(self):
        cats = json.dumps({"por_defecto": "improductivo"})
        f = actividad_dia([_fila(_doc("2026-10-10"))], "", cats)["filas"][0]
        assert f["improductivo_min"] == 120


class TestActividadRango:
    def test_agrega_dias_por_usuario(self):
        rows = [
            _fila(_doc("2026-10-06", activo=100)),
            _fila(_doc("2026-10-07", activo=200)),
            _fila(_doc("2026-10-20", activo=999)),
        ]
        res = actividad_rango(rows, "2026-10-05", 7, CATS)
        assert res["fechas"] == ["2026-10-06", "2026-10-07"]
        f = res["filas"][0]
        assert f["dias"] == 2
        assert f["activo_min"] == 300
        assert f["activo_prom_min"] == 150
        assert res["procesos"][0]["proceso"] == "excel.exe"
        assert res["procesos"][0]["min"] == 180


class TestOrdenYKeyStore:
    def test_gana_la_corrida_mas_reciente_aunque_lleguen_desordenadas(self):
        nueva = _fila(_doc("2026-10-10", activo=99))
        nueva["time"] = "2026-10-11 02:55:00+00:00"
        vieja = _fila(_doc("2026-10-10", activo=10))
        vieja["time"] = "2026-10-10 18:00:00+00:00"
        res = actividad_dia([nueva, vieja], "2026-10-10")
        assert res["filas"][0]["activo_min"] == 99

    def test_categorias_desde_la_fuente_del_key_store(self):
        kv = [{"value": CATS}]
        f = actividad_dia([_fila(_doc("2026-10-10"))], "", kv)["filas"][0]
        assert f["productivo_min"] == 90


class TestFiltrosEquipoUsuario:
    def _rows(self):
        a = _fila(_doc("2026-10-10", usuario="DOM\\ana", activo=120), host="PC-A")
        b = _fila(_doc("2026-10-10", usuario="DOM\\bruno", activo=60), host="PC-B")
        return [a, b]

    def test_sin_filtro_trae_todos(self):
        res = actividad_dia(self._rows(), "2026-10-10")
        assert {f["usuario"] for f in res["filas"]} == {"DOM\\ana", "DOM\\bruno"}

    def test_filtra_por_equipo_exacto_sin_mayusculas(self):
        res = actividad_dia(self._rows(), "2026-10-10", equipo="pc-a")
        assert [f["equipo"] for f in res["filas"]] == ["PC-A"]
        assert res["filas"][0]["usuario"] == "DOM\\ana"

    def test_filtra_por_usuario_coincidencia_parcial(self):
        res = actividad_dia(self._rows(), "2026-10-10", usuario="bruno")
        assert [f["usuario"] for f in res["filas"]] == ["DOM\\bruno"]

    def test_equipo_que_no_existe_da_vacio(self):
        res = actividad_dia(self._rows(), "2026-10-10", equipo="PC-Z")
        assert res["filas"] == []

    def test_rango_filtra_equipo_y_usuario(self):
        rows = [
            _fila(_doc("2026-10-07", usuario="DOM\\ana", activo=100), host="PC-A"),
            _fila(_doc("2026-10-07", usuario="DOM\\bruno", activo=50), host="PC-B"),
        ]
        res = actividad_rango(rows, "2026-10-05", 7, equipo="PC-A", usuario="ana")
        assert len(res["filas"]) == 1
        assert res["filas"][0]["usuario"] == "DOM\\ana"


# --- 049-C: sitios web, red por app y categoría sin ".exe" -------------------


def _doc_049c(fecha):
    d = _doc(fecha, procs={"chrome.exe": 60})
    u = d["dias"][0]["usuarios"][0]
    u["sitios"] = {"Gmail": 40, "YouTube": 20}
    u["red"] = {"chrome.exe": {"min": 55, "conex_max": 9, "destinos": 14}}
    return d


def test_dia_incluye_sitios_y_red():
    r = actividad_dia([_fila(_doc_049c("2026-10-11"))], fecha="2026-10-11")
    f = r["filas"][0]
    assert f["sitios_web"][0] == {"sitio": "Gmail", "min": 40}
    assert f["red"][0] == {
        "app": "chrome.exe",
        "min": 55,
        "conex_max": 9,
        "destinos": 14,
    }


def test_rango_agrega_sitios_y_red():
    filas = [
        _fila(_doc_049c("2026-10-10")),
        _fila(_doc_049c("2026-10-11")),
    ]
    r = actividad_rango(filas, desde="2026-10-10", dias=7)
    assert r["sitios_web"][0] == {"sitio": "Gmail", "min": 80}
    assert r["red"][0]["min"] == 110
    assert r["red"][0]["conex_max"] == 9


def test_doc_sin_049c_no_rompe():
    r = actividad_dia([_fila(_doc("2026-10-11"))], fecha="2026-10-11")
    assert r["filas"][0]["sitios_web"] == []
    assert r["filas"][0]["red"] == []


def test_categoria_ignora_exe():
    cats = json.dumps({"improductivo": ["chrome"], "productivo": ["excel.exe"]})
    r = actividad_dia(
        [_fila(_doc("2026-10-11", procs={"chrome.exe": 30, "excel": 90}))],
        fecha="2026-10-11",
        categorias=cats,
    )
    procs = {p["proceso"]: p["cat"] for p in r["filas"][0]["procs"]}
    assert procs == {"chrome.exe": "improductivo", "excel": "productivo"}


def test_sitio_sin_correo_y_sumado():
    d = _doc("2026-10-11")
    d["dias"][0]["usuarios"][0]["sitios"] = {
        "Zoho Mail (ana@acme.cl)": 10,
        "Zoho Mail": 5,
    }
    r = actividad_dia([_fila(d)], fecha="2026-10-11")
    assert r["filas"][0]["sitios_web"] == [{"sitio": "Zoho Mail", "min": 15}]
