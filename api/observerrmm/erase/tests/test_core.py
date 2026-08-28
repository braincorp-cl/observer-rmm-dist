"""Tests del núcleo de Observer Erase (B0/C/D): invariantes que no pueden fallar.

Cubren lo irreversible: append-only + hash-chain (C3/RF-G04), doble confirmación de
dos personas (RF-G02), ventana de arrepentimiento y su cancelación (RF-G03), el gate
ADR-029 del despacho, aislamiento por tenant (D4) y firma del certificado (C2).
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from model_bakery import baker

from accounts.models import Role, User
from erase import certificate as cert_mod
from erase import services
from erase.models import (
    CertificateKind,
    EraseAction,
    EraseAuditRecord,
    EraseCertificate,
    ImmutableRecordError,
    WipeOrderStatus,
)


def _rsa_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


class ImmutableStoreTests(TestCase):
    def _mk(self, event: str) -> EraseAuditRecord:
        rec = EraseAuditRecord(event=event, actor="tester", detail={"e": event})
        rec.save()
        return rec

    def test_encadena_prev_hash(self):
        a = self._mk("a")
        b = self._mk("b")
        c = self._mk("c")
        self.assertEqual(a.prev_hash, "")
        self.assertEqual(b.prev_hash, a.record_hash)
        self.assertEqual(c.prev_hash, b.record_hash)
        # cada record_hash recomputa
        for r in (a, b, c):
            self.assertEqual(r.record_hash, r.compute_record_hash(r.prev_hash))

    def test_no_se_puede_modificar(self):
        a = self._mk("a")
        a.event = "cambiado"
        with self.assertRaises(ImmutableRecordError):
            a.save()

    def test_no_se_puede_eliminar(self):
        a = self._mk("a")
        with self.assertRaises(ImmutableRecordError):
            a.delete()

    def test_deteccion_de_alteracion(self):
        a = self._mk("a")
        # simula edición directa en BD del contenido: el record_hash ya no cuadra
        EraseAuditRecord.objects.filter(pk=a.pk).update(detail={"e": "TAMPERED"})
        a.refresh_from_db()
        self.assertNotEqual(a.record_hash, a.compute_record_hash(a.prev_hash))


async def _fake_nats_ok(*a, **k):
    return "ok"


class OrderGovernanceTests(TestCase):
    def setUp(self):
        self.client_obj = baker.make("clients.Client")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-1", agent_id="aid-1"
        )

    def _order(self):
        return services.create_order(
            agent=self.agent,
            client=self.client_obj,
            site=self.site,
            action=EraseAction.CRYPTO_ERASE,
            ordered_by="operador1",
            reason="equipo robado",
        )

    @patch("erase.tasks.dispatch_wipe_order.apply_async")
    def test_confirmacion_exige_segunda_persona(self, _mock):
        order = self._order()
        with self.assertRaises(services.OrderStateError):
            services.confirm_order(order=order, confirmed_by="operador1")
        # persona distinta sí
        services.confirm_order(order=order, confirmed_by="jefe2", recovery_seconds=60)
        order.refresh_from_db()
        self.assertEqual(order.status, WipeOrderStatus.RECOVERY_WINDOW)
        self.assertEqual(order.confirmed_by, "jefe2")
        self.assertIsNotNone(order.recovery_deadline)

    @patch("erase.tasks.dispatch_wipe_order.apply_async")
    def test_cancelar_en_ventana_frena_despacho(self, _mock):
        order = self._order()
        services.confirm_order(order=order, confirmed_by="jefe2", recovery_seconds=60)
        services.cancel_order(
            order=order, cancelled_by="operador1", reason="falso positivo"
        )
        order.refresh_from_db()
        self.assertEqual(order.status, WipeOrderStatus.CANCELLED)
        # el task, si dispara igual, no hace nada
        services.dispatch_order(order=order)
        order.refresh_from_db()
        self.assertEqual(order.status, WipeOrderStatus.CANCELLED)

    @patch("erase.tasks.dispatch_wipe_order.apply_async")
    def test_despacho_gated_por_defecto(self, _mock):
        order = self._order()
        services.confirm_order(order=order, confirmed_by="jefe2", recovery_seconds=60)
        services.dispatch_order(order=order)
        order.refresh_from_db()
        # sigue en ventana (no despachado) y quedó el registro del gate
        self.assertEqual(order.status, WipeOrderStatus.RECOVERY_WINDOW)
        self.assertTrue(
            EraseAuditRecord.objects.filter(
                order=order, event="dispatch_gated_adr029"
            ).exists()
        )

    @override_settings(ERASE_DESTRUCTIVE_DISPATCH_ENABLED=True)
    @patch("agents.models.Agent.nats_cmd", _fake_nats_ok)
    @patch("erase.tasks.dispatch_wipe_order.apply_async")
    def test_despacho_habilitado_marca_dispatched(self, _mock):
        # Con el flag ON y el equipo alcanzable (nats_cmd mockeado), dispatch_order
        # envía el comando al agente y marca la orden DISPATCHED (feature 043).
        order = self._order()
        services.confirm_order(order=order, confirmed_by="jefe2", recovery_seconds=60)
        services.dispatch_order(order=order)
        order.refresh_from_db()
        self.assertEqual(order.status, WipeOrderStatus.DISPATCHED)

    @patch("erase.tasks.dispatch_wipe_order.apply_async")
    def test_cada_transicion_deja_auditoria(self, _mock):
        order = self._order()
        services.confirm_order(order=order, confirmed_by="jefe2", recovery_seconds=60)
        eventos = set(
            EraseAuditRecord.objects.filter(order=order).values_list("event", flat=True)
        )
        self.assertTrue({"created", "confirmed"}.issubset(eventos))


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.c1 = baker.make("clients.Client")
        self.c2 = baker.make("clients.Client")
        self.s1 = baker.make("clients.Site", client=self.c1)
        self.s2 = baker.make("clients.Site", client=self.c2)
        self.cert1 = self._cert(self.c1, self.s1)
        self.cert2 = self._cert(self.c2, self.s2)

    def _cert(self, client, site):
        return cert_mod.issue_certificate(
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=client,
            site=site,
            tenant=client.name,
            operator="op",
        )

    def _user_scoped_to(self, client):
        role = Role.objects.create(
            name=f"r-{client.pk}", can_view_erase_certificates=True
        )
        role.can_view_clients.add(client)
        u = User.objects.create_user(username=f"u-{client.pk}", password="x")
        u.role = role
        u.save()
        return u

    def test_rol_ve_solo_su_cliente(self):
        u = self._user_scoped_to(self.c1)
        visibles = set(
            EraseCertificate.objects.filter_by_role(u).values_list(
                "certificate_id", flat=True
            )
        )
        self.assertIn(self.cert1.certificate_id, visibles)
        self.assertNotIn(self.cert2.certificate_id, visibles)

    def test_superuser_ve_todo(self):
        u = User.objects.create_user(username="super", password="x", is_superuser=True)
        self.assertEqual(EraseCertificate.objects.filter_by_role(u).count(), 2)

    def test_rol_sin_alcance_ve_todo(self):
        role = Role.objects.create(name="sinalcance", can_view_erase_certificates=True)
        u = User.objects.create_user(username="libre", password="x")
        u.role = role
        u.save()
        # alcance vacío = todo, igual que PermissionQuerySet
        self.assertEqual(EraseCertificate.objects.filter_by_role(u).count(), 2)


class CertificateSigningTests(TestCase):
    def setUp(self):
        self.client_obj = baker.make("clients.Client")

    @override_settings(ERASE_SIGNING_KEY=_rsa_pem())
    def test_certificado_firmado_verifica(self):
        cert = cert_mod.issue_certificate(
            kind=CertificateKind.REMOTE_DESTRUCTION,
            client=self.client_obj,
            tenant="ACME",
            method_applied="crypto-erase",
            standard_ref="NIST 800-88 Rev.1 Purge",
            verification_result="PASS",
            operator="op1",
        )
        self.assertTrue(cert.signature)
        res = cert_mod.verify_certificate(cert)
        self.assertTrue(res["document_intact"])
        self.assertTrue(res["signature_valid"])
        self.assertTrue(res["chain_intact"])
        self.assertTrue(res["valid"])

    @override_settings(ERASE_SIGNING_KEY=_rsa_pem())
    def test_alteracion_del_documento_invalida(self):
        cert = cert_mod.issue_certificate(
            kind=CertificateKind.REMOTE_DESTRUCTION,
            client=self.client_obj,
            tenant="ACME",
            operator="op1",
        )
        EraseCertificate.objects.filter(pk=cert.pk).update(
            data={**cert.data, "operator": "otro"}
        )
        cert.refresh_from_db()
        res = cert_mod.verify_certificate(cert)
        self.assertFalse(res["document_intact"])
        self.assertFalse(res["valid"])

    def test_sin_clave_emite_sin_firma_pero_valido(self):
        cert = cert_mod.issue_certificate(
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=self.client_obj,
            tenant="ACME",
            operator="op1",
        )
        self.assertEqual(cert.signature, "")
        res = cert_mod.verify_certificate(cert)
        # documento y cadena íntegros; sin firma no invalida (ambiente de prueba)
        self.assertTrue(res["document_intact"])
        self.assertTrue(res["chain_intact"])
        self.assertTrue(res["valid"])
        self.assertFalse(res["signature_present"])

    @override_settings(ERASE_SIGNING_KEY=_rsa_pem())
    def test_render_html_no_revienta(self):
        cert = cert_mod.issue_certificate(
            kind=CertificateKind.REMOTE_DESTRUCTION,
            client=self.client_obj,
            tenant="ACME",
            verification_result="PASS",
            operator="op1",
        )
        html = cert_mod.render_html(cert)
        self.assertIn(cert.certificate_id, html)
        self.assertIn("Observer Erase", html)
