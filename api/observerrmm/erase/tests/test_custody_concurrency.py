"""Escrituras concurrentes sobre la misma acta no rompen la cadena.

Feature 053 · ola 2 · RF-06. Es el riesgo que la ola 1 **no tuvo**: los
certificados se emiten de a uno, pero la custodia tiene un endpoint de creación
y dos peticiones simultáneas podrían tomar el mismo `prev_hash`.

🔑 Este test **verifica**, no implementa: la serialización ya vive en
`ImmutableChainRecord.save()`, que lee el último eslabón con
`select_for_update()` dentro de `transaction.atomic()`. `CustodyEvent` la hereda
sin escribir una línea. Lo que faltaba era probarlo, y probarlo exige
`TransactionTestCase`: la transacción envolvente de `TestCase` anularía el
bloqueo y el test pasaría sin ejercitar nada.
"""

import threading

from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from model_bakery import baker

from erase.models import AssetIntake, CustodyEvent, CustodyEventKind

HILOS = 8


class CustodyConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.client_obj = baker.make("clients.Client", name="Cliente Concurrente")
        self.intake = AssetIntake.objects.create(
            process_id="OE-IN-CONC-1",
            client=self.client_obj,
            equipment_serial="SN-CONC-1",
            received_by="bodega",
        )
        # El acta nace con su `received`: la cadena nunca esta vacia cuando
        # llegan escrituras concurrentes, que es el caso real.
        self._crear(CustodyEventKind.RECEIVED)

    def _crear(self, kind, actor="bodega"):
        return CustodyEvent.objects.create(
            intake=self.intake,
            intake_process_id=self.intake.process_id,
            equipment_serial=self.intake.equipment_serial,
            kind=kind,
            at=timezone.now(),
            actor=actor,
        )

    def test_ocho_escrituras_simultaneas_dejan_la_cadena_intacta(self):
        errores = []
        arrancar = threading.Barrier(HILOS)

        def escribir(n):
            try:
                arrancar.wait(timeout=30)
                self._crear(CustodyEventKind.RELOCATED, actor=f"operador-{n}")
            except Exception as exc:  # pragma: no cover - solo si falla
                errores.append(repr(exc))
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=escribir, args=(n,)) for n in range(HILOS)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=60)

        self.assertEqual(errores, [], f"escrituras fallidas: {errores}")

        eslabones = list(CustodyEvent.objects.order_by("id"))
        self.assertEqual(len(eslabones), HILOS + 1)

        # Ningun prev_hash repetido: dos eslabones que colgaran del mismo
        # anterior serian exactamente la corrupcion que el bloqueo evita.
        previos = [e.prev_hash for e in eslabones]
        self.assertEqual(len(set(previos)), len(previos))

        # Y la cadena encadena y recomputa de punta a punta.
        anterior = ""
        for e in eslabones:
            self.assertEqual(e.prev_hash, anterior)
            self.assertEqual(e.compute_record_hash(e.prev_hash), e.record_hash)
            anterior = e.record_hash

    def tearDown(self):
        connection.close()
