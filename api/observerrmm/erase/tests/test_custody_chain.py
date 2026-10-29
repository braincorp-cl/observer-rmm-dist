"""La cadena de custodia es append-only, encadenada y no se borra por arrastre.

Feature 053 · ola 2 · RF-06 y CA-06. Un eslabón de custodia vale lo que vale su
inmutabilidad: si se puede editar o borrar sin dejar rastro, el registro no
prueba nada que no probara una planilla.

Tres cosas se cuidan acá, y la tercera es la que casi se escribe mal:

1. que la cadena encadene y recompute;
2. que modificar o borrar un eslabón lance `ImmutableRecordError`;
3. 🔴 que **borrar el acta no borre los eslabones**. La FK es `SET_NULL`, no
   `CASCADE`, porque un `CASCADE` no pasa por `Model.delete()` —el collector de
   Django borra en bloque— y habría eliminado filas append-only sin disparar la
   excepción, dejando la cadena con el `prev_hash` descolgado.
"""

from django.utils import timezone
from model_bakery import baker

from erase.models import (
    AssetIntake,
    CustodyEvent,
    CustodyEventKind,
    EraseCertificate,
    ImmutableRecordError,
)
from observerrmm.test import ObserverTestCase


class CustodyChainTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client", name="Cliente Custodia")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.intake = AssetIntake.objects.create(
            process_id="OE-IN-CUSTODIA-1",
            client=self.client_obj,
            site=self.site,
            equipment_serial="SN-CUSTODIA-1",
            received_by="bodega",
        )

    def _evento(self, kind=CustodyEventKind.RELOCATED, intake=None, **kw):
        intake = self.intake if intake is None else intake
        return CustodyEvent.objects.create(
            intake=intake,
            intake_process_id=intake.process_id if intake else "",
            equipment_serial=intake.equipment_serial if intake else "",
            kind=kind,
            at=timezone.now(),
            actor="bodega",
            **kw,
        )

    # --- la cadena encadena ---

    def test_el_primer_eslabon_no_tiene_anterior(self):
        ev = self._evento(kind=CustodyEventKind.RECEIVED)
        self.assertEqual(ev.prev_hash, "")
        self.assertTrue(ev.record_hash)

    def test_cada_eslabon_encadena_el_anterior(self):
        uno = self._evento(kind=CustodyEventKind.RECEIVED)
        dos = self._evento(kind=CustodyEventKind.RELOCATED)
        tres = self._evento(kind=CustodyEventKind.STORED)

        self.assertEqual(dos.prev_hash, uno.record_hash)
        self.assertEqual(tres.prev_hash, dos.record_hash)

    def test_el_record_hash_recomputa(self):
        ev = self._evento()
        self.assertEqual(ev.compute_record_hash(ev.prev_hash), ev.record_hash)

    def test_mutar_un_eslabon_en_memoria_rompe_la_recomputacion(self):
        """Control negativo: si el hash no dependiera del contenido, este test
        pasaria igual y la cadena no probaria nada."""
        ev = self._evento(location="Bodega central")
        ev.location = "Otro lugar"
        self.assertNotEqual(ev.compute_record_hash(ev.prev_hash), ev.record_hash)

    def test_la_cadena_es_propia_y_no_toca_la_del_certificado(self):
        """`ImmutableChainRecord` es abstracta: cada subclase lleva su cadena."""
        cert = EraseCertificate.objects.create(
            certificate_id="CERT-CADENA-PROPIA",
            kind="physical_destruction",
            client=self.client_obj,
            data={"x": 1},
            document_hash="a" * 64,
        )
        self._evento(kind=CustodyEventKind.RECEIVED)
        self._evento(kind=CustodyEventKind.DESTROYED)

        cert.refresh_from_db()
        self.assertEqual(cert.prev_hash, "")
        ultimo = EraseCertificate.objects.order_by("-id").first()
        self.assertEqual(ultimo.pk, cert.pk)

    # --- no se modifica ni se borra ---

    def test_no_se_puede_modificar(self):
        ev = self._evento()
        ev.location = "Otro"
        with self.assertRaises(ImmutableRecordError):
            ev.save()

    def test_no_se_puede_borrar(self):
        ev = self._evento()
        with self.assertRaises(ImmutableRecordError):
            ev.delete()
        self.assertEqual(CustodyEvent.objects.filter(pk=ev.pk).count(), 1)

    # --- 🔴 ni por arrastre ---

    def test_borrar_el_acta_deja_el_eslabon_huerfano_no_lo_borra(self):
        """Lo que el `CASCADE` original habria roto en silencio.

        El collector de Django no llama a `Model.delete()` de los hijos, asi que
        con `CASCADE` estas filas se habrian ido sin excepcion y sin rastro.
        """
        uno = self._evento(kind=CustodyEventKind.RECEIVED)
        dos = self._evento(kind=CustodyEventKind.HANDED_TO_PROCESSOR)

        self.intake.delete()

        uno.refresh_from_db()
        dos.refresh_from_db()
        self.assertIsNone(uno.intake_id)
        self.assertIsNone(dos.intake_id)
        # El eslabon huerfano sigue diciendo que paso y con que activo.
        self.assertEqual(uno.intake_process_id, "OE-IN-CUSTODIA-1")
        self.assertEqual(uno.equipment_serial, "SN-CUSTODIA-1")
        # Y la cadena sigue intacta: nada se borro en medio.
        self.assertEqual(dos.prev_hash, uno.record_hash)
        self.assertEqual(uno.compute_record_hash(uno.prev_hash), uno.record_hash)

    def test_borrar_el_cliente_tampoco_borra_los_eslabones(self):
        """El acta cuelga del cliente con `CASCADE`: es la ruta larga del mismo
        problema."""
        ev = self._evento(kind=CustodyEventKind.RECEIVED)
        self.client_obj.delete()
        self.assertEqual(CustodyEvent.objects.filter(pk=ev.pk).count(), 1)
        self.assertEqual(AssetIntake.objects.filter(pk=self.intake.pk).count(), 0)
