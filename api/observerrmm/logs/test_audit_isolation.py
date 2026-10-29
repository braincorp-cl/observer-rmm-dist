"""Un `TestCase` que crea `AuditLog` no deja filas commiteadas detrás.

Es la invariante que se SOSPECHÓ rota el 2026-10-28, cuando
`test_get_audit_logs` contó 99 filas donde esperaba 86, trece de más, en un
commit que sólo tocaba HTML. No era ésta: ver abajo.

⚠️ ESTE TEST NO ES EL QUE CAZA EL INCIDENTE DEL 2026-10-28, y conviene saberlo
antes de confiar en él. El barrido que lo motivó —los 1260 tests contando
`logs_auditlog` por una conexión aparte después de CADA test, o sea leyendo sólo
lo commiteado— da cero filas en todos, y eso está bien medido. La conclusión que
se sacó de ahí era la equivocada: que entonces no había nada que tapar. Lo que
mostraba era que las trece filas NUNCA estuvieron commiteadas.

La causa real no es una fila que sobrevive a un rollback sino estado de PROCESO:
`AuditMiddleware.process_view` deja el usuario autenticado en `request_local`
(un `threading.local()` de módulo) y hasta el arreglo sólo lo limpiaba en
`process_template_response`/`process_exception` —hooks que no corren si la
respuesta no se renderiza, como una `FileResponse` o un `HttpResponse` plano—,
así que cualquier test que bajara un archivo dejaba el usuario pegado. Con el
usuario puesto, `BaseAuditModel.save()` audita CADA save de un modelo auditado,
y entonces el propio fixture de `test_get_audit_logs` se fabricaba sus filas de
más, dentro de su transacción: cuatro en `setUp` (tres `User` y un
`CoreSettings`) y nueve en `create_audit_records()` (`Client`/`Site`/`Agent`).
Cuatro más nueve, trece. Reproducible y con el número exacto del incidente:

    GHACTIONS=yes pytest -p no:randomly \
      observerrmm/test_observer_client_header.py::TestMiddlewareClientHeader \
      logs/tests.py::TestAuditViews::test_get_audit_logs

El arreglo vive en `observerrmm/middleware.py` y lo fija
`observerrmm/test_audit_request_local.py`. Acá no, porque lo que se mide acá es
otra cosa.

Y la mitigación de `create_audit_records()` (el `delete()` de la tabla antes de
sembrar) sí tapaba parte del síntoma: borra las cuatro filas de `setUp`, así que
con ella puesta el test falla con 95 y sin ella con las 99 del incidente. Tapa
cuatro de trece. Conviene que se quede igual, pero porque vuelve al test
independiente del estado de la tabla, no porque arregle nada.

Lo que este archivo sí fija es la invariante de aislamiento, para que si alguien
introduce una escritura fuera de la transacción del test —el otro mecanismo
posible, el que sí commitea— se vea acá y no tres archivos más allá en una
aserción de conteo absoluto. Está comprobado que detecta el caso: creando las
mismas filas desde un hilo —que abre su propia conexión, fuera del bloque
atómico— falla con `13 != 0`.

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
