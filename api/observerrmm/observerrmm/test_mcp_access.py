"""Feature 045: interruptor global y permiso RBAC del canal MCP.

El canal MCP se reconoce por X-Observer-Client "mcp/..." (lo pone observer-mcp).
Se corta en la autenticación por API key: plataforma apagada o rol sin
can_use_mcp => 403 con `code`. La misma clave sin la marca MCP sigue sirviendo
para la REST directa: el interruptor gobierna el canal del asistente, no la clave.
"""

from model_bakery import baker

from accounts.models import APIKey, User
from core.utils import get_core_settings
from observerrmm.auth import is_mcp_request
from observerrmm.test import ObserverTestCase

URL = "/core/version/"
MCP = {"HTTP_X_OBSERVER_CLIENT": "mcp/0.1.0 tool=auth-check"}


class TestMCPAccess(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()
        self.role = baker.make("accounts.Role")
        self.user = baker.make("accounts.User", role=self.role, is_active=True)
        APIKey.objects.create(name="tecnico", key="k-tecnico", user=self.user)
        self.client.credentials(HTTP_X_API_KEY="k-tecnico")

    def _set_platform(self, enabled: bool) -> None:
        core = get_core_settings()
        core.mcp_enabled = enabled
        core.save()  # save() invalida la caché de CoreSettings

    def test_encendido_por_omision_en_plataforma_y_rol(self):
        self.assertTrue(get_core_settings().mcp_enabled)
        self.assertTrue(self.role.can_use_mcp)
        r = self.client.get(URL, **MCP)
        self.assertEqual(r.status_code, 200)

    def test_plataforma_apagada_da_403_con_motivo(self):
        self._set_platform(False)
        r = self.client.get(URL, **MCP)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "mcp_disabled")

    def test_plataforma_apagada_alcanza_al_superusuario(self):
        self._set_platform(False)
        admin = User.objects.create(username="admin-mcp", is_superuser=True)
        APIKey.objects.create(name="admin", key="k-admin", user=admin)
        self.client.credentials(HTTP_X_API_KEY="k-admin")
        r = self.client.get(URL, **MCP)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "mcp_disabled")

    def test_rol_sin_permiso_da_403_con_motivo(self):
        self.role.can_use_mcp = False
        self.role.save()
        r = self.client.get(URL, **MCP)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "mcp_not_permitted")

    def test_superusuario_no_necesita_el_permiso(self):
        self.role.can_use_mcp = False
        self.role.is_superuser = True
        self.role.save()
        r = self.client.get(URL, **MCP)
        self.assertEqual(r.status_code, 200)

    def test_usuario_sin_rol_no_entra_por_mcp(self):
        sin_rol = baker.make("accounts.User", role=None, is_active=True)
        APIKey.objects.create(name="sin-rol", key="k-sin-rol", user=sin_rol)
        self.client.credentials(HTTP_X_API_KEY="k-sin-rol")
        r = self.client.get(URL, **MCP)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "mcp_not_permitted")

    def test_rest_directa_no_se_ve_afectada(self):
        self._set_platform(False)
        self.role.can_use_mcp = False
        self.role.save()
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        r = self.client.get(URL, HTTP_X_OBSERVER_CLIENT="n8n/1.0")
        self.assertEqual(r.status_code, 200)

    def test_clave_invalida_sigue_siendo_401(self):
        self._set_platform(False)
        self.client.credentials(HTTP_X_API_KEY="no-existe")
        r = self.client.get(URL, **MCP)
        self.assertEqual(r.status_code, 401)

    def test_reencender_restablece_el_acceso(self):
        self._set_platform(False)
        self.assertEqual(self.client.get(URL, **MCP).status_code, 403)
        self._set_platform(True)
        self.assertEqual(self.client.get(URL, **MCP).status_code, 200)


class TestIsMCPRequest(ObserverTestCase):
    def _req(self, value):
        class R:
            META = {} if value is None else {"HTTP_X_OBSERVER_CLIENT": value}

        return R()

    def test_detecta_prefijo(self):
        self.assertTrue(is_mcp_request(self._req("mcp/0.1.0 tool=x")))
        self.assertTrue(is_mcp_request(self._req("  MCP/0.2.0")))
        self.assertTrue(is_mcp_request(self._req(b"mcp/0.1.0")))

    def test_otros_clientes_no(self):
        self.assertFalse(is_mcp_request(self._req(None)))
        self.assertFalse(is_mcp_request(self._req("")))
        self.assertFalse(is_mcp_request(self._req("n8n/1.0 mcp/")))
