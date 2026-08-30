"""Tests de auditoría del wipe (feature 043 · T021) y del enganche al certificado
(T016).

T021 — la traza de la orden (creación, confirmación, despacho-bloqueado por el gate
y resultado) queda en `EraseAuditRecord`, la cadena inmutable que **sobrevive a la
poda** (`prune_audit_log` solo toca `AuditLog`) y **no se puede borrar**
(`ImmutableRecordError`).

T016 — una orden con `verified=True` emite el certificado C (RF-10); una `incomplete`
o un dry-run NO lo emiten (RN-08).
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from model_bakery import baker

from erase import services
from erase.models import (
    CertificateKind,
    EraseAction,
    EraseAuditRecord,
    EraseCertificate,
    ImmutableRecordError,
    WipeOrderStatus,
)


async def _fake_nats_ok(*a, **k):
    return "ok"


class WipeAuditTrailTests(TestCase):
    """T021 · la traza completa de la orden queda en la cadena inmutable."""

    @override_settings(ERASE_DESTRUCTIVE_DISPATCH_ENABLED=False)
    @patch("erase.tasks.dispatch_wipe_order.apply_async")
    def test_ciclo_completo_deja_traza(self, _apply):
        agent = baker.make("agents.Agent", agent_id="aid-audit")
        client = baker.make("clients.Client")
        site = baker.make("clients.Site", client=client)

        order = services.create_order(
            agent=agent,
            client=client,
            site=site,
            action=EraseAction.WIPE,
            ordered_by="john",
            scope={"paths": ["/a"]},
            dry_run=False,
            reason="baja de equipo",
        )
        services.confirm_order(order=order, confirmed_by="alice")
        order.refresh_from_db()
        # El gate deja constancia y no despacha (flag False).
        services.dispatch_order(order=order)
        # Simula el reporte del agente con verificación OK.
        order.status = WipeOrderStatus.DISPATCHED
        order.save(update_fields=["status"])
        services.apply_wipe_report(
            order=order,
            result={"/a": "borrado+verificado"},
            verified=True,
            method_applied="overwrite-fsync-unlink/1pass",
        )

        eventos = list(
            order.audit_records.order_by("id").values_list("event", flat=True)
        )
        for esperado in ("created", "confirmed", "dispatch_gated_adr029", "executed"):
            self.assertIn(esperado, eventos, f"falta el evento {esperado}: {eventos}")
        # El certificado emitido también deja su fila de auditoría.
        self.assertTrue(
            EraseAuditRecord.objects.filter(
                order=order, event="certificate_issued"
            ).exists()
        )

    def test_prune_audit_log_no_toca_erase(self):
        """`prune_audit_log` borra `AuditLog`, JAMÁS `EraseAuditRecord` (RF-G04)."""
        from logs.models import AuditLog
        from logs.tasks import prune_audit_log

        order = baker.make(
            "erase.WipeOrder", action=EraseAction.WIPE, ordered_by="john"
        )
        services.record_event(order=order, event="created", actor="john")
        baker.make("logs.AuditLog")  # ruido operativo purgable

        antes = EraseAuditRecord.objects.count()
        self.assertGreaterEqual(antes, 1)
        self.assertEqual(AuditLog.objects.count(), 1)

        # older_than_days=-1 → umbral en el futuro: purga hasta las filas recién creadas.
        prune_audit_log(-1)

        self.assertEqual(AuditLog.objects.count(), 0, "el audit operativo sí se poda")
        self.assertEqual(
            EraseAuditRecord.objects.count(),
            antes,
            "la evidencia legal NO se poda",
        )

    def test_erase_audit_record_no_se_puede_borrar(self):
        order = baker.make(
            "erase.WipeOrder", action=EraseAction.WIPE, ordered_by="john"
        )
        rec = services.record_event(order=order, event="created", actor="john")
        with self.assertRaises(ImmutableRecordError):
            rec.delete()


class WipeCertificateHookTests(TestCase):
    """T016 · el certificado C se emite sólo con verificación (RN-08 / RF-10)."""

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

    def test_verificado_emite_certificado(self):
        o = self._order()
        services.apply_wipe_report(
            order=o,
            result={"/a": "borrado+verificado"},
            verified=True,
            method_applied="overwrite-rename-delete/1pass",
        )
        certs = EraseCertificate.objects.filter(order=o)
        self.assertEqual(certs.count(), 1)
        cert = certs.first()
        self.assertEqual(cert.kind, CertificateKind.REMOTE_DESTRUCTION)
        self.assertEqual(cert.verification_result, "PASS")
        self.assertEqual(cert.method_applied, "overwrite-rename-delete/1pass")
        self.assertIn("800-88", cert.standard_ref)
        # El wipe SÍ llena la verificación por relectura (no es N/A del Bloque B).
        self.assertEqual(cert.data["verification_level"], "relectura por-ruta (RN-08)")
        self.assertEqual(cert.data["paths_total"], 1)

    def test_incompleto_no_emite_certificado(self):
        o = self._order()
        services.apply_wipe_report(order=o, result={"/a": "residuo"}, verified=False)
        o.refresh_from_db()
        self.assertEqual(o.status, WipeOrderStatus.INCOMPLETE)
        self.assertFalse(EraseCertificate.objects.filter(order=o).exists())

    def test_dry_run_no_emite_certificado(self):
        o = self._order(dry_run=True)
        services.apply_wipe_report(order=o, plan="3 archivo(s)")
        self.assertFalse(EraseCertificate.objects.filter(order=o).exists())

    def test_emision_idempotente(self):
        o = self._order()
        services.apply_wipe_report(
            order=o, result={"/a": "borrado+verificado"}, verified=True
        )
        # Un segundo intento de emisión no duplica el certificado.
        services.issue_wipe_certificate(order=o)
        self.assertEqual(EraseCertificate.objects.filter(order=o).count(), 1)
