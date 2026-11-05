import logging

from observerrmm.celery import app

logger = logging.getLogger("ormm")


@app.task
def dispatch_wipe_order(order_pk: int) -> str:
    """Despacha la orden al vencer la ventana de arrepentimiento (RF-G03).

    Se agenda con `eta=recovery_deadline` al confirmar. Si la orden fue cancelada
    dentro de la ventana, ya no está en `RECOVERY_WINDOW` y `dispatch_order` no
    hace nada. El despacho real al agente sigue GATED por ADR-029.
    """
    from erase.models import WipeOrder
    from erase.services import dispatch_order

    try:
        order = WipeOrder.objects.get(pk=order_pk)
    except WipeOrder.DoesNotExist:
        return "orden inexistente"

    dispatch_order(order=order)
    return f"ok:{order.status}"


@app.task
def prune_erase_attachments(dry_run: bool = False) -> str:
    """Retención D5: purga los ADJUNTOS vencidos del módulo de borrado seguro.

    Alcanza **las dos** tablas de adjuntos, con el plazo resuelto **por cliente**:

    - `RetrievedFile` — los archivos recuperados de un equipo perdido (042).
    - `DestructionEvidence` — el registro fotográfico de una destrucción física
      (053 · C7). 🔴 Hasta la ola 3 esta tabla **no se purgaba nunca**, así que la
      fotografía de una destrucción era permanente de facto, al revés de lo que
      declaran L-04 y la política de uso aceptable.

    🔒 **Jamás** toca `EraseCertificate` ni `EraseAuditRecord`: borra el binario y
    deja la fila con su `original_name`, su `size` y su `sha256`. Ese hash ya viaja
    dentro del documento firmado, así que purgar el archivo **no invalida nada** —
    quien conserve una copia todavía puede comprobar que es la que el certificado
    citó. Borrar la fila sería destruir evidencia; borrar el binario conservando el
    hash es retención.

    🪤 Agrupa por plazo y resuelve la retención **una vez por cliente**, no una por
    fila. Resolver por adjunto repetiría el N+1 que la ola 2 midió en la
    reconciliación (5,38 s con 6.000 actas) con el agravante de que acá **borra**.

    `dry_run=True` cuenta y devuelve exactamente lo mismo **sin borrar un solo
    archivo**: es lo que permite medir el alcance real antes de armar la purga en
    un ambiente con datos vivos.

    El plazo nunca baja del piso legal (RF-D5, ≥ 12 meses): lo garantiza
    `resolve_attachment_retention()`, que lo aplica al leer.
    """
    from collections import defaultdict
    from datetime import timedelta

    from django.utils import timezone

    from clients.models import Client
    from core.utils import get_core_settings
    from erase.models import DestructionEvidence, RetrievedFile
    from erase.services import resolve_attachment_retention

    core = get_core_settings()
    ahora = timezone.now()

    # Una resolución por cliente (no por fila), y después un solo recorrido por
    # cada plazo distinto: los clientes que comparten plazo comparten consulta.
    por_plazo = defaultdict(list)
    for client in Client.objects.only("pk", "erase_attachment_retention_days"):
        dias = resolve_attachment_retention(client=client, core=core)
        por_plazo[dias].append(client.pk)

    purgados = 0
    bytes_purgados = 0
    detalle = []

    for dias, client_pks in sorted(por_plazo.items()):
        corte = ahora - timedelta(days=dias)
        del_grupo = 0
        bytes_grupo = 0

        # Las dos rutas al cliente son FK directas y DISTINTAS. 🪤 Nunca
        # `agent__client`: `Agent.client` es una @property que resuelve
        # `self.site.client` y no se puede consultar desde el ORM.
        lotes = (
            RetrievedFile.objects.filter(
                order__client_id__in=client_pks, uploaded_at__lt=corte
            ).exclude(asset=""),
            DestructionEvidence.objects.filter(
                intake__client_id__in=client_pks, uploaded_at__lt=corte
            ).exclude(asset=""),
        )

        for qs in lotes:
            for fila in qs.iterator():
                if not fila.asset:
                    continue
                del_grupo += 1
                bytes_grupo += int(fila.size or 0)
                if dry_run:
                    continue
                fila.asset.delete(save=False)
                fila.asset = ""
                fila.save(update_fields=["asset"])

        purgados += del_grupo
        bytes_purgados += bytes_grupo
        if del_grupo:
            detalle.append(
                f"{dias}d:{len(client_pks)}cli:{del_grupo}adj:{bytes_grupo}b"
            )

    modo = "ensayo" if dry_run else "purga"
    resumen = " ".join(detalle) if detalle else "sin adjuntos vencidos"

    # 🪤 El detalle viaja en el VALOR DE RETORNO, no sólo en el log, y es
    # deliberado: el nivel por omisión de `ORMM_LOG_LEVEL` es ERROR
    # (`settings.py:193`), así que este `info` se descarta en silencio en una
    # instancia sin ajustar. Un borrado irreversible cuyo único rastro es una
    # línea que la configuración por omisión tira no es un rastro. El resultado
    # de la tarea sí lo guarda Celery, y es lo que se lee en el ensayo de T064.
    logger.info(
        "erase/retencion %s: %s adjuntos, %s bytes, %s grupos de plazo [%s]",
        modo,
        purgados,
        bytes_purgados,
        len(por_plazo),
        resumen,
    )
    return f"ok:{modo}:purged={purgados}:bytes={bytes_purgados}:{resumen}"


@app.task
def redispatch_pending_retrieval_orders() -> str:
    """Reintenta despachar órdenes de fileretrieval que quedaron en cola porque el
    equipo estaba offline. Idempotente: `dispatch_retrieval_order` sólo actúa sobre
    `pending`, y el `order_id` garantiza ejecución única en el agente.
    """
    from erase.models import FileRetrievalOrder, FileRetrievalStatus
    from erase.services import dispatch_retrieval_order

    pending = FileRetrievalOrder.objects.filter(
        status=FileRetrievalStatus.PENDING
    ).select_related("agent")
    n = 0
    for order in pending:
        dispatch_retrieval_order(order=order)
        n += 1
    return f"ok:tried={n}"


@app.task
def expire_stale_retrieval_orders() -> str:
    """Mueve a `expired` las órdenes cuya ventana (TTL) venció sin completarse."""
    from erase.services import expire_stale_retrieval_orders as _expire

    return f"ok:expired={_expire()}"
