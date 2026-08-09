"""Guard de arquitectura de los instaladores unix: que se niegue de verdad.

Instalar el agente de la arquitectura equivocada es un error de operador —el
instalador se elige a mano en la consola— y tiene dos finales, uno ruidoso y uno
mudo:

* **Mudo, el peligroso:** un binario Go de 32 bits es estático y **corre perfecto**
  en un equipo de 64 bits. Medido el 2026-08-09 en este x86_64: `Arch: 386`, rc=0.
  El equipo queda reportando `goarch=386` y, como el servidor elige el instalador
  del update con el goarch que el agente reporta, pide 32 bits **para siempre**.
* **Ruidoso:** el binario de 64 bits no ejecuta en un kernel de 32 bits.

Los tests corren el guard DE VERDAD, en bash, con `uname`/`sysctl` sustituidos —
no comprueban que el texto exista. Un guard que existe y no bloquea y uno que
bloquea se ven idénticos desde un `assertIn`.

🪤 El caso que motivó la lista blanca: el servidor reemplaza **todas** las
apariciones de `archChange` en el archivo. Un guard que comparara el valor contra
ese literal para saber «si vino sustituido» terminaría comparándolo contra la
arquitectura real, y se apagaría solo justo para ella. Está cubierto abajo.
"""

import re
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.conf import settings

from agents.utils import generate_linux_install, generate_macos_install
from observerrmm.test import ObserverTestCase

MARCADOR_INICIO = "# ARCH-GUARD-START"
MARCADOR_FIN = "# ARCH-GUARD-END"

# Stubs de las dos fuentes de verdad, para poder actuar cualquier equipo desde
# este x86_64. Van como funciones de shell: sombrean al binario real.
STUB_LINUX = (
    'uname() {{ if [ "$1" = "-m" ]; then echo "{maquina}"; else echo Linux; fi; }}\n'
)
STUB_MACOS = 'sysctl() {{ echo "{arm64}"; }}\n'


def _bloque_guard(script: Path) -> str:
    texto = script.read_text()
    m = re.search(
        re.escape(MARCADOR_INICIO) + r"(.*?)" + re.escape(MARCADOR_FIN),
        texto,
        re.DOTALL,
    )
    if not m:
        raise AssertionError(f"{script}: faltan los marcadores del guard")
    return m.group(1)


def _correr(guard: str, stub: str, esperada: str):
    """Ejecuta CheckArch en un bash de verdad. Devuelve (returncode, salida)."""
    programa = stub + guard + f'\nCheckArch "{esperada}"\n'
    p = subprocess.run(
        ["bash", "-c", programa], capture_output=True, text=True, timeout=30
    )
    return p.returncode, p.stdout + p.stderr


class TestGuardLinux(ObserverTestCase):
    def setUp(self):
        self.guard = _bloque_guard(Path(settings.LINUX_AGENT_SCRIPT))

    def _check(self, esperada, maquina):
        return _correr(self.guard, STUB_LINUX.format(maquina=maquina), esperada)

    def test_386_sobre_64_bits_se_niega(self):
        """El caso mudo: sin este guard el instalador seguía de largo y el equipo
        quedaba pidiendo updates de 32 bits para siempre."""
        rc, salida = self._check("386", "x86_64")

        self.assertEqual(rc, 1)
        self.assertIn("ERROR", salida)
        self.assertIn("386", salida)
        self.assertIn("amd64", salida)

    def test_amd64_sobre_32_bits_se_niega(self):
        rc, salida = self._check("amd64", "i686")

        self.assertEqual(rc, 1)
        self.assertIn("ERROR", salida)

    def test_cruce_con_arm_se_niega(self):
        for esperada, maquina in (
            ("amd64", "aarch64"),
            ("arm64", "x86_64"),
            ("arm", "aarch64"),
        ):
            with self.subTest(esperada=esperada, maquina=maquina):
                rc, _ = self._check(esperada, maquina)
                self.assertEqual(rc, 1)

    def test_las_arquitecturas_que_calzan_pasan(self):
        """Control negativo. Sin él, un guard que bloqueara SIEMPRE se vería
        igual de verde que el correcto."""
        for esperada, maquina in (
            ("amd64", "x86_64"),
            ("386", "i686"),
            ("386", "i386"),
            ("arm64", "aarch64"),
            ("arm", "armv7l"),
        ):
            with self.subTest(esperada=esperada, maquina=maquina):
                rc, salida = self._check(esperada, maquina)
                self.assertEqual(rc, 0, salida)
                self.assertNotIn("ERROR", salida)

    def test_sin_sustituir_avisa_y_sigue(self):
        """La copia cruda del repo tiene que poder usarse: avisa, no bloquea."""
        rc, salida = self._check("archChange", "x86_64")

        self.assertEqual(rc, 0)
        self.assertIn("WARNING", salida)

    def test_arquitectura_desconocida_avisa_y_sigue(self):
        rc, salida = self._check("amd64", "riscv64")

        self.assertEqual(rc, 0)
        self.assertIn("WARNING", salida)

    def test_el_guard_va_despues_del_despacho_de_uninstall(self):
        """La consola manda este MISMO archivo, sin sustituir, para desinstalar
        (agents/views.py, AgentHandler.delete). Un guard más arriba bloquearía
        desinstalaciones legítimas."""
        texto = Path(settings.LINUX_AGENT_SCRIPT).read_text()
        linea_uninstall = texto.index("    Uninstall\n")
        linea_guard = texto.index('CheckArch "${expectedArch}"')

        self.assertLess(linea_uninstall, linea_guard)


class TestGuardMacos(ObserverTestCase):
    def setUp(self):
        self.guard = _bloque_guard(Path(settings.MACOS_AGENT_SCRIPT))

    def _check(self, esperada, es_apple_silicon):
        stub = STUB_MACOS.format(arm64="1" if es_apple_silicon else "")
        return _correr(self.guard, stub, esperada)

    def test_intel_sobre_apple_silicon_se_niega(self):
        """El caso que Rosetta 2 taparía: el binario Intel corre traducido y
        parece que funciona."""
        rc, salida = self._check("amd64", es_apple_silicon=True)

        self.assertEqual(rc, 1)
        self.assertIn("Apple Silicon", salida)

    def test_apple_silicon_sobre_intel_se_niega(self):
        rc, salida = self._check("arm64", es_apple_silicon=False)

        self.assertEqual(rc, 1)
        self.assertIn("Intel", salida)

    def test_las_que_calzan_pasan(self):
        rc, salida = self._check("arm64", es_apple_silicon=True)
        self.assertEqual(rc, 0, salida)

        rc, salida = self._check("amd64", es_apple_silicon=False)
        self.assertEqual(rc, 0, salida)

    def test_no_usa_uname_para_decidir(self):
        """🪤 Bajo Rosetta `uname -m` devuelve x86_64 en un Mac Apple Silicon, así
        que decidir por ahí aprobaría justo el caso que hay que atajar."""
        self.assertNotIn("uname", self.guard)
        self.assertIn("hw.optional.arm64", self.guard)


class TestInstallerPs1NoMienteCuandoElGuardBloquea(ObserverTestCase):
    """Que la negativa del instalador de Windows LLEGUE a la consola.

    El guard de `setup.iss` aborta antes de copiar nada, pero `installer.ps1` lo
    corre con `/SUPPRESSMSGBOXES` —el operador no ve el mensaje— y después
    enrolaba sin verificar. Como el script no fija `$ErrorActionPreference =
    'Stop'`, un `Start-Process` sobre una ruta inexistente es un error NO
    terminante: el `Catch` no se enteraba y la línea siguiente era `exit 0`.

    Resultado: el instalador se negaba bien y la consola decía que todo salió
    bien. Es el `exit 0` que no prueba el efecto, en el camino de instalación por
    defecto de Windows.

    Esto se afirma sobre el texto porque no hay dónde correr PowerShell en la CI
    del backend; la verificación de verdad es en terreno.
    """

    def setUp(self):
        self.ps1 = (Path(settings.BASE_DIR) / "core" / "installer.ps1").read_text()

    def test_verifica_el_binario_antes_de_enrolar(self):
        pos_check = self.ps1.index("if (-not (Test-Path $agentExe))")
        pos_enrolar = self.ps1.index("Start-Process -FilePath $agentExe")

        self.assertLess(pos_check, pos_enrolar)

    def test_la_falla_sale_con_codigo_distinto_de_cero(self):
        bloque = self.ps1[self.ps1.index("if (-not (Test-Path $agentExe))") :]
        bloque = bloque[: bloque.index("Start-Process -FilePath $agentExe")]

        self.assertIn("exit 1", bloque)
        self.assertNotIn("exit 0", bloque)

    def test_el_mensaje_nombra_la_arquitectura(self):
        """Sin el mensaje del guard (suprimido), este texto es lo único que el
        operador tiene para saber qué pasó."""
        bloque = self.ps1[self.ps1.index("if (-not (Test-Path $agentExe))") :]

        self.assertIn("arquitectura", bloque[:1200])


class TestArquitecturaSustituida(ObserverTestCase):
    """El servidor tiene que dejar el guard ARMADO, no sólo presente.

    Estos tests corren el guard tal como sale del generador: si el valor no se
    sustituye, el script degrada a WARNING y deja pasar cualquier cosa.
    """

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.setup_base_instance()

    def _generar(self, generador, arch):
        with patch("agents.utils.get_mesh_device_id"), patch(
            "agents.utils.asyncio.run", return_value="meshid"
        ), patch("agents.utils.get_mesh_ws_url", return_value="meshws"), patch(
            "agents.utils.get_core_settings"
        ) as mock_core:
            mock_core.return_value.mesh_site = "meshsite"
            r = generador(
                client="1",
                site="1",
                agent_type="server",
                arch=arch,
                token="token123",
                api="api.example.com",
                download_url="https://ejemplo/agente",
            )
        return r.getvalue().decode("utf-8")

    def test_linux_queda_con_la_arquitectura_puesta(self):
        script = self._generar(generate_linux_install, "386")

        self.assertIn("expectedArch='386'", script)

    def test_macos_queda_con_la_arquitectura_puesta(self):
        script = self._generar(generate_macos_install, "arm64")

        self.assertIn("expectedArch='arm64'", script)

    def test_el_guard_generado_bloquea_de_verdad(self):
        """🪤 El caso de la lista blanca, extremo a extremo: se genera el script
        para 386, se le corre el guard ya sustituido en un equipo x86_64 y tiene
        que negarse. Si el guard comparara contra el literal del marcador, la
        sustitución lo habría apagado justo acá."""
        script = self._generar(generate_linux_install, "386")
        m = re.search(
            re.escape(MARCADOR_INICIO) + r"(.*?)" + re.escape(MARCADOR_FIN),
            script,
            re.DOTALL,
        )
        self.assertIsNotNone(m)

        rc, salida = _correr(m.group(1), STUB_LINUX.format(maquina="x86_64"), "386")

        self.assertEqual(rc, 1, salida)
        self.assertIn("ERROR", salida)
