from unittest.mock import patch

from django.test import override_settings
from model_bakery import baker, seq

from accounts.models import APIKey, Role, User
from accounts.serializers import APIKeySerializer
from accounts.utils import can_assign_role, can_manage_user
from logs.models import AuditLog
from observerrmm.constants import (
    AgentDblClick,
    AgentTableTabs,
    AuditActionType,
    ClientTreeSort,
)
from observerrmm.test import ObserverTestCase, missing_pk


class TestAccounts(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()
        self.bob = User(username="bob")
        self.bob.set_password("hunter2")
        self.bob.save()

    def test_check_creds(self):
        url = "/v2/checkcreds/"

        data = {"username": "bob", "password": "hunter2"}
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("totp", r.data.keys())
        self.assertEqual(r.data["totp"], False)

        data = {"username": "bob", "password": "a3asdsa2314"}
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "Bad credentials")

        data = {"username": "billy", "password": "hunter2"}
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "Bad credentials")

        self.bob.totp_key = "AB5RI6YPFTZAS52G"
        self.bob.save()
        data = {"username": "bob", "password": "hunter2"}
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["totp"], True)

        # test user set to block dashboard logins
        self.bob.block_dashboard_login = True
        self.bob.save()
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("pyotp.TOTP.verify")
    def test_login_view(self, mock_verify):
        url = "/v2/login/"

        # `bob` necesita `totp_key` para representar a un usuario que YA completó
        # el alta de 2FA, que es el único que puede pasar por `/v2/login/`.
        # Este test venía de upstream esperando 200 sin clave, y quedó roto por un
        # endurecimiento nuestro deliberado: `396c82d` (GAP-043) agregó el guard
        # `if not user.totp_key` para que un POST directo devuelva 400 en vez de
        # reventar en `pyotp.TOTP(None)` con un HTTP 500. El flujo real pasa por
        # `CheckCredsV2` → alta de TOTP antes de llegar acá.
        self.bob.totp_key = "AB5RI6YPFTZAS52G"
        self.bob.save()

        mock_verify.return_value = True
        data = {"username": "bob", "password": "hunter2", "twofactor": "123456"}
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("expiry", r.data.keys())
        self.assertIn("token", r.data.keys())

        mock_verify.return_value = False
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "Bad credentials")

        mock_verify.return_value = True
        data = {"username": "bob", "password": "asd234234asd", "twofactor": "123456"}
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("non_field_errors", r.data.keys())

    @patch("pyotp.TOTP.verify")
    def test_login_view_rejects_user_without_totp_key(self, mock_verify):
        """GAP-043: sin `totp_key` la respuesta es 400 limpio, no un 500.

        El caso que el arreglo cerró: `pyotp.TOTP(None)` reventaba. Este test es
        la red que faltaba — el guard llevaba desde `396c82d` sin cobertura, y el
        test de al lado quedó rojo en su lugar.
        """
        mock_verify.return_value = True
        self.assertFalse(self.bob.totp_key)

        data = {"username": "bob", "password": "hunter2", "twofactor": "123456"}
        r = self.client.post("/v2/login/", data, format="json")

        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "Bad credentials")

    # @override_settings(DEBUG=True)
    # @patch("pyotp.TOTP.verify")
    # def test_debug_login_view(self, mock_verify):
    #     url = "/login/"
    #     mock_verify.return_value = True

    #     data = {"username": "bob", "password": "hunter2", "twofactor": "sekret"}
    #     r = self.client.post(url, data, format="json")
    #     self.assertEqual(r.status_code, 200)
    #     self.assertIn("expiry", r.data.keys())
    #     self.assertIn("token", r.data.keys())


class TestGetAddUsers(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_get(self):
        url = "/accounts/users/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        assert any(i["username"] == "john" for i in r.json())

        assert not any(
            i["username"] == "71AHC-AA813-HH1BC-AAHH5-00013|DESKTOP-TEST123"
            for i in r.json()
        )

        self.check_not_authenticated("get", url)

    def test_post_add_duplicate(self):
        url = "/accounts/users/"
        data = {
            "username": "john",
            "password": "askdjaskdj",
            "email": "john@example.com",
            "first_name": "",
            "last_name": "",
        }
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 400)

    def test_post_add_new(self):
        url = "/accounts/users/"
        data = {
            "username": "jane",
            "password": "ASd1234asd",
            "email": "jane@example.com",
            "first_name": "",
            "last_name": "",
        }
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, "jane")

        self.check_not_authenticated("post", url)


class GetUpdateDeleteUser(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_get(self):
        url = f"/accounts/{self.john.pk}/users/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["username"], "john")

        url = "/accounts/2345/users/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        self.check_not_authenticated("get", url)

    def test_put(self):
        url = f"/accounts/{self.john.pk}/users/"
        data = {
            "id": self.john.pk,
            "username": "john",
            "email": "johndoe@xlawgaming.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        data["email"] = "aksjdaksjdklasjdlaksdj"
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 400)

        self.check_not_authenticated("put", url)

    @override_settings(ROOT_USER="john")
    def test_put_root_user(self):
        url = f"/accounts/{self.john.pk}/users/"
        data = {
            "id": self.john.pk,
            "username": "john",
            "email": "johndoe@xlawgaming.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 200)

    @override_settings(ROOT_USER="john")
    def test_put_not_root_user(self):
        url = f"/accounts/{self.john.pk}/users/"
        data = {
            "id": self.john.pk,
            "username": "john",
            "email": "johndoe@xlawgaming.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        self.client.force_authenticate(user=self.alice)
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 400)

    def test_delete(self):
        url = f"/accounts/{self.john.pk}/users/"
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 200)

        url = "/accounts/893452/users/"
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 404)

        self.check_not_authenticated("delete", url)

    @override_settings(ROOT_USER="john")
    def test_delete_root_user(self):
        url = f"/accounts/{self.john.pk}/users/"
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 200)

    @override_settings(ROOT_USER="john")
    def test_delete_non_root_user(self):
        url = f"/accounts/{self.john.pk}/users/"
        self.client.force_authenticate(user=self.alice)
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 400)


class TestUserAction(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_post(self):
        url = "/accounts/users/reset/"
        data = {"id": self.john.pk, "password": "3ASDjh2345kJA!@#)#@__123"}
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        data["id"] = 43924
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 404)

        self.check_not_authenticated("post", url)

    @override_settings(ROOT_USER="john")
    def test_post_root_user(self):
        url = "/accounts/users/reset/"
        data = {"id": self.john.pk, "password": "3ASDjh2345kJA!@#)#@__123"}
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)

    @override_settings(ROOT_USER="john")
    def test_post_non_root_user(self):
        url = "/accounts/users/reset/"
        data = {"id": self.john.pk, "password": "3ASDjh2345kJA!@#)#@__123"}
        self.client.force_authenticate(user=self.alice)
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 400)

    def test_put(self):
        url = "/accounts/users/reset/"
        data = {"id": self.john.pk}
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        user = User.objects.get(pk=self.john.pk)
        self.assertEqual(user.totp_key, "")

        self.check_not_authenticated("put", url)

    @override_settings(ROOT_USER="john")
    def test_put_root_user(self):
        url = "/accounts/users/reset/"
        data = {"id": self.john.pk}
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        user = User.objects.get(pk=self.john.pk)
        self.assertEqual(user.totp_key, "")

    @override_settings(ROOT_USER="john")
    def test_put_non_root_user(self):
        url = "/accounts/users/reset/"
        data = {"id": self.john.pk}
        self.client.force_authenticate(user=self.alice)
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 400)

    def test_user_ui(self):
        url = "/accounts/users/ui/"

        data = {
            "dark_mode": True,
            "show_community_scripts": True,
            "agent_dblclick_action": AgentDblClick.EDIT_AGENT,
            "default_agent_tbl_tab": AgentTableTabs.MIXED,
            "client_tree_sort": ClientTreeSort.ALPHA,
            "client_tree_splitter": 14,
            "loading_bar_color": "green",
            "clear_search_when_switching": False,
        }
        r = self.client.patch(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("patch", url)

    def test_user_ui_language(self):
        # i18n (feature 010): la preferencia de idioma de UI se persiste por usuario,
        # espejando el patrón de dark_mode. Default vacío = "sin preferencia".
        url = "/accounts/users/ui/"

        self.john.refresh_from_db()
        self.assertEqual(self.john.language, "")

        # idioma soportado -> persiste
        r = self.client.patch(url, {"language": "es"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.john.refresh_from_db()
        self.assertEqual(self.john.language, "es")

        # idioma no soportado -> 400 de validación (choices), nunca 500 (RN-031);
        # el valor previo no se altera
        r = self.client.patch(url, {"language": "fr"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.john.refresh_from_db()
        self.assertEqual(self.john.language, "es")

        self.check_not_authenticated("patch", url)


class TestUserReset(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_reset_pw(self):
        url = "/accounts/resetpw/"
        data = {"password": "superSekret123456"}
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("put", url)

    def test_reset_2fa(self):
        url = "/accounts/reset2fa/"
        r = self.client.put(url)
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("put", url)


class TestAPIKeyViews(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()

    def test_get_api_keys(self):
        url = "/accounts/apikeys/"
        apikeys = baker.make("accounts.APIKey", key=seq("APIKEY"), _quantity=3)

        serializer = APIKeySerializer(apikeys, many=True)
        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(serializer.data, resp.data)

        self.check_not_authenticated("get", url)

    def test_add_api_keys(self):
        url = "/accounts/apikeys/"

        user = baker.make("accounts.User")
        data = {"name": "Name", "user": user.id, "expiration": None}

        resp = self.client.post(url, data, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(APIKey.objects.filter(name="Name").exists())
        self.assertTrue(APIKey.objects.get(name="Name").key)

        self.check_not_authenticated("post", url)

    def test_modify_api_key(self):
        # test a call where api key doesn't exist
        resp = self.client.put(
            f"/accounts/apikeys/{missing_pk(APIKey)}/", format="json"
        )
        self.assertEqual(resp.status_code, 404)

        apikey = baker.make("accounts.APIKey", name="Test")
        url = f"/accounts/apikeys/{apikey.pk}/"

        data = {"name": "New Name"}

        resp = self.client.put(url, data, format="json")
        self.assertEqual(resp.status_code, 200)
        apikey = APIKey.objects.get(pk=apikey.pk)
        self.assertEqual(apikey.name, "New Name")

        self.check_not_authenticated("put", url)

    def test_delete_api_key(self):
        # test a call where api key doesn't exist
        resp = self.client.delete(
            f"/accounts/apikeys/{missing_pk(APIKey)}/", format="json"
        )
        self.assertEqual(resp.status_code, 404)

        # test delete api key
        apikey = baker.make("accounts.APIKey")
        url = f"/accounts/apikeys/{apikey.pk}/"
        resp = self.client.delete(url, format="json")
        self.assertEqual(resp.status_code, 200)

        self.assertFalse(APIKey.objects.filter(pk=apikey.pk).exists())

        self.check_not_authenticated("delete", url)


class TestTOTPSetup(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_post(self):
        url = "/accounts/users/setup_totp/"
        r = self.client.post(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("username", r.json().keys())
        self.assertIn("totp_key", r.json().keys())
        self.assertIn("qr_url", r.json().keys())
        self.assertEqual("john", r.json()["username"])
        self.assertIn("otpauth://totp", r.json()["qr_url"])

        self.check_not_authenticated("post", url)

    def test_post_totp_set(self):
        url = "/accounts/users/setup_totp/"
        self.john.totp_key = "AB5RI6YPFTZAS52G"
        self.john.save()

        r = self.client.post(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, False)


class TestAPIAuthentication(ObserverTestCase):
    def setUp(self):
        # create User and associate to API Key
        self.user = User.objects.create(username="api_user", is_superuser=True)
        self.api_key = APIKey.objects.create(
            name="Test Token", key="123456", user=self.user
        )

        self.setup_client()

    def test_api_auth(self):
        url = "/clients/"
        # auth should fail if no header set
        self.check_not_authenticated("get", url)

        # invalid api key in header should return code 400
        self.client.credentials(HTTP_X_API_KEY="000000")
        r = self.client.get(url, format="json")
        self.assertEqual(r.status_code, 401)

        # valid api key in header should return code 200
        self.client.credentials(HTTP_X_API_KEY="123456")
        r = self.client.get(url, format="json")
        self.assertEqual(r.status_code, 200)


class TestRoleDelegation(ObserverTestCase):
    """Feature 052: delegación restringida de la administración de usuarios.

    El escenario de base es el que pidió el cliente: un perfil que administra
    cuentas y solo puede repartir UN perfil, el de soporte.
    """

    def setUp(self):
        self.authenticate()  # john y alice, superusuarios
        self.setup_coresettings()

        # Perfil de soporte: el único que el delegado puede otorgar.
        self.soporte = Role.objects.create(
            name="Soporte de prueba",
            can_list_agents=True,
            can_list_accounts=True,
        )
        # Perfil del delegado: superconjunto estricto del de soporte, para que
        # el invariante de no-elevación no sea quien bloquee en los casos donde
        # lo que se prueba es la lista.
        self.delegado_role = Role.objects.create(
            name="Delegado de prueba",
            can_list_agents=True,
            can_list_accounts=True,
            can_manage_accounts=True,
            can_list_roles=True,
        )
        self.delegado_role.assignable_roles.add(self.soporte)

        # Perfil fuera de la lista y con un permiso que el delegado NO tiene:
        # sirve para separar el rechazo por lista del rechazo por invariante.
        self.potente = Role.objects.create(
            name="Potente de prueba",
            can_list_agents=True,
            can_run_scripts=True,
        )
        self.rol_super = Role.objects.create(name="Super de prueba", is_superuser=True)

        self.delegado = User.objects.create_user(  # type: ignore
            username="delegado", password="hunter2delegado"
        )
        self.delegado.role = self.delegado_role
        self.delegado.save()

        self.subordinado = User.objects.create_user(  # type: ignore
            username="subordinado", password="hunter2subordinado"
        )
        self.subordinado.role = self.soporte
        self.subordinado.save()

        self.ajeno = User.objects.create_user(  # type: ignore
            username="ajeno", password="hunter2ajeno"
        )
        self.ajeno.role = self.potente
        self.ajeno.save()

        self.jefe = User.objects.create_user(  # type: ignore
            username="jefe", password="hunter2jefe"
        )
        self.jefe.role = self.rol_super
        self.jefe.save()

    def as_delegado(self) -> None:
        self.client.force_authenticate(user=self.delegado)

    # --- T006: el M2M en sí -------------------------------------------------

    def test_assignable_roles_no_es_simetrico(self):
        # 🔑 La trampa de ManyToManyField("self"): sin symmetrical=False, habilitar
        # A → B habilitaría B → A y el perfil de soporte podría repartir el que lo
        # administra. Es un error que no da error, por eso se afirma explícitamente.
        self.assertIn(self.soporte, self.delegado_role.assignable_roles.all())
        self.assertNotIn(self.delegado_role, self.soporte.assignable_roles.all())

    def test_borrar_un_rol_lo_saca_de_las_listas(self):
        self.soporte.delete()
        self.delegado_role.refresh_from_db()
        self.assertEqual(self.delegado_role.assignable_roles.count(), 0)

    # --- T007: can_assign_role() -------------------------------------------

    def test_can_assign_role_permite_lo_que_esta_en_la_lista(self):
        ok, _ = can_assign_role(self.delegado, self.soporte)
        self.assertTrue(ok)

    def test_can_assign_role_rechaza_lo_que_no_esta_en_la_lista(self):
        ok, motivo = can_assign_role(self.delegado, self.potente)
        self.assertFalse(ok)
        self.assertIn("Potente de prueba", motivo)

    def test_can_assign_role_rechaza_por_invariante_aunque_este_en_la_lista(self):
        # El caso que define RN-02: la lista solo restringe, nunca amplía.
        self.delegado_role.assignable_roles.add(self.potente)
        ok, motivo = can_assign_role(self.delegado, self.potente)
        self.assertFalse(ok)
        self.assertIn("permisos", motivo)

    def test_can_assign_role_rechaza_rol_superusuario(self):
        self.delegado_role.assignable_roles.add(self.rol_super)
        ok, _ = can_assign_role(self.delegado, self.rol_super)
        self.assertFalse(ok)

    def test_can_assign_role_superusuario_puede_todo(self):
        ok, _ = can_assign_role(self.john, self.rol_super)
        self.assertTrue(ok)

    def test_can_assign_role_lista_vacia_no_asigna_nada(self):
        self.delegado_role.assignable_roles.clear()
        ok, _ = can_assign_role(self.delegado, self.soporte)
        self.assertFalse(ok)

    # --- T008: can_manage_user() -------------------------------------------

    def test_can_manage_user_rechaza_cuenta_superusuario(self):
        ok, motivo = can_manage_user(self.delegado, self.jefe)
        self.assertFalse(ok)
        self.assertIn("superusuario", motivo.lower())

    def test_can_manage_user_rechaza_rol_fuera_de_la_lista(self):
        ok, _ = can_manage_user(self.delegado, self.ajeno)
        self.assertFalse(ok)

    def test_can_manage_user_permite_rol_en_la_lista(self):
        ok, _ = can_manage_user(self.delegado, self.subordinado)
        self.assertTrue(ok)

    def test_can_manage_user_permite_la_propia_cuenta(self):
        # Los datos propios sí; el propio ROL lo corta RN-03 en la vista.
        ok, _ = can_manage_user(self.delegado, self.delegado)
        self.assertTrue(ok)

    def test_can_manage_user_superusuario_puede_todo(self):
        ok, _ = can_manage_user(self.john, self.jefe)
        self.assertTrue(ok)

    # --- T009: los cinco puntos de escritura --------------------------------

    def test_los_cinco_puntos_de_escritura_rechazan(self):
        self.as_delegado()
        casos = [
            (
                "POST /accounts/users/ con rol no asignable",
                lambda: self.client.post(
                    "/accounts/users/",
                    {
                        "username": "colado",
                        "email": "c@ej.cl",
                        "password": "hunter2colado",
                        "role": self.potente.pk,
                    },
                    format="json",
                ),
            ),
            (
                "PUT sobre una cuenta superusuario",
                lambda: self.client.put(
                    f"/accounts/{self.jefe.pk}/users/",
                    {"id": self.jefe.pk, "username": "jefe", "first_name": "X"},
                    format="json",
                ),
            ),
            (
                "DELETE sobre una cuenta superusuario",
                lambda: self.client.delete(f"/accounts/{self.jefe.pk}/users/"),
            ),
            (
                "reset de contraseña de una cuenta superusuario",
                lambda: self.client.post(
                    "/accounts/users/reset/",
                    {"id": self.jefe.pk, "password": "hunter2nuevo"},
                    format="json",
                ),
            ),
            (
                "reset de MFA de una cuenta superusuario",
                lambda: self.client.put(
                    "/accounts/users/reset_totp/", {"id": self.jefe.pk}, format="json"
                ),
            ),
        ]
        for nombre, llamada in casos:
            with self.subTest(caso=nombre):
                r = llamada()
                self.assertEqual(r.status_code, 403, msg=nombre)

        # Ninguna de las cinco dejó rastro: la cuenta del jefe sigue igual.
        self.jefe.refresh_from_db()
        self.assertEqual(self.jefe.role, self.rol_super)
        self.assertFalse(User.objects.filter(username="colado").exists())

    def test_el_delegado_si_puede_crear_con_el_rol_asignable(self):
        self.as_delegado()
        r = self.client.post(
            "/accounts/users/",
            {
                "username": "nuevo",
                "email": "n@ej.cl",
                "password": "hunter2nuevo",
                "role": self.soporte.pk,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.get(username="nuevo").role, self.soporte)

    # --- T010: el listado de roles se filtra --------------------------------

    def test_listado_de_roles_filtrado(self):
        r = self.client.get("/accounts/roles/")
        self.assertEqual(r.status_code, 200)
        todos = Role.objects.count()
        self.assertEqual(len(r.json()), todos)

        self.as_delegado()
        r = self.client.get("/accounts/roles/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x["name"] for x in r.json()], ["Soporte de prueba"])

        self.delegado_role.assignable_roles.clear()
        r = self.client.get("/accounts/roles/")
        self.assertEqual(r.json(), [])

    def test_listado_de_roles_excluye_lo_que_el_invariante_bloquea(self):
        # El listado y la validación tienen que decir lo mismo: si un rol está en
        # la lista pero el invariante lo va a rechazar, ofrecerlo en el selector
        # sería ofrecer algo imposible de guardar.
        self.delegado_role.assignable_roles.add(self.potente)
        self.as_delegado()

        r = self.client.get("/accounts/roles/")
        self.assertEqual(r.status_code, 200)
        nombres = [x["name"] for x in r.json()]
        self.assertIn("Soporte de prueba", nombres)
        self.assertNotIn("Potente de prueba", nombres)

        # Y lo que no se ofrece, tampoco se puede asignar: las dos caras coinciden.
        ok, _ = can_assign_role(self.delegado, self.potente)
        self.assertFalse(ok)

    def test_listado_de_usuarios_no_se_filtra(self):
        # RN-09: visibles aunque no sean editables, para conservar la
        # trazabilidad y evitar colisiones de nombre de usuario.
        self.as_delegado()
        r = self.client.get("/accounts/users/")
        self.assertEqual(r.status_code, 200)
        nombres = [u["username"] for u in r.json()]
        self.assertIn("jefe", nombres)
        self.assertIn("ajeno", nombres)

    # --- T011: nadie se cambia su propio rol --------------------------------

    def test_no_puede_cambiarse_el_propio_rol(self):
        self.as_delegado()
        r = self.client.put(
            f"/accounts/{self.delegado.pk}/users/",
            {"id": self.delegado.pk, "username": "delegado", "role": self.rol_super.pk},
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        self.delegado.refresh_from_db()
        self.assertEqual(self.delegado.role, self.delegado_role)

    def test_si_puede_cambiar_sus_propios_datos(self):
        self.as_delegado()
        r = self.client.put(
            f"/accounts/{self.delegado.pk}/users/",
            {"id": self.delegado.pk, "username": "delegado", "first_name": "Dele"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.delegado.refresh_from_db()
        self.assertEqual(self.delegado.first_name, "Dele")

    # --- T012: el rechazo queda auditado ------------------------------------

    def test_el_rechazo_queda_en_auditoria(self):
        # 🪤 pytest-randomly: se cuenta sobre un queryset filtrado por acción y
        # autor, nunca sobre la tabla entera, para no depender del orden.
        antes = AuditLog.objects.filter(
            action=AuditActionType.DELEGATION_DENIED, username="delegado"
        ).count()

        self.as_delegado()
        r = self.client.post(
            "/accounts/users/",
            {
                "username": "colado",
                "email": "c@ej.cl",
                "password": "hunter2colado",
                "role": self.potente.pk,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 403)

        filas = AuditLog.objects.filter(
            action=AuditActionType.DELEGATION_DENIED, username="delegado"
        )
        self.assertEqual(filas.count(), antes + 1)
        fila = filas.last()
        self.assertIn("Potente de prueba", fila.after_value)
