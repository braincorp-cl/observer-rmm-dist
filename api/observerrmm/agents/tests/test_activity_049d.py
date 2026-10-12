"""049-D · patrones "siempre activo", jornada esperada y procesos unificados.

Lo que no puede romperse: los patrones viajan al agente (push y config) sólo con
el monitoreo encendido; un patrón que RE2 no compila se rechaza en la consola en
vez de perderse en silencio en el agente; la ingesta unifica "chrome.exe" y
"chrome".
"""

from unittest.mock import patch

from model_bakery import baker

from agents.activity import (
    always_active_patterns,
    canon_process,
    resolve_activity,
    validate_always_active,
)
from agents.models import AgentActivityDaily
from apiv3.utils import get_agent_config
from core.models import ACTIVITY_ALWAYS_ACTIVE_DEFAULT
from core.utils import get_core_settings
from observerrmm.test import ObserverTestCase


class TestHelpers049D(ObserverTestCase):
    def test_canon_process(self):
        self.assertEqual(
            canon_process("C:\\Program Files\\Google\\chrome.exe"), "chrome"
        )
        self.assertEqual(canon_process("MSEdge.EXE"), "edge")
        self.assertEqual(canon_process("firefox-esr"), "firefox")
        self.assertEqual(canon_process("ms-teams"), "teams")
        self.assertEqual(canon_process("code"), "code")

    def test_patrones_limpios_y_validacion(self):
        self.assertEqual(
            always_active_patterns(" teams \n\nzoom\nteams"), ["teams", "zoom"]
        )
        self.assertEqual(validate_always_active(ACTIVITY_ALWAYS_ACTIVE_DEFAULT), [])
        self.assertTrue(validate_always_active("(?<=x)y"))  # lookbehind: RE2 no
        self.assertTrue(validate_always_active("(abc"))
        self.assertTrue(validate_always_active("\n".join(str(i) for i in range(31))))


class TestPatronesViajan(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")

    def test_default_y_solo_con_monitoreo_encendido(self):
        res = resolve_activity(self.agent)
        self.assertFalse(res.active)
        self.assertEqual(res.nats_payload()["siempre_activo"], "")
        self.assertEqual(
            get_agent_config(self.agent.agent_id).actividad_siempre_activo, []
        )

        cs = get_core_settings()
        cs.activity_monitoring_enabled = True
        cs.save()
        self.agent.activity_monitoring = True
        self.agent.save()
        res = resolve_activity(self.agent)
        self.assertEqual(
            res.nats_payload()["siempre_activo"], "teams\nzoom\nwebex\n\\bmeet\\b"
        )
        self.assertEqual(
            get_agent_config(self.agent.agent_id).actividad_siempre_activo,
            ["teams", "zoom", "webex", "\\bmeet\\b"],
        )

    @patch("agents.tasks.push_activity_monitoring_task.delay")
    def test_consola_valida_y_cambiar_patrones_empuja(self, push):
        self.agent.activity_monitoring = True
        self.agent.save()
        data = self.client.get("/core/settings/").data
        data.pop("all_timezones", None)

        data["activity_always_active_patterns"] = "teams\n(?!x)y"
        r = self.client.put("/core/settings/", data, format="json")
        self.assertEqual(r.status_code, 400)
        push.assert_not_called()

        data["activity_always_active_patterns"] = " webex \n\nanydesk"
        data["activity_expected_min"] = 504
        r = self.client.put("/core/settings/", data, format="json")
        self.assertEqual(r.status_code, 200)
        cs = get_core_settings()
        self.assertEqual(cs.activity_always_active_patterns, "webex\nanydesk")
        self.assertEqual(cs.activity_expected_min, 504)
        push.assert_called_once_with(agent_pks=[self.agent.pk])

    def test_jornada_fuera_de_rango(self):
        data = self.client.get("/core/settings/").data
        data.pop("all_timezones", None)
        data["activity_expected_min"] = 0
        r = self.client.put("/core/settings/", data, format="json")
        self.assertEqual(r.status_code, 400)


class TestIngestaUnifica(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")

    def test_procesos_unificados_al_guardar(self):
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        user = baker.make("accounts.User", agent=self.agent)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
        dia = {
            "fecha": "2026-10-12",
            "usuarios": [
                {
                    "usuario": "ana",
                    "procs": {"chrome.exe": 10, "Chrome": 5, "msedge.exe": 3},
                    "horas": {
                        "09": {"a": 15, "i": 0, "p": {"chrome.exe": 10, "chrome": 5}}
                    },
                    "red": {
                        "chrome.exe": {"min": 4, "conex_max": 9, "destinos": 3},
                        "chrome": {"min": 2, "conex_max": 12, "destinos": 1},
                    },
                    "tramos": {"54": [600, 600]},
                    "pausas": [["10:00", "10:20"]],
                }
            ],
            "huecos": [{"desde": "00:00", "hasta": "08:00", "motivo": "apagado"}],
        }
        r = c.post(
            f"/api/v3/{self.agent.agent_id}/activity/",
            {"v": 1, "so": "windows", "equipo": "PC", "dias": [dia]},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        u = AgentActivityDaily.objects.get(agent=self.agent).data["dias"][0][
            "usuarios"
        ][0]
        self.assertEqual(u["procs"], {"chrome": 15, "edge": 3})
        self.assertEqual(u["horas"]["09"]["p"], {"chrome": 15})
        self.assertEqual(u["red"]["chrome"], {"min": 6, "conex_max": 12, "destinos": 3})
        self.assertEqual(u["tramos"], {"54": [600, 600]})
        dia_guardado = AgentActivityDaily.objects.get(agent=self.agent).data["dias"][0]
        self.assertEqual(dia_guardado["huecos"][0]["motivo"], "apagado")
