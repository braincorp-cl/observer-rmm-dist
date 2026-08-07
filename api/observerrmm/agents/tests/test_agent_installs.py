from unittest.mock import patch

from rest_framework.response import Response

from observerrmm.test import ObserverTestCase


class TestAgentInstalls(ObserverTestCase):
    def setUp(self) -> None:
        self.authenticate()
        self.setup_coresettings()
        self.setup_base_instance()

    @patch("agents.utils.generate_linux_install")
    @patch("knox.models.AuthToken.objects.create")
    @patch("observerrmm.utils.generate_winagent_exe")
    @patch("core.utils.token_is_valid")
    @patch("agents.utils.get_agent_url")
    def test_install_agent(
        self,
        mock_agent_url,
        mock_token_valid,
        mock_gen_win_exe,
        mock_auth,
        mock_linux_install,
    ):
        mock_agent_url.return_value = "https://example.com"
        mock_token_valid.return_value = "", False
        mock_gen_win_exe.return_value = Response("ok")
        mock_auth.return_value = "", "token"
        mock_linux_install.return_value = Response("ok")

        url = "/agents/installer/"

        # test windows dynamic exe
        data = {
            "installMethod": "exe",
            "client": self.site2.client.pk,
            "site": self.site2.pk,
            "expires": 24,
            "agenttype": "server",
            "power": 0,
            "rdp": 1,
            "ping": 0,
            "goarch": "amd64",
            "api": "https://api.example.com",
            "fileName": "rmm-client-site-server.exe",
            "plat": "windows",
        }

        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        mock_gen_win_exe.assert_called_with(
            client=self.site2.client.pk,
            site=self.site2.pk,
            agent_type="server",
            rdp=1,
            ping=0,
            power=0,
            goarch="amd64",
            token="token",
            api="https://api.example.com",
            file_name="rmm-client-site-server.exe",
        )

        # test linux without code sign token — allowed in Observer RMM fork
        # (EE code signing gate disabled in agents/views.py install_agent)
        data["plat"] = "linux"
        data["installMethod"] = "bash"
        data["rdp"] = 0
        data["agenttype"] = "workstation"
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        # test linux with valid code sign token
        mock_token_valid.return_value = "token123", True
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)
        mock_linux_install.assert_called_with(
            client=str(self.site2.client.pk),
            site=str(self.site2.pk),
            agent_type="workstation",
            arch="amd64",
            token="token",
            api="https://api.example.com",
            download_url="https://example.com",
        )

        # test manual
        data["rdp"] = 1
        data["installMethod"] = "manual"
        r = self.client.post(url, data, format="json")
        self.assertIn("rdp", r.json()["cmd"])
        self.assertNotIn("power", r.json()["cmd"])

        data.update({"ping": 1, "power": 1})
        r = self.client.post(url, data, format="json")
        self.assertIn("power", r.json()["cmd"])
        self.assertIn("ping", r.json()["cmd"])

        # test powershell
        data["installMethod"] = "powershell"
        r = self.client.post(url, data, format="json")
        self.assertEqual(r.status_code, 200)

        self.check_not_authenticated("post", url)

    @patch("knox.models.AuthToken.objects.create")
    @patch("core.utils.token_is_valid")
    @patch("agents.utils.get_agent_url")
    def test_powershell_installer_runs_on_powershell_2(
        self, mock_agent_url, mock_token_valid, mock_auth
    ):
        """El script generado tiene que correr en un Windows 7 de fábrica.

        Win7 SP1 y Server 2008 R2 traen **PowerShell 2.0 sobre CLR 2.0**, y son
        exactamente las plataformas para las que existe el binario legacy del agente
        (ADR-023). El script heredado del proyecto de origen usaba tres cosas que ahí
        no existen —`Test-NetConnection` (PS 4.0), `Invoke-WebRequest` (PS 3.0) y el
        enum `Tls12` (.NET 4.5)— y fallaba con "Unable to connect to server" sin
        instalar nada. Medido en un Win7 real el 2026-08-06.

        El test afirma sobre el texto **ya renderizado** que devuelve el endpoint, no
        sobre la plantilla: es lo que termina corriendo en el equipo.
        """
        mock_agent_url.return_value = "https://example.com/agent.exe"
        mock_token_valid.return_value = "", False
        mock_auth.return_value = "", "token"

        r = self.client.post(
            "/agents/installer/",
            {
                "installMethod": "powershell",
                "client": self.site2.client.pk,
                "site": self.site2.pk,
                "expires": 24,
                "agenttype": "server",
                "power": 0,
                "rdp": 0,
                "ping": 0,
                "goarch": "amd64",
                "api": "https://api.example.com",
                "fileName": "rmm-client-site-server.exe",
                "plat": "windows",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        script = r.content.decode()

        # 🪤 Hay que afirmar sobre CÓDIGO, no sobre prosa: los comentarios del propio
        # script nombran los cmdlets prohibidos para explicar por qué no están, y un
        # `assertNotIn` crudo los confunde con invocaciones reales. Pasó al escribir
        # este test. Simplificación deliberada: se corta en el primer `#` de cada
        # línea, válido mientras ningún literal del script contenga `#`.
        code = "\n".join(
            line if (i := line.find("#")) == -1 else line[:i]
            for line in script.splitlines()
        )

        for cmdlet in ("Test-NetConnection", "Invoke-WebRequest", "Invoke-RestMethod"):
            self.assertNotIn(
                cmdlet,
                code,
                f"{cmdlet} no existe en PowerShell 2.0 y rompe la instalación en Win7",
            )

        # `::Tls12` es el enum ausente en .NET 3.5. El valor numérico 3072 sí se puede
        # pedir en cualquier versión, y va envuelto en try/catch porque en CLR 2.0 la
        # asignación igual lanza: ahí manda SystemDefaultTlsVersions.
        self.assertNotIn("::Tls12", code)
        self.assertIn("3072", code)
        self.assertIn("SystemDefaultTlsVersions", code)

        # Los reemplazos de .NET 2.0 tienen que estar presentes de verdad, no sólo
        # ausentes los viejos: sin esto el test pasaría con el script mutilado.
        self.assertIn("System.Net.Sockets.TcpClient", code)
        self.assertIn("System.Net.WebClient", code)

        # Y el renderizado tiene que seguir funcionando: ningún placeholder vivo.
        for placeholder in (
            "innosetupchange",
            "clientchange",
            "sitechange",
            "apichange",
            "atypechange",
            "powerchange",
            "rdpchange",
            "pingchange",
            "downloadchange",
            "tokenchange",
        ):
            self.assertNotIn(placeholder, script)
