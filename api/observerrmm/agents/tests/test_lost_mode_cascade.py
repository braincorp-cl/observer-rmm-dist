"""Feature 038 · cascada al marcar perdido/robado — resolución de precedencia.

La regla central de la feature es una sola: la cascada se resuelve con
precedencia **incidente > equipo > global**, y esa resolución vive en UN solo
lugar (`agents.utils.resolve_lost_mode_cascade`), para que el push por NATS y el
polling de config entreguen exactamente lo mismo (watch item W002).

Lo que se prueba acá es lo que puede romperse en silencio: que un override por
caso deje de pisar al del equipo, que el del equipo deje de pisar al global, o
que un campo NO fijado (NULO) deje de heredar y se apague/encienda solo.
"""

from django.utils import timezone
from model_bakery import baker

from agents.models import LostModePolicy, LostModeState
from agents.utils import resolve_lost_mode_cascade
from core.utils import get_core_settings
from observerrmm.test import ObserverTestCase


class TestResolucionDeCascada(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")

    def _marcar(self, **overrides):
        return LostModeState.objects.create(
            agent=self.agent,
            active=True,
            reason="robo",
            interval_min=5,
            marked_at=timezone.now(),
            **overrides,
        )

    def test_defaults_salen_del_global(self):
        """Sin política de equipo ni override de caso, manda CoreSettings."""
        cs = get_core_settings()
        cs.lost_mode_auto_lock_enabled = True
        cs.lost_mode_lock_delay_min = 7
        cs.lost_mode_no_hibernate_enabled = True
        cs.lost_mode_webcam_override_default = True
        cs.lost_mode_alarm_enabled = False
        cs.save()

        cascade = resolve_lost_mode_cascade(self.agent, state=self._marcar())

        self.assertTrue(cascade.auto_lock)
        self.assertEqual(cascade.lock_delay_min, 7)
        self.assertTrue(cascade.no_hibernate)
        self.assertTrue(cascade.webcam_override)
        self.assertFalse(cascade.alarm)

    def test_equipo_pisa_al_global_solo_donde_tiene_valor(self):
        """La política de equipo pisa el global campo a campo; los NULOS heredan."""
        cs = get_core_settings()
        cs.lost_mode_alarm_enabled = False
        cs.lost_mode_lock_delay_min = 5
        cs.save()

        # El equipo enciende la alarma y sube el delay; el resto queda NULO.
        LostModePolicy.objects.create(agent=self.agent, alarm=True, lock_delay_min=20)

        cascade = resolve_lost_mode_cascade(self.agent, state=self._marcar())

        self.assertTrue(cascade.alarm)  # pisado por el equipo
        self.assertEqual(cascade.lock_delay_min, 20)  # pisado por el equipo
        # no_hibernate quedó NULO en la política => hereda del global (default True)
        self.assertTrue(cascade.no_hibernate)

    def test_caso_pisa_al_equipo_y_al_global(self):
        """El override por caso es la máxima precedencia."""
        cs = get_core_settings()
        cs.lost_mode_alarm_enabled = False
        cs.save()
        LostModePolicy.objects.create(agent=self.agent, alarm=True, auto_lock=True)

        # El caso apaga la alarma que el equipo había encendido, y baja el delay.
        state = self._marcar(
            cascade_alarm=False,
            cascade_lock_delay_min=0,
        )
        cascade = resolve_lost_mode_cascade(self.agent, state=state)

        self.assertFalse(cascade.alarm)  # el caso pisó al equipo
        self.assertEqual(cascade.lock_delay_min, 0)  # bloqueo inmediato por caso
        self.assertTrue(cascade.auto_lock)  # NULO en el caso => hereda del equipo

    def test_config_endpoint_lleva_la_cascada_resuelta(self):
        """El canal garantizado (polling) entrega la misma cascada resuelta."""
        cs = get_core_settings()
        cs.lost_mode_webcam_override_default = True
        cs.save()
        self._marcar(cascade_no_hibernate=False)

        r = self.client.get(f"/api/v3/{self.agent.agent_id}/config/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["lost_mode"])
        self.assertTrue(r.data["lost_mode_webcam_override"])
        self.assertFalse(r.data["lost_mode_no_hibernate"])  # apagado por el caso

    def test_config_apagado_cuando_no_esta_perdido(self):
        """Equipo no marcado: la cascada viaja en cero, nada se dispara por herencia."""
        r = self.client.get(f"/api/v3/{self.agent.agent_id}/config/")
        self.assertFalse(r.data["lost_mode"])
        self.assertFalse(r.data["lost_mode_auto_lock"])
        self.assertEqual(r.data["lost_mode_lock_delay_min"], 0)
        self.assertFalse(r.data["lost_mode_webcam_override"])


class TestMarcarConOverridesDeCascada(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")
        self.url = f"/agents/{self.agent.agent_id}/lostmode/"

    def test_post_guarda_overrides_por_caso(self):
        from unittest.mock import patch

        with patch("agents.models.Agent.nats_cmd", return_value="ok"):
            r = self.client.post(
                self.url,
                {
                    "reason": "robo, ticket #5",
                    "cascade": {
                        "alarm": True,
                        "lock_delay_min": 0,
                        "webcam_override": False,
                    },
                },
                format="json",
            )
        self.assertEqual(r.status_code, 200)

        state = LostModeState.objects.get(agent=self.agent)
        self.assertTrue(state.cascade_alarm)
        self.assertEqual(state.cascade_lock_delay_min, 0)
        self.assertFalse(state.cascade_webcam_override)
        # Lo NO enviado queda NULO = heredar.
        self.assertIsNone(state.cascade_auto_lock)
        self.assertIsNone(state.cascade_no_hibernate)

        # La respuesta y la cascada resuelta reflejan el override.
        self.assertTrue(r.data["cascade"]["alarm"])
        self.assertEqual(r.data["cascade"]["lock_delay_min"], 0)
        self.assertFalse(r.data["cascade"]["webcam_override"])


class TestPoliticaPorEquipo(ObserverTestCase):
    """Feature 038 · T008: los defaults de la cascada POR EQUIPO (GET/PUT).

    El nivel de equipo es el intermedio: pisa al global campo a campo y el caso
    lo pisa a él. Lo que puede romperse en silencio y se prueba acá: que un PUT
    que deja todo en "heredar" NO deje una fila vacía en la BD (invariante del
    modelo), que un override sí cree/actualice la fila, y que el GET muestre la
    cascada resuelta para que la UI sepa qué se hereda.
    """

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")
        self.url = f"/agents/{self.agent.agent_id}/lostmode/policy/"

    def test_get_sin_politica_hereda_todo(self):
        """Sin fila, los overrides salen en NULO y `resolved` es el global."""
        cs = get_core_settings()
        cs.lost_mode_alarm_enabled = True
        cs.lost_mode_lock_delay_min = 9
        cs.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["policy"]["alarm"])
        self.assertIsNone(r.data["policy"]["lock_delay_min"])
        # `resolved` refleja el global cuando no hay override de equipo.
        self.assertTrue(r.data["resolved"]["alarm"])
        self.assertEqual(r.data["resolved"]["lock_delay_min"], 9)

    def test_put_crea_fila_y_pisa_al_global(self):
        cs = get_core_settings()
        cs.lost_mode_alarm_enabled = False
        cs.save()

        r = self.client.put(
            self.url,
            {"alarm": True, "lock_delay_min": 15},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

        policy = LostModePolicy.objects.get(agent=self.agent)
        self.assertTrue(policy.alarm)
        self.assertEqual(policy.lock_delay_min, 15)
        # Lo NO enviado queda NULO = heredar.
        self.assertIsNone(policy.auto_lock)
        self.assertIsNone(policy.no_hibernate)
        # `resolved` ya muestra el valor del equipo pisando al global.
        self.assertTrue(r.data["resolved"]["alarm"])
        self.assertEqual(r.data["resolved"]["lock_delay_min"], 15)

    def test_put_todo_heredado_borra_la_fila(self):
        """Un PUT que deja todo en NULO no debe dejar una fila vacía."""
        LostModePolicy.objects.create(agent=self.agent, alarm=True)

        r = self.client.put(self.url, {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(LostModePolicy.objects.filter(agent=self.agent).exists())

    def test_put_delay_fuera_de_rango_es_400(self):
        r = self.client.put(self.url, {"lock_delay_min": 999}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(LostModePolicy.objects.filter(agent=self.agent).exists())

    def test_put_con_equipo_perdido_reempuja(self):
        """Si el equipo está perdido, cambiar la política re-empuja la cascada."""
        from unittest.mock import patch

        LostModeState.objects.create(
            agent=self.agent,
            active=True,
            reason="robo",
            interval_min=5,
            marked_at=timezone.now(),
        )

        with patch("agents.models.Agent.nats_cmd", return_value="ok") as nats:
            r = self.client.put(self.url, {"no_hibernate": True}, format="json")

        self.assertEqual(r.status_code, 200)
        nats.assert_called_once()
