"""La purga alcanza los dos tipos de adjunto, respeta el plazo de cada cliente y
nunca toca el certificado.

Feature 053 · ola 3 · RNF-06 / L-04.

🔴 Antes de esta ola la purga **no corría en absoluto**: `prune_erase_attachments`
no estaba agendada en ninguna parte —el único `grep` que la encontraba en todo el
repo era su propio `def`— y además sólo recorría `RetrievedFile`, así que
`DestructionEvidence` no se purgaba nunca y la fotografía de una destrucción
física era permanente de facto, al revés de lo que declaran L-04 y la política de
uso aceptable.

🪤 **Deltas, nunca conteos absolutos.** `pytest-randomly` está activo y hay una
fuga conocida de filas de `AuditLog` que sobrevive a los rollbacks: cualquier
aserción sobre un total se vuelve frágil por razones que no tienen nada que ver
con lo que se está probando.
"""

import hashlib
import tempfile

from cryptography.fernet import Fernet
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone
from erase.models import (
    AssetIntake,
    DestructionEvidence,
    EraseAuditRecord,
    EraseCertificate,
    FileRetrievalOrder,
    RetrievedFile,
)
from erase.tasks import prune_erase_attachments
from model_bakery import baker
from observerrmm.constants import ERASE_ATTACHMENT_RETENTION_FLOOR_DAYS as PISO
from observerrmm.test import ObserverTestCase

LLAVE = Fernet.generate_key().decode()
TMP = tempfile.mkdtemp()
CONTENIDO = b"evidencia-binaria-de-prueba"


@override_settings(LOST_MODE_EVIDENCE_BASE_PATH=TMP, LOST_MODE_EVIDENCE_KEY=LLAVE)
class _Base(ObserverTestCase):
    """🪤 El override cubre la CLASE: el almacén resuelve la ruta en cada uso."""

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _cliente(self, nombre, dias=None):
        c = baker.make("clients.Client", name=nombre)
        if dias is not None:
            c.erase_attachment_retention_days = dias
            c.save()
        self._site = baker.make("clients.Site", client=c)
        return c

    def _evidencia_de_destruccion(self, cliente, *, dias_atras):
        """Un adjunto de C7 con la antigüedad pedida."""
        acta = AssetIntake.objects.create(
            process_id=f"P-{AssetIntake.objects.count() + 1}",
            client=cliente,
            received_by="bodega",
            equipment_serial="SN-X",
        )
        ev = DestructionEvidence(
            intake=acta,
            original_name="foto.jpg",
            size=len(CONTENIDO),
            sha256=hashlib.sha256(CONTENIDO).hexdigest(),
            uploaded_by="john",
        )
        ev.asset.save("foto.jpg", ContentFile(CONTENIDO), save=True)
        self._envejecer(DestructionEvidence, ev.pk, dias_atras)
        ev.refresh_from_db()
        return ev

    def _archivo_recuperado(self, cliente, *, dias_atras):
        """Un adjunto de fileretrieval con la antigüedad pedida."""
        agent = baker.make("agents.Agent", site=self._site)
        order = FileRetrievalOrder.objects.create(
            agent=agent, client=cliente, site=self._site
        )
        rf = RetrievedFile(order=order, source_path="C:/x.docx", size=len(CONTENIDO))
        rf.asset.save("x.docx", ContentFile(CONTENIDO), save=True)
        self._envejecer(RetrievedFile, rf.pk, dias_atras)
        rf.refresh_from_db()
        return rf

    @staticmethod
    def _envejecer(modelo, pk, dias):
        """`uploaded_at` es `auto_now_add`: sólo se puede mover con `update()`."""
        modelo.objects.filter(pk=pk).update(
            uploaded_at=timezone.now() - timezone.timedelta(days=dias)
        )


class AlcanceTests(_Base):
    def test_purga_las_dos_tablas_de_adjuntos(self):
        """🔴 `DestructionEvidence` entra en la purga: antes quedaba fuera."""
        cliente = self._cliente("Alcance", dias=PISO)
        ev = self._evidencia_de_destruccion(cliente, dias_atras=PISO + 10)
        rf = self._archivo_recuperado(cliente, dias_atras=PISO + 10)

        prune_erase_attachments()

        ev.refresh_from_db()
        rf.refresh_from_db()
        self.assertFalse(ev.asset, "la evidencia de destruccion no se purgo")
        self.assertFalse(rf.asset, "el archivo recuperado no se purgo")

    def test_borra_el_binario_y_conserva_la_fila_con_su_hash(self):
        """🔑 El hash es el rastro: sin él, purgar sería destruir evidencia."""
        cliente = self._cliente("Rastro", dias=PISO)
        ev = self._evidencia_de_destruccion(cliente, dias_atras=PISO + 10)
        sha_antes, nombre_antes, size_antes = ev.sha256, ev.original_name, ev.size

        prune_erase_attachments()

        ev.refresh_from_db()
        self.assertFalse(ev.asset)
        self.assertEqual(ev.sha256, sha_antes)
        self.assertEqual(ev.original_name, nombre_antes)
        self.assertEqual(ev.size, size_antes)

    def test_un_adjunto_dentro_del_plazo_no_se_toca(self):
        cliente = self._cliente("Vigente", dias=PISO)
        ev = self._evidencia_de_destruccion(cliente, dias_atras=10)

        prune_erase_attachments()

        ev.refresh_from_db()
        self.assertTrue(ev.asset, "purgo un adjunto que todavia esta en plazo")


class PlazoPorClienteTests(_Base):
    def test_el_cliente_con_mas_plazo_conserva_lo_que_el_otro_pierde(self):
        """El control que da sentido a toda la ola: dos plazos, dos resultados."""
        corto = self._cliente("Plazo corto", dias=PISO)
        ev_corto = self._evidencia_de_destruccion(corto, dias_atras=PISO + 10)
        largo = self._cliente("Plazo largo", dias=730)
        ev_largo = self._evidencia_de_destruccion(largo, dias_atras=PISO + 10)

        prune_erase_attachments()

        ev_corto.refresh_from_db()
        ev_largo.refresh_from_db()
        self.assertFalse(ev_corto.asset, "no purgo al cliente de plazo corto")
        self.assertTrue(
            ev_largo.asset, "purgo al cliente de 730 dias aplicandole el plazo ajeno"
        )

    def test_el_cliente_sin_plazo_propio_usa_el_global(self):
        from core.utils import get_core_settings

        core = get_core_settings()
        core.erase_attachment_retention_days = 1000
        core.save()

        hereda = self._cliente("Hereda")
        ev = self._evidencia_de_destruccion(hereda, dias_atras=PISO + 10)

        prune_erase_attachments()

        ev.refresh_from_db()
        self.assertTrue(ev.asset, "aplico el piso en vez del global de 1000 dias")


class EnsayoTests(_Base):
    def test_dry_run_cuenta_lo_mismo_y_no_borra_nada(self):
        cliente = self._cliente("Ensayo", dias=PISO)
        ev = self._evidencia_de_destruccion(cliente, dias_atras=PISO + 10)
        rf = self._archivo_recuperado(cliente, dias_atras=PISO + 10)

        ensayo = prune_erase_attachments(dry_run=True)
        ev.refresh_from_db()
        rf.refresh_from_db()
        self.assertIn("purged=2", ensayo)
        self.assertIn("ensayo", ensayo)
        self.assertTrue(ev.asset, "el ensayo borro la evidencia")
        self.assertTrue(rf.asset, "el ensayo borro el archivo recuperado")

        real = prune_erase_attachments()
        self.assertIn("purged=2", real, "el conteo real no coincide con el ensayo")
        ev.refresh_from_db()
        self.assertFalse(ev.asset)

    def test_es_idempotente(self):
        """Corre cada hora: la segunda pasada no debe encontrar nada."""
        cliente = self._cliente("Idempotente", dias=PISO)
        self._evidencia_de_destruccion(cliente, dias_atras=PISO + 10)

        prune_erase_attachments()
        segunda = prune_erase_attachments()
        self.assertIn("purged=0", segunda)


class InmutabilidadTests(_Base):
    def test_purgar_no_toca_el_certificado_ni_la_auditoria(self):
        """🔴 Delta 0, contando filas.

        No alcanza con que no se lance `ImmutableRecordError`: la ola 2 demostró
        que un borrado en cascada se lleva filas append-only **sin dispararlo**.
        """
        cliente = self._cliente("Inmutable", dias=PISO)
        self._evidencia_de_destruccion(cliente, dias_atras=PISO + 10)
        certs_antes = EraseCertificate.objects.count()
        audit_antes = EraseAuditRecord.objects.count()

        prune_erase_attachments()

        self.assertEqual(EraseCertificate.objects.count() - certs_antes, 0)
        self.assertEqual(EraseAuditRecord.objects.count() - audit_antes, 0)


class ElEngancheTests(_Base):
    """🔴 Que la tarea esté AGENDADA. Es lo que faltaba durante dos olas.

    `prune_erase_attachments` existía desde la 042, bien escrita y con la cita
    normativa correcta, y **no la llamaba nadie**: el único `grep` del nombre en
    todo el repo era su propio `def`. Pasaba los tests porque los tests la
    invocaban a mano. Este enganche es lo que la vuelve efecto, y estos dos tests
    son lo que impide que vuelva a desaparecer en silencio.
    """

    def test_el_mantenimiento_la_encola_siempre(self):
        """SIN guard `> 0`, al molde de `prune_lost_mode_evidence` (ADR-025)."""
        from unittest.mock import patch

        from core.tasks import core_maintenance_tasks

        with patch("core.tasks.prune_erase_attachments") as tarea:
            core_maintenance_tasks()

        tarea.delay.assert_called_once()

    def test_apagada_se_encola_en_ensayo_y_no_con_dientes(self):
        """El ajuste gobierna si BORRA, no si CORRE."""
        from unittest.mock import patch

        from core.tasks import core_maintenance_tasks
        from core.utils import get_core_settings

        core = get_core_settings()
        self.assertFalse(
            core.erase_attachment_prune_enabled,
            "control: nace apagada",
        )

        with patch("core.tasks.prune_erase_attachments") as tarea:
            core_maintenance_tasks()
        tarea.delay.assert_called_once_with(dry_run=True)

        core.erase_attachment_prune_enabled = True
        core.save()
        with patch("core.tasks.prune_erase_attachments") as tarea:
            core_maintenance_tasks()
        tarea.delay.assert_called_once_with(dry_run=False)
