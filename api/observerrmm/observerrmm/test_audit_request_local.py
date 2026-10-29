"""`request_local` no puede sobrevivir al request que lo llenó.

`AuditMiddleware.process_view` guarda el usuario autenticado en `request_local`,
que es un `threading.local()` de MÓDULO: se crea al importar y no se reinicia
entre requests ni entre tests. Y mientras siga puesto, `BaseAuditModel.save()`
(`logs/models.py`) escribe un `AuditLog` por cada save de un modelo auditado
—`Agent`, `Client`, `Site`, `User`, `CoreSettings`, …— aunque ya no haya ningún
request en curso.

Ésa es la causa de la contaminación de `logs.AuditLog` del 2026-10-28, cuando
`logs/tests.py::test_get_audit_logs` contó 99 filas donde esperaba 86. Las trece
de más no sobrevivían a ningún rollback: las creaba el propio fixture del test
—tres `User` y un `CoreSettings` en `setUp`, más los nueve `Client`/`Site`/`Agent`
de `create_audit_records()`— porque el test arrancó con el usuario de otro test
todavía pegado en `request_local`. Detalle en `logs/test_audit_isolation.py`.

🪤 Se miden DELTAS, nunca conteos absolutos: `pytest-randomly` baraja el orden en
cada corrida y cualquier total depende de qué corrió antes.
"""

import datetime as dt

from model_bakery import baker

from logs.models import AuditLog
from observerrmm.middleware import get_debug_info, get_username, request_local
from observerrmm.test import ObserverTestCase

# El XLSX de actividad (`agents.views.ActivityExport`) es un endpoint autenticado
# REAL cuya respuesta es un `HttpResponse` plano y no una `Response` de DRF. Es
# justo el caso que `process_template_response` no cubre —no hay nada que
# renderizar—, así que sirve de testigo de los endpoints de descarga: el
# instalador .ps1, el PDF del informe de extravío, los certificados de borrado.
URL_DESCARGA = "/agents/activity/export/"


class RequestLocalNoSobreviveAlRequestTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        # El estado es de PROCESO: si un test anterior lo dejó puesto, lo de
        # abajo no mediría nada. Se parte de limpio a propósito, y se limpia al
        # salir para no ser uno más de los que contaminan.
        self._limpiar()
        self.addCleanup(self._limpiar)

    def _limpiar(self) -> None:
        request_local.username = None
        request_local.debug_info = None

    def _descargar(self):
        hoy = dt.date.today()
        resp = self.client.get(
            URL_DESCARGA, {"desde": hoy.isoformat(), "hasta": hoy.isoformat()}
        )
        self.assertEqual(resp.status_code, 200)
        # Si el endpoint pasara a responder con DRF, dejaría de ser testigo de
        # nada (DRF sí renderiza) y habría que elegir otro. Se afirma acá para
        # que eso se vea como una falla y no como un test que ya no prueba nada.
        self.assertFalse(
            hasattr(resp, "render"),
            f"{URL_DESCARGA} ya no devuelve una respuesta sin render: "
            "elegir otro endpoint de descarga como testigo",
        )
        return resp

    def test_una_descarga_no_deja_el_usuario_pegado(self):
        self._descargar()

        self.assertIsNone(
            get_username(),
            "el usuario del request quedó en request_local al terminar la "
            "respuesta: todo save posterior del proceso se va a auditar",
        )
        self.assertFalse(get_debug_info())

    def test_despues_de_una_descarga_un_save_no_audita(self):
        self._descargar()

        antes = AuditLog.objects.count()
        baker.make("clients.Client")

        self.assertEqual(
            AuditLog.objects.count() - antes,
            0,
            "un save posterior al request se auditó solo: el usuario quedó en "
            "request_local y contamina los conteos de los tests siguientes",
        )
