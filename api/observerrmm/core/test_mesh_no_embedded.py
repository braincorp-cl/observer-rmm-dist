"""O-MESH-01 — ninguna invocación del binario del mesh se queda sin la bandera.

El binario que MeshCentral entrega para instalar en Linux y macOS **no es el
agente**: la URL lleva `meshinstall=` y el servidor responde con el agente más un
instalador JavaScript anexado que reacciona a CUALQUIER argumento. Medido en
`HP-ProOne-400`: con `-nodeid` devolvía la salida entera de una reinstalación —que
el `.sh` pasaba por `eval`, o sea que el shell la EJECUTABA— y con `-fulluninstall`
abría un `zenity` en el escritorio de la persona y colgaba el uninstall completo
sin desinstalar nada, mientras la API respondía 200.

La protección es una sola línea: **`--no-embedded=1`, y va DESPUÉS del comando**.
Está puesta en las cuatro invocaciones que la necesitan.

Lo que este gate cuida NO es que MeshCentral deje de anexar el JS —eso vive
upstream y puede mutar con cualquier update suyo, por eso T015 se cerró sin
investigar la causa—. Lo que puede regresionar es que **nosotros agreguemos una
invocación nueva y olvidemos la bandera**, y hasta hoy no había nada que lo
atrapara.

🪤 **La trampa de este gate es el cero silencioso.** Un barrido que no encuentra
nada pasa en verde exactamente igual que uno que encuentra todo conforme. Por eso
hay tres cinturones y no uno:

* el **censo exacto** (`CENSO`): la lista de invocaciones reales del repo se
  compara entera, así que tanto una invocación nueva como la desaparición de una
  conocida rompen la CI;
* el **control positivo**: se le da al mismo barrido un script sintético al que le
  falta la bandera y tiene que denunciarlo — si el detector se rompe, este test
  cae antes de que el silencio parezca conformidad;
* el **control negativo**: líneas donde el binario aparece como ARGUMENTO
  (`wget -O`, `chmod +x`, `[ -f ... ]`) no pueden contarse como invocaciones, o el
  gate se llenaría de ruido y terminaría desactivado.

**Fuera de alcance, a propósito:** la invocación de Windows vive en el Go de
`agent-dist` (`agent_windows.go`, `getMeshNodeID`), otro repo. Y este archivo se
excluye del barrido porque contiene invocaciones sintéticas de mentira.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, NamedTuple

from django.conf import settings

from observerrmm.test import ObserverTestCase

BANDERA = "--no-embedded=1"

# Comandos exentos, con su razón. Angosta a propósito y verificada por
# `test_las_excepciones_son_las_declaradas`: crecer esta lista exige tocarla a
# mano, que es justamente el momento en que alguien tiene que pensarlo.
#
# `-install` está exento porque en Linux/macOS el binario descargado ES el
# auto-instalador y el `-install` se apoya en ese JS anexado: ponerle la bandera
# no es endurecer el gate, es cambiar el camino de enrolamiento de dos sistemas
# operativos sin haberlo medido en terreno.
EXCEPCIONES = {"-install"}

# El propio gate: sus invocaciones son sintéticas.
NO_BARRER = {"api/observerrmm/core/test_mesh_no_embedded.py"}

LINUX = "api/observerrmm/core/agent_linux.sh"
MACOS = "api/observerrmm/core/agent_macos.sh"
MAC_UNINSTALL = "api/observerrmm/core/mac_uninstall.sh"

# Censo de TODAS las invocaciones del binario del mesh con argumentos que hay hoy
# en el repo, con su comando y si llevan la bandera. Se compara entero: una
# invocación nueva rompe la CI aunque venga conforme, y eso es deliberado —
# obliga a que alguien la mire y la agregue acá.
CENSO = [
    (LINUX, "-install", False),
    (LINUX, "-fulluninstall", True),
    (MACOS, "-install", False),
    (MACOS, "-uninstall", True),
    (MAC_UNINSTALL, "-fulluninstall", True),
    (MAC_UNINSTALL, "-fulluninstall", True),
]

_COMILLAS = "\"'"
_VAR_RE = re.compile(r"^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?$")
# Sufijos que delatan que la variable guarda el BINARIO y no un directorio, una
# URL o el nombre del servicio: meshDir, meshDL, meshSvcName no son invocables.
_SUFIJOS_BINARIO = ("bin", "exe", "binary", "agent")


class Invocacion(NamedTuple):
    archivo: str
    linea: int
    comando: str
    lleva_bandera: bool
    bandera_despues_del_comando: bool
    texto: str

    def conforme(self) -> bool:
        if self.comando in EXCEPCIONES:
            return True
        return self.lleva_bandera and self.bandera_despues_del_comando


def _limpiar(token: str) -> str:
    return token.strip(_COMILLAS)


def _es_binario_mesh(token: str) -> bool:
    """¿Este token nombra al binario del mesh?

    Cubre las dos formas que existen: la variable (`${meshSystemBin}`) y la ruta
    literal (`/opt/observermesh/meshagent`).
    """
    t = _limpiar(token)

    m = _VAR_RE.match(t)
    if m:
        nombre = m.group(1).lower()
        return "mesh" in nombre and nombre.endswith(_SUFIJOS_BINARIO)

    return t.rsplit("/", 1)[-1].lower() in ("meshagent", "meshagent.exe")


def invocaciones(texto: str, archivo: str = "<memoria>") -> List[Invocacion]:
    """Invocaciones del binario del mesh CON ARGUMENTOS que hay en `texto`.

    Una invocación es un token que nombra al binario seguido inmediatamente por
    un token que empieza con `-`. Esa condición es la que separa la invocación
    del caso en que el binario viaja como argumento de otro comando
    (`wget -O ${meshTmpBin} <url>`, `chmod +x ${meshTmpBin}`, `[ -f "${meshBin}" ]`),
    donde lo que sigue nunca es una bandera del mesh.
    """
    salida = []

    for nro, linea in enumerate(texto.splitlines(), start=1):
        # Los comentarios de estos scripts explican la bandera y la nombran
        # entera; leerlos como código daría invocaciones fantasma.
        if linea.lstrip().startswith("#"):
            continue

        tokens = linea.split()
        for i, tok in enumerate(tokens[:-1]):
            if not _es_binario_mesh(tok):
                continue

            resto = [_limpiar(t) for t in tokens[i + 1 :]]
            comando = resto[0]
            if not comando.startswith("-"):
                continue

            salida.append(
                Invocacion(
                    archivo=archivo,
                    linea=nro,
                    comando=comando,
                    lleva_bandera=BANDERA in resto,
                    bandera_despues_del_comando=BANDERA in resto[1:],
                    texto=linea.strip(),
                )
            )

    return salida


def barrer(raiz: Path, relativos: List[str]) -> List[Invocacion]:
    """Corre el detector sobre cada archivo, en el orden en que se le pasan."""
    encontradas = []

    for rel in relativos:
        if rel in NO_BARRER:
            continue
        try:
            texto = (raiz / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        if "mesh" not in texto.lower():
            continue
        encontradas.extend(invocaciones(texto, archivo=rel))

    return encontradas


def archivos_versionados(raiz: Path) -> List[str]:
    """Todo lo que el repo versiona, desde la RAÍZ.

    Barrer sólo los tres `.sh` conocidos sería medir lo que ya se sabe: la
    invocación nueva que este gate existe para atrapar puede aparecer en un
    archivo que todavía no existe. Si `git` no responde, esto revienta en vez de
    devolver una lista corta — una lista corta es indistinguible de un repo
    limpio.
    """
    p = subprocess.run(
        ["git", "-C", str(raiz), "ls-files", "-z"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if p.returncode != 0:
        raise AssertionError(f"git ls-files falló en {raiz}: {p.stderr.strip()}")

    nombres = [n for n in p.stdout.split("\0") if n]
    if not nombres:
        raise AssertionError(f"git ls-files no devolvió archivos en {raiz}")
    return nombres


def _raiz_del_repo() -> Path:
    # BASE_DIR es api/observerrmm; la raíz está dos niveles arriba.
    return Path(settings.BASE_DIR).parent.parent


class TestBarridoDelRepo(ObserverTestCase):
    def setUp(self):
        self.raiz = _raiz_del_repo()
        self.relativos = archivos_versionados(self.raiz)
        self.encontradas = barrer(self.raiz, self.relativos)

    def test_el_barrido_alcanza_los_scripts_que_sirve_el_backend(self):
        """Que el barrido llegue de verdad a los archivos que importan.

        Sin esto, un cambio en cómo se listan los archivos podría dejar los tres
        `.sh` afuera y el gate seguiría verde."""
        for ruta in (
            settings.LINUX_AGENT_SCRIPT,
            settings.MACOS_AGENT_SCRIPT,
            settings.MAC_UNINSTALL,
        ):
            rel = str(Path(ruta).relative_to(self.raiz))
            with self.subTest(archivo=rel):
                self.assertIn(rel, self.relativos)

    def test_el_censo_es_exactamente_el_declarado(self):
        """Una invocación nueva rompe acá aunque venga conforme: alguien tiene
        que mirarla y agregarla al CENSO a mano."""
        real = [(i.archivo, i.comando, i.lleva_bandera) for i in self.encontradas]

        self.assertEqual(sorted(real), sorted(CENSO))

    def test_toda_invocacion_con_argumentos_lleva_la_bandera(self):
        """El gate, en una línea."""
        infractoras = [i for i in self.encontradas if not i.conforme()]

        self.assertEqual(
            infractoras,
            [],
            "invocaciones del binario del mesh sin `--no-embedded=1` después del "
            "comando:\n"
            + "\n".join(f"  {i.archivo}:{i.linea}  {i.texto}" for i in infractoras),
        )

    def test_las_excepciones_son_las_declaradas(self):
        exentas = [i for i in self.encontradas if i.comando in EXCEPCIONES]

        self.assertEqual({i.comando for i in exentas}, EXCEPCIONES)
        self.assertEqual(
            sorted(i.archivo for i in exentas),
            sorted([LINUX, MACOS]),
        )

    def test_el_gate_se_excluye_a_si_mismo_y_nada_mas(self):
        """La exclusión es un agujero: lo que se excluye no se mira. Que sea uno
        solo y que sea este archivo."""
        self.assertEqual(NO_BARRER, {"api/observerrmm/core/test_mesh_no_embedded.py"})
        self.assertTrue((self.raiz / next(iter(NO_BARRER))).is_file())


class TestControlPositivo(ObserverTestCase):
    """Que el detector sepa decir «no».

    Un barrido roto y un repo conforme se ven idénticos desde un `assertEqual([],
    infractoras)`. Estos tests le dan al MISMO código las líneas que tiene que
    denunciar."""

    def _infractoras(self, guion: str):
        return [i for i in invocaciones(guion) if not i.conforme()]

    def test_una_invocacion_sin_la_bandera_se_denuncia(self):
        guion = "timeout 120 ${meshSystemBin} -fulluninstall\n"

        infractoras = self._infractoras(guion)

        self.assertEqual(len(infractoras), 1)
        self.assertEqual(infractoras[0].comando, "-fulluninstall")

    def test_la_ruta_literal_tambien_se_denuncia(self):
        guion = "  /opt/observermesh/meshagent -nodeid\n"

        self.assertEqual(len(self._infractoras(guion)), 1)

    def test_la_bandera_antes_del_comando_no_sirve(self):
        """La bandera va DESPUÉS del comando: el binario la interpreta como una
        opción del subcomando, no del proceso."""
        guion = "${meshBin} --no-embedded=1 -fulluninstall\n"

        self.assertEqual(len(self._infractoras(guion)), 1)

    def test_un_binario_mesh_con_otro_nombre_de_variable_igual_se_ve(self):
        guion = "${meshServiceExe} -uninstall\n"

        self.assertEqual(len(self._infractoras(guion)), 1)

    def test_el_barrido_recorre_archivos_de_verdad(self):
        """Control positivo del barrido completo, no sólo del detector: se
        planta un `.sh` sin bandera y `barrer` tiene que traerlo."""
        raiz = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, raiz, True)
        (raiz / "nuevo.sh").write_text("${meshBin} -fulluninstall\n", encoding="utf-8")

        encontradas = barrer(raiz, ["nuevo.sh"])

        self.assertEqual(len(encontradas), 1)
        self.assertFalse(encontradas[0].conforme())


class TestControlNegativo(ObserverTestCase):
    """Que el detector sepa decir «sí».

    Un gate que denunciara todo se vería igual de rojo que uno correcto, y el
    primer arreglo sería apagarlo."""

    def test_las_invocaciones_conformes_pasan(self):
        guion = (
            "env XAUTHORITY=foo DISPLAY=bar timeout 120 ${meshSystemBin} "
            "-fulluninstall --no-embedded=1\n"
            "perl -e 'alarm shift; exec @ARGV' 120 \"${meshBin}\" -uninstall "
            "--no-embedded=1\n"
        )

        encontradas = invocaciones(guion)

        self.assertEqual(len(encontradas), 2)
        self.assertTrue(all(i.conforme() for i in encontradas))

    def test_el_binario_como_argumento_no_es_una_invocacion(self):
        guion = (
            'wget --no-check-certificate -q -O ${meshTmpBin} "${meshDL}"\n'
            "if [ $? -ne 0 ] || [ ! -s ${meshTmpBin} ]; then\n"
            "chmod +x ${meshTmpBin}\n"
            'if [ -f "${meshBin}" ]; then\n'
            'curl -fL --insecure -o "${meshTmpBin}" "${meshDL}"\n'
            'meshSystemBin="${meshDir}/meshagent"\n'
            "rm -rf ${meshDir}\n"
        )

        self.assertEqual(invocaciones(guion), [])

    def test_el_agente_observer_no_es_el_binario_del_mesh(self):
        """`${agentBin} -m nixmeshnodeid` nombra al mesh y lleva argumentos, pero
        el binario es el nuestro y no tiene instalador anexado."""
        guion = 'MESH_NODE_ID=$("${agentBin}" -m nixmeshnodeid)\n'

        self.assertEqual(invocaciones(guion), [])

    def test_los_comentarios_no_son_codigo(self):
        guion = "# `meshagent -nodeid` devolvía la salida de una reinstalación\n"

        self.assertEqual(invocaciones(guion), [])
