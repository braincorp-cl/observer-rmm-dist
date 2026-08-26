"""Firma del certificado de borrado (C2).

**Con qué se arranca: firma propia, lista para FEA.** Una clave RSA gestionada por
BrainCorp, custodiada FUERA de la aplicación (patrón autovault, igual que
`LOST_MODE_EVIDENCE_KEY`: `install.yml` la genera por ambiente, la guarda cifrada
en el vault y la renderiza en `local_settings.py`; no se versiona, no viaja a la
flota). Firma el documento canónico del certificado (el mismo bundle que arma el
PDF y el JSON), de modo que cualquier alteración posterior se detecta.

**Preparado para firma electrónica avanzada (Ley 19.799) sin rediseño.** La firma
se resuelve detrás de la interfaz `Signer`; hoy el único backend es
`LocalRSASigner`. Cuando un cliente exija FEA, se agrega un backend que delegue en
un proveedor acreditado y se selecciona por settings, sin tocar el modelo ni el
generador de certificados: lo que se firma (bytes canónicos) y lo que se guarda
(`signature`, `signature_alg`, `signing_key_id`) no cambian.

**Si no hay clave configurada**, el certificado se emite SIN firma (`signature=""`)
y así queda registrado. No se inventa una firma ni se bloquea la emisión: un
ambiente sin clave es un ambiente de prueba, y eso se ve en el propio certificado,
no se descubre al verificar.
"""

import base64
import hashlib
from typing import Optional, Tuple

from django.conf import settings


class SignerError(Exception):
    pass


class Signer:
    alg: str = ""

    def key_id(self) -> str:
        raise NotImplementedError

    def sign(self, data: bytes) -> bytes:
        raise NotImplementedError

    def verify(self, data: bytes, signature: bytes) -> bool:
        raise NotImplementedError

    def public_key_pem(self) -> str:
        raise NotImplementedError


class LocalRSASigner(Signer):
    """RSA-PSS SHA-256 con clave PEM en `settings.ERASE_SIGNING_KEY`."""

    alg = "RSASSA-PSS-SHA256"

    def __init__(self, private_pem: str) -> None:
        from cryptography.hazmat.primitives import serialization

        try:
            self._key = serialization.load_pem_private_key(
                private_pem.encode(), password=None
            )
        except (ValueError, TypeError) as e:
            raise SignerError(
                "ERASE_SIGNING_KEY no es una clave privada PEM válida. "
                "Regenerarla con install.yml."
            ) from e

    def key_id(self) -> str:
        from cryptography.hazmat.primitives import serialization

        der = self._key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return hashlib.sha256(der).hexdigest()[:16]

    def sign(self, data: bytes) -> bytes:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        return self._key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

    def verify(self, data: bytes, signature: bytes) -> bool:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        try:
            self._key.public_key().verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            return False

    def public_key_pem(self) -> str:
        from cryptography.hazmat.primitives import serialization

        return (
            self._key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )


def get_signer() -> Optional[Signer]:
    """Devuelve el firmante del ambiente, o None si no hay clave configurada."""
    pem = (getattr(settings, "ERASE_SIGNING_KEY", "") or "").strip()
    if not pem:
        return None
    return LocalRSASigner(pem)


def signing_available() -> bool:
    return get_signer() is not None


def sign_document(data: bytes) -> Tuple[str, str, str]:
    """Firma `data`. Devuelve `(signature_b64, alg, key_id)`.

    Si no hay clave, devuelve `("", "", "")` — certificado sin firma, registrado
    como tal.
    """
    signer = get_signer()
    if signer is None:
        return "", "", ""
    signature = signer.sign(data)
    return base64.b64encode(signature).decode(), signer.alg, signer.key_id()


def verify_document(data: bytes, signature_b64: str) -> bool:
    """Verifica la firma de `data`. Sin clave o sin firma ⇒ False."""
    signer = get_signer()
    if signer is None or not signature_b64:
        return False
    try:
        signature = base64.b64decode(signature_b64)
    except (ValueError, TypeError):
        return False
    return signer.verify(data, signature)
