"""El reporte de wipe POR HTTP, que es el único camino que el agente usa.

🔑 Por qué existe este archivo aparte de `erase/tests/test_wipe_states.py`: aquel
llama `apply_wipe_report()` con un **dict de Python**, y por eso estuvo verde
mientras el camino real estaba roto. El envelope del agente es
`map[string]string` (`agent/wipe.go`), así que el mapa por-ruta llega
**serializado**: sin parsearlo, `order.result` queda como `str` dentro del
JSONField y la emisión del certificado —que lo recorre con `.items()`— revienta
DESPUÉS de que el borrado irreversible ya ocurrió.

Medido en staging el 2026-11-01 (T024): el borrado dejó los tres archivos
ausentes y `verified=true`, el reporte respondió **500**, el reintento recibió el
**409** del estado terminal, y la orden quedó sin certificado y sin un solo
rastro del fallo.
"""

import json

from model_bakery import baker
from rest_framework.authtoken.models import Token

from accounts.models import User
from erase.models import EraseAction, WipeOrderStatus
from observerrmm.helpers import make_random_password
from observerrmm.test import ObserverTestCase


class ReporteDeWipePorHTTPTests(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()

        self.agent = baker.make_recipe("agents.agent")
        # Token DEL AGENTE, no sesión de operador: `User.agent` es lo que puebla
        # `NewAgent` al enrolar y de donde `_agente_del_token` resuelve el equipo.
        user = User.objects.create_user(  # type: ignore
            username=self.agent.agent_id,
            password=make_random_password(len=60),  # type: ignore
            agent=self.agent,
        )
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _orden(self, **kw):
        defaults = dict(
            agent=self.agent,
            action=EraseAction.WIPE,
            scope={"paths": [r"C:\\d"]},
            dry_run=False,
            status=WipeOrderStatus.DISPATCHED,
            ordered_by="john",
            confirmed_by="alice",
        )
        defaults.update(kw)
        return baker.make("erase.WipeOrder", **defaults)

    def _url(self, order):
        return f"/api/v3/{self.agent.agent_id}/wipe/{order.pk}/report/"

    def test_el_result_serializado_del_agente_llega_como_diccionario(self):
        """El agente manda texto; en la base tiene que quedar un mapa."""
        o = self._orden()
        por_ruta = {r"C:\\d\\uno.txt": "borrado+verificado"}

        r = self.client.post(
            self._url(o),
            {
                "result": json.dumps(por_ruta),  # ← tal como lo manda wipe.go
                "verified": "1",
                "method_applied": "overwrite-rename-delete/1pass",
            },
        )

        self.assertEqual(r.status_code, 200)
        o.refresh_from_db()
        self.assertIsInstance(o.result, dict)
        self.assertEqual(o.result, por_ruta)

    def test_un_borrado_verificado_emite_su_certificado(self):
        """El control que T024 no pudo cerrar: borrar y quedar sin documento."""
        o = self._orden()

        r = self.client.post(
            self._url(o),
            {
                "result": json.dumps({r"C:\\d\\uno.txt": "borrado+verificado"}),
                "verified": "1",
                "method_applied": "overwrite-rename-delete/1pass",
            },
        )

        self.assertEqual(r.status_code, 200)
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.EXECUTED)
        self.assertTrue(o.verified)
        self.assertEqual(o.certificates.count(), 1)
        # Y sin `certificate_error` en la cadena: el camino feliz no deja rastro
        # de fallo.
        self.assertFalse(o.audit_records.filter(event="certificate_error").exists())

    def test_un_result_que_no_es_json_no_se_pierde_ni_rompe(self):
        """Texto suelto: se conserva bajo `_`, la clave que el panel descarta."""
        o = self._orden()

        r = self.client.post(
            self._url(o),
            {"result": "sin archivos que borrar", "verified": "0"},
        )

        self.assertEqual(r.status_code, 200)
        o.refresh_from_db()
        self.assertEqual(o.result, {"_": "sin archivos que borrar"})
        self.assertEqual(o.status, WipeOrderStatus.INCOMPLETE)

    def test_si_la_emision_falla_queda_constancia_y_el_reporte_responde(self):
        """Un fallo al emitir no puede volverse un 500 silencioso.

        El 500 es lo que hizo desaparecer el defecto en staging: el agente
        reintentaba, recibía el 409 del estado terminal y abandonaba.
        """
        from unittest.mock import patch

        o = self._orden()
        with patch(
            "erase.services.issue_wipe_certificate",
            side_effect=RuntimeError("falla simulada al emitir"),
        ):
            r = self.client.post(
                self._url(o),
                {
                    "result": json.dumps({r"C:\\d\\uno.txt": "borrado+verificado"}),
                    "verified": "1",
                },
            )

        self.assertEqual(r.status_code, 200)
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.EXECUTED)
        self.assertEqual(o.certificates.count(), 0)
        evento = o.audit_records.filter(event="certificate_error").first()
        self.assertIsNotNone(evento)
        self.assertIn("falla simulada al emitir", evento.detail["error"])

    def test_el_dry_run_sigue_reportando_su_plan(self):
        """Control de no-regresión: el simulacro no pasa por el mapa por-ruta."""
        o = self._orden(dry_run=True)

        r = self.client.post(self._url(o), {"plan": "3 archivo(s) que se borrarían"})

        self.assertEqual(r.status_code, 200)
        o.refresh_from_db()
        self.assertEqual(o.result, {"plan": "3 archivo(s) que se borrarían"})
        self.assertEqual(o.certificates.count(), 0)
        self.assertIsNone(o.verified)
