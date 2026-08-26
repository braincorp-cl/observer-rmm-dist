"""Modelos del módulo Observer Erase — Bloques C (certificación) y D (custodia).

Tres piezas y un invariante:

- **`WipeOrder`** es la orden destructiva gobernada (ADR-029). Es MUTABLE: recorre
  una máquina de estados (borrador → confirmada → ventana de arrepentimiento →
  despachada → ejecutada/cancelada/fallida). El despacho real al agente es del
  Bloque A y está GATED; en este incremento la orden se gobierna y se audita pero
  no viaja al equipo.

- **`EraseAuditRecord`** y **`EraseCertificate`** son APPEND-ONLY y ENCADENADOS por
  hash (`ImmutableChainRecord`). Es la "auditoría que sobrevive al borrado" (RF-G04)
  y el "repositorio inmutable write-once" (C3): una fila emitida no se modifica ni
  se elimina, y cada fila encadena el hash de la anterior, de modo que borrar un
  registro intermedio rompe la cadena y se nota. Deliberadamente NO heredan de
  `BaseAuditModel` ni entran en `prune_audit_log` (`logs/tasks.py`), que borra en
  duro: mezclar el audit operativo purgable con la evidencia legal permanente sería
  el "ok falso" que este módulo no puede permitirse.

- **`AssetIntake`** (D1) es el registro de ingreso del activo a proceso de baja.

**Aislamiento multi-tenant (D4).** Se reutiliza el criterio de
`observerrmm.models.PermissionQuerySet` (filtrado por rol, no RLS de Postgres): los
modelos llevan FK `client`/`site` y `EraseQuerySet.filter_by_role` recorta por el
alcance del rol con la MISMA semántica que la rama `Client` del filtro compartido
(alcance vacío = todo, dentro de lo que ya autorizó el permiso de la vista). Se
acredita equivalencia funcional; adoptar RLS real queda como cambio transversal
aparte.
"""

import hashlib
import json
from typing import TYPE_CHECKING, Any, Dict

from django.db import models, transaction
from django.utils import timezone

if TYPE_CHECKING:
    from accounts.models import User


class ImmutableRecordError(Exception):
    """Se intentó modificar o eliminar un registro append-only ya emitido."""


class EraseAction(models.TextChoices):
    CRYPTO_ERASE = "crypto_erase", "Crypto-erase remoto"
    WIPE = "wipe", "Wipe selectivo por rutas"
    FULLWIPE = "fullwipe", "Borrado total del volumen de datos"
    FACTORY_RESET = "factoryreset", "Restauración de fábrica"


class WipeOrderStatus(models.TextChoices):
    # Orden estricto de irreversibilidad de la máquina de estados.
    DRAFT = "draft", "Borrador"
    PENDING_CONFIRMATION = "pending_confirmation", "Pendiente de segunda confirmación"
    CONFIRMED = "confirmed", "Confirmada"
    RECOVERY_WINDOW = "recovery_window", "En ventana de arrepentimiento"
    DISPATCHED = "dispatched", "Despachada al equipo"
    CANCELLED = "cancelled", "Cancelada"
    EXECUTED = "executed", "Ejecutada"
    FAILED = "failed", "Fallida"


class CertificateKind(models.TextChoices):
    REMOTE_DESTRUCTION = "remote_destruction", "Destrucción remota / borrado lógico"
    PHYSICAL_DESTRUCTION = "physical_destruction", "Destrucción física"


class AssetIntakeState(models.TextChoices):
    FUNCTIONAL = "functional", "Funcional"
    NON_FUNCTIONAL = "non_functional", "No funcional"
    NO_MEDIA = "no_media", "Sin medio detectable"


class EraseQuerySet(models.QuerySet):
    """Filtrado por rol equivalente a la rama `Client` de `PermissionQuerySet`.

    Los modelos de este módulo pueden no tener un `agent` (una destrucción física
    de un disco suelto no cuelga de ningún equipo enrolado), así que el filtro del
    core —que se apoya en `agent`— no aplica. Se filtra directo por `client`/`site`,
    con la misma regla: superuser ve todo; sin rol, nada; alcance de rol vacío = ve
    todo lo que su permiso de vista ya autorizó; con alcance, se recorta a él.
    """

    def filter_by_role(self, user: "User") -> "models.QuerySet":
        role = getattr(user, "role", None)

        if user.is_superuser or (role and getattr(role, "is_superuser", False)):
            return self

        if not role:
            return self.none()

        can_view_clients = role.can_view_clients.all()
        can_view_sites = role.can_view_sites.all()

        # Alcance vacío = sin restricción por cliente/sitio, idéntico a como la
        # rama Client de PermissionQuerySet cae al `return self` cuando el rol no
        # declara can_view_clients ni can_view_sites.
        if not can_view_clients and not can_view_sites:
            return self

        scope = models.Q()
        if can_view_clients:
            scope |= models.Q(client__in=can_view_clients)
        if can_view_sites:
            scope |= models.Q(site__in=can_view_sites)

        return self.filter(scope)


class ImmutableChainRecord(models.Model):
    """Base append-only con encadenamiento de hash (write-once, C3 / RF-G04).

    - No se modifica: `save()` sobre una fila con pk lanza `ImmutableRecordError`.
    - No se elimina: `delete()` lanza `ImmutableRecordError`.
    - Al insertar, toma el `record_hash` del último registro de SU MISMA clase como
      `prev_hash`, y calcula `record_hash = sha256(prev_hash + contenido canónico)`.
      La lectura del último registro va bajo `select_for_update()` dentro de una
      transacción para serializar inserciones concurrentes (Postgres).

    Verificar la cadena = recorrer por id ascendente comprobando que cada fila
    encadena el hash de la anterior y que su `record_hash` recomputa. Un borrado
    intermedio rompe la continuidad de `prev_hash` y queda en evidencia.
    """

    created_at = models.DateTimeField(editable=False)
    prev_hash = models.CharField(max_length=64, blank=True, default="", editable=False)
    record_hash = models.CharField(max_length=64, unique=True, editable=False)

    class Meta:
        abstract = True

    def canonical_content(self) -> Dict[str, Any]:
        raise NotImplementedError

    def compute_record_hash(self, prev_hash: str) -> str:
        payload = json.dumps(
            self.canonical_content(),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256((prev_hash + "\n" + payload).encode("utf-8")).hexdigest()

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            raise ImmutableRecordError(
                f"{type(self).__name__} es append-only: no se puede modificar un "
                "registro ya emitido."
            )

        with transaction.atomic():
            last = type(self)._base_manager.select_for_update().order_by("-id").first()
            self.prev_hash = last.record_hash if last else ""
            if not self.created_at:
                self.created_at = timezone.now()
            self.record_hash = self.compute_record_hash(self.prev_hash)
            super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:
        raise ImmutableRecordError(
            f"{type(self).__name__} es append-only: no se puede eliminar un "
            "registro. La retención (D5) purga adjuntos, nunca la fila ni su hash."
        )


class WipeOrder(models.Model):
    """Orden destructiva gobernada (ADR-029). Mutable, con máquina de estados.

    El despacho real al agente (Bloque A) está GATED por ADR-029; en este
    incremento la orden nace, se confirma a dos personas y espera la ventana de
    arrepentimiento, pero el envío al equipo queda deshabilitado.
    """

    objects = EraseQuerySet.as_manager()

    # A quién apunta. `agent` puede quedar null si el equipo se da de baja luego;
    # por eso se snapshotea la identidad en columnas propias (sobreviven al borrado
    # y al des-enrolamiento).
    agent = models.ForeignKey(
        "agents.Agent",
        related_name="wipe_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        "clients.Client", related_name="wipe_orders", on_delete=models.CASCADE
    )
    site = models.ForeignKey(
        "clients.Site",
        related_name="wipe_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    agent_hostname = models.CharField(max_length=255, blank=True, default="")
    agent_serial = models.CharField(max_length=255, blank=True, default="")

    action = models.CharField(max_length=32, choices=EraseAction.choices)
    scope = models.JSONField(default=dict, blank=True)
    dry_run = models.BooleanField(default=True)
    reason = models.TextField(blank=True, default="")

    # Ancla al caso perdido abierto (RF-G06): el ciclo del modo perdido vigente al
    # crear la orden. No se ordena un borrado desde el listado general.
    lost_mode_cycle = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=32,
        choices=WipeOrderStatus.choices,
        default=WipeOrderStatus.DRAFT,
    )

    # Personas como texto (username), no FK: la traza tiene que sobrevivir a que la
    # cuenta se elimine, igual que `AuditLog.username`.
    ordered_by = models.CharField(max_length=255)
    ordered_at = models.DateTimeField(auto_now_add=True)
    confirmed_by = models.CharField(max_length=255, blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    recovery_deadline = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=255, blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-ordered_at"]

    def __str__(self) -> str:
        return (
            f"WipeOrder<{self.pk}> {self.action} {self.agent_hostname} [{self.status}]"
        )


class EraseAuditRecord(ImmutableChainRecord):
    """Auditoría append-only que sobrevive al borrado (RF-G04).

    Registra cada transición de una `WipeOrder` y la emisión de cada certificado.
    Denormaliza la identidad del equipo para que la fila conserve sentido aunque la
    orden, el agente o el cliente desaparezcan después.
    """

    order = models.ForeignKey(
        WipeOrder,
        related_name="audit_records",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    agent_id = models.CharField(max_length=255, blank=True, default="")
    hostname = models.CharField(max_length=255, blank=True, default="")
    event = models.CharField(max_length=64)
    actor = models.CharField(max_length=255, blank=True, default="")
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"EraseAuditRecord<{self.pk}> {self.event} {self.actor}"

    def canonical_content(self) -> Dict[str, Any]:
        return {
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "order_id": self.order_id,
            "agent_id": self.agent_id,
            "hostname": self.hostname,
            "event": self.event,
            "actor": self.actor,
            "detail": self.detail,
        }


class EraseCertificate(ImmutableChainRecord):
    """Certificado de borrado/destrucción, append-only y firmado (C1/C2/C3).

    Sin el Bloque B, certifica destrucción remota (acciones del Bloque A) o
    destrucción física manual (C7). Los campos propios de B (método ATA/NVMe,
    SMART, verificación por relectura de sectores) quedan en `data` como N/A y los
    llenará el Bloque B cuando exista.

    `document_hash` es el hash del documento JSON canónico (el que también arma el
    PDF); `signature` firma ese documento; el `record_hash` de la base encadena el
    certificado dentro del repositorio inmutable.
    """

    objects = EraseQuerySet.as_manager()

    certificate_id = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=32, choices=CertificateKind.choices)

    order = models.ForeignKey(
        WipeOrder,
        related_name="certificates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    intake = models.ForeignKey(
        "erase.AssetIntake",
        related_name="certificates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    client = models.ForeignKey(
        "clients.Client", related_name="erase_certificates", on_delete=models.CASCADE
    )
    site = models.ForeignKey(
        "clients.Site",
        related_name="erase_certificates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    agent = models.ForeignKey(
        "agents.Agent",
        related_name="erase_certificates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    tenant = models.CharField(max_length=255)
    asset_tag = models.CharField(max_length=255, blank=True, default="")
    method_applied = models.CharField(max_length=64, blank=True, default="")
    standard_ref = models.CharField(max_length=128, blank=True, default="")
    verification_result = models.CharField(max_length=16, blank=True, default="")
    operator = models.CharField(max_length=255, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    software_version = models.CharField(max_length=64, blank=True, default="")

    # Documento completo (par JSON del certificado). El PDF se re-renderiza de acá,
    # así que no se guarda el blob del PDF: la fila es pequeña y se conserva para
    # siempre.
    data = models.JSONField(default=dict)
    document_hash = models.CharField(max_length=64)
    signature = models.TextField(blank=True, default="")
    signature_alg = models.CharField(max_length=64, blank=True, default="")
    signing_key_id = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"EraseCertificate<{self.certificate_id}> {self.kind}"

    def canonical_content(self) -> Dict[str, Any]:
        # El hash de cadena se ata al documento firmado y a su identidad, no a la
        # fila entera: así el encadenamiento cubre exactamente lo que el
        # certificado promete.
        return {
            "certificate_id": self.certificate_id,
            "kind": self.kind,
            "tenant": self.tenant,
            "document_hash": self.document_hash,
            "signature": self.signature,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


class AssetIntake(models.Model):
    """Registro de ingreso del activo a proceso de baja (D1).

    Formaliza la recepción antes de cualquier operación y ancla la cadena de
    custodia. Un activo no funcional o sin medio detectable se enruta directo a
    destrucción física (C7), que comparte el `process_id`.
    """

    objects = EraseQuerySet.as_manager()

    process_id = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(
        "clients.Client", related_name="asset_intakes", on_delete=models.CASCADE
    )
    site = models.ForeignKey(
        "clients.Site",
        related_name="asset_intakes",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    agent = models.ForeignKey(
        "agents.Agent",
        related_name="asset_intakes",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    equipment_serial = models.CharField(max_length=255, blank=True, default="")
    media_serial = models.CharField(max_length=255, blank=True, default="")
    asset_tag = models.CharField(max_length=255, blank=True, default="")
    ticket_ref = models.CharField(max_length=255, blank=True, default="")

    delivered_by = models.CharField(max_length=255, blank=True, default="")
    received_by = models.CharField(max_length=255)
    received_at = models.DateTimeField(null=True, blank=True)
    state = models.CharField(
        max_length=32,
        choices=AssetIntakeState.choices,
        default=AssetIntakeState.FUNCTIONAL,
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AssetIntake<{self.process_id}> {self.equipment_serial}"

    @property
    def routes_to_physical_destruction(self) -> bool:
        # Regla D1: no funcional o sin medio ⇒ destrucción física.
        return self.state in (
            AssetIntakeState.NON_FUNCTIONAL,
            AssetIntakeState.NO_MEDIA,
        )
