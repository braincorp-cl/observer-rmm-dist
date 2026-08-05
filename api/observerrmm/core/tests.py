import json
import os
from unittest.mock import patch

import requests
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

# from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from model_bakery import baker
from rest_framework.authtoken.models import Token

# from agents.models import Agent
from core.utils import (
    _b64_to_hex,
    _mesh_id_to_hex,
    get_core_settings,
    get_mesh_ws_url,
    get_meshagent_url,
    strip_ai_reasoning,
)

# from logs.models import PendingAction
from observerrmm.constants import (  # PAAction,; PAStatus,
    CONFIG_MGMT_CMDS,
    CustomFieldModel,
    MeshAgentIdent,
)
from observerrmm.helpers import get_nats_hosts, get_nats_url
from observerrmm.test import ObserverTestCase, missing_pk

from .consumers import DashInfo
from .models import CoreSettings, CustomField, GlobalKVStore, URLAction
from .serializers import (
    CLEAR_SECRET,
    SECRET_FIELDS,
    CustomFieldSerializer,
    KeyStoreSerializer,
    URLActionSerializer,
)
from .tasks import core_maintenance_tasks  # , resolve_pending_actions


class TestCodeSign(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()
        self.url = "/core/codesign/"

    def test_get_codesign(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("get", self.url)

    @patch("requests.post")
    def test_edit_codesign_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError()
        data = {"token": "token123"}
        r = self.client.patch(self.url, data, format="json")
        self.assertEqual(r.status_code, 400)

        self.check_not_authenticated("patch", self.url)

    def test_delete_codesign(self):
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("delete", self.url)


class TestConsumers(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()

    @database_sync_to_async
    def get_token(self):
        token = Token.objects.create(user=self.john)
        return token.key

    async def test_dash_info(self):
        key = self.get_token()
        communicator = WebsocketCommunicator(
            DashInfo.as_asgi(), f"/ws/dashinfo/?access_token={key}"
        )
        communicator.scope["user"] = self.john
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()


class TestCoreTasks(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()

    def test_core_maintenance_tasks(self):
        core_maintenance_tasks()
        self.assertTrue(True)

    def test_dashboard_info(self):
        url = "/core/dashinfo/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("get", url)

    def test_vue_version(self):
        url = "/core/version/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("get", url)

    def test_get_core_settings(self):
        url = "/core/settings/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("get", url)

    def test_edit_coresettings(self):
        url = "/core/settings/"
        # setup
        baker.make("automation.Policy", _quantity=2)
        # test normal request
        data = {
            "smtp_from_email": "newexample@example.com",
            "mesh_company_name": "BrainCorp",
        }
        r = self.client.put(url, data)
        self.assertEqual(r.status_code, 200)
        core = get_core_settings()
        self.assertEqual(core.smtp_from_email, "newexample@example.com")
        self.assertEqual(core.mesh_company_name, "BrainCorp")

        # test to_representation
        r = self.client.get(url)
        self.assertEqual(r.data["smtp_from_email"], "newexample@example.com")
        self.assertEqual(r.data["mesh_company_name"], "BrainCorp")
        # el token es un secreto: sale vacío y sólo se anuncia que está puesto
        self.assertEqual(r.data["mesh_token"], "")
        self.assertTrue(r.data["mesh_token_set"])

        self.check_not_authenticated("put", url)

    def test_mesh_integration_is_read_only(self):
        """La integración con MeshCentral no se configura desde la consola.

        Los datos de conexión vienen de local_settings.py y `initial_mesh_setup`
        los copia acá. El grupo de dispositivos es peor: nadie lo resincroniza,
        así que un nombre equivocado deja sin instaladores ni altas de agentes de
        forma permanente. Y apagar la sincronización de permisos borra todos los
        usuarios de MeshCentral.
        """
        url = "/core/settings/"
        core = get_core_settings()
        core.mesh_site = "https://mesh.interno"
        core.mesh_username = "observer"
        core.mesh_token = "token-de-verdad"
        core.mesh_device_group = "ObserverRMM"
        core.sync_mesh_with_ormm = True
        core.save()

        r = self.client.put(
            url,
            {
                "smtp_from_email": "nuevo@example.com",
                "mesh_site": "https://mesh.del-atacante",
                "mesh_username": "intruso",
                "mesh_token": "token-falso",
                "mesh_device_group": "GrupoQueNoExiste",
                "sync_mesh_with_ormm": False,
            },
        )
        self.assertEqual(r.status_code, 200)

        core = get_core_settings()
        self.assertEqual(core.mesh_site, "https://mesh.interno")
        self.assertEqual(core.mesh_username, "observer")
        self.assertEqual(core.mesh_token, "token-de-verdad")
        self.assertEqual(core.mesh_device_group, "ObserverRMM")
        self.assertTrue(core.sync_mesh_with_ormm)
        # lo que sí se puede editar en la misma petición no queda bloqueado
        self.assertEqual(core.smtp_from_email, "nuevo@example.com")

        # el centinela de borrado tampoco alcanza al token de Mesh
        r = self.client.put(url, {"mesh_token": CLEAR_SECRET})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get_core_settings().mesh_token, "token-de-verdad")

    def test_mesh_company_name_stays_editable(self):
        """Lo único cosmético de esa pestaña sigue siendo editable."""
        url = "/core/settings/"
        r = self.client.put(url, {"mesh_company_name": "BrainCorp"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get_core_settings().mesh_company_name, "BrainCorp")

    @override_settings(HOSTED=True)
    def test_hosted_edit_coresettings(self):
        url = "/core/settings/"
        baker.make("automation.Policy", _quantity=2)
        data = {
            "smtp_from_email": "newexample1@example.com",
            "mesh_token": "abc123",
            "mesh_site": "https://mesh15534.example.com",
            "mesh_username": "jane",
            "sync_mesh_with_ormm": False,
        }
        r = self.client.put(url, data)
        self.assertEqual(r.status_code, 200)
        core = get_core_settings()
        self.assertEqual(core.smtp_from_email, "newexample1@example.com")
        self.assertIn("41410834b8bb4481446027f8", core.mesh_token)  # type: ignore
        self.assertTrue(core.sync_mesh_with_ormm)
        if "GHACTIONS" in os.environ:
            self.assertEqual(core.mesh_site, "https://example.com")
            self.assertEqual(core.mesh_username, "pipeline")

        # test to_representation
        r = self.client.get(url)
        self.assertEqual(r.data["smtp_from_email"], "newexample1@example.com")
        self.assertEqual(r.data["mesh_token"], "n/a")
        self.assertEqual(r.data["mesh_site"], "n/a")
        self.assertEqual(r.data["mesh_username"], "n/a")
        self.assertTrue(r.data["sync_mesh_with_ormm"])

        self.check_not_authenticated("put", url)

    def test_secrets_never_leave_the_backend(self):
        """Los 4 secretos de la configuración global salen vacíos.

        Enmascararlos en el formulario no basta: antes viajaban en claro dentro
        del JSON, o sea que quedaban a la vista en las herramientas del
        navegador y en cualquier proxy que registrara la respuesta.
        """
        url = "/core/settings/"
        core = get_core_settings()
        core.smtp_host_password = "clave-smtp"
        core.twilio_auth_token = "token-twilio"
        core.mesh_token = "token-mesh"
        core.open_ai_token = "sk-secreta"
        core.save()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for field in SECRET_FIELDS:
            self.assertEqual(r.data[field], "")
            self.assertTrue(r.data[f"{field}_set"])

        # el JSON serializado tampoco los lleva por otra vía
        body = json.dumps(r.data, default=str)
        for value in ("clave-smtp", "token-twilio", "token-mesh", "sk-secreta"):
            self.assertNotIn(value, body)

    def test_secret_not_set_reports_false(self):
        url = "/core/settings/"
        core = get_core_settings()
        core.open_ai_token = ""
        core.save()

        r = self.client.get(url)
        self.assertEqual(r.data["open_ai_token"], "")
        self.assertFalse(r.data["open_ai_token_set"])

    def test_empty_secret_preserves_stored_value(self):
        """Guardar el formulario sin tocar un secreto no lo borra.

        Es el caso normal: la consola ya no conoce el valor, así que manda
        vacío. Si vacío significara "borrar", grabar la pestaña de correo
        dejaría sin clave al asistente de IA.
        """
        url = "/core/settings/"
        core = get_core_settings()
        core.smtp_host_password = "clave-smtp"
        core.open_ai_token = "sk-secreta"
        core.save()

        r = self.client.put(
            url,
            {
                "smtp_from_email": "nuevo@example.com",
                "smtp_host_password": "",
                "open_ai_token": "",
            },
        )
        self.assertEqual(r.status_code, 200)

        core = get_core_settings()
        self.assertEqual(core.smtp_host_password, "clave-smtp")
        self.assertEqual(core.open_ai_token, "sk-secreta")
        self.assertEqual(core.smtp_from_email, "nuevo@example.com")

    def test_new_secret_replaces_stored_value(self):
        url = "/core/settings/"
        core = get_core_settings()
        core.open_ai_token = "sk-vieja"
        core.save()

        r = self.client.put(url, {"open_ai_token": "sk-nueva"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get_core_settings().open_ai_token, "sk-nueva")

    def test_clear_sentinel_removes_secret(self):
        """Sólo el centinela borra: es la única forma de apagar la integración."""
        url = "/core/settings/"
        core = get_core_settings()
        core.open_ai_token = "sk-secreta"
        core.twilio_auth_token = "token-twilio"
        core.save()

        r = self.client.put(url, {"open_ai_token": CLEAR_SECRET})
        self.assertEqual(r.status_code, 200)

        core = get_core_settings()
        self.assertEqual(core.open_ai_token, "")
        # borrar uno no toca a los demás
        self.assertEqual(core.twilio_auth_token, "token-twilio")

        r = self.client.get(url)
        self.assertFalse(r.data["open_ai_token_set"])

    def test_audit_serializer_masks_secrets(self):
        """El log de auditoría se consulta desde la consola: tampoco los lleva."""
        core = get_core_settings()
        core.smtp_host_password = "clave-smtp"
        core.open_ai_token = "sk-secreta"
        core.save()

        serialized = CoreSettings.serialize(core)
        self.assertEqual(serialized["smtp_host_password"], "")
        self.assertEqual(serialized["open_ai_token"], "")
        self.assertNotIn("clave-smtp", json.dumps(serialized, default=str))

    @patch("observerrmm.utils.reload_nats")
    @patch("autotasks.tasks.remove_orphaned_win_tasks.delay")
    def test_ui_maintenance_actions(self, remove_orphaned_win_tasks, reload_nats):
        url = "/core/servermaintenance/"

        baker.make_recipe("agents.online_agent", _quantity=3)

        # test with empty data
        r = self.client.post(url, {})
        self.assertEqual(r.status_code, 400)

        # test with invalid action
        data = {"action": "invalid_action"}

        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 400)

        # test reload nats action
        data = {"action": "reload_nats"}
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)
        reload_nats.assert_called_once()

        # test prune db with no tables
        data = {"action": "prune_db"}
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 400)

        # test prune db with tables
        data = {
            "action": "prune_db",
            "prune_tables": ["audit_logs", "alerts", "pending_actions"],
        }
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)

        # test remove orphaned tasks
        data = {"action": "rm_orphaned_tasks"}
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)
        remove_orphaned_win_tasks.assert_called()

        self.check_not_authenticated("post", url)

    def test_get_custom_fields(self):
        url = "/core/customfields/"

        # setup
        custom_fields = baker.make("core.CustomField", _quantity=2)

        r = self.client.get(url)
        serializer = CustomFieldSerializer(custom_fields, many=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)
        self.assertEqual(r.data, serializer.data)

        self.check_not_authenticated("get", url)

    def test_get_custom_fields_by_model(self):
        url = "/core/customfields/"

        # setup
        baker.make("core.CustomField", model=CustomFieldModel.AGENT, _quantity=5)
        baker.make("core.CustomField", model="client", _quantity=5)

        # will error if request invalid
        r = self.client.patch(url, {"invalid": ""})
        self.assertEqual(r.status_code, 400)

        data = {"model": "agent"}
        r = self.client.patch(url, data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 5)

        self.check_not_authenticated("patch", url)

    def test_add_custom_field(self):
        url = "/core/customfields/"

        data = {"model": "client", "type": "text", "name": "Field"}
        r = self.client.patch(url, data)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("post", url)

    def test_get_custom_field(self):
        # setup
        custom_field = baker.make("core.CustomField")

        # test not found
        r = self.client.get(f"/core/customfields/{missing_pk(CustomField)}/")
        self.assertEqual(r.status_code, 404)

        url = f"/core/customfields/{custom_field.id}/"
        r = self.client.get(url)
        serializer = CustomFieldSerializer(custom_field)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, serializer.data)

        self.check_not_authenticated("get", url)

    def test_update_custom_field(self):
        # setup
        custom_field = baker.make("core.CustomField")

        # test not found
        r = self.client.put(f"/core/customfields/{missing_pk(CustomField)}/")
        self.assertEqual(r.status_code, 404)

        url = f"/core/customfields/{custom_field.id}/"
        data = {"type": "single", "options": ["ione", "two", "three"]}
        r = self.client.put(url, data)
        self.assertEqual(r.status_code, 200)

        new_field = CustomField.objects.get(pk=custom_field.id)
        self.assertEqual(new_field.type, data["type"])
        self.assertEqual(new_field.options, data["options"])

        self.check_not_authenticated("put", url)

    def test_delete_custom_field(self):
        # setup
        custom_field = baker.make("core.CustomField")

        # test not found
        r = self.client.delete(f"/core/customfields/{missing_pk(CustomField)}/")
        self.assertEqual(r.status_code, 404)

        url = f"/core/customfields/{custom_field.id}/"
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 200)

        self.assertFalse(CustomField.objects.filter(pk=custom_field.id).exists())

        self.check_not_authenticated("delete", url)

    def test_get_keystore(self):
        url = "/core/keystore/"

        # setup
        keys = baker.make("core.GlobalKVStore", _quantity=2)

        r = self.client.get(url)
        serializer = KeyStoreSerializer(keys, many=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)
        self.assertEqual(r.data, serializer.data)

        self.check_not_authenticated("get", url)

    def test_add_keystore(self):
        url = "/core/keystore/"

        data = {"name": "test", "value": "text"}
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("post", url)

    def test_update_keystore(self):
        # setup
        key = baker.make("core.GlobalKVStore")

        # test not found
        r = self.client.put(f"/core/keystore/{missing_pk(GlobalKVStore)}/")
        self.assertEqual(r.status_code, 404)

        url = f"/core/keystore/{key.id}/"
        data = {"name": "test", "value": "text"}
        r = self.client.put(url, data)
        self.assertEqual(r.status_code, 200)

        new_key = GlobalKVStore.objects.get(pk=key.id)
        self.assertEqual(new_key.name, data["name"])
        self.assertEqual(new_key.value, data["value"])

        self.check_not_authenticated("put", url)

    def test_delete_keystore(self):
        # setup
        key = baker.make("core.GlobalKVStore")

        # test not found
        r = self.client.delete(f"/core/keystore/{missing_pk(GlobalKVStore)}/")
        self.assertEqual(r.status_code, 404)

        url = f"/core/keystore/{key.id}/"
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 200)

        self.assertFalse(GlobalKVStore.objects.filter(pk=key.id).exists())

        self.check_not_authenticated("delete", url)

    def test_get_urlaction(self):
        url = "/core/urlaction/"

        # setup
        action = baker.make("core.URLAction", _quantity=2)

        r = self.client.get(url)
        serializer = URLActionSerializer(action, many=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)
        self.assertEqual(r.data, serializer.data)

        self.check_not_authenticated("get", url)

    def test_add_urlaction(self):
        url = "/core/urlaction/"

        data = {"name": "name", "desc": "desc", "pattern": "pattern"}
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("post", url)

    def test_update_urlaction(self):
        # setup
        action = baker.make("core.URLAction")

        # test not found
        r = self.client.put(f"/core/urlaction/{missing_pk(URLAction)}/")
        self.assertEqual(r.status_code, 404)

        url = f"/core/urlaction/{action.id}/"
        data = {"name": "test", "pattern": "text"}
        r = self.client.put(url, data)
        self.assertEqual(r.status_code, 200)

        new_action = URLAction.objects.get(pk=action.id)
        self.assertEqual(new_action.name, data["name"])
        self.assertEqual(new_action.pattern, data["pattern"])

        self.check_not_authenticated("put", url)

    def test_delete_urlaction(self):
        # setup
        action = baker.make("core.URLAction")

        # test not found
        r = self.client.delete(f"/core/urlaction/{missing_pk(URLAction)}/")
        self.assertEqual(r.status_code, 404)

        url = f"/core/urlaction/{action.id}/"
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 200)

        self.assertFalse(URLAction.objects.filter(pk=action.id).exists())

        self.check_not_authenticated("delete", url)

    def test_run_url_action(self):
        self.maxDiff = None
        # setup
        agent = baker.make_recipe(
            "agents.agent", agent_id="123123-assdss4s-343-sds545-45dfdf|DESKTOP"
        )
        baker.make("core.GlobalKVStore", name="Test Name", value="value with space")
        action = baker.make(
            "core.URLAction",
            pattern="https://remote.example.com/connect?globalstore={{global.Test Name}}&client_name={{client.name}}&site id={{site.id}}&agent_id={{agent.agent_id}}",
        )

        url = "/core/urlaction/run/"
        # test not found
        r = self.client.patch(url, {"agent_id": 500, "action": 500})
        self.assertEqual(r.status_code, 404)

        data = {"agent_id": agent.agent_id, "action": action.id}
        r = self.client.patch(url, data)
        self.assertEqual(r.status_code, 200)

        self.assertEqual(
            r.data,
            f"https://remote.example.com/connect?globalstore=value%20with%20space&client_name={agent.client.name}&site%20id={agent.site.id}&agent_id=123123-assdss4s-343-sds545-45dfdf%7CDESKTOP",
        )

        self.check_not_authenticated("patch", url)

    def test_clear_cache(self):
        url = "/core/clearcache/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("get", url)

    # def test_resolved_pending_agentupdate_task(self):
    #     online = baker.make_recipe("agents.online_agent", version="2.0.0", _quantity=20)
    #     offline = baker.make_recipe(
    #         "agents.offline_agent", version="2.0.0", _quantity=20
    #     )
    #     agents = online + offline
    #     for agent in agents:
    #         baker.make_recipe("logs.pending_agentupdate_action", agent=agent)

    #     Agent.objects.update(version=settings.LATEST_AGENT_VER)

    #     resolve_pending_actions()

    #     complete = PendingAction.objects.filter(
    #         action_type=PAAction.AGENT_UPDATE, status=PAStatus.COMPLETED
    #     ).count()
    #     old = PendingAction.objects.filter(
    #         action_type=PAAction.AGENT_UPDATE, status=PAStatus.PENDING
    #     ).count()

    #     self.assertEqual(complete, 20)
    #     self.assertEqual(old, 20)


class TestCoreMgmtCommands(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    def test_get_config(self):
        for cmd in CONFIG_MGMT_CMDS:
            call_command("get_config", cmd)


class TestNatsUrls(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    def test_standard_install(self):
        self.assertEqual(get_nats_url(), "nats://127.0.0.1:4222")

    @override_settings(
        NATS_STANDARD_PORT=5000,
        USE_NATS_STANDARD=True,
        ALLOWED_HOSTS=["api.example.com"],
    )
    def test_custom_port_nats_standard(self):
        self.assertEqual(get_nats_url(), "tls://api.example.com:5000")

    @override_settings(DOCKER_BUILD=True, ALLOWED_HOSTS=["api.example.com"])
    def test_docker_nats(self):
        self.assertEqual(get_nats_url(), "nats://api.example.com:4222")

    @patch.dict("os.environ", {"NATS_CONNECT_HOST": "172.20.4.3"})
    @override_settings(ALLOWED_HOSTS=["api.example.com"])
    def test_custom_connect_host_env(self):
        self.assertEqual(get_nats_url(), "nats://172.20.4.3:4222")

    def test_standard_nats_hosts(self):
        self.assertEqual(get_nats_hosts(), ("127.0.0.1", "127.0.0.1", "127.0.0.1"))

    @override_settings(DOCKER_BUILD=True, ALLOWED_HOSTS=["api.example.com"])
    def test_docker_nats_hosts(self):
        self.assertEqual(get_nats_hosts(), ("0.0.0.0", "0.0.0.0", "api.example.com"))


class TestMeshWSUrl(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    @patch("core.utils.get_auth_token")
    def test_standard_install(self, mock_token):
        mock_token.return_value = "abc123"
        self.assertEqual(
            get_mesh_ws_url(), "ws://127.0.0.1:4430/control.ashx?auth=abc123"
        )

    @patch("core.utils.get_auth_token")
    @override_settings(MESH_PORT=8876)
    def test_standard_install_custom_port(self, mock_token):
        mock_token.return_value = "abc123"
        self.assertEqual(
            get_mesh_ws_url(), "ws://127.0.0.1:8876/control.ashx?auth=abc123"
        )

    @patch("core.utils.get_auth_token")
    @override_settings(DOCKER_BUILD=True, MESH_WS_URL="ws://observer-meshcentral:4443")
    def test_docker_install(self, mock_token):
        mock_token.return_value = "abc123"
        self.assertEqual(
            get_mesh_ws_url(), "ws://observer-meshcentral:4443/control.ashx?auth=abc123"
        )

    @patch("core.utils.get_auth_token")
    @override_settings(USE_EXTERNAL_MESH=True)
    def test_external_mesh(self, mock_token):
        mock_token.return_value = "abc123"

        from core.models import CoreSettings

        core = CoreSettings.objects.first()
        core.mesh_site = "https://mesh.external.com"  # type: ignore
        core.save(update_fields=["mesh_site"])  # type: ignore
        self.assertEqual(
            get_mesh_ws_url(), "wss://mesh.external.com/control.ashx?auth=abc123"
        )


class TestCorePermissions(ObserverTestCase):
    def setUp(self):
        self.setup_client()
        self.setup_coresettings()


class TestCoreUtils(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    def test_get_meshagent_url_standard(self):
        r = get_meshagent_url(
            ident=MeshAgentIdent.DARWIN_UNIVERSAL,
            plat="darwin",
            mesh_site="https://mesh.example.com",
            mesh_device_id="abc123",
        )
        self.assertEqual(
            r,
            "http://127.0.0.1:4430/meshagents?id=abc123&installflags=2&meshinstall=10005",
        )

        r = get_meshagent_url(
            ident=MeshAgentIdent.WIN64,
            plat="windows",
            mesh_site="https://mesh.example.com",
            mesh_device_id="abc123",
        )
        self.assertEqual(
            r,
            "http://127.0.0.1:4430/meshagents?id=4&meshid=abc123&installflags=0",
        )

    @override_settings(DOCKER_BUILD=True)
    @override_settings(MESH_WS_URL="ws://observer-meshcentral:4443")
    def test_get_meshagent_url_docker(self):
        r = get_meshagent_url(
            ident=MeshAgentIdent.DARWIN_UNIVERSAL,
            plat="darwin",
            mesh_site="https://mesh.example.com",
            mesh_device_id="abc123",
        )
        self.assertEqual(
            r,
            "http://observer-meshcentral:4443/meshagents?id=abc123&installflags=2&meshinstall=10005",
        )

        r = get_meshagent_url(
            ident=MeshAgentIdent.WIN64,
            plat="windows",
            mesh_site="https://mesh.example.com",
            mesh_device_id="abc123",
        )
        self.assertEqual(
            r,
            "http://observer-meshcentral:4443/meshagents?id=4&meshid=abc123&installflags=0",
        )

    @override_settings(USE_EXTERNAL_MESH=True)
    def test_get_meshagent_url_external_mesh(self):
        r = get_meshagent_url(
            ident=MeshAgentIdent.DARWIN_UNIVERSAL,
            plat="darwin",
            mesh_site="https://mesh.example.com",
            mesh_device_id="abc123",
        )
        self.assertEqual(
            r,
            "https://mesh.example.com/meshagents?id=abc123&installflags=2&meshinstall=10005",
        )

        r = get_meshagent_url(
            ident=MeshAgentIdent.WIN64,
            plat="windows",
            mesh_site="https://mesh.example.com",
            mesh_device_id="abc123",
        )
        self.assertEqual(
            r,
            "https://mesh.example.com/meshagents?id=4&meshid=abc123&installflags=0",
        )

    @override_settings(MESH_PORT=8653)
    def test_get_meshagent_url_mesh_port(self):
        r = get_meshagent_url(
            ident=MeshAgentIdent.DARWIN_UNIVERSAL,
            plat="darwin",
            mesh_site="https://mesh.example.com",
            mesh_device_id="abc123",
        )
        self.assertEqual(
            r,
            "http://127.0.0.1:8653/meshagents?id=abc123&installflags=2&meshinstall=10005",
        )

        r = get_meshagent_url(
            ident=MeshAgentIdent.WIN64,
            plat="windows",
            mesh_site="https://mesh.example.com",
            mesh_device_id="abc123",
        )
        self.assertEqual(
            r,
            "http://127.0.0.1:8653/meshagents?id=4&meshid=abc123&installflags=0",
        )


class TestMeshIdToHex(ObserverTestCase):
    """T020 de la 031: `_mesh_id_to_hex` descarta, no revienta.

    El endpoint `/api/v3/syncmesh/` lo llama en cada ciclo de cada agente
    (~13-20 min), y el alta en `/api/v3/newagent/` también. Un nodeid con
    basura devolvía HTTP 500 desde un `b64decode` sin protección.
    """

    # 96 hex = SHA-384, el largo real de un node id de MeshCentral.
    HEX_ID = "B5A56374" + "A1B2C3D4" * 10 + "D917AAD4"

    def test_hex_passthrough_uppercased(self):
        self.assertEqual(_mesh_id_to_hex(self.HEX_ID.lower()), self.HEX_ID)

    def test_base64_roundtrip(self):
        # `_b64_to_hex` produce la forma en que el id viaja por URL
        # (`/`→`$`, `+`→`@`); `_mesh_id_to_hex` la deshace.
        self.assertEqual(_mesh_id_to_hex(_b64_to_hex(self.HEX_ID)), self.HEX_ID)

    def test_garbage_returns_none_instead_of_raising(self):
        # Esta era exactamente la entrada que devolvía HTTP 500.
        for garbage in ("!!!!", "no-es-un-nodeid", "%%%", "\x00\x01"):
            with self.subTest(garbage=garbage):
                self.assertIsNone(_mesh_id_to_hex(garbage))

    def test_bad_padding_returns_none(self):
        # Este caso destapó que `validate=True` NO valida el padding en Python
        # 3.11, que es el que corre en los servidores: devolvía '414243' en 3.11
        # y None en 3.13 (Python 3.12 endureció `binascii.a2b_base64`). Lo cazó
        # el CI el primer día que corrió, después de que la verificación local
        # —hecha en 3.13— lo diera por cerrado.
        self.assertIsNone(_mesh_id_to_hex("QUJD="))

    def test_valid_but_too_short_returns_none(self):
        # "QQ" es base64 VÁLIDO y decodifica a '41'. El alfabeto no alcanza:
        # hace falta el piso de largo, el mismo que ya exigen el agente y los
        # instaladores.
        self.assertIsNone(_mesh_id_to_hex("QQ"))

    def test_the_mac_that_broke_a_real_machine(self):
        # `0A179C9229E0` es hexadecimal legítimo, así que la primera rama lo
        # aceptaba tal cual. Es el valor con el que HP-ProOne-400 quedó
        # registrado el 2026-07-28, y con el que «Tomar control» dejó de
        # funcionar sin ningún aviso.
        self.assertIsNone(_mesh_id_to_hex("0A179C9229E0"))

    def test_boundary_of_the_length_floor(self):
        self.assertIsNone(_mesh_id_to_hex("AB" * 31))  # 62 hex → descartado
        self.assertEqual(_mesh_id_to_hex("ab" * 32), "AB" * 32)  # 64 → pasa

    def test_non_alphabet_chars_are_not_silently_stripped(self):
        # Con `validate=False` (el default de b64decode) esto NO lanza: los
        # caracteres fuera del alfabeto se descartan y sale un hex más corto,
        # plausible y falso. Preferimos None a un id inventado.
        self.assertIsNone(_mesh_id_to_hex("QUJD****"))


class TestOpenAICodeCompletion(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()
        self.url = "/core/openai/generate/"
        self.coresettings.open_ai_token = "sk-test-token"
        self.coresettings.save()

    @patch("core.views.requests.post")
    def test_generate_success_default_base_url(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Get-Process"}}]
        }

        r = self.client.post(
            self.url,
            {"prompt": "powershell code that lists processes"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, "Get-Process")

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(kwargs["timeout"], 120)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test-token")
        body = json.loads(kwargs["data"])
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(
            body["messages"][1]["content"],
            "powershell code that lists processes",
        )
        self.assertEqual(body["max_tokens"], 4000)
        # sin temperature configurada el campo NO viaja (kimi-k3 rechaza con
        # 400 cualquier valor distinto de su default)
        self.assertNotIn("temperature", body)
        self.assertNotIn("n", body)
        self.assertNotIn("stop", body)

        self.check_not_authenticated("post", self.url)

    @patch("core.views.requests.post")
    def test_generate_uses_custom_base_url(self, mock_post):
        # trailing slash must be stripped (Moonshot AI config example)
        self.coresettings.open_ai_base_url = "https://api.moonshot.ai/v1/"
        self.coresettings.open_ai_model = "kimi-k3"
        self.coresettings.save()

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "echo hello"}}]
        }

        r = self.client.post(
            self.url, {"prompt": "shell code that prints hello"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, "echo hello")

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.moonshot.ai/v1/chat/completions")
        body = json.loads(kwargs["data"])
        self.assertEqual(body["model"], "kimi-k3")

    @patch("core.views.requests.post")
    def test_generate_uses_configured_max_tokens(self, mock_post):
        self.coresettings.open_ai_max_tokens = 16000
        self.coresettings.save()

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "echo hello"}}]
        }

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 200)

        _, kwargs = mock_post.call_args
        body = json.loads(kwargs["data"])
        self.assertEqual(body["max_tokens"], 16000)

    @patch("core.views.requests.post")
    def test_generate_max_tokens_zero_falls_back(self, mock_post):
        # 0 sería rechazado por el proveedor: se cae al valor por defecto
        self.coresettings.open_ai_max_tokens = 0
        self.coresettings.save()

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "echo hello"}}]
        }

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 200)

        _, kwargs = mock_post.call_args
        body = json.loads(kwargs["data"])
        self.assertEqual(body["max_tokens"], 4000)

    @patch("core.views.requests.post")
    def test_generate_sends_temperature_only_when_configured(self, mock_post):
        self.coresettings.open_ai_temperature = 0.5
        self.coresettings.save()

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "echo hello"}}]
        }

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 200)

        _, kwargs = mock_post.call_args
        body = json.loads(kwargs["data"])
        self.assertEqual(body["temperature"], 0.5)

    @patch("core.views.requests.post")
    def test_generate_temperature_zero_is_sent(self, mock_post):
        # 0 es un valor legítimo (determinista): no debe confundirse con "vacío"
        self.coresettings.open_ai_temperature = 0
        self.coresettings.save()

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "echo hello"}}]
        }

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 200)

        _, kwargs = mock_post.call_args
        body = json.loads(kwargs["data"])
        self.assertEqual(body["temperature"], 0)

    @patch("core.views.requests.post")
    def test_generate_http_error_status(self, mock_post):
        mock_post.return_value.status_code = 401
        mock_post.return_value.text = "<html>unauthorized</html>"

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("401", r.data)

    @patch("core.views.requests.post")
    def test_generate_api_error_payload(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "error": {"message": "rate limited"}
        }

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("rate limited", r.data)

    @patch("core.views.requests.post")
    def test_generate_invalid_json(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = ValueError("no json")

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalid response", r.data)

    @patch("core.views.requests.post")
    def test_generate_unexpected_payload_shape(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"unexpected": True}

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("unexpected response format", r.data)

    @patch("core.views.requests.post")
    def test_generate_connection_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError()

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_generate_no_token_configured(self):
        self.coresettings.open_ai_token = ""
        self.coresettings.save()

        r = self.client.post(self.url, {"prompt": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("API key not found", r.data)

    def test_generate_missing_prompt(self):
        r = self.client.post(self.url, {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("prompt", r.data)

    @patch("core.views.requests.post")
    def test_generate_strips_model_reasoning(self, mock_post):
        """La vista devuelve solo la respuesta, no el razonamiento del modelo."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "Get-CimInstance Win32_LogicalDisk | Select-Object X\n"
                            "}</think>Get-Volume | Format-Table"
                        )
                    }
                }
            ]
        }

        r = self.client.post(self.url, {"prompt": "espacio libre"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, "Get-Volume | Format-Table")
        self.assertNotIn("think", r.data)


class TestStripAiReasoning(ObserverTestCase):
    """El razonamiento de los modelos que "piensan" no debe llegar al editor.

    El caso que motivó esto se midió contra un modelo gratuito de OpenRouter: el
    `content` traía un borrador completo, después `</think>`, y solo entonces la
    respuesta. La etiqueta de APERTURA no venía, así que un `<think>.*?</think>` no
    habría sacado nada.
    """

    def test_deja_el_codigo_intacto_si_no_hay_razonamiento(self):
        codigo = 'Get-CimInstance -ClassName Win32_LogicalDisk\nWrite-Output "listo"'
        self.assertEqual(strip_ai_reasoning(codigo), codigo)

    def test_corta_cuando_solo_viene_la_etiqueta_de_cierre(self):
        # el caso real: reflexión sin <think> de apertura + </think> + respuesta
        crudo = "Get-Process | Sort-Object CPU\n}</think>Get-Service -Name Spooler"
        self.assertEqual(strip_ai_reasoning(crudo), "Get-Service -Name Spooler")

    def test_saca_el_bloque_bien_formado(self):
        crudo = "<think>a ver, primero enumero los discos</think>\nGet-Volume"
        self.assertEqual(strip_ai_reasoning(crudo), "Get-Volume")

    def test_corta_en_el_ULTIMO_cierre(self):
        crudo = "<think>uno</think>borrador viejo<think>dos</think>Get-Date"
        self.assertEqual(strip_ai_reasoning(crudo), "Get-Date")

    def test_apertura_sin_cierre_deja_lo_previo(self):
        crudo = "Get-Date\n<think>me quedé pensando y no cerré"
        self.assertEqual(strip_ai_reasoning(crudo), "Get-Date")

    def test_no_devuelve_vacio_si_todo_era_razonamiento(self):
        # sin respuesta detrás del cierre, es mejor entregar algo revisable que un
        # editor en blanco: el operador ve qué pasó en vez de un silencio
        crudo = "<think>pensé pero no escribí código</think>"
        self.assertEqual(strip_ai_reasoning(crudo), "pensé pero no escribí código")

    def test_variante_thinking_y_mayusculas(self):
        crudo = "<THINKING>ruido</Thinking>Get-Host"
        self.assertEqual(strip_ai_reasoning(crudo), "Get-Host")

    def test_tolera_lo_que_no_es_texto(self):
        self.assertIsNone(strip_ai_reasoning(None))
