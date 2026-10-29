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

**Una clave POR TENANT** (decisión 2026-10-29). El `key_id` identifica al emisor
concreto, cada cliente verifica contra la clave de su propia instancia y
comprometer una no toca a las demás. Es la misma razón por la que cada tenant
tiene su base y su MeshCentral: el certificado se entrega a terceros y conviene
que la firma ate a quien lo emitió, no al software que lo generó.

**La rotación NO es rutina, es respuesta a incidente.** Una clave pública no
caduca, así que rotar por calendario no compra nada acá: no hay CA ni certificado
que venza, y RSA-4096 con PSS no se queda corto en un plazo relevante. La única
razón real para retirar una clave es que la privada se haya comprometido. Pero
rotar **debe ser posible sin romper el pasado**, y por eso la verificación elige
la clave por el `key_id` que el propio documento declara, nunca «la clave
actual»: un certificado firmado en 2026 se sigue verificando en 2035 mientras su
clave pública siga publicada. Las retiradas viven en
`settings.ERASE_SIGNING_KEYS_RETIRED` como PEM **públicos** — para verificar no
hace falta la privada, y no tenerla es justamente lo que se quiere después de un
compromiso.

🔑 **Y rotar no basta ante un compromiso**: quien tenga la privada puede firmar
certificados falsos y antedatarlos. Lo que separa lo genuino de lo forjado es la
**cadena de hashes** del repositorio append-only —un certificado inventado no
encaja en ella—, no la firma. Por eso la verificación de la cadena vale más que
cualquier esquema de rotación.

**Si no hay clave configurada**, el certificado se emite SIN firma (`signature=""`)
y así queda registrado. No se inventa una firma ni se bloquea la emisión: un
ambiente sin clave es un ambiente de prueba, y eso se ve en el propio certificado,
no se descubre al verificar.
"""

import base64
import hashlib
from typing import Dict, List, Optional, Tuple

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


class RSAPublicVerifier(Signer):
    """Solo verifica: lleva la clave PÚBLICA de una clave retirada.

    No puede firmar, y es deliberado. Después de un compromiso la privada no debe
    seguir en ninguna parte; lo único que hay que conservar para siempre es la
    pública, para que los certificados ya emitidos sigan verificándose.
    """

    alg = LocalRSASigner.alg

    def __init__(self, public_pem: str) -> None:
        from cryptography.hazmat.primitives import serialization

        try:
            self._pub = serialization.load_pem_public_key(public_pem.encode())
        except (ValueError, TypeError) as e:
            raise SignerError(
                "ERASE_SIGNING_KEYS_RETIRED trae un PEM público inválido."
            ) from e

    def key_id(self) -> str:
        from cryptography.hazmat.primitives import serialization

        der = self._pub.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return hashlib.sha256(der).hexdigest()[:16]

    def sign(self, data: bytes) -> bytes:
        raise SignerError("una clave retirada no firma")

    def verify(self, data: bytes, signature: bytes) -> bool:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        try:
            self._pub.verify(
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

        return self._pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()


def get_signer() -> Optional[Signer]:
    """Devuelve el firmante ACTIVO del ambiente, o None si no hay clave.

    Es el que FIRMA. Para verificar no se usa éste sino `get_verifier(key_id)`:
    un certificado se verifica con la clave que lo firmó, no con la de hoy.
    """
    pem = (getattr(settings, "ERASE_SIGNING_KEY", "") or "").strip()
    if not pem:
        return None
    return LocalRSASigner(pem)


def retired_verifiers() -> List[Signer]:
    """Claves retiradas, en PEM público. Verifican, no firman."""
    pems = getattr(settings, "ERASE_SIGNING_KEYS_RETIRED", None) or []
    salida: List[Signer] = []
    for pem in pems:
        pem = (pem or "").strip()
        if pem:
            salida.append(RSAPublicVerifier(pem))
    return salida


def get_verifier(key_id: str = "") -> Optional[Signer]:
    """El verificador cuya clave coincide con `key_id`.

    Sin `key_id` —certificados del esquema v1, que no lo declaraban— cae al
    firmante activo, que es el comportamiento anterior.
    """
    activo = get_signer()
    if not key_id:
        return activo
    for s in ([activo] if activo else []) + retired_verifiers():
        if s.key_id() == key_id:
            return s
    return None


def public_keys() -> List[Dict[str, str]]:
    """Todas las claves públicas publicables, activa primero.

    Es un CONJUNTO y no una sola a propósito: con una sola, el día que se retire
    una clave todos los certificados firmados con ella dejarían de verificar. El
    documento ya declara su `key_id`, así que el destinatario sabe cuál tomar.
    """
    salida: List[Dict[str, str]] = []
    activo = get_signer()
    if activo is not None:
        salida.append(
            {
                "key_id": activo.key_id(),
                "algorithm": activo.alg,
                "status": "active",
                "public_key_pem": activo.public_key_pem(),
            }
        )
    for s in retired_verifiers():
        salida.append(
            {
                "key_id": s.key_id(),
                "algorithm": s.alg,
                "status": "retired",
                "public_key_pem": s.public_key_pem(),
            }
        )
    return salida


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


def verify_document(data: bytes, signature_b64: str, key_id: str = "") -> bool:
    """Verifica la firma de `data` con la clave que la produjo.

    🔑 Elige por `key_id`, no por «la clave actual»: si se verificara siempre con
    la activa, retirar una clave pondría en inválidos todos los certificados que
    firmó — incluido el chip de la consola. Un `key_id` que no se reconoce ⇒
    `False`, que es lo correcto: no se puede afirmar nada sobre esa firma.
    """
    signer = get_verifier(key_id)
    if signer is None or not signature_b64:
        return False
    try:
        signature = base64.b64decode(signature_b64)
    except (ValueError, TypeError):
        return False
    return signer.verify(data, signature)
