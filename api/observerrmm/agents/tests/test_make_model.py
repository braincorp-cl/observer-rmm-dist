"""Feature 051 · `Agent.make_model` con respaldo del fabricante (RN-02).

Caso real: un notebook Lenovo cuyo WMI no entrega `Win32_ComputerSystemProduct`
(`comp_sys_prod` vacío) aparecía como «unknown make/model» aunque
`Win32_ComputerSystem` y `Win32_BaseBoard` traían el fabricante. Los equipos que
SÍ traen `comp_sys_prod` tienen que seguir viéndose exactamente igual (RF-05).
"""

import json
import os

from django.conf import settings
from django.test import SimpleTestCase

from agents.models import Agent


def wmi(comp_sys, comp_sys_prod, base_board):
    # Mismo formato que reporta el agente: cada clase WMI es una lista de
    # instancias y cada instancia una lista de {propiedad: valor}.
    def inst(props):
        return [{k: v} for k, v in props.items()]

    return {
        "comp_sys": [inst(comp_sys)],
        "comp_sys_prod": [inst(p) for p in comp_sys_prod],
        "base_board": [inst(base_board)],
    }


def windows(detail):
    return Agent(plat="windows", wmi_detail=detail)


def fixture(name):
    path = os.path.join(settings.BASE_DIR, "observerrmm/test_data", f"{name}.json")
    with open(path) as f:
        return json.load(f)


LT_TI01 = {
    "comp_sys": {
        "Manufacturer": "LENOVO",
        "Model": "83CC",
        "SystemFamily": "V15 G4 IRU 1",
    },
    "base_board": {"Manufacturer": "LENOVO", "Product": "LNVNB161216"},
}


class TestMakeModelSinCambios(SimpleTestCase):
    """RF-05: con `comp_sys_prod` presente el texto es el de siempre."""

    def test_fixtures_del_repo(self):
        self.assertEqual(windows(fixture("wmi1")).make_model, "HP ProLiant DL380 Gen9")
        self.assertEqual(
            windows(fixture("wmi3")).make_model,
            "Gigabyte Technology Co., Ltd. X570 AORUS ULTRA",
        )

    def test_dell(self):
        a = windows(
            wmi(
                {"Manufacturer": "Dell Inc.", "Model": "Latitude 5420"},
                [{"Vendor": "Dell Inc.", "Version": ""}],
                {"Manufacturer": "Dell Inc.", "Product": "0K2WXG"},
            )
        )
        self.assertEqual(a.make_model, "Dell Inc. Latitude 5420")

    def test_lenovo_usa_system_family(self):
        a = windows(
            wmi(
                {
                    "Manufacturer": "LENOVO",
                    "Model": "20W0S0CN00",
                    "SystemFamily": "ThinkPad T14 Gen 2i",
                },
                [{"Vendor": "LENOVO", "Version": "ThinkPad T14 Gen 2i"}],
                {"Manufacturer": "LENOVO", "Product": "20W0S0CN00"},
            )
        )
        self.assertEqual(a.make_model, "LENOVO ThinkPad T14 Gen 2i")

    def test_to_be_filled_cae_a_la_placa(self):
        a = windows(
            wmi(
                {
                    "Manufacturer": "To be filled by O.E.M.",
                    "Model": "To be filled by O.E.M.",
                },
                [{"Vendor": "To be filled by O.E.M."}],
                {"Manufacturer": "ASUSTeK COMPUTER INC.", "Product": "PRIME B450M-A"},
            )
        )
        self.assertEqual(a.make_model, "ASUSTeK COMPUTER INC. PRIME B450M-A")

    def test_posix_no_cambia(self):
        a = Agent(plat="linux", wmi_detail={"make_model": "Dell Inc. OptiPlex 7090"})
        self.assertEqual(a.make_model, "Dell Inc. OptiPlex 7090")


class TestMakeModelRespaldo(SimpleTestCase):
    """RF-04: sin `comp_sys_prod`, el fabricante sale de `comp_sys` o de la placa."""

    def test_lt_ti01_sin_comp_sys_prod(self):
        a = windows(wmi(LT_TI01["comp_sys"], [], LT_TI01["base_board"]))
        self.assertEqual(a.make_model, "LENOVO V15 G4 IRU 1")

    def test_comp_sys_prod_sin_vendor(self):
        a = windows(wmi(LT_TI01["comp_sys"], [{"Version": ""}], LT_TI01["base_board"]))
        self.assertEqual(a.make_model, "LENOVO V15 G4 IRU 1")

    def test_sin_manufacturer_en_comp_sys_usa_la_placa(self):
        a = windows(
            wmi(
                {"Model": "OptiPlex 7090"},
                [],
                {"Manufacturer": "Dell Inc.", "Product": "0K2WXG"},
            )
        )
        self.assertEqual(a.make_model, "Dell Inc. OptiPlex 7090")

    def test_sin_ningun_fabricante_sigue_desconocido(self):
        a = windows(wmi({"Model": "X"}, [], {"Product": "Y"}))
        self.assertEqual(a.make_model, "unknown make/model")
