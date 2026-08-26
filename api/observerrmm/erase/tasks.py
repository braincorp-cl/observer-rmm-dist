from observerrmm.celery import app


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
def prune_erase_attachments(older_than_days: int) -> str:
    """Retención D5: purga adjuntos vencidos (ej. registro fotográfico de C7 y los
    archivos recuperados por fileretrieval), preservando SIEMPRE la fila del
    certificado/auditoría y su hash — la cadena C3 no se toca.

    `older_than_days` respeta el piso legal (RF-D5, ≥12 meses): el llamador pasa
    `FILERETRIEVAL_RETENTION_DAYS`, que nunca baja del mínimo. Nunca borra
    `EraseCertificate` ni `EraseAuditRecord`, sólo el binario del adjunto.
    """
    from datetime import timedelta

    from django.utils import timezone

    from erase.models import RetrievedFile

    cutoff = timezone.now() - timedelta(days=older_than_days)
    purged = 0
    for rf in RetrievedFile.objects.filter(uploaded_at__lt=cutoff).exclude(asset=""):
        if rf.asset:
            rf.asset.delete(save=False)
            rf.asset = ""
            rf.save(update_fields=["asset"])
            purged += 1
    return f"ok:purged={purged}"


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
