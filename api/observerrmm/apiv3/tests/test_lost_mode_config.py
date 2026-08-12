"""Feature 030 · el canal de respaldo del modo perdido (T005).

`/api/v3/<agentid>/config/` era 100 % global: el `agentid` llegaba en la ruta y
se ignoraba. Con esta feature pasa a resolver un campo POR AGENTE, y ese campo
es el único canal garantizado — el push por NATS se pierde si el equipo estaba
apagado cuando lo marcaron, que es justamente el escenario para el que existe
la feature.

Lo que se prueba acá es lo que puede romperse en silencio: que el equipo
correcto reciba SU estado (y no el de otro), y que cualquier problema de lectura
degrade a "no está perdido" en vez de encender una captura de evidencia por
error.
"""

from unittest.mock import patch

from django.utils import timezone
from model_bakery import baker

from agents.models import LostModeState
from observerrmm.test import ObserverTestCase


class TestLostModeEnLaConfig(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.online_agent")
        self.url = f"/api/v3/{self.agent.agent_id}/config/"

    def test_agente_no_marcado(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["lost_mode"])
        self.assertEqual(r.data["lost_mode_interval_min"], 0)

    def test_agente_marcado(self):
        LostModeState.objects.create(
            agent=self.agent,
            active=True,
            reason="robo",
            interval_min=15,
            marked_at=timezone.now(),
        )
        r = self.client.get(self.url)
        self.assertTrue(r.data["lost_mode"])
        self.assertEqual(r.data["lost_mode_interval_min"], 15)

    def test_el_campo_es_por_agente(self):
        """El primer campo per-agente de este endpoint.

        Si se resolviera global —o con el agente equivocado— marcar un equipo
        pondría a capturar a toda la flota.
        """
        otro = baker.make_recipe("agents.online_agent")
        LostModeState.objects.create(
            agent=self.agent,
            active=True,
            reason="robo",
            interval_min=10,
            marked_at=timezone.now(),
        )

        r = self.client.get(self.url)
        self.assertTrue(r.data["lost_mode"])

        r_otro = self.client.get(f"/api/v3/{otro.agent_id}/config/")
        self.assertFalse(r_otro.data["lost_mode"])

    def test_recuperado_apaga_el_campo(self):
        LostModeState.objects.create(
            agent=self.agent,
            active=False,
            reason="robo",
            interval_min=15,
            marked_at=timezone.now(),
            recovered_at=timezone.now(),
        )
        r = self.client.get(self.url)
        self.assertFalse(r.data["lost_mode"])

    @patch("agents.models.LostModeState.objects")
    def test_falla_de_lectura_degrada_a_apagado(self, objects):
        """Fail-safe: ante cualquier problema, "no está perdido".

        Encender una recolección de evidencia sobre una persona por un error de
        lectura sería el peor fallo posible de esta feature.
        """
        objects.filter.side_effect = Exception("BD con hipo")

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["lost_mode"])
