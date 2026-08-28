"""Tests de la lógica de wipe (feature 043 · A2): resolución de rutas, tope,
máquina de estados del reporte y verificación por relectura.

Complementa `test_core.py` (gobernanza B0) probando el delta del verbo `wipe`:
plantilla + ajustes (RN-07), tope por orden (RF-07), y las transiciones que produce
el reporte del agente — incluida la clave: sin `verified` la orden queda
`incomplete` y NO emite certificado (RN-08 / RF-10).
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from model_bakery import baker

from erase import services
from erase.models import (
    EraseAction,
    WipeOrderStatus,
    WipePathTemplate,
)


async def _fake_nats_ok(*a, **k):
    return "ok"


async def _fake_nats_down(*a, **k):
    return "natsdown"


class ResolveWipePathsTests(TestCase):
    def test_plantilla_mas_ajustes(self):
        tpl = WipePathTemplate(paths=["/a", "/b"])
        out = services.resolve_wipe_paths(
            template=tpl, paths_add=["/c"], paths_remove=["/b"]
        )
        self.assertEqual(out, ["/a", "/c"])

    def test_sin_plantilla_solo_ajustes(self):
        out = services.resolve_wipe_paths(paths_add=["/x", "/y"])
        self.assertEqual(out, ["/x", "/y"])

    def test_sin_duplicados_preserva_orden(self):
        tpl = WipePathTemplate(paths=["/a"])
        out = services.resolve_wipe_paths(template=tpl, paths_add=["/a", "/b", "/b"])
        self.assertEqual(out, ["/a", "/b"])


class ValidateWipePathsTests(TestCase):
    def test_vacio_falla(self):
        with self.assertRaises(services.OrderStateError):
            services.validate_wipe_paths([])

    @override_settings(WIPE_MAX_PATHS_PER_ORDER=2)
    def test_supera_tope_falla(self):
        with self.assertRaises(services.OrderStateError):
            services.validate_wipe_paths(["/a", "/b", "/c"])

    @override_settings(WIPE_MAX_PATHS_PER_ORDER=2)
    def test_dentro_del_tope_ok(self):
        services.validate_wipe_paths(["/a", "/b"])  # no lanza


class ApplyWipeReportTests(TestCase):
    def _order(self, **kw):
        defaults = dict(
            action=EraseAction.WIPE,
            scope={"paths": ["/a"]},
            dry_run=False,
            status=WipeOrderStatus.DISPATCHED,
            ordered_by="john",
            confirmed_by="alice",
        )
        defaults.update(kw)
        return baker.make("erase.WipeOrder", **defaults)

    def test_verificado_queda_ejecutada(self):
        o = self._order()
        services.apply_wipe_report(
            order=o,
            result={"/a": "borrada"},
            verified=True,
            method_applied="clear/overwrite+unlink",
        )
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.EXECUTED)
        self.assertTrue(o.verified)
        self.assertEqual(o.method_applied, "clear/overwrite+unlink")

    def test_sin_verificar_queda_incompleta(self):
        o = self._order()
        services.apply_wipe_report(order=o, result={"/a": "borrada"}, verified=False)
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.INCOMPLETE)
        self.assertFalse(o.verified)

    def test_dry_run_reporta_plan_sin_borrar(self):
        o = self._order(dry_run=True)
        services.apply_wipe_report(order=o, plan="3 archivo(s) que se borrarían")
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.EXECUTED)
        self.assertEqual(o.result, {"plan": "3 archivo(s) que se borrarían"})

    def test_error_queda_fallida(self):
        o = self._order()
        services.apply_wipe_report(order=o, error="borrado no disponible")
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.FAILED)
        self.assertEqual(o.failure_reason, "borrado no disponible")

    def test_idempotente_en_estado_terminal(self):
        o = self._order(status=WipeOrderStatus.EXECUTED, verified=True)
        services.apply_wipe_report(order=o, result={}, verified=False)
        o.refresh_from_db()
        # No re-transiciona: sigue EXECUTED, no lo pisa a INCOMPLETE.
        self.assertEqual(o.status, WipeOrderStatus.EXECUTED)


class DispatchWipeTests(TestCase):
    def _order_en_ventana(self, **kw):
        agent = baker.make("agents.Agent", agent_id="aid-wipe")
        defaults = dict(
            agent=agent,
            action=EraseAction.WIPE,
            scope={"paths": ["/a", "/b"]},
            dry_run=True,
            status=WipeOrderStatus.RECOVERY_WINDOW,
            ordered_by="john",
            confirmed_by="alice",
        )
        defaults.update(kw)
        return baker.make("erase.WipeOrder", **defaults)

    @override_settings(ERASE_DESTRUCTIVE_DISPATCH_ENABLED=False)
    def test_gated_no_despacha(self):
        o = self._order_en_ventana()
        services.dispatch_order(order=o)
        o.refresh_from_db()
        # Sigue en ventana; deja constancia del gate y no viaja al equipo.
        self.assertEqual(o.status, WipeOrderStatus.RECOVERY_WINDOW)
        self.assertTrue(o.audit_records.filter(event="dispatch_gated_adr029").exists())

    @override_settings(ERASE_DESTRUCTIVE_DISPATCH_ENABLED=True)
    @patch("agents.models.Agent.nats_cmd", _fake_nats_ok)
    def test_flag_activo_despacha(self):
        o = self._order_en_ventana()
        services.dispatch_order(order=o)
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.DISPATCHED)

    @override_settings(ERASE_DESTRUCTIVE_DISPATCH_ENABLED=True)
    @patch("agents.models.Agent.nats_cmd", _fake_nats_down)
    def test_flag_activo_pero_offline_queda_en_ventana(self):
        o = self._order_en_ventana()
        services.dispatch_order(order=o)
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.RECOVERY_WINDOW)
