"""Máquina de estados de la orden destructiva (B0 · ADR-029).

Aísla la gobernanza del transporte HTTP para poder probarla sola: doble
confirmación de dos personas (RF-G02), ventana de arrepentimiento (RF-G03) y
auditoría que sobrevive al borrado (RF-G04). El despacho real al agente (Bloque A)
está GATED por ADR-029 y por `settings.ERASE_DESTRUCTIVE_DISPATCH_ENABLED`
(default False): en este incremento la orden se gobierna pero no viaja al equipo.
"""

from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from erase.models import (
    EraseAuditRecord,
    WipeOrder,
    WipeOrderStatus,
)

# Ventana de arrepentimiento por defecto (segundos). Configurable por settings; el
# valor exacto y su flujo es la laguna L-03 del requirements, se fija acá.
DEFAULT_RECOVERY_SECONDS = 300


class OrderStateError(Exception):
    """Transición inválida de una orden (ej. confirmar una ya cancelada)."""


def record_event(
    *,
    order: Optional[WipeOrder],
    event: str,
    actor: str,
    detail: Optional[Dict[str, Any]] = None,
) -> EraseAuditRecord:
    rec = EraseAuditRecord(
        order=order,
        agent_id=(
            getattr(order.agent, "agent_id", "") if order and order.agent else ""
        ),
        hostname=(order.agent_hostname if order else ""),
        event=event,
        actor=actor,
        detail=detail or {},
    )
    rec.save()
    return rec


def create_order(
    *,
    agent,
    client,
    site,
    action: str,
    ordered_by: str,
    scope: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
    reason: str = "",
    lost_mode_cycle: Optional[int] = None,
) -> WipeOrder:
    order = WipeOrder.objects.create(
        agent=agent,
        client=client,
        site=site,
        agent_hostname=getattr(agent, "hostname", "") or "",
        agent_serial=getattr(agent, "serial_number", "") or "",
        action=action,
        scope=scope or {},
        dry_run=dry_run,
        reason=reason,
        lost_mode_cycle=lost_mode_cycle,
        status=WipeOrderStatus.PENDING_CONFIRMATION,
        ordered_by=ordered_by,
    )
    record_event(
        order=order,
        event="created",
        actor=ordered_by,
        detail={"action": action, "dry_run": dry_run, "reason": reason},
    )
    return order


def confirm_order(
    *,
    order: WipeOrder,
    confirmed_by: str,
    recovery_seconds: Optional[int] = None,
) -> WipeOrder:
    """Segunda confirmación por una persona distinta (RF-G02).

    Arranca la ventana de arrepentimiento (RF-G03). La verificación de que
    `confirmed_by` tiene `can_wipe_device` es de la vista; acá se garantiza el
    invariante que no puede delegarse: ordenante ≠ confirmante.
    """
    if order.status != WipeOrderStatus.PENDING_CONFIRMATION:
        raise OrderStateError(
            f"la orden no está pendiente de confirmación (está {order.status})"
        )
    if confirmed_by == order.ordered_by:
        raise OrderStateError(
            "la segunda confirmación debe ser de una persona distinta a quien "
            "ordenó el borrado (RF-G02)"
        )

    seconds = (
        recovery_seconds
        if recovery_seconds is not None
        else getattr(settings, "ERASE_RECOVERY_SECONDS", DEFAULT_RECOVERY_SECONDS)
    )
    now = timezone.now()
    order.confirmed_by = confirmed_by
    order.confirmed_at = now
    order.recovery_deadline = now + timedelta(seconds=seconds)
    order.status = WipeOrderStatus.RECOVERY_WINDOW
    order.save(
        update_fields=[
            "confirmed_by",
            "confirmed_at",
            "recovery_deadline",
            "status",
        ]
    )
    record_event(
        order=order,
        event="confirmed",
        actor=confirmed_by,
        detail={"recovery_seconds": seconds},
    )

    # Programa el despacho al vencer la ventana. Import diferido para no acoplar
    # el servicio a celery en tiempo de import (facilita los tests unitarios).
    from erase.tasks import dispatch_wipe_order

    dispatch_wipe_order.apply_async(args=[order.pk], eta=order.recovery_deadline)
    return order


def cancel_order(*, order: WipeOrder, cancelled_by: str, reason: str = "") -> WipeOrder:
    """Cancela dentro de la ventana de arrepentimiento (o antes)."""
    if order.status not in (
        WipeOrderStatus.PENDING_CONFIRMATION,
        WipeOrderStatus.CONFIRMED,
        WipeOrderStatus.RECOVERY_WINDOW,
    ):
        raise OrderStateError(f"la orden ya no es cancelable (está {order.status})")
    order.status = WipeOrderStatus.CANCELLED
    order.cancelled_by = cancelled_by
    order.cancelled_at = timezone.now()
    order.save(update_fields=["status", "cancelled_by", "cancelled_at"])
    record_event(
        order=order, event="cancelled", actor=cancelled_by, detail={"reason": reason}
    )
    return order


def dispatch_order(*, order: WipeOrder) -> WipeOrder:
    """Punto de despacho al agente — GATED por ADR-029 (Bloque A).

    En este incremento no envía nada al equipo. Si la orden sigue en ventana y no
    fue cancelada, deja constancia de que el despacho quedó bloqueado por el gate
    legal. El envío real (case en `rpc.go`, con dry-run RF-G05) entra cuando
    ADR-029 pase a ACEPTADO y se active `ERASE_DESTRUCTIVE_DISPATCH_ENABLED`.
    """
    if order.status != WipeOrderStatus.RECOVERY_WINDOW:
        # Cancelada o ya resuelta: no se hace nada (idempotente).
        return order

    enabled = getattr(settings, "ERASE_DESTRUCTIVE_DISPATCH_ENABLED", False)
    if not enabled:
        record_event(
            order=order,
            event="dispatch_gated_adr029",
            actor="system",
            detail={
                "note": "Bloque A destructivo GATED: falta ADR-029 ACEPTADO por "
                "legal y ERASE_DESTRUCTIVE_DISPATCH_ENABLED."
            },
        )
        return order

    # Reservado para Fase A: aquí iría el nats_cmd al agente + reconciliación.
    order.status = WipeOrderStatus.DISPATCHED
    order.dispatched_at = timezone.now()
    order.save(update_fields=["status", "dispatched_at"])
    record_event(order=order, event="dispatched", actor="system", detail={})
    return order
