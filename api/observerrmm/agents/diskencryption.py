"""Feature 037 · el veredicto de cumplimiento de cifrado (Fase 2).

Acá vive **la** regla del panel: cómo se pasa de las filas que escribe el
microservicio Go a uno de los cuatro estados de RF-04. La regla es RN-A02 —el
veredicto del equipo es el de su **volumen de sistema**, sin estados intermedios
tipo «parcial»— más RN-A03 —«sin dato» y «sin cifrar» son cosas distintas—.

🪤 La regla se necesita en dos formas y esa es la trampa de este archivo:

* en **Python**, para responder el estado de cada fila del panel;
* en **SQL**, para que el filtro por estado no traiga la flota entera a memoria
  y la recorra (RF-04 con 28.300 agentes a escala).

Dos formas es dos copias, y dos copias divergen. Por eso las dos viven en este
archivo, una al lado de la otra, y hay una prueba —`test_disk_encryption.py`,
`test_sql_y_python_coinciden`— que las contrasta caso por caso. Si alguien toca
una y no la otra, esa prueba se pone roja.
"""

from django.db.models import Q

from observerrmm.constants import (
    DISK_ENCRYPTION_PROTECTION_OFF,
    DISK_ENCRYPTION_PROTECTION_ON,
    DiskEncryptionStatus,
)


def volumen_de_sistema(agent):
    """El volumen que decide el veredicto, o None si no hay.

    Espera que la vista haya hecho el `Prefetch` a `system_volumes`; si no está,
    cae a una consulta. La caída existe para que la función sirva también en el
    detalle de un agente, donde una consulta más no cambia nada.
    """
    volumenes = getattr(agent, "system_volumes", None)
    if volumenes is None:
        return agent.disk_encryption_volumes.filter(is_system_volume=True).first()
    return volumenes[0] if volumenes else None


def derivar_estado(agent) -> str:
    """El estado del EQUIPO, derivado (RN-A02).

    El orden de las guardas no es estético: cada una tapa una forma de mentir.

    1. Sin fila de estado: nunca reportó. **Sin dato**, jamás «sin cifrar» —es
       el caso de un agente anterior a la feature, o de uno que nunca prendió.
    2. Con error de consulta: no sabemos. **Sin dato** con causa (RF-07).
    3. Sin soporte: el equipo no ofrece BitLocker. Es su propio estado, no un
       incumplimiento (RN-A07).
    4. Sin volumen de sistema en el reporte: reportó, pero no sabemos cuál
       manda. Preferimos «sin dato» a un veredicto inventado.
    5. Y sólo acá se mira la protección. Un `protection_status` que no sea 0 ni 1
       —el 2 de WMI es literalmente «desconocido»— también es **sin dato**.
    """
    estado = getattr(agent, "disk_encryption", None)
    if estado is None:
        return DiskEncryptionStatus.NO_DATA

    if estado.query_error:
        return DiskEncryptionStatus.NO_DATA

    if not estado.supported:
        return DiskEncryptionStatus.UNSUPPORTED

    volumen = volumen_de_sistema(agent)
    if volumen is None:
        return DiskEncryptionStatus.NO_DATA

    if volumen.protection_status == DISK_ENCRYPTION_PROTECTION_ON:
        return DiskEncryptionStatus.ENCRYPTED
    if volumen.protection_status == DISK_ENCRYPTION_PROTECTION_OFF:
        return DiskEncryptionStatus.UNENCRYPTED

    return DiskEncryptionStatus.NO_DATA


# La misma regla, en SQL. Se lee de arriba abajo como la de Python: cada entrada
# es la traducción literal de su guarda.
#
# `disk_encryption__isnull` funciona porque la relación es OneToOne: un agente
# sin reporte no tiene fila, y eso es exactamente el cuarto estado.
#
# 🪤 «Sin error» es NULO **o vacío**, no sólo nulo. En Python la guarda es
# `if estado.query_error:`, y una cadena vacía es falsa; si acá se preguntara
# sólo por `isnull`, una fila con `query_error=''` caería en «sin dato» para el
# filtro y en «cifrado» para la fila del panel — el mismo equipo contado de dos
# maneras en la misma pantalla. El agente no emite errores vacíos, pero la
# columna los admite y la divergencia no depende de las buenas intenciones del
# escritor.
_SIN_ERROR = Q(disk_encryption__query_error__isnull=True) | Q(
    disk_encryption__query_error=""
)
_CON_ERROR = Q(disk_encryption__query_error__isnull=False) & ~Q(
    disk_encryption__query_error=""
)

_SIN_DATO = (
    Q(disk_encryption__isnull=True)
    | _CON_ERROR
    | (
        Q(disk_encryption__supported=True)
        & _SIN_ERROR
        & ~Q(
            disk_encryption_volumes__is_system_volume=True,
            disk_encryption_volumes__protection_status__in=(
                DISK_ENCRYPTION_PROTECTION_OFF,
                DISK_ENCRYPTION_PROTECTION_ON,
            ),
        )
    )
)

_CON_VEREDICTO = (
    Q(disk_encryption__isnull=False) & _SIN_ERROR & Q(disk_encryption__supported=True)
)

FILTROS_POR_ESTADO = {
    DiskEncryptionStatus.ENCRYPTED: _CON_VEREDICTO
    & Q(
        disk_encryption_volumes__is_system_volume=True,
        disk_encryption_volumes__protection_status=DISK_ENCRYPTION_PROTECTION_ON,
    ),
    DiskEncryptionStatus.UNENCRYPTED: _CON_VEREDICTO
    & Q(
        disk_encryption_volumes__is_system_volume=True,
        disk_encryption_volumes__protection_status=DISK_ENCRYPTION_PROTECTION_OFF,
    ),
    DiskEncryptionStatus.UNSUPPORTED: Q(disk_encryption__isnull=False)
    & _SIN_ERROR
    & Q(disk_encryption__supported=False),
    DiskEncryptionStatus.NO_DATA: _SIN_DATO,
}


def filtro_por_estado(estado: str):
    """El `Q` que deja sólo los agentes en ese estado, o None si no es válido.

    Devolver None en vez de levantar deja que la vista decida: un filtro
    desconocido en la URL no puede tumbar el panel, pero tampoco puede
    silenciosamente devolver la flota entera como si el filtro se hubiera
    aplicado — la vista responde 400.
    """
    return FILTROS_POR_ESTADO.get(estado)
