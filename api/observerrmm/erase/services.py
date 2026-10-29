"""Máquina de estados de la orden destructiva (B0 · ADR-029).

Aísla la gobernanza del transporte HTTP para poder probarla sola: doble
confirmación de dos personas (RF-G02), ventana de arrepentimiento (RF-G03) y
auditoría que sobrevive al borrado (RF-G04). El despacho real al agente (Bloque A)
está GATED por ADR-029 y por `settings.ERASE_DESTRUCTIVE_DISPATCH_ENABLED`
(default False): en este incremento la orden se gobierna pero no viaja al equipo.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db.models import Count, Exists, F, Max, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from agents.models import LostModeEvidence, LostModeState
from observerrmm.constants import ERASE_ATTACHMENT_RETENTION_FLOOR_DAYS
from erase.models import (
    AssetIntake,
    CertificateKind,
    CustodyEvent,
    CustodyEventKind,
    EraseAuditRecord,
    EraseCertificate,
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


# Lo que `Agent.make_model` devuelve cuando el WMI no alcanza (agents/models.py).
# Son mensajes de diagnóstico, no modelos: un certificado que se entrega a un
# tercero no publica "error getting make/model" en la casilla del modelo.
MAKE_MODEL_SENTINELS = ("error getting make/model", "unknown make/model")


def clean_make_model(value: Optional[str]) -> str:
    """Devuelve el fabricante y modelo, o "" si lo que vino es un centinela."""
    text = (value or "").strip()
    return "" if text.lower() in MAKE_MODEL_SENTINELS else text


class OrderStateError(Exception):
    """Transición inválida de una orden (ej. confirmar una ya cancelada)."""


class OrderAnchorError(Exception):
    """El equipo no tiene expediente del cual colgar la orden (RF-12).

    NO hereda de `OrderStateError` a propósito: `WipeOrderCreate` ya captura ese
    tipo y responde 400, y heredar haría que esto cayera ahí por accidente. Esto
    es un 409 —conflicto con el estado del equipo, no una transición inválida—,
    el mismo código que fileretrieval ya devolvía antes de unificarse.
    """


@dataclass(frozen=True)
class OrderAnchor:
    """Expediente que autoriza una orden, resuelto por el servidor.

    `source` dice de cuál de los dos vino; los otros dos campos son lo que se
    congela en la orden. `lost_mode_cycle` puede ser `None` con `source`
    `"lost_mode"`: es el caso recién denunciado, que todavía no capturó
    evidencia (CA-09), y coaccionarlo a 0 inventaría un ciclo que no existe.
    """

    source: str
    lost_mode_cycle: Optional[int] = None
    intake: Optional[AssetIntake] = None


def resolve_order_anchor(*, agent) -> OrderAnchor:
    """Resuelve el expediente de un equipo: caso perdido abierto > acta de ingreso.

    Único punto de verdad para las dos vistas que crean órdenes (RF-12). Todo se
    deriva en el servidor: lo que mande el cliente en el payload se ignora, para
    que la guardia no dependa de la consola.

    🔑 Se filtra SIEMPRE por `active=True`. La fila de `LostModeState` sobrevive
    al cierre del caso por diseño (guarda la configuración del equipo), así que
    un `filter(agent=agent)` suelto sería una no-guardia: dejaría pasar cualquier
    equipo que alguna vez estuvo perdido.

    No se usa `lost_mode_cycle` del payload ni para detectar el caso: es un
    contador de capturas de evidencia y el diálogo de la consola manda `null`
    cuando el caso todavía no capturó nada, justo el equipo recién denunciado.
    """
    if LostModeState.objects.filter(agent=agent, active=True).exists():
        cycle = LostModeEvidence.objects.filter(agent=agent).aggregate(m=Max("cycle"))[
            "m"
        ]
        return OrderAnchor(source="lost_mode", lost_mode_cycle=cycle)

    intake = AssetIntake.objects.filter(agent=agent).order_by("-created_at").first()
    if intake is not None:
        return OrderAnchor(source="intake", intake=intake)

    raise OrderAnchorError(
        "este equipo no tiene expediente abierto: una orden cuelga de un caso de "
        "equipo perdido abierto o de un acta de ingreso a baja, nunca del listado "
        "general (RF-12)"
    )


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
    intake: Optional[AssetIntake] = None,
) -> WipeOrder:
    order = WipeOrder.objects.create(
        agent=agent,
        client=client,
        site=site,
        agent_hostname=getattr(agent, "hostname", "") or "",
        agent_serial=getattr(agent, "serial_number", "") or "",
        # Snapshot de fabricante y modelo (RF-04): el agente es `SET_NULL` y puede
        # no existir al emitir el certificado. Se guarda ya limpio de centinelas
        # para que la columna no llegue a contener un mensaje de error.
        agent_make_model=clean_make_model(getattr(agent, "make_model", "")),
        action=action,
        scope=scope or {},
        dry_run=dry_run,
        reason=reason,
        lost_mode_cycle=lost_mode_cycle,
        intake=intake,
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

    # 🔑 El operador es quien ORDENÓ, no `confirmed_by or ordered_by`. Con la
    # expresión anterior, una orden confirmada mostraba a la misma persona como
    # operador y como quien da fe: justo el "ok falso" que la separación de
    # deberes existe para evitar. Quien confirmó va al bloque de concurrencia.
    operator = order.ordered_by
    concurrence = (
        {
            "name": order.confirmed_by,
            "role": "Segunda confirmación de la orden (RF-G02)",
            "at": order.confirmed_at.isoformat() if order.confirmed_at else "",
        }
        if order.confirmed_by
        else None
    )

    # Fabricante y modelo: el snapshot que se congeló al crear la orden (RF-04).
    # Si la orden es anterior a la feature 053 la columna está vacía, así que se
    # cae al agente en vivo — que puede no existir (`SET_NULL`) y puede devolver
    # un centinela de error, de ahí el mismo filtro.
    make_model = order.agent_make_model or clean_make_model(
        getattr(order.agent, "make_model", "")
    )

    # Destino del medio: sólo si la orden cuelga de un acta de ingreso. Anclada a
    # un caso de equipo perdido el campo viaja presente y VACÍO, que es la verdad
    # —el medio sigue en el equipo, dondequiera que esté—, no un dato ausente.
    intake = order.intake
    try:
        certificate.issue_certificate(
            kind=CertificateKind.REMOTE_DESTRUCTION,
            client=order.client,
            site=order.site,
            agent=order.agent,
            order=order,
            intake=intake,
            # El actor de la auditoría es quien autorizó, que no es lo mismo que
            # el operador del documento: la emisión la dispara el reporte del
            # agente, no una persona.
            actor=order.confirmed_by or order.ordered_by,
            method_applied=order.method_applied,
            standard_ref=certificate.STANDARD_REF_CLEAR,
            verification_result=certificate.VERIFICATION_PASS,
            verification_method="Relectura por-ruta informada por el agente (RN-08)",
            operator=operator,
            concurrence=concurrence,
            media_disposition=getattr(intake, "media_disposition", "") or "",
            media_disposition_detail=(
                getattr(intake, "media_disposition_detail", "") or ""
            ),
            # RF-09. Sin acta los dos viajan vacíos: el medio sigue en el equipo
            # y su procedencia no consta en ninguna parte que podamos citar.
            media_type=getattr(intake, "media_type", "") or "",
            media_origin=compose_media_origin(intake),
            started_at=started.isoformat() if started else "",
            finished_at=order.executed_at.isoformat() if order.executed_at else "",
            # 🐞 Antes esto ponía `model = agent_hostname`: el documento que se
            # entrega a un tercero llevaba el nombre de red como si fuera el
            # modelo del equipo. Ahora cada dato va en su casilla.
            equipment={
                "make_model": make_model,
                "make": getattr(intake, "equipment_make", "") or "",
                "model": getattr(intake, "equipment_model", "") or "",
                "serial": order.agent_serial or "",
                "hostname": order.agent_hostname or "",
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
    intake: Optional[AssetIntake] = None,
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
        intake=intake,
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


# ============================================================================
# Custodia por eventos (feature 053 · ola 2 · RF-06, RF-07, RF-09)
# ============================================================================


class CustodyEventError(Exception):
    """Un eslabón que no se puede registrar.

    NO hereda de `OrderStateError`: esa excepción la traducen las vistas de
    órdenes a 400, y el duplicado de `received` tiene que salir como 409. Son
    dos errores distintos y mezclarlos los haría indistinguibles para el cliente.
    """


def record_custody_event(
    *,
    intake: AssetIntake,
    kind: str,
    actor: str,
    at=None,
    location: str = "",
    detail: Optional[Dict[str, Any]] = None,
) -> CustodyEvent:
    """Único punto de escritura de la cadena de custodia.

    Valida lo que no puede validar el modelo:

    - `kind` dentro del vocabulario cerrado (lo que hace contable el informe);
    - `at` no en el futuro: un eslabón fechado mañana no es un hecho;
    - `received` una sola vez, porque lo escribe el servidor al crear el acta.

    La identidad del expediente se congela en el eslabón: la FK es `SET_NULL` y
    el eslabón tiene que seguir valiendo si el acta desaparece.
    """
    if kind not in CustodyEventKind.values:
        raise CustodyEventError(
            f"'{kind}' no es un evento de custodia conocido; el vocabulario es "
            "cerrado a propósito, porque es lo que hace contable la reconciliación"
        )

    ahora = timezone.now()
    at = at or ahora
    if at > ahora:
        raise CustodyEventError(
            "un evento de custodia registra cuándo OCURRIÓ, así que no puede "
            "estar en el futuro"
        )

    if kind == CustodyEventKind.RECEIVED:
        ya_existe = CustodyEvent.objects.filter(
            intake=intake, kind=CustodyEventKind.RECEIVED
        ).exists()
        if ya_existe:
            raise CustodyEventError(
                "el acta ya tiene su eslabón de recepción: lo escribe el servidor "
                "al crearla y no se duplica"
            )

    return CustodyEvent.objects.create(
        intake=intake,
        intake_process_id=intake.process_id,
        equipment_serial=intake.equipment_serial,
        kind=kind,
        at=at,
        actor=actor,
        location=location,
        detail=detail or {},
    )


def verify_custody_chain(intake: AssetIntake) -> bool:
    """¿Encadena y recomputa la cadena de custodia de este acta?

    Misma comprobación que el detalle del certificado hace sobre su cadena, pero
    acotada a los eslabones del acta: se recorre por `id` ascendente —el orden de
    inserción, no el de `at`— verificando que cada uno encadene el `record_hash`
    del anterior y que su propio hash recompute.

    🪤 El primer eslabón del acta NO tiene por qué traer `prev_hash` vacío: la
    cadena es global por tabla y otro acta pudo escribir antes. Lo que se
    comprueba acá es la continuidad entre los eslabones de ESTE expediente.
    """
    eslabones = list(CustodyEvent.objects.filter(intake=intake).order_by("id"))
    anterior: Optional[CustodyEvent] = None
    for ev in eslabones:
        if ev.compute_record_hash(ev.prev_hash) != ev.record_hash:
            return False
        if anterior is not None and ev.prev_hash != anterior.record_hash:
            return False
        anterior = ev
    return True


def first_custody_event(intake: AssetIntake) -> Optional[CustodyEvent]:
    """El eslabón de recepción del acta, si lo tiene."""
    return (
        CustodyEvent.objects.filter(intake=intake, kind=CustodyEventKind.RECEIVED)
        .order_by("id")
        .first()
    )


def compose_media_origin(intake: Optional[AssetIntake]) -> str:
    """El *Media Source* del Apéndice C: de dónde provino el medio.

    🔑 No es dónde se almacenó. El dato vive en el acta —equipo enrolado, serie y
    quién lo entregó— y la cadena aporta la fecha de entrada a custodia. Si el
    acta no tiene nada de eso, se devuelve vacío: el certificado declara "no
    consta" antes que inventar una procedencia (ADR-032).
    """
    if intake is None:
        return ""

    partes: List[str] = []
    hostname = getattr(getattr(intake, "agent", None), "hostname", "") or ""
    if hostname:
        partes.append(f"equipo {hostname}")
    if intake.equipment_serial:
        partes.append(f"serie {intake.equipment_serial}")
    if intake.delivered_by:
        partes.append(f"entregado por {intake.delivered_by}")

    if not partes:
        return ""

    recibido = first_custody_event(intake)
    if recibido is not None:
        partes.append(f"en custodia desde {recibido.at.date().isoformat()}")

    return "; ".join(partes)


MISSING_PAGE_LIMIT_DEFAULT = 100
MISSING_PAGE_LIMIT_MAX = 500


def reconciliation(
    *,
    qs,
    client=None,
    desde=None,
    hasta=None,
    stalled_days: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> Dict[str, Any]:
    """Ingresados, certificados y faltantes, por cliente y período (RF-07).

    `qs` llega **ya filtrado por el alcance de rol**: los totales se calculan
    después de recortar, nunca antes, para que un usuario de alcance limitado vea
    números que cuadran con lo que puede abrir.

    🔑 **Faltante = acta sin certificado**, no "acta vieja". Definirlo por
    antigüedad inventaría un plazo que la plataforma no conoce. `stalled_days`
    sólo **marca** un faltante como detenido; no cambia quién es faltante.

    🔴 **Los totales se agregan en la base, no recorriendo filas en Python**, y
    de `missing_items` se materializa **sólo la página pedida**. La primera
    versión traía todas las actas del período a memoria y devolvía todos los
    faltantes de una vez: con 6.000 actas eran 4.000 ítems en una respuesta, y
    ni los tests ni la prueba manual lo notaban porque con tres actas da igual.

    Los parámetros se llaman `desde`/`hasta` porque `from` es reservada en
    Python; la vista traduce los `from`/`to` del contrato HTTP.
    """
    if desde and hasta and desde > hasta:
        raise CustodyEventError("el inicio del período es posterior a su fin")

    if client is not None:
        qs = qs.filter(client=client)
    if desde:
        qs = qs.filter(created_at__gte=desde)
    if hasta:
        qs = qs.filter(created_at__lte=hasta)

    ahora = timezone.now()
    corte = (
        ahora - timedelta(days=stalled_days) if stalled_days not in (None, "") else None
    )

    # Fecha contra la que se mide "detenido": la del último eslabón, y si el
    # acta no tiene ninguno, la de su ingreso — un acta sin movimientos es
    # justamente la que lleva más tiempo quieta.
    ultimo_at = Subquery(
        CustodyEvent.objects.filter(intake=OuterRef("pk"))
        .order_by("-id")
        .values("at")[:1]
    )
    base = qs.annotate(
        certificado=Exists(EraseCertificate.objects.filter(intake=OuterRef("pk"))),
        referencia=Coalesce(ultimo_at, F("created_at")),
    )

    def agregados() -> Dict[str, Any]:
        """Instancias NUEVAS en cada uso: una expresión de agregación se resuelve
        contra el queryset donde se usa, así que no se comparten entre el
        `aggregate()` y el `annotate()`.

        🪤 Sin umbral, `stalled` **no se consulta**: se resuelve a 0 después. Un
        `Q(pk__in=[])` como filtro vacío parece lo natural y colapsa el
        `aggregate` entero a ceros —todas las claves, sin error—, porque Django
        propaga `EmptyResultSet` a la consulta completa.
        """
        cuentas = {
            "intakes": Count("pk"),
            "certified": Count("pk", filter=Q(certificado=True)),
            "missing": Count("pk", filter=Q(certificado=False)),
        }
        if corte is not None:
            cuentas["stalled"] = Count(
                "pk", filter=Q(certificado=False) & Q(referencia__lt=corte)
            )
        return cuentas

    def con_stalled(fila: Dict[str, Any]) -> Dict[str, Any]:
        # Sin umbral nadie está detenido: detenido es otra cosa que faltante.
        fila.setdefault("stalled", 0)
        return fila

    totales = con_stalled(base.aggregate(**agregados()))
    por_cliente = [
        con_stalled(
            {
                "client_id": fila["client_id"],
                "client": fila["client__name"],
                "intakes": fila["intakes"],
                "certified": fila["certified"],
                "missing": fila["missing"],
                **({"stalled": fila["stalled"]} if "stalled" in fila else {}),
            }
        )
        for fila in base.values("client_id", "client__name")
        .annotate(**agregados())
        .order_by("client__name")
    ]

    # --- la página de faltantes, y sólo la página ---
    limite = limit if limit is not None else MISSING_PAGE_LIMIT_DEFAULT
    limite = max(1, min(int(limite), MISSING_PAGE_LIMIT_MAX))
    desplazamiento = max(0, int(offset))

    faltantes_qs = base.filter(certificado=False).order_by("created_at", "pk")
    pagina = list(faltantes_qs[desplazamiento : desplazamiento + limite])

    # El último eslabón de los de ESTA página, en dos consultas fijas.
    ultimos: Dict[int, CustodyEvent] = {}
    if pagina:
        ids = (
            CustodyEvent.objects.filter(intake_id__in=[a.pk for a in pagina])
            .values("intake_id")
            .annotate(ultimo=Max("id"))
            .values_list("ultimo", flat=True)
        )
        ultimos = {
            ev.intake_id: ev for ev in CustodyEvent.objects.filter(id__in=list(ids))
        }

    faltantes = []
    for acta in pagina:
        ultimo = ultimos.get(acta.pk)
        referencia = ultimo.at if ultimo is not None else acta.created_at
        faltantes.append(
            {
                "intake_id": acta.pk,
                "process_id": acta.process_id,
                "equipment_serial": acta.equipment_serial,
                "received_at": acta.created_at,
                "days_open": (ahora - acta.created_at).days,
                "last_event": (
                    {"kind": ultimo.kind, "at": ultimo.at} if ultimo else None
                ),
                "stalled": bool(corte and referencia < corte),
            }
        )

    return {
        "period": {"from": desde, "to": hasta},
        "totals": totales,
        "by_client": por_cliente,
        "missing_items": faltantes,
        # Lo que la consola necesita para paginar sin adivinar.
        "missing_page": {
            "limit": limite,
            "offset": desplazamiento,
            "total": totales["missing"],
            "returned": len(faltantes),
        },
    }


# --- retención de adjuntos (feature 053 · ola 3 — RNF-06/L-04) ----------------


def resolve_attachment_retention(*, client=None, core=None) -> int:
    """Días que sobrevive un ADJUNTO de borrado. Precedencia **cliente > global**.

    - Global: `CoreSettings.erase_attachment_retention_days`, siempre presente.
    - Cliente: `Client.erase_attachment_retention_days`. Un valor no-nulo pisa al
      global; `None` es **«sin decidir» y hereda**, nunca «cero días».
    - Sobre el resultado se aplica el piso legal
      `ERASE_ATTACHMENT_RETENTION_FLOOR_DAYS` (RF-D5, ≥ 12 meses).

    Regla única y central: **nadie más resuelve esta precedencia. Vive acá.** Al
    molde de `agents.utils.resolve_lost_mode_cascade`, y por la misma razón: para
    que la consola, la API y la purga entreguen exactamente el mismo número. Si se
    resolviera en dos lugares, la consola mostraría 400 días y la purga aplicaría
    366, y nadie se enteraría hasta que faltara un archivo.

    🔑 El piso se aplica **al leer**, no sólo en el validador del campo: un
    `loaddata`, un `queryset.update()` o una fila escrita antes de que el validador
    existiera **no pasan por él**. Dos guardas a propósito, porque un piso que se
    puede esquivar no es un piso.

    🔒 Este plazo **nunca** alcanza al certificado, que es permanente e inmutable
    (RNF-01 / RN-E07). Sólo al binario del adjunto.
    """
    if core is None:
        from core.utils import get_core_settings

        core = get_core_settings()

    dias = getattr(core, "erase_attachment_retention_days", None)
    if client is not None:
        propio = getattr(client, "erase_attachment_retention_days", None)
        if propio is not None:
            dias = propio

    if dias is None:
        # Sin ajuste global legible (instancia a medio migrar): el piso manda.
        return ERASE_ATTACHMENT_RETENTION_FLOOR_DAYS

    return max(int(dias), ERASE_ATTACHMENT_RETENTION_FLOOR_DAYS)
