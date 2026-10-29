"""La firma del certificado es verificable POR UN TERCERO (053 · RF-08 · T017).

Hasta esta feature `public_key_pem()` existía en las dos implementaciones de
`Signer` y **no se llamaba desde ninguna parte**: quien recibía un certificado
tenía `signature.value`, `algorithm` y `key_id`, pero ninguna llave contra la cual
probarlos. Lo único que podía comprobar solo —recalcular el `document_hash`—
prueba consistencia interna, no autoría. La firma era decorativa fuera de Observer.

El test que importa es `test_V7_un_tercero_verifica_con_openssl`: sale de Python,
usa `openssl` con la clave publicada y los bytes canónicos rearmados del documento,
y trae su control negativo. Es lo que un auditor haría, y es lo que destapó que la
receta publicada estaba mal: el firmante usa salt **máximo** (222 bytes con
RSA-2048), así que verificar con `rsa_pss_saltlen:-1` —el largo del digest, que es
lo que uno escribiría por defecto— **rechaza una firma válida**.
"""

import base64
import json
import subprocess
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings
from model_bakery import baker

from erase import certificate as cert_mod
from erase.models import CertificateKind
from observerrmm.test import ObserverTestCase

_llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CLAVE_PRIVADA = _llave.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()


@override_settings(
    ERASE_SIGNING_KEY=CLAVE_PRIVADA,
    # El host real va PRIMERO porque signing_key_url() usa ALLOWED_HOSTS[0];
    # "testserver" tiene que estar o el cliente de pruebas se rechaza a si mismo.
    ALLOWED_HOSTS=["api.tenant.observer.cl", "testserver"],
)
class SigningKeyTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client", name="Cliente X")

    def test_el_endpoint_publica_la_clave_sin_auth(self):
        self.client.logout()
        r = self.client.get("/erase/signing-key/")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        print("\n  available =", d["available"], "| key_id =", d["key_id"])
        print("  algorithm =", d["algorithm"])
        self.assertTrue(d["available"])
        self.assertIn("BEGIN PUBLIC KEY", d["public_key_pem"])
        self.assertNotIn("PRIVATE", d["public_key_pem"])
        self.assertEqual(len(d["key_id"]), 16)

    @override_settings(ERASE_SIGNING_KEY="")
    def test_sin_clave_lo_dice_en_vez_de_404(self):
        self.client.logout()
        r = self.client.get("/erase/signing-key/")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        print("  sin clave ->", d["detail"][:60])
        self.assertFalse(d["available"])
        self.assertEqual(d["public_key_pem"], "")

    def test_la_url_viaja_dentro_del_documento_firmado(self):
        cert = cert_mod.issue_certificate(
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=self.client_obj,
            tenant="Cliente X",
        )
        url = cert.data["signing_key_url"]
        print("  signing_key_url =", url)
        self.assertEqual(url, "https://api.tenant.observer.cl/erase/signing-key/")
        # Cubierta por la firma: alterarla rompe el hash.
        copia = dict(cert.data)
        copia["signing_key_url"] = "https://atacante.example/erase/signing-key/"
        import hashlib

        self.assertNotEqual(
            hashlib.sha256(cert_mod.canonical_bytes(copia)).hexdigest(),
            cert.document_hash,
        )

    def test_V7_un_tercero_verifica_con_openssl(self):
        """La prueba que importa: openssl, fuera de Python y fuera de la consola."""
        cert = cert_mod.issue_certificate(
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=self.client_obj,
            tenant="Cliente X",
            operator="john",
        )
        paquete = cert_mod.certificate_json(cert)

        self.client.logout()
        pem = self.client.get("/erase/signing-key/").json()["public_key_pem"]

        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            # Los bytes canonicos se rearman del documento publicado, no se piden.
            canonico = json.dumps(
                paquete["document"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            (t / "doc.bin").write_bytes(canonico)
            (t / "pub.pem").write_text(pem)
            (t / "sig.bin").write_bytes(base64.b64decode(paquete["signature"]["value"]))

            r = subprocess.run(
                [
                    "openssl",
                    "dgst",
                    "-sha256",
                    "-verify",
                    str(t / "pub.pem"),
                    "-sigopt",
                    "rsa_padding_mode:pss",
                    "-sigopt",
                    "rsa_pss_saltlen:-2",
                    "-signature",
                    str(t / "sig.bin"),
                    str(t / "doc.bin"),
                ],
                capture_output=True,
                text=True,
            )
            print("  openssl:", (r.stdout + r.stderr).strip())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("Verified OK", r.stdout)

            # Control negativo: un byte distinto y openssl lo rechaza.
            (t / "malo.bin").write_bytes(canonico.replace(b'"john"', b'"jhon"'))
            r2 = subprocess.run(
                [
                    "openssl",
                    "dgst",
                    "-sha256",
                    "-verify",
                    str(t / "pub.pem"),
                    "-sigopt",
                    "rsa_padding_mode:pss",
                    "-sigopt",
                    "rsa_pss_saltlen:-2",
                    "-signature",
                    str(t / "sig.bin"),
                    str(t / "malo.bin"),
                ],
                capture_output=True,
                text=True,
            )
            print(
                "  openssl con un byte alterado:", (r2.stdout + r2.stderr).strip()[:60]
            )
            self.assertNotEqual(r2.returncode, 0)
