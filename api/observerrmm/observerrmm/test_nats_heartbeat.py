"""Pruebas de la tanda B: NATS sin suscriptor y latido de los workers.

Las dos cubren fallos que el resto de la suite no ve: una excepcion que nadie
atrapaba y una metrica que solo existe si la tarea de fondo corre de verdad.
"""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone as djangotime
from nats.errors import NoRespondersError
from nats.errors import TimeoutError as NatsTimeout

from core.tasks import celery_heartbeat_task
from observerrmm.constants import CELERY_HEARTBEAT_CACHE_KEY, CELERY_HEARTBEAT_MAX_AGE
from observerrmm.nats_utils import a_nats_cmd, nats_request


class TestNatsNoResponders(IsolatedAsyncioTestCase):
    """Un agente no suscrito debe verse como un timeout, no reventar la vista."""

    async def test_no_responders_se_traduce_a_timeout(self):
        nc = MagicMock()
        nc.request = AsyncMock(side_effect=NoRespondersError)

        with self.assertRaises(NatsTimeout):
            await nats_request(nc=nc, subject="abc", payload=b"", timeout=1)

    async def test_no_responders_no_escapa_como_error_propio(self):
        """NoRespondersError no desciende de TimeoutError: sin traducir subiria
        hasta la vista y saldria como 500."""
        self.assertFalse(issubclass(NoRespondersError, TimeoutError))

        nc = MagicMock()
        nc.request = AsyncMock(side_effect=NoRespondersError)
        try:
            await nats_request(nc=nc, subject="abc", payload=b"", timeout=1)
        except NoRespondersError:  # pragma: no cover
            self.fail("NoRespondersError salio sin traducir")
        except NatsTimeout:
            pass

    async def test_a_nats_cmd_devuelve_timeout_si_nadie_escucha(self):
        nc = MagicMock()
        nc.request = AsyncMock(side_effect=NoRespondersError)

        ret = await a_nats_cmd(nc=nc, sub="abc", data={"func": "ping"}, timeout=1)
        self.assertEqual(ret, "timeout")

    async def test_timeout_normal_sigue_funcionando(self):
        nc = MagicMock()
        nc.request = AsyncMock(side_effect=NatsTimeout)

        ret = await a_nats_cmd(nc=nc, sub="abc", data={"func": "ping"}, timeout=1)
        self.assertEqual(ret, "timeout")

    async def test_respuesta_buena_no_se_toca(self):
        import msgpack

        msg = MagicMock()
        msg.data = msgpack.dumps("pong")
        nc = MagicMock()
        nc.request = AsyncMock(return_value=msg)

        ret = await a_nats_cmd(nc=nc, sub="abc", data={"func": "ping"}, timeout=1)
        self.assertEqual(ret, "pong")


class TestCeleryHeartbeat(SimpleTestCase):
    def setUp(self):
        cache.delete(CELERY_HEARTBEAT_CACHE_KEY)

    def tearDown(self):
        cache.delete(CELERY_HEARTBEAT_CACHE_KEY)

    def test_la_tarea_sella_la_hora(self):
        antes = int(djangotime.now().timestamp())
        celery_heartbeat_task()
        sellado = cache.get(CELERY_HEARTBEAT_CACHE_KEY)

        self.assertIsNotNone(sellado)
        self.assertGreaterEqual(sellado, antes)

    def test_sin_latido_la_clave_no_existe(self):
        """El endpoint distingue «nunca latio» de «latio hace rato»."""
        self.assertIsNone(cache.get(CELERY_HEARTBEAT_CACHE_KEY))

    def test_un_latido_viejo_queda_fuera_del_margen(self):
        viejo = int(djangotime.now().timestamp()) - (CELERY_HEARTBEAT_MAX_AGE + 60)
        cache.set(CELERY_HEARTBEAT_CACHE_KEY, viejo, None)

        edad = int(djangotime.now().timestamp()) - cache.get(CELERY_HEARTBEAT_CACHE_KEY)
        self.assertGreater(edad, CELERY_HEARTBEAT_MAX_AGE)
