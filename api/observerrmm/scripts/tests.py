from unittest.mock import patch

from django.test import override_settings
from model_bakery import baker

from observerrmm.constants import (
    CustomFieldModel,
    CustomFieldType,
    ScriptShell,
    ScriptType,
)
from observerrmm.test import ObserverTestCase, missing_pk

from .models import Script, ScriptSnippet
from .serializers import (
    ScriptSerializer,
    ScriptSnippetSerializer,
    ScriptTableSerializer,
)


class TestScriptViews(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()

    def test_get_scripts(self):
        url = "/scripts/"
        scripts = baker.make("scripts.Script", _quantity=3)

        serializer = ScriptTableSerializer(scripts, many=True)
        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(serializer.data, resp.data)

        self.check_not_authenticated("get", url)

    @override_settings(SECRET_KEY="Test Secret Key")
    def test_add_script(self):
        url = "/scripts/"

        data = {
            "name": "Name",
            "description": "Description",
            "shell": ScriptShell.POWERSHELL,
            "category": "New",
            "script_body": "Test Script",
            "default_timeout": 99,
            "args": ["hello", "world", r"{{agent.public_ip}}"],
            "favorite": False,
        }

        # test without file upload
        resp = self.client.post(url, data, format="json")
        self.assertEqual(resp.status_code, 200)

        new_script = Script.objects.filter(name="Name").get()
        self.assertTrue(new_script)

        # correct_hash = hmac.new(
        #     settings.SECRET_KEY.encode(), data["script_body"].encode(), hashlib.sha256
        # ).hexdigest()
        # self.assertEqual(new_script.script_hash, correct_hash)

        self.check_not_authenticated("post", url)

    @override_settings(SECRET_KEY="Test Secret Key")
    def test_modify_script(self):
        # test a call where script doesn't exist
        resp = self.client.put(f"/scripts/{missing_pk(Script)}/", format="json")
        self.assertEqual(resp.status_code, 404)

        # make a userdefined script
        script = baker.make_recipe("scripts.script")
        url = f"/scripts/{script.pk}/"

        data = {
            "name": script.name,
            "description": "Description Change",
            "shell": script.shell,
            "script_body": "Test Script Body",  # Test
            "default_timeout": 13344556,
        }

        # test edit a userdefined script
        resp = self.client.put(url, data, format="json")
        self.assertEqual(resp.status_code, 200)
        script = Script.objects.get(pk=script.pk)
        self.assertEqual(script.description, "Description Change")

        # correct_hash = hmac.new(
        #     settings.SECRET_KEY.encode(), data["script_body"].encode(), hashlib.sha256
        # ).hexdigest()
        # self.assertEqual(script.script_hash, correct_hash)

        # test edit a builtin script
        data = {
            "name": "New Name",
            "description": "New Desc",
            "script_body": "aasdfdsf",
        }  # Test
        builtin_script = baker.make_recipe(
            "scripts.script", script_type=ScriptType.BUILT_IN
        )

        resp = self.client.put(f"/scripts/{builtin_script.pk}/", data, format="json")
        self.assertEqual(resp.status_code, 400)

        data = {
            "name": script.name,
            "description": "Description Change",
            "shell": script.shell,
            "favorite": True,
            "script_body": "Test Script Body",  # Test
            "default_timeout": 54345,
        }
        # test marking a builtin script as favorite
        resp = self.client.put(f"/scripts/{builtin_script.pk}/", data, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Script.objects.get(pk=builtin_script.pk).favorite)

        self.check_not_authenticated("put", url)

    def test_get_script(self):
        # test a call where script doesn't exist
        resp = self.client.get(f"/scripts/{missing_pk(Script)}/", format="json")
        self.assertEqual(resp.status_code, 404)

        script = baker.make("scripts.Script")
        url = f"/scripts/{script.pk}/"
        serializer = ScriptSerializer(script)
        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(serializer.data, resp.data)

        self.check_not_authenticated("get", url)

    @patch("agents.models.Agent.nats_cmd", return_value="return value")
    def test_test_script(self, run_script):
        agent = baker.make_recipe("agents.agent")
        url = f"/scripts/{agent.agent_id}/test/"

        data = {
            "code": "some_code",
            "timeout": 90,
            "args": [],
            "shell": ScriptShell.POWERSHELL,
            "run_as_user": False,
            "env_vars": ["hello=world", "foo=bar"],
        }

        resp = self.client.post(url, data, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, "return value")

        self.check_not_authenticated("post", url)

    def test_delete_script(self):
        # test a call where script doesn't exist
        resp = self.client.delete(f"/scripts/{missing_pk(Script)}/", format="json")
        self.assertEqual(resp.status_code, 404)

        # test delete script
        script = baker.make_recipe("scripts.script")
        url = f"/scripts/{script.pk}/"
        resp = self.client.delete(url, format="json")
        self.assertEqual(resp.status_code, 200)

        self.assertFalse(Script.objects.filter(pk=script.pk).exists())

        # test delete community script
        script = baker.make_recipe("scripts.script", script_type=ScriptType.BUILT_IN)
        url = f"/scripts/{script.pk}/"
        resp = self.client.delete(url, format="json")
        self.assertEqual(resp.status_code, 400)

        self.check_not_authenticated("delete", url)

    def test_download_script(self):
        # test a call where script doesn't exist
        resp = self.client.get(
            f"/scripts/{missing_pk(Script)}/download/", format="json"
        )
        self.assertEqual(resp.status_code, 404)

        # return script code property should be "Test"

        # test powershell file
        script = baker.make(
            "scripts.Script",
            script_body="Test Script Body",
            shell=ScriptShell.POWERSHELL,
        )
        url = f"/scripts/{script.pk}/download/"

        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data, {"filename": f"{script.name}.ps1", "code": "Test Script Body"}
        )

        # test batch file
        script = baker.make(
            "scripts.Script", script_body="Test Script Body", shell=ScriptShell.CMD
        )
        url = f"/scripts/{script.pk}/download/"

        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data, {"filename": f"{script.name}.bat", "code": "Test Script Body"}
        )

        # test python file
        script = baker.make(
            "scripts.Script", script_body="Test Script Body", shell=ScriptShell.PYTHON
        )
        url = f"/scripts/{script.pk}/download/"

        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data, {"filename": f"{script.name}.py", "code": "Test Script Body"}
        )

        self.check_not_authenticated("get", url)

    def test_script_arg_variable_replacement(self):
        agent = baker.make_recipe("agents.agent", public_ip="12.12.12.12")
        args = [
            "-Parameter",
            "-Another {{agent.public_ip}}",
            "-Client {{client.name}}",
            "-Site {{site.name}}",
        ]

        self.assertEqual(
            [
                "-Parameter",
                "-Another '12.12.12.12'",
                f"-Client '{agent.client.name}'",
                f"-Site '{agent.site.name}'",
            ],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

    def test_script_env_vars_variable_replacement(self):
        agent = baker.make_recipe("agents.agent", public_ip="12.12.12.12")
        env_vars = [
            "PUBIP={{agent.public_ip}}",
            "123CLIENT={{client.name}}",
            "FOOBARSITE={{site.name}}",
        ]

        self.assertEqual(
            [
                "PUBIP=12.12.12.12",
                f"123CLIENT={agent.client.name}",
                f"FOOBARSITE={agent.site.name}",
            ],
            Script.parse_script_env_vars(
                agent=agent, shell=ScriptShell.POWERSHELL, env_vars=env_vars
            ),
        )

    def test_script_arg_replacement_custom_field(self):
        agent = baker.make_recipe("agents.agent")
        field = baker.make(
            "core.CustomField",
            name="Test Field",
            model=CustomFieldModel.AGENT,
            type=CustomFieldType.TEXT,
            default_value_string="DEFAULT",
        )

        args = ["-Parameter", "-Another {{agent.Test Field}}"]

        # test default value
        self.assertEqual(
            ["-Parameter", "-Another 'DEFAULT'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

        # test with set value
        baker.make(
            "agents.AgentCustomField",
            field=field,
            agent=agent,
            string_value="CUSTOM VALUE",
        )
        self.assertEqual(
            ["-Parameter", "-Another 'CUSTOM VALUE'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

    def test_script_env_vars_replacement_custom_field(self):
        agent = baker.make_recipe("agents.agent")
        field = baker.make(
            "core.CustomField",
            name="Test Field",
            model=CustomFieldModel.AGENT,
            type=CustomFieldType.TEXT,
            default_value_string="DEFAULT",
        )

        env_vars = ["FOOBAR={{agent.Test Field}}"]

        # test default value
        self.assertEqual(
            ["FOOBAR=DEFAULT"],
            Script.parse_script_env_vars(
                agent=agent, shell=ScriptShell.POWERSHELL, env_vars=env_vars
            ),
        )

        # test with set value
        baker.make(
            "agents.AgentCustomField",
            field=field,
            agent=agent,
            string_value="CUSTOM VALUE",
        )
        self.assertEqual(
            ["FOOBAR=CUSTOM VALUE"],
            Script.parse_script_env_vars(
                agent=agent, shell=ScriptShell.POWERSHELL, env_vars=env_vars
            ),
        )

    def test_script_arg_replacement_client_custom_fields(self):
        agent = baker.make_recipe("agents.agent")
        field = baker.make(
            "core.CustomField",
            name="Test Field",
            model=CustomFieldModel.CLIENT,
            type=CustomFieldType.TEXT,
            default_value_string="DEFAULT",
        )

        args = ["-Parameter", "-Another {{client.Test Field}}"]

        # test default value
        self.assertEqual(
            ["-Parameter", "-Another 'DEFAULT'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

        # test with set value
        baker.make(
            "clients.ClientCustomField",
            field=field,
            client=agent.client,
            string_value="CUSTOM VALUE",
        )
        self.assertEqual(
            ["-Parameter", "-Another 'CUSTOM VALUE'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

    def test_script_env_vars_replacement_client_custom_fields(self):
        agent = baker.make_recipe("agents.agent")
        field = baker.make(
            "core.CustomField",
            name="test123",
            model=CustomFieldModel.CLIENT,
            type=CustomFieldType.TEXT,
            default_value_string="https://a1234lkasd.asdinasd234.com/ask2348uASDlk234@!#$@#asd1dsf",
        )

        env_vars = ["FOOBAR={{client.test123}}"]

        # test default value
        self.assertEqual(
            ["FOOBAR=https://a1234lkasd.asdinasd234.com/ask2348uASDlk234@!#$@#asd1dsf"],
            Script.parse_script_env_vars(
                agent=agent, shell=ScriptShell.POWERSHELL, env_vars=env_vars
            ),
        )

        # test with set value
        baker.make(
            "clients.ClientCustomField",
            field=field,
            client=agent.client,
            string_value="uASdklj23487ASDkjhr345il987UASXK<DFOIul32oi454329837492384512342134!@#!@#ADSFW45X",
        )
        self.assertEqual(
            [
                "FOOBAR=uASdklj23487ASDkjhr345il987UASXK<DFOIul32oi454329837492384512342134!@#!@#ADSFW45X"
            ],
            Script.parse_script_env_vars(
                agent=agent, shell=ScriptShell.POWERSHELL, env_vars=env_vars
            ),
        )

    def test_script_arg_replacement_site_custom_fields(self):
        agent = baker.make_recipe("agents.agent")
        field = baker.make(
            "core.CustomField",
            name="Test Field",
            model=CustomFieldModel.SITE,
            type=CustomFieldType.TEXT,
            default_value_string="DEFAULT",
        )

        args = ["-Parameter", "-Another {{site.Test Field}}"]

        # test default value
        self.assertEqual(
            ["-Parameter", "-Another 'DEFAULT'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

        # test with set value
        value = baker.make(
            "clients.SiteCustomField",
            field=field,
            site=agent.site,
            string_value="CUSTOM VALUE",
        )
        self.assertEqual(
            ["-Parameter", "-Another 'CUSTOM VALUE'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

        # test with set but empty field value
        value.string_value = ""
        value.save()

        self.assertEqual(
            ["-Parameter", "-Another 'DEFAULT'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

        # test blank default and value
        field.default_value_string = ""
        field.save()

        self.assertEqual(
            ["-Parameter", "-Another ''"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

    def test_script_env_vars_replacement_site_custom_fields(self):
        agent = baker.make_recipe("agents.agent")
        field = baker.make(
            "core.CustomField",
            name="ffas2345asdasasdWEdd",
            model=CustomFieldModel.SITE,
            type=CustomFieldType.TEXT,
            default_value_string="https://site.easkdjas.com/asik2348aSDH234RJKADBCA%123SAD",
        )

        env_vars = ["ASD45ASDKJASHD={{site.ffas2345asdasasdWEdd}}"]

        # test default value
        self.assertEqual(
            ["ASD45ASDKJASHD=https://site.easkdjas.com/asik2348aSDH234RJKADBCA%123SAD"],
            Script.parse_script_env_vars(
                agent=agent, shell=ScriptShell.POWERSHELL, env_vars=env_vars
            ),
        )

        # test with set value
        value = baker.make(
            "clients.SiteCustomField",
            field=field,
            site=agent.site,
            string_value="g435asdASD2354SDFasdfsdf",
        )
        self.assertEqual(
            ["ASD45ASDKJASHD=g435asdASD2354SDFasdfsdf"],
            Script.parse_script_env_vars(
                agent=agent, shell=ScriptShell.POWERSHELL, env_vars=env_vars
            ),
        )

        # test with set but empty field value
        value.string_value = ""
        value.save()

        self.assertEqual(
            ["ASD45ASDKJASHD=https://site.easkdjas.com/asik2348aSDH234RJKADBCA%123SAD"],
            Script.parse_script_env_vars(
                agent=agent, shell=ScriptShell.POWERSHELL, env_vars=env_vars
            ),
        )

    def test_script_arg_replacement_array_fields(self):
        agent = baker.make_recipe("agents.agent")
        field = baker.make(
            "core.CustomField",
            name="Test Field",
            model=CustomFieldModel.AGENT,
            type=CustomFieldType.MULTIPLE,
            default_values_multiple=["this", "is", "an", "array"],
        )

        args = ["-Parameter", "-Another {{agent.Test Field}}"]

        # test default value
        self.assertEqual(
            ["-Parameter", "-Another 'this,is,an,array'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

        # test with set value and python shell
        baker.make(
            "agents.AgentCustomField",
            field=field,
            agent=agent,
            multiple_value=["this", "is", "new"],
        )
        self.assertEqual(
            ["-Parameter", "-Another 'this,is,new'"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

    def test_script_arg_replacement_boolean_fields(self):
        agent = baker.make_recipe("agents.agent")
        field = baker.make(
            "core.CustomField",
            name="Test Field",
            model=CustomFieldModel.AGENT,
            type=CustomFieldType.CHECKBOX,
            default_value_bool=True,
        )

        args = ["-Parameter", "-Another {{agent.Test Field}}"]

        # test default value with python
        self.assertEqual(
            ["-Parameter", "-Another 1"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

        # test with set value and python shell
        custom = baker.make(
            "agents.AgentCustomField",
            field=field,
            agent=agent,
            bool_value=False,
        )
        self.assertEqual(
            ["-Parameter", "-Another 0"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.PYTHON, args=args),
        )

        # test with set value and cmd shell
        self.assertEqual(
            ["-Parameter", "-Another 0"],
            Script.parse_script_args(agent=agent, shell=ScriptShell.CMD, args=args),
        )

        # test with set value and powershell
        self.assertEqual(
            ["-Parameter", "-Another $False"],
            Script.parse_script_args(
                agent=agent, shell=ScriptShell.POWERSHELL, args=args
            ),
        )

        # test with True value powershell
        custom.bool_value = True
        custom.save()

        self.assertEqual(
            ["-Parameter", "-Another $True"],
            Script.parse_script_args(
                agent=agent, shell=ScriptShell.POWERSHELL, args=args
            ),
        )


class TestScriptSnippetViews(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()

    def test_get_script_snippets(self):
        url = "/scripts/snippets/"
        snippets = baker.make("scripts.ScriptSnippet", _quantity=3)

        serializer = ScriptSnippetSerializer(snippets, many=True)
        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(serializer.data, resp.data)

        self.check_not_authenticated("get", url)

    def test_add_script_snippet(self):
        url = "/scripts/snippets/"

        data = {
            "name": "Name",
            "description": "Description",
            "shell": ScriptShell.POWERSHELL,
            "code": "Test",
        }

        resp = self.client.post(url, data, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ScriptSnippet.objects.filter(name="Name").exists())

        self.check_not_authenticated("post", url)

    def test_modify_script_snippet(self):
        # test a call where script doesn't exist
        resp = self.client.put(
            f"/scripts/snippets/{missing_pk(ScriptSnippet)}/", format="json"
        )
        self.assertEqual(resp.status_code, 404)

        # make a userdefined script
        snippet = baker.make("scripts.ScriptSnippet", name="Test")
        url = f"/scripts/snippets/{snippet.pk}/"

        data = {"name": "New Name"}

        resp = self.client.put(url, data, format="json")
        self.assertEqual(resp.status_code, 200)
        snippet = ScriptSnippet.objects.get(pk=snippet.pk)
        self.assertEqual(snippet.name, "New Name")

        self.check_not_authenticated("put", url)

    def test_get_script_snippet(self):
        # test a call where script doesn't exist
        resp = self.client.get(
            f"/scripts/snippets/{missing_pk(ScriptSnippet)}/", format="json"
        )
        self.assertEqual(resp.status_code, 404)

        snippet = baker.make("scripts.ScriptSnippet")
        url = f"/scripts/snippets/{snippet.pk}/"
        serializer = ScriptSnippetSerializer(snippet)
        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(serializer.data, resp.data)

        self.check_not_authenticated("get", url)

    def test_delete_script_snippet(self):
        # test a call where script doesn't exist
        resp = self.client.delete(
            f"/scripts/snippets/{missing_pk(ScriptSnippet)}/", format="json"
        )
        self.assertEqual(resp.status_code, 404)

        # test delete script snippet
        snippet = baker.make("scripts.ScriptSnippet")
        url = f"/scripts/snippets/{snippet.pk}/"
        resp = self.client.delete(url, format="json")
        self.assertEqual(resp.status_code, 200)

        self.assertFalse(ScriptSnippet.objects.filter(pk=snippet.pk).exists())

        self.check_not_authenticated("delete", url)

    def test_snippet_replacement(self):
        snippet1 = baker.make(
            "scripts.ScriptSnippet", name="snippet1", code="Snippet 1 Code"
        )
        snippet2 = baker.make(
            "scripts.ScriptSnippet", name="snippet2", code="Snippet 2 Code"
        )

        test_no_snippet = "No Snippets Here"
        test_with_snippet = "Snippet 1: {{snippet1}}\nSnippet 2: {{snippet2}}"

        # test putting snippet in text
        result = Script.replace_with_snippets(test_with_snippet)
        self.assertEqual(
            result,
            f"Snippet 1: {snippet1.code}\nSnippet 2: {snippet2.code}",  # type: ignore
        )

        # test text with no snippets
        result = Script.replace_with_snippets(test_no_snippet)
        self.assertEqual(result, test_no_snippet)


class TestBibliotecaDeScripts(ObserverTestCase):
    """Contrato de la biblioteca de scripts del producto (settings.SCRIPTS_DIR).

    La biblioteca son datos versionados junto al código: un manifiesto JSON más un
    archivo por script. El cargador confía en que ambos lados estén sincronizados y
    SALTA EN SILENCIO cualquier entrada cuyo archivo no exista (models.py:104), así
    que un renombre a medias no rompe nada visible — el script simplemente no
    aparece en la consola. Estos tests convierten eso en una falla de CI.
    """

    def test_manifiesto_coherente_con_los_archivos(self):
        import json
        import os

        from django.conf import settings

        ruta_manifiesto = os.path.join(settings.SCRIPTS_DIR, "observer_scripts.json")
        self.assertTrue(
            os.path.isfile(ruta_manifiesto),
            f"no existe el manifiesto de la biblioteca en {ruta_manifiesto}",
        )

        with open(ruta_manifiesto) as archivo:
            manifiesto = json.load(archivo)

        self.assertGreater(len(manifiesto), 0, "el manifiesto está vacío")

        guids = [entrada["guid"] for entrada in manifiesto]
        self.assertEqual(
            len(guids), len(set(guids)), "hay guids repetidos en el manifiesto"
        )

        obligatorias = ("guid", "filename", "name", "description", "shell")
        for entrada in manifiesto:
            for clave in obligatorias:
                self.assertIn(
                    clave, entrada, f"falta '{clave}' en {entrada.get('name', entrada)}"
                )

            ruta = os.path.join(settings.SCRIPTS_DIR, "scripts", entrada["filename"])
            self.assertTrue(
                os.path.isfile(ruta),
                f"'{entrada['name']}' apunta a {entrada['filename']}, que no existe",
            )

            self.assertIn(
                entrada["shell"],
                ScriptShell.values,
                f"shell '{entrada['shell']}' no válido en '{entrada['name']}'",
            )

            # Los .ps1 DEBEN llevar BOM UTF-8. El agente los ejecuta con
            # powershell.exe (Windows PowerShell 5.1) escribiendo el cuerpo crudo a
            # un archivo temporal, y 5.1 sin BOM interpreta el archivo como ANSI:
            # cada acento sale como mojibake en la salida. Nuestros scripts están en
            # español, así que sin BOM el defecto es garantizado y silencioso.
            if entrada["shell"] == ScriptShell.POWERSHELL:
                with open(ruta, "rb") as binario:
                    crudo = binario.read()

                self.assertEqual(
                    crudo[:3],
                    b"\xef\xbb\xbf",
                    f"'{entrada['filename']}' no empieza con BOM UTF-8: "
                    "Windows PowerShell 5.1 va a romper sus acentos",
                )

                # La otra mitad del problema de codificación, y la que NO se ve
                # revisando el archivo: el BOM arregla cómo PowerShell LEE el script,
                # pero 5.1 ESCRIBE su stdout en la página de códigos OEM de la consola.
                # El agente pasa esa salida por strings.ToValidUTF8(s, "")
                # (agent/utils.go:401), que borra lo que no sea UTF-8 válido, así que
                # los acentos desaparecen sin dejar rastro. Medido en Windows 11 real.
                self.assertIn(
                    "[Console]::OutputEncoding",
                    crudo.decode("utf-8-sig"),
                    f"'{entrada['filename']}' no fija la codificación de salida: "
                    "sus acentos se van a perder en el camino al servidor",
                )

            # Los .py tienen el MISMO problema por otra vía: en Windows el Python
            # embebido del agente escribe stdout en cp1252 (medido en un equipo real),
            # así que hay que reconfigurarlo a UTF-8 o los acentos se pierden igual.
            if entrada["shell"] == ScriptShell.PYTHON:
                with open(ruta, "r", encoding="utf-8") as texto:
                    self.assertIn(
                        'sys.stdout.reconfigure(encoding="utf-8"',
                        texto.read(),
                        f"'{entrada['filename']}' no reconfigura stdout a UTF-8: "
                        "en Windows sus acentos se van a perder",
                    )

            for plataforma in entrada.get("supported_platforms", []):
                self.assertIn(
                    plataforma,
                    ("windows", "linux", "darwin"),
                    f"plataforma '{plataforma}' no válida en '{entrada['name']}'",
                )

    def test_cargar_biblioteca_siembra_la_bd(self):
        import json
        import os

        from django.conf import settings

        with open(
            os.path.join(settings.SCRIPTS_DIR, "observer_scripts.json")
        ) as archivo:
            manifiesto = json.load(archivo)

        Script.load_community_scripts()

        cargados = Script.objects.filter(script_type=ScriptType.BUILT_IN)
        self.assertEqual(
            cargados.count(),
            len(manifiesto),
            "el cargador no dejó en la BD un script por entrada del manifiesto",
        )

        # El cuerpo tiene que llegar a la BD: es lo que se le manda al agente.
        for entrada in manifiesto:
            guardado = cargados.get(guid=entrada["guid"])
            self.assertEqual(guardado.name, entrada["name"])
            self.assertEqual(guardado.shell, entrada["shell"])
            self.assertTrue(
                guardado.script_body.strip(),
                f"'{entrada['name']}' quedó con el cuerpo vacío en la BD",
            )

        # Idempotencia: una segunda pasada no duplica ni borra.
        Script.load_community_scripts()
        self.assertEqual(
            Script.objects.filter(script_type=ScriptType.BUILT_IN).count(),
            len(manifiesto),
        )
