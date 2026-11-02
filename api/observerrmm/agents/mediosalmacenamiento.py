"""Feature 055 · el veredicto de categoría de sanitización alcanzable (RF-05).

Acá vive **la** regla del panel: cómo se pasa de las filas que escribe el
microservicio Go a uno de los seis veredictos. La regla es RN-03 —el veredicto
del equipo es el de su **disco de sistema**— más RN-02 —«no se pudo leer» no es
«no es capaz»—.

🪤 La regla se necesita en dos formas y esa es la trampa de este archivo, igual
que en `diskencryption.py`:

* en **Python**, para responder el veredicto de cada fila del panel;
* en **SQL**, para que el filtro por veredicto no traiga la flota entera a
  memoria y la recorra.

Dos formas es dos copias, y dos copias divergen. Por eso las dos viven en este
archivo, una al lado de la otra, y hay una prueba —`test_storage_media.py`,
`test_sql_y_python_coinciden`— que las contrasta caso por caso.

📌 Los códigos del sistema se guardan y se comparan **crudos** (RN-04). Este
archivo no traduce ninguno: la traducción a etiqueta vive en la consola, y los
nombres de los códigos en `observerrmm/constants.py`.
"""

from django.db.models import Q

from observerrmm.constants import (
    STORAGE_MEDIA_TYPE_HDD,
    STORAGE_MEDIA_TYPE_SCM,
    STORAGE_MEDIA_TYPE_SSD,
    StorageSanitizationVerdict,
    StorageSelfEncryption,
)

# Los medios sobre los que la sobrescritura NO es sanitización defendible. El
# estándar es explícito: en memoria de estado sólido el nivelado de desgaste y
# las celdas de reserva dejan fuera del alcance del comando parte del dato.
_MEDIOS_NO_MAGNETICOS = (STORAGE_MEDIA_TYPE_SSD, STORAGE_MEDIA_TYPE_SCM)


def disco_de_sistema(agent):
    """El disco que decide el veredicto, o None si no hay.

    Espera que la vista haya hecho el `Prefetch` a `system_disks`; si no está,
    cae a una consulta. La caída existe para que la función sirva también en el
    detalle de un agente, donde una consulta más no cambia nada.
    """
    discos = getattr(agent, "system_disks", None)
    if discos is None:
        return agent.storage_media_devices.filter(
            is_system_disk=True, removable=False
        ).first()
    return discos[0] if discos else None


def derivar_veredicto(agent) -> str:
    """El veredicto del EQUIPO, derivado (RN-03).

    El orden de las guardas no es estético: cada una tapa una forma de mentir.

    1. Sin fila de estado: nunca reportó. **Sin dato**.
    2. Con error de consulta: no sabemos. **Sin dato** con causa.
    3. Sin soporte: el sistema no expone la fuente de almacenamiento. Tampoco
       sabemos qué medio hay ⇒ **sin dato**. A diferencia del cifrado, acá «no
       soportado» no es una propiedad del equipo que valga la pena mostrar: no
       saber qué disco tiene no dice nada sobre el disco.
    4. Sin disco de sistema en el reporte: reportó, pero no sabemos cuál manda.
       Preferimos «sin dato» a un veredicto inventado.
    5. Disco virtualizado: el medio real está en otra parte. Ninguna categoría
       del estándar aplica al disco que el sistema operativo ve, y decir «sin
       categoría alcanzable» sería afirmar algo sobre un medio que no estamos
       mirando.
    6. Autocifrado **habilitado**: purge remoto. «Capaz pero no habilitado» no
       sirve — sin clave en uso no hay nada que destruir.
    7. El firmware declara un comando de sanitización: purge con imagen live.
       Va **antes** del magnético a propósito: el estándar prefiere purge sobre
       clear cuando las dos están disponibles.
    8. Magnético: la sobrescritura sí es defendible como clear. Esto se puede
       afirmar **sin** haber sondeado capacidades, porque el tipo de medio
       basta.
    9. 🔑 No magnético y **sin sondear capacidades**: *sin dato*, no «sin
       categoría». Decir que no hay categoría alcanzable cuando ni siquiera se
       preguntó al firmware es exactamente el ok falso que RN-02 prohíbe. Es el
       caso que el despliegue por fases hace inevitable, y la razón de ser de
       `capabilities_probed`.
    10. No magnético, sondeado, y el firmware no declara nada: ahí sí, **sin
        categoría alcanzable**. Se midió y no hay.
    """
    estado = getattr(agent, "storage_media", None)
    if estado is None:
        return StorageSanitizationVerdict.NO_DATA

    if estado.query_error:
        return StorageSanitizationVerdict.NO_DATA

    if not estado.supported:
        return StorageSanitizationVerdict.NO_DATA

    disco = disco_de_sistema(agent)
    if disco is None:
        return StorageSanitizationVerdict.NO_DATA

    if disco.is_virtual:
        return StorageSanitizationVerdict.VIRTUAL_MEDIA

    if disco.self_encrypting == StorageSelfEncryption.ENABLED:
        return StorageSanitizationVerdict.PURGE_REMOTE

    if (disco.sanitize_capabilities or {}).get("supported") is True:
        return StorageSanitizationVerdict.PURGE_LIVE_IMAGE

    if disco.media_type_code == STORAGE_MEDIA_TYPE_HDD:
        return StorageSanitizationVerdict.CLEAR_REMOTE

    if disco.media_type_code in _MEDIOS_NO_MAGNETICOS:
        if not estado.capabilities_probed:
            return StorageSanitizationVerdict.NO_DATA
        return StorageSanitizationVerdict.NO_CATEGORY

    # Tipo de medio nulo o sin especificar: no sabemos qué hay dentro.
    return StorageSanitizationVerdict.NO_DATA


# ---------------------------------------------------------------------------
# La misma regla, en SQL. Se lee de arriba abajo como la de Python: cada entrada
# es la traducción literal de su guarda.
# ---------------------------------------------------------------------------
#
# `storage_media__isnull` funciona porque la relación es OneToOne: un agente sin
# reporte no tiene fila, y eso es exactamente el estado «sin dato».
#
# 🪤 «Sin error» es NULO **o vacío**, no sólo nulo — la misma trampa que ya
# costó documentar en `diskencryption.py`. En Python la guarda es
# `if estado.query_error:` y una cadena vacía es falsa; preguntar sólo por
# `isnull` haría que una fila con `query_error=''` cayera en «sin dato» para el
# filtro y en un veredicto concreto para su propia fila: el mismo equipo contado
# de dos maneras en la misma pantalla.
_SIN_ERROR = Q(storage_media__query_error__isnull=True) | Q(
    storage_media__query_error=""
)
_CON_ERROR = Q(storage_media__query_error__isnull=False) & ~Q(
    storage_media__query_error=""
)

# El equipo reportó bien y su reporte sirve para decidir algo.
_REPORTE_UTIL = (
    Q(storage_media__isnull=False) & _SIN_ERROR & Q(storage_media__supported=True)
)


# El disco que manda. Se repite en cada filtro porque un `Q` sobre una relación
# a muchos tiene que nombrar sus condiciones JUNTAS: separarlas en dos `Q`
# encadenados haría que Django las resuelva contra filas distintas de la misma
# tabla, y el veredicto saldría de dos discos combinados.
def _sistema(**extra):
    return Q(
        storage_media_devices__is_system_disk=True,
        storage_media_devices__removable=False,
        **{f"storage_media_devices__{k}": v for k, v in extra.items()},
    )


_VIRTUAL = _sistema(is_virtual=True)
_AUTOCIFRADO = _sistema(is_virtual=False, self_encrypting=StorageSelfEncryption.ENABLED)
_CON_COMANDO = _sistema(is_virtual=False, sanitize_capabilities__supported=True) & ~Q(
    storage_media_devices__self_encrypting=StorageSelfEncryption.ENABLED
)

# Las guardas 6 y 7 ya se llevaron a los que tienen autocifrado o comando, así
# que las de abajo tienen que excluirlos explícitamente para no reclamarlos.
_SIN_VIA_DE_PURGE = ~Q(
    storage_media_devices__self_encrypting=StorageSelfEncryption.ENABLED
) & ~Q(storage_media_devices__sanitize_capabilities__supported=True)

_MAGNETICO = (
    _sistema(is_virtual=False, media_type_code=STORAGE_MEDIA_TYPE_HDD)
    & _SIN_VIA_DE_PURGE
)

_NO_MAGNETICO = (
    _sistema(is_virtual=False, media_type_code__in=_MEDIOS_NO_MAGNETICOS)
    & _SIN_VIA_DE_PURGE
)

# «Sin dato» es todo lo demás, y por eso se escribe por complemento: cualquier
# cosa que no caiga en un veredicto concreto cae acá. Escribirlo enumerando sus
# causas obligaría a acordarse de actualizarlo cada vez que se agrega un
# veredicto — y olvidarse significaría que un equipo no aparece en NINGÚN filtro.
_CON_VEREDICTO = (
    _VIRTUAL
    | _AUTOCIFRADO
    | _CON_COMANDO
    | _MAGNETICO
    | (_NO_MAGNETICO & Q(storage_media__capabilities_probed=True))
)

FILTROS_POR_VEREDICTO = {
    StorageSanitizationVerdict.VIRTUAL_MEDIA: _REPORTE_UTIL & _VIRTUAL,
    StorageSanitizationVerdict.PURGE_REMOTE: _REPORTE_UTIL & _AUTOCIFRADO,
    StorageSanitizationVerdict.PURGE_LIVE_IMAGE: _REPORTE_UTIL & _CON_COMANDO,
    StorageSanitizationVerdict.CLEAR_REMOTE: _REPORTE_UTIL & _MAGNETICO,
    StorageSanitizationVerdict.NO_CATEGORY: _REPORTE_UTIL
    & _NO_MAGNETICO
    & Q(storage_media__capabilities_probed=True),
    StorageSanitizationVerdict.NO_DATA: (
        Q(storage_media__isnull=True) | _CON_ERROR | Q(storage_media__supported=False)
    )
    | (_REPORTE_UTIL & ~_CON_VEREDICTO),
}


def filtro_por_veredicto(veredicto: str):
    """El `Q` que deja sólo los agentes en ese veredicto, o None si no es válido.

    Devolver None en vez de levantar deja que la vista decida: un filtro
    desconocido en la URL no puede tumbar el panel, pero tampoco puede
    devolver silenciosamente la flota entera como si el filtro se hubiera
    aplicado — la vista responde 400.
    """
    return FILTROS_POR_VEREDICTO.get(veredicto)
