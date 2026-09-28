"""Feature 045: marca de cliente de origen (X-Observer-Client) en la auditoría."""

from unittest.mock import patch

from logs.models import AuditLog
from observerrmm.middleware import (
    CLIENT_HEADER_MAX_LEN,
    AuditMiddleware,
    get_debug_info,
    request_local,
    sanitize_client_header,
)
from observerrmm.test import ObserverTestCase


class TestSanitizeClientHeader(ObserverTestCase):
    def test_valor_normal_se_conserva(self):
        self.assertEqual(
            sanitize_client_header("mcp/0.1.0 tool=add_note"), "mcp/0.1.0 tool=add_note"
        )

    def test_vacio_o_ausente_es_none(self):
        self.assertIsNone(sanitize_client_header(None))
        self.assertIsNone(sanitize_client_header(""))
        self.assertIsNone(sanitize_client_header("<>{}"))

    def test_filtra_caracteres_y_trunca(self):
        raw = "mcp<script>\"'\n" + "x" * 500
        clean = sanitize_client_header(raw)
        self.assertEqual(len(clean), CLIENT_HEADER_MAX_LEN)
        for ch in "<>\"'\n":
            self.assertNotIn(ch, clean)


class TestMiddlewareClientHeader(ObserverTestCase):
    # El middleware limpia request_local al final de cada respuesta DRF
    # (process_template_response); se neutraliza esa limpieza para poder leer lo
    # que quedó durante el request.
    def setUp(self):
        self.authenticate()
        request_local.debug_info = None
        request_local.username = None
        patcher = patch.object(
            AuditMiddleware,
            "process_template_response",
            lambda self, request, response: response,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_header_presente_queda_en_debug_info(self):
        r = self.client.get(
            "/core/version/", HTTP_X_OBSERVER_CLIENT="mcp/0.1.0 tool=get_agent"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get_debug_info().get("client"), "mcp/0.1.0 tool=get_agent")

    def test_sin_header_no_aparece_la_clave(self):
        r = self.client.get("/core/version/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("client", get_debug_info())


class TestAuditLogClientMerge(ObserverTestCase):
    def setUp(self):
        request_local.debug_info = {"ip": "10.0.0.1", "client": "mcp/0.1.0 tool=x"}
        request_local.username = "john"

    def tearDown(self):
        request_local.debug_info = None
        request_local.username = None

    def _create(self, username, debug_info):
        return AuditLog.objects.create(
            username=username,
            object_type="agent",
            action="modify",
            message="test",
            debug_info=debug_info,
        )

    def test_debug_info_propio_recibe_el_cliente(self):
        log = self._create("john", {"ip": "10.0.0.1"})
        self.assertEqual(
            log.debug_info, {"ip": "10.0.0.1", "client": "mcp/0.1.0 tool=x"}
        )

    def test_otro_usuario_no_hereda_el_cliente(self):
        log = self._create("alice", {"ip": "10.0.0.2"})
        self.assertNotIn("client", log.debug_info)

    def test_sin_cliente_en_el_request_no_cambia(self):
        request_local.debug_info = {"ip": "10.0.0.1"}
        log = self._create("john", {"ip": "10.0.0.1"})
        self.assertEqual(log.debug_info, {"ip": "10.0.0.1"})

    def test_debug_info_limpio_en_none_no_revienta(self):
        # El middleware deja request_local.debug_info = None al terminar cada
        # respuesta; crear un AuditLog después (tareas, señales) no debe fallar.
        request_local.debug_info = None
        log = self._create("john", {"ip": "10.0.0.1"})
        self.assertEqual(log.debug_info, {"ip": "10.0.0.1"})

    def test_no_pisa_un_cliente_ya_presente(self):
        log = self._create("john", {"client": "otro"})
        self.assertEqual(log.debug_info, {"client": "otro"})
