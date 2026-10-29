"""Un `TestCase` que crea `AuditLog` no deja filas commiteadas detrás.

Es la invariante que se rompió el 2026-10-28: `test_get_audit_logs` contó 99
filas donde esperaba 86, trece de más, en un commit que sólo tocaba HTML.

⚠️ Hoy la fuga NO se reproduce, y está medido, no supuesto. Un barrido de los
1260 tests contando `logs_auditlog` por una conexión aparte después de CADA test
—o sea leyendo sólo lo commiteado, que es exactamente lo que sobrevive a un
rollback— da cero filas en todos. Y quitando la mitigación de
`create_audit_records()` (el `delete()` de la tabla antes de sembrar), el test
sigue dando 86 con 6 semillas distintas corriendo solo y con 5 semillas
corriendo `logs/` entero. Es decir: esa mitigación hoy no tapa nada, porque no
hay nada que tapar. Lo que sí hace es volver el test independiente del estado
de la tabla, y por eso conviene que se quede.

Este archivo no acompaña un arreglo entonces: fija la invariante para que, si
alguien vuelve a introducir una escritura fuera de la transacción del test, se
vea acá y no tres archivos más allá en una aserción de conteo absoluto. Está
comprobado que detecta el caso: creando las mismas filas desde un hilo —que abre
su propia conexión, fuera del bloque atómico— falla con `13 != 0`.

Lo que se afirma acá es el invariante en sí, y por eso el envoltorio es un
`TransactionTestCase`: hay que poder leer lo COMMITEADO. Dentro de la
transacción de un `TestCase` el rollback del caso interno no se podría observar,
porque lo que se mide es precisamente lo que sobrevive a ese rollback. Se corre
un `TestCase` anidado de verdad para que sea su propia maquinaria de
`_fixture_setup`/`_fixture_teardown` la que se ponga a prueba, no una imitación.

🪤 Se mide DELTA, nunca un conteo absoluto: `pytest-randomly` baraja el orden en
cada corrida y cualquier total depende de qué corrió antes.

🪤 Las filas se crean con `baker.make("logs.AuditLog")` y NO con las recetas
`logs.*_logs` a propósito. Esas recetas consumen un `cycle(...)` que es estado
de módulo (ver la cabecera de `logs/baker_recipes.py`): gastar posiciones acá
acercaría a `test_get_audit_logs` al offset en que su aserción de 26 pasa a 25.
Este test no toca ese presupuesto.
"""

import io
import unittest

from django.test import TransactionTestCase
from model_bakery import baker

from logs.models import AuditLog

# Trece, el número exacto del incidente: 99 contra 86 esperadas.
FILAS = 13


class AuditLogNoDejaFilasCommiteadasTests(TransactionTestCase):
    def test_un_testcase_que_crea_auditlog_devuelve_la_tabla_a_su_estado(self):
        from observerrmm.test import ObserverTestCase

        class CreaYDeberiaRevertir(ObserverTestCase):
            def test_crea_filas(self):
                baker.make("logs.AuditLog", _quantity=FILAS)
                # Control de que el caso interno hizo su trabajo: si no creara
                # nada, el delta de cero de abajo no probaría absolutamente nada.
                assert AuditLog.objects.count() >= FILAS

        antes = AuditLog.objects.count()

        suite = unittest.TestLoader().loadTestsFromTestCase(CreaYDeberiaRevertir)
        resultado = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            suite
        )
        self.assertTrue(
            resultado.wasSuccessful(),
            f"el TestCase anidado falló: {resultado.errors or resultado.failures}",
        )

        self.assertEqual(
            AuditLog.objects.count() - antes,
            0,
            "un TestCase dejó filas de AuditLog commiteadas: sobrevivieron a su "
            "rollback y contaminan a los tests siguientes",
        )
