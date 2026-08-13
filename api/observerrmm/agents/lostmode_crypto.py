"""Cifrado en reposo de la evidencia del modo perdido/robado (030 · T020, ADR-025 punto 5).

**Qué se cifra y qué no.** Sólo el ARCHIVO (la captura de pantalla, y mañana la
foto de webcam). Las coordenadas, el ciclo, el motivo y las fechas siguen en
columnas normales de PostgreSQL: son lo que la consola lista, ordena y filtra, y
cifrarlas volvería la línea de tiempo imposible de consultar sin descifrar la
tabla entera. Lo que expone a una persona es la imagen, y es la imagen la que
queda ilegible para quien lea el disco.

**De dónde sale la llave: el patrón autovault.** `install.yml` genera una llave
Fernet por ambiente la primera vez, la guarda cifrada en
`group_vars/observer_api/vault_lostmode.yml` (gitignored) y la renderiza en
`local_settings.py`. No se versiona, no viaja a la flota y no está en el código.

**Compatibilidad hacia atrás, deliberada.** Un archivo escrito antes de que
existiera la llave se lee igual: el cifrado se reconoce por CABECERA, no por una
columna de la tabla. Sin eso, encender el cifrado en un ambiente con casos
abiertos habría dejado la evidencia ya capturada como bytes ilegibles sin
ningún aviso — exactamente el "ok falso" que esta feature no puede permitirse.
La cabecera además hace que un archivo cifrado se pueda identificar con `head -c
10` sobre el disco, sin la llave y sin la base de datos.

**Si la llave se pierde, la evidencia cifrada se pierde con ella.** No hay
recuperación y no debe haberla: una copia de rescate del material de ADR-025
sería un segundo depósito que nadie inventaría. La llave se respalda con el
resto del vault del ambiente.
"""

from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

# Cabecera de los archivos cifrados por este módulo. Lleva versión porque
# cambiar de esquema más adelante (otra AEAD, llaves rotadas por caso) tiene que
# poder convivir con lo ya escrito en disco.
EVIDENCE_MAGIC = b"ORMM-LME1\n"


class EvidenceKeyMissing(Exception):
    """Hay un archivo cifrado en disco y el ambiente no tiene la llave.

    Es un error explícito y no una lectura silenciosa de bytes crudos: devolver
    el ciphertext como si fuera un PNG dejaría a la consola mostrando una imagen
    rota, y "la imagen no se ve" es indistinguible de "el equipo capturó negro".
    """


def _fernet() -> Optional[Fernet]:
    llave = (getattr(settings, "LOST_MODE_EVIDENCE_KEY", "") or "").strip()
    if not llave:
        return None
    try:
        return Fernet(llave.encode())
    except (ValueError, TypeError) as e:
        # Una llave mal formada es un error de despliegue, no un modo de
        # operación: si se ignorara, el ambiente escribiría evidencia en claro
        # creyendo que la cifra.
        raise ValueError(
            "LOST_MODE_EVIDENCE_KEY no es una llave Fernet válida "
            "(32 bytes en base64 urlsafe). Regenerarla con install.yml."
        ) from e


def encryption_enabled() -> bool:
    """¿Este ambiente cifra la evidencia que reciba de ahora en adelante?"""
    return _fernet() is not None


def is_encrypted(blob: bytes) -> bool:
    return blob.startswith(EVIDENCE_MAGIC)


def encrypt_bytes(raw: bytes) -> bytes:
    """Cifra si hay llave; si no la hay devuelve el contenido tal cual.

    No lanza cuando falta la llave a propósito: negarse a guardar dejaría al
    operador de un caso ABIERTO sin las capturas de ese ciclo, que es un daño
    peor y además irrecuperable. Que el ambiente no cifra se ve en el estado que
    devuelve el listado del caso (`encryption.enabled`), no se descubre el día
    que alguien lea el disco.
    """
    f = _fernet()
    if f is None:
        return raw
    return EVIDENCE_MAGIC + f.encrypt(raw)


def decrypt_bytes(blob: bytes) -> bytes:
    """Descifra si el archivo lleva la cabecera; si no, lo devuelve intacto."""
    if not is_encrypted(blob):
        return blob

    f = _fernet()
    if f is None:
        raise EvidenceKeyMissing(
            "Esta evidencia está cifrada y el ambiente no tiene "
            "LOST_MODE_EVIDENCE_KEY configurada."
        )

    try:
        return f.decrypt(blob[len(EVIDENCE_MAGIC) :])
    except InvalidToken as e:
        raise EvidenceKeyMissing(
            "Esta evidencia no se puede descifrar con la llave de este ambiente "
            "(¿llave rotada, o evidencia restaurada desde otro servidor?)."
        ) from e
