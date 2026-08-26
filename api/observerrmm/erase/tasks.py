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
    """Retención D5: purga adjuntos vencidos (ej. registro fotográfico de C7),
    preservando SIEMPRE la fila del certificado y su hash — la cadena C3 no se
    toca. En este incremento no hay adjuntos pesados aún; queda el enganche.
    """
    # Placeholder de retención: cuando C7 sume adjuntos de foto, acá se borran los
    # archivos vencidos dejando el registro (document_hash, firma, encadenado)
    # intacto. Nunca borra EraseCertificate ni EraseAuditRecord.
    return "ok"
