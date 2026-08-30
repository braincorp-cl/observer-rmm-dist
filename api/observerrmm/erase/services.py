"""Máquina de estados de la orden destructiva (B0 · ADR-029).

Aísla la gobernanza del transporte HTTP para poder probarla sola: doble
confirmación de dos personas (RF-G02), ventana de arrepentimiento (RF-G03) y
auditoría que sobrevive al borrado (RF-G04). El despacho real al agente (Bloque A)
está GATED por ADR-029 y por `settings.ERASE_DESTRUCTIVE_DISPATCH_ENABLED`
(default False): en este incremento la orden se gobierna pero no viaja al equipo.
"""

import asyncio
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from erase.models import (
    CertificateKind,
    EraseAuditRecord,
    FileRetrievalOrder,
    FileRetrievalStatus,
    WipeOrder,
    WipeOrderStatus,
)

# Ventana de arrepentimiento por defecto (segundos). Configurable por settings; el
# valor exacto y su flujo es la laguna L-03 del requirements, se fija acá.
DEFAULT_RECOVERY_SECONDS = 300

# --- fileretrieval (feature 042) — defaults configurables por settings ---------
# TTL de la orden encolada: si el equipo no la toma antes, expira (no queda zombie).
DEFAULT_FILERETRIEVAL_TTL_SECONDS = 7 * 24 * 3600  # 7 días
# Tope por orden (RF-08). Piso de retención (RF-D5): mínimo legal 12 meses.
DEFAULT_FILERETRIEVAL_SIZE_LIMIT_BYTES = 500 * 2**20  # 500 MiB
DEFAULT_FILERETRIEVAL_FILE_LIMIT = 500
DEFAULT_FILERETRIEVAL_RETENTION_DAYS = 366  # ≥ 12 meses (RF-D5)

# --- wipe (feature 043) — tope por orden (RF-07). Configurable por settings. ------
DEFAULT_WIPE_MAX_PATHS_PER_ORDER = 200
DEFAULT_WIPE_MAX_BYTES_PER_ORDER = 5 * 2**30  # 5 GiB


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


def resolve_wipe_paths(
    *,
    template: Optional["Any"] = None,
    paths_add: Optional[List[str]] = None,
    paths_remove: Optional[List[str]] = None,
) -> List[str]:
    """Materializa las rutas de un wipe: plantilla base + ajustes (RN-07 / feature 043).

    Resultado = rutas de la plantilla + `paths_add` − `paths_remove`, preservando el
    orden y sin duplicados. Se congela en `WipeOrder.scope` al crear la orden: cambiar
    la plantilla después no altera órdenes ya emitidas.
    """
    resolved: List[str] = []
    base = list(getattr(template, "paths", []) or []) if template is not None else []
    for p in base + list(paths_add or []):
        if p and p not in resolved:
            resolved.append(p)
    remove = set(paths_remove or [])
    return [p for p in resolved if p not in remove]


def validate_wipe_paths(paths: List[str]) -> None:
    """Valida el tope por orden de wipe (RF-07 / feature 043). Solo cuenta de rutas.

    El tope de volumen (`WIPE_MAX_BYTES_PER_ORDER`) lo hace cumplir el agente al
    enumerar (viaja en el payload); acá se acota lo que el servidor sí conoce.
    """
    if not paths:
        raise OrderStateError("la orden de wipe debe designar al menos una ruta")
    max_paths = getattr(
        settings, "WIPE_MAX_PATHS_PER_ORDER", DEFAULT_WIPE_MAX_PATHS_PER_ORDER
    )
    if max_paths and len(paths) > max_paths:
        raise OrderStateError(
            f"la orden supera el tope de {max_paths} rutas por orden (RF-07)"
        )


def dispatch_order(*, order: WipeOrder) -> WipeOrder:
    """Punto de despacho al agente — GATED por ADR-029 (Bloque A).

    Con `ERASE_DESTRUCTIVE_DISPATCH_ENABLED=False` (default en prod) no envía nada al
    equipo y solo deja constancia de que el despacho quedó bloqueado por el gate legal.
    Con el flag activo (staging, tras el simulacro en seco RF-G05), envía el `nats_cmd`
    al agente espejando el molde de `fileretrieval` (feature 042); el agente respeta
    `dry_run` y el borrado real es del case `wipe` en `rpc.go` (feature 043).
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

    if order.agent is None:
        # El equipo se des-enroló: no hay a quién despachar. Queda en ventana y la
        # reconciliación/expiración la maneja el beat.
        return order

    # Envelope NATS {func, payload:{str:str}} — todo viaja como texto (las rutas van
    # como JSON y el agente las parsea). `func` = la acción destructiva (wipe, …).
    paths = (order.scope or {}).get("paths", [])
    payload = {
        "func": order.action,  # "wipe" (prepara fullwipe/factoryreset)
        "payload": {
            "order_id": str(order.pk),
            "paths": json.dumps(paths),
            "dry_run": "1" if order.dry_run else "0",
            "path_limit": str(
                getattr(
                    settings,
                    "WIPE_MAX_PATHS_PER_ORDER",
                    DEFAULT_WIPE_MAX_PATHS_PER_ORDER,
                )
            ),
            "size_limit_bytes": str(
                getattr(
                    settings,
                    "WIPE_MAX_BYTES_PER_ORDER",
                    DEFAULT_WIPE_MAX_BYTES_PER_ORDER,
                )
            ),
        },
    }
    try:
        ret = asyncio.run(order.agent.nats_cmd(payload, timeout=15))
    except Exception as e:  # noqa: BLE001 — el transporte no debe tumbar la orden
        ret = str(e)

    no_llego = not isinstance(ret, dict) and (
        ret in ("natsdown", "timeout")
        or (isinstance(ret, str) and ret.startswith(("Errno", "nats")))
    )
    if no_llego:
        # Equipo offline: queda en ventana; la reconciliación/reintento la hace el
        # beat hasta que el equipo reconecte y tome la orden por `order_id`.
        record_event(
            order=order,
            event="dispatch_deferred_offline",
            actor="system",
            detail={"ack": ret},
        )
        return order

    order.status = WipeOrderStatus.DISPATCHED
    order.dispatched_at = timezone.now()
    order.save(update_fields=["status", "dispatched_at"])
    record_event(order=order, event="dispatched", actor="system", detail={"ack": ret})
    return order


def apply_wipe_report(
    *,
    order: WipeOrder,
    result: Optional[Dict[str, Any]] = None,
    verified: Optional[bool] = None,
    method_applied: str = "",
    plan: Optional[str] = None,
    error: str = "",
) -> WipeOrder:
    """Aplica el reporte del agente sobre una orden de wipe (feature 043).

    Transiciona `DISPATCHED` → terminal según lo reportado:
      - `error`               → `FAILED`.
      - `dry_run` (con plan)  → `EXECUTED` (sin borrado, sin certificado).
      - real con `verified`   → `EXECUTED` (habilita certificado C, RF-10, en T016).
      - real sin verificación → `INCOMPLETE` (NO emite certificado, RN-08).

    Idempotente: si la orden ya está en estado terminal, no reejecuta.
    """
    terminal = (
        WipeOrderStatus.EXECUTED,
        WipeOrderStatus.INCOMPLETE,
        WipeOrderStatus.FAILED,
        WipeOrderStatus.CANCELLED,
    )
    if order.status in terminal:
        return order

    now = timezone.now()
    if error:
        order.status = WipeOrderStatus.FAILED
        order.failure_reason = str(error)[:255]
        order.executed_at = now
        order.save(update_fields=["status", "failure_reason", "executed_at"])
        record_event(
            order=order,
            event="failed",
            actor="agent",
            detail={"error": order.failure_reason},
        )
        return order

    if order.dry_run:
        order.result = {"plan": plan or ""}
        order.status = WipeOrderStatus.EXECUTED
        order.executed_at = now
        order.save(update_fields=["status", "result", "executed_at"])
        record_event(
            order=order,
            event="dry_run_plan",
            actor="agent",
            detail={"plan_bytes": len(str(plan or ""))},
        )
        return order

    order.result = result or {}
    order.method_applied = (method_applied or "")[:64]
    order.verified = bool(verified)
    order.executed_at = now
    order.status = (
        WipeOrderStatus.EXECUTED if order.verified else WipeOrderStatus.INCOMPLETE
    )
    order.save(
        update_fields=["status", "result", "method_applied", "verified", "executed_at"]
    )
    record_event(
        order=order,
        event="executed" if order.verified else "incomplete",
        actor="agent",
        detail={"verified": order.verified, "method_applied": order.method_applied},
    )
    # Enganche al certificado C (RF-10 / T016): SOLO con `verified=True`. Una orden
    # `incomplete` (verificación por relectura fallida, RN-08) nunca lo emite.
    if order.verified:
        issue_wipe_certificate(order=order)
    return order


def issue_wipe_certificate(*, order: WipeOrder) -> None:
    """Emite el certificado C de un wipe verificado (RF-10 / feature 043 · T016).

    Solo se invoca con `verified=True` (RN-08): un borrado sin verificación queda
    `incomplete` y NO certifica. Idempotente: no reemite si la orden ya tiene
    certificado. El wipe A2 es destrucción remota (`REMOTE_DESTRUCTION`) a nivel
    NIST SP 800-88 "Clear", verificada por relectura por-ruta —no por sectores, que
    es del Bloque B—, así que se llenan por `extra` los campos que el wipe SÍ conoce.

    Blindado: si la emisión falla, la orden ya quedó `EXECUTED`; se deja constancia
    en la cadena inmutable y no se tumba el reporte del agente.
    """
    from erase import certificate  # import diferido: evita ciclo services↔certificate

    if order.certificates.exists():
        return

    result = order.result or {}
    paths_result = {k: v for k, v in result.items() if k != "_"}
    started = order.dispatched_at or order.confirmed_at or order.ordered_at
    operator = order.confirmed_by or order.ordered_by
    try:
        certificate.issue_certificate(
            kind=CertificateKind.REMOTE_DESTRUCTION,
            client=order.client,
            site=order.site,
            agent=order.agent,
            order=order,
            actor=operator,
            method_applied=order.method_applied,
            standard_ref="NIST SP 800-88r1 Clear",
            verification_result="PASS",
            operator=operator,
            started_at=started.isoformat() if started else "",
            finished_at=order.executed_at.isoformat() if order.executed_at else "",
            equipment={
                "model": order.agent_hostname or "",
                "serial": order.agent_serial or "",
            },
            software_version=getattr(order.agent, "version", "") or "",
            extra={
                "action": order.action,
                "passes": 1,
                "patterns": "aleatorio (1 pasada)",
                "verification_level": "relectura por-ruta (RN-08)",
                "paths_total": len(paths_result),
                "paths_result": paths_result,
            },
        )
    except (
        Exception
    ) as e:  # noqa: BLE001 — la orden ya es EXECUTED; no tumbar el reporte
        record_event(
            order=order,
            event="certificate_error",
            actor="system",
            detail={"error": str(e)[:255]},
        )


# ===========================================================================
# fileretrieval (Bloque A · B1) — recuperar archivos antes de borrar.
#
# No destructivo: el despacho al agente NO está atado a
# `ERASE_DESTRUCTIVE_DISPATCH_ENABLED` y no exige doble confirmación ni ventana.
# Reusa la cadena inmutable `EraseAuditRecord` para la auditoría que sobrevive
# (RF-G04/RF-07), atando la fila a la orden por `detail` (su FK apunta a
# `WipeOrder`, así que aquí `order=None` y el id va en el detalle).
# ===========================================================================


def _fr_setting(name: str, default: Any) -> Any:
    return getattr(settings, name, default)


def record_retrieval_event(
    *,
    order: FileRetrievalOrder,
    event: str,
    actor: str,
    detail: Optional[Dict[str, Any]] = None,
) -> EraseAuditRecord:
    """Auditoría de fileretrieval en la cadena inmutable (RF-G04/RF-07)."""
    payload = {"retrieval_order": str(order.pk), "dry_run": order.dry_run}
    payload.update(detail or {})
    rec = EraseAuditRecord(
        order=None,
        agent_id=order.agent_id_snapshot,
        hostname=order.agent_hostname,
        event=event,
        actor=actor,
        detail=payload,
    )
    rec.save()
    return rec


def create_retrieval_order(
    *,
    agent,
    client,
    site,
    paths: List[str],
    requested_by: str,
    dry_run: bool = False,
    lost_mode_cycle: Optional[int] = None,
) -> FileRetrievalOrder:
    """Crea una orden de recuperación y la despacha (best-effort).

    Valida el tope (RF-08) ANTES de despachar. Fija `expires_at` para que una orden
    a un equipo que nunca reconecta no quede zombie (D-04).
    """
    if not paths:
        raise OrderStateError("la orden debe designar al menos una ruta a recuperar")

    file_limit = _fr_setting(
        "FILERETRIEVAL_FILE_LIMIT", DEFAULT_FILERETRIEVAL_FILE_LIMIT
    )
    size_limit = _fr_setting(
        "FILERETRIEVAL_SIZE_LIMIT_BYTES", DEFAULT_FILERETRIEVAL_SIZE_LIMIT_BYTES
    )
    if file_limit and len(paths) > file_limit:
        raise OrderStateError(
            f"la orden supera el tope de {file_limit} archivos por orden (RF-08)"
        )

    ttl = _fr_setting("FILERETRIEVAL_TTL_SECONDS", DEFAULT_FILERETRIEVAL_TTL_SECONDS)
    now = timezone.now()
    order = FileRetrievalOrder.objects.create(
        agent=agent,
        client=client,
        site=site,
        agent_id_snapshot=getattr(agent, "agent_id", "") or "",
        agent_hostname=getattr(agent, "hostname", "") or "",
        agent_serial=getattr(agent, "serial_number", "") or "",
        paths=list(paths),
        dry_run=dry_run,
        lost_mode_cycle=lost_mode_cycle,
        size_limit_bytes=size_limit,
        file_limit=file_limit,
        status=FileRetrievalStatus.PENDING,
        requested_by=requested_by,
        expires_at=now + timedelta(seconds=ttl),
    )
    record_retrieval_event(
        order=order,
        event="retrieval_created",
        actor=requested_by,
        detail={"paths": list(paths), "path_count": len(paths)},
    )
    dispatch_retrieval_order(order=order)
    return order


def dispatch_retrieval_order(*, order: FileRetrievalOrder) -> FileRetrievalOrder:
    """Despacha la orden al agente por NATS (no destructivo, sin gate ADR-029).

    Idempotente: solo despacha órdenes en `pending`. Si el equipo está offline
    (`natsdown`/`timeout`), la orden queda `pending` y la reintenta el beat
    `redispatch_pending_retrieval_orders` hasta `expires_at`. El `order_id` viaja
    al agente y garantiza ejecución única al reconectar.
    """
    if order.status != FileRetrievalStatus.PENDING:
        return order
    if order.agent is None:
        return order

    # Envelope NATS: {func, payload:{str:str}} — el agente decodifica `payload`
    # en un map[string]string, así que TODO viaja como texto (las rutas van como
    # JSON y el agente las parsea). Espeja el molde de `lost_mode`.
    payload = {
        "func": "fileretrieval",
        "payload": {
            "order_id": str(order.pk),
            "paths": json.dumps(order.paths),
            "dry_run": "1" if order.dry_run else "0",
            "size_limit_bytes": str(order.size_limit_bytes),
            "file_limit": str(order.file_limit),
        },
    }
    try:
        ret = asyncio.run(order.agent.nats_cmd(payload, timeout=15))
    except Exception as e:  # noqa: BLE001 — el transporte no debe tumbar la orden
        ret = str(e)

    # El equipo no está (offline / NATS caído): la orden sigue en cola y la
    # reintenta el beat `redispatch_pending_retrieval_orders` hasta expirar.
    no_llego = not isinstance(ret, dict) and (
        ret in ("natsdown", "timeout")
        or (isinstance(ret, str) and ret.startswith(("Errno", "nats")))
    )
    if no_llego:
        return order

    order.status = FileRetrievalStatus.DISPATCHED
    order.dispatched_at = timezone.now()
    order.save(update_fields=["status", "dispatched_at"])
    record_retrieval_event(
        order=order, event="retrieval_dispatched", actor="system", detail={"ack": ret}
    )
    return order


def cancel_retrieval_order(
    *, order: FileRetrievalOrder, cancelled_by: str, reason: str = ""
) -> FileRetrievalOrder:
    if order.status in (
        FileRetrievalStatus.DONE,
        FileRetrievalStatus.CANCELLED,
        FileRetrievalStatus.EXPIRED,
        FileRetrievalStatus.FAILED,
    ):
        raise OrderStateError(f"la orden ya no es cancelable (está {order.status})")
    order.status = FileRetrievalStatus.CANCELLED
    order.cancelled_by = cancelled_by
    order.cancelled_at = timezone.now()
    order.save(update_fields=["status", "cancelled_by", "cancelled_at"])
    record_retrieval_event(
        order=order,
        event="retrieval_cancelled",
        actor=cancelled_by,
        detail={"reason": reason},
    )
    return order


def expire_stale_retrieval_orders() -> int:
    """Mueve a `expired` las órdenes no completadas cuya ventana venció (D-04)."""
    now = timezone.now()
    stale = FileRetrievalOrder.objects.filter(
        status__in=[
            FileRetrievalStatus.PENDING,
            FileRetrievalStatus.DISPATCHED,
            FileRetrievalStatus.UPLOADING,
        ],
        expires_at__lt=now,
    )
    count = 0
    for order in stale:
        order.status = FileRetrievalStatus.EXPIRED
        order.save(update_fields=["status"])
        record_retrieval_event(
            order=order, event="retrieval_expired", actor="system", detail={}
        )
        count += 1
    return count
