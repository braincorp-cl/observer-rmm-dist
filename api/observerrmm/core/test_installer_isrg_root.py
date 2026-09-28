"""Que `installer.ps1` lleve la raíz de Let's Encrypt a los equipos que no la tienen.

El exe se baja de `agents.observer.cl` (cert Let's Encrypt, cadena a ISRG Root X1).
Windows obtiene esa raíz bajo demanda desde `ctldl.windowsupdate.com`; donde ese
host está bloqueado o la actualización de raíces está desactivada por GPO, la
raíz no llega y `WebClient.DownloadFile` falla con «No se puede establecer una
relación de confianza para el canal seguro SSL/TLS», aunque el navegador del
mismo equipo abra la URL sin problema. Medido en SML Valparaíso el 2026-09-28.

Se afirma sobre el texto porque no hay dónde correr PowerShell en la CI del
backend; la verificación de verdad es en terreno.
"""

import base64
import hashlib
import re
from pathlib import Path

from django.conf import settings

from observerrmm.test import ObserverTestCase

HUELLA_ISRG_ROOT_X1 = "CABD2A79A1076A31F21D253635CB039D4329A5E8"


class TestInstallerPs1AgregaIsrgRootX1(ObserverTestCase):
    def setUp(self):
        self.ps1 = (Path(settings.BASE_DIR) / "core" / "installer.ps1").read_text()

    def test_la_raiz_embebida_es_isrg_root_x1(self):
        """La huella se calcula sobre el DER embebido: si alguien pega otro
        certificado, el SHA-1 deja de coincidir."""
        b64 = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", self.ps1).group(1)
        der = base64.b64decode(b64)

        self.assertEqual(hashlib.sha1(der).hexdigest().upper(), HUELLA_ISRG_ROOT_X1)
        self.assertIn(f"$thumb = '{HUELLA_ISRG_ROOT_X1}'", self.ps1)

    def test_se_agrega_antes_de_descargar(self):
        pos_llamada = self.ps1.index("\n    Install-IsrgRootX1\n")
        pos_descarga = self.ps1.index("$wc.DownloadFile(")

        self.assertLess(pos_llamada, pos_descarga)

    def test_solo_si_falta_y_verificando_la_huella(self):
        funcion = self.ps1[self.ps1.index("function Install-IsrgRootX1") :]
        funcion = funcion[: funcion.index("\n    Install-IsrgRootX1\n")]

        self.assertIn('Test-Path "Cert:\\LocalMachine\\Root\\$thumb"', funcion)
        self.assertIn("$cert.Thumbprint -ne $thumb", funcion)
