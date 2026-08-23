from typing import Optional

from django.core.cache import cache
from rest_framework import serializers

from observerrmm.constants import (
    AGENT_CHECKS_CACHE_PREFIX,
    AGENT_STATUS_ONLINE,
    ALL_TIMEZONES,
)
from winupdate.serializers import WinUpdatePolicySerializer

from .diskencryption import derivar_estado, volumen_de_sistema
from .models import (
    Agent,
    AgentCustomField,
    AgentHistory,
    DiskEncryptionHistory,
    DiskEncryptionVolume,
    LostModeEvidence,
    LostModePolicy,
    LostModeState,
    Note,
)


class AgentCustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentCustomField
        fields = (
            "id",
            "field",
            "agent",
            "value",
            "string_value",
            "bool_value",
            "multiple_value",
        )
        extra_kwargs = {
            "string_value": {"write_only": True},
            "bool_value": {"write_only": True},
            "multiple_value": {"write_only": True},
        }


class AgentSerializer(serializers.ModelSerializer):
    winupdatepolicy = WinUpdatePolicySerializer(many=True, read_only=True)
    status = serializers.ReadOnlyField()
    # Agente de 32 bits sobre un Windows de 64 bits: instalación equivocada que
    # deja el equipo sin actualizarse y con el inventario incompleto, sin síntoma
    # visible. Ver Agent.wrong_arch_install.
    wrong_arch_install = serializers.ReadOnlyField()
    cpu_model = serializers.ReadOnlyField()
    local_ips = serializers.ReadOnlyField()
    make_model = serializers.ReadOnlyField()
    physical_disks = serializers.ReadOnlyField()
    graphics = serializers.ReadOnlyField()
    checks = serializers.ReadOnlyField()
    timezone = serializers.ReadOnlyField()
    all_timezones = serializers.SerializerMethodField()
    client = serializers.ReadOnlyField(source="client.name")
    site_name = serializers.ReadOnlyField(source="site.name")
    custom_fields = AgentCustomFieldSerializer(many=True, read_only=True)
    patches_last_installed = serializers.ReadOnlyField()
    last_seen = serializers.ReadOnlyField()
    applied_policies = serializers.SerializerMethodField()
    effective_patch_policy = serializers.SerializerMethodField()
    alert_template = serializers.SerializerMethodField()

    def get_alert_template(self, obj):
        from alerts.serializers import AlertTemplateSerializer

        return (
            AlertTemplateSerializer(obj.alert_template).data
            if obj.alert_template
            else None
        )

    def get_effective_patch_policy(self, obj):
        return WinUpdatePolicySerializer(obj.get_patch_policy()).data

    def get_applied_policies(self, obj):
        from automation.serializers import PolicySerializer

        policies = obj.get_agent_policies()

        # need to serialize model objects manually
        for key, policy in policies.items():
            if policy:
                policies[key] = PolicySerializer(policy).data

        return policies

    def get_all_timezones(self, obj):
        return ALL_TIMEZONES

    class Meta:
        model = Agent
        exclude = ["id"]


class AgentTableSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()
    wrong_arch_install = serializers.ReadOnlyField()
    checks = serializers.SerializerMethodField()
    client_name = serializers.ReadOnlyField(source="site.client.name")
    site_name = serializers.ReadOnlyField(source="site.name")
    logged_username = serializers.SerializerMethodField()
    italic = serializers.SerializerMethodField()
    policy = serializers.ReadOnlyField(source="policy.id")
    alert_template = serializers.SerializerMethodField()
    pending_actions_count = serializers.SerializerMethodField()
    has_patches_pending = serializers.SerializerMethodField()
    cpu_model = serializers.ReadOnlyField()
    graphics = serializers.ReadOnlyField()
    local_ips = serializers.ReadOnlyField()
    make_model = serializers.ReadOnlyField()
    physical_disks = serializers.ReadOnlyField()
    serial_number = serializers.ReadOnlyField()
    custom_fields = AgentCustomFieldSerializer(many=True, read_only=True)

    def get_has_patches_pending(self, obj) -> bool:
        return getattr(obj, "has_patches_pending", False)

    def get_checks(self, obj) -> dict:
        data = cache.get(f"{AGENT_CHECKS_CACHE_PREFIX}{obj.pk}")
        if data is None:
            return {
                "total": 0,
                "passing": 0,
                "failing": 0,
                "warning": 0,
                "info": 0,
                "has_failing_checks": False,
            }
        return data

    def get_pending_actions_count(self, obj) -> int:
        return getattr(obj, "_pending_actions_count", 0)

    def get_alert_template(self, obj):
        if not obj.alert_template:
            return None

        return {
            "name": obj.alert_template.name,
            "always_email": obj.alert_template.agent_always_email,
            "always_text": obj.alert_template.agent_always_text,
            "always_alert": obj.alert_template.agent_always_alert,
        }

    def get_logged_username(self, obj) -> str:
        if obj.logged_in_username == "None" and obj.status == AGENT_STATUS_ONLINE:
            return obj.last_logged_in_user
        elif obj.logged_in_username != "None":
            return obj.logged_in_username

        return "-"

    def get_italic(self, obj) -> bool:
        return obj.logged_in_username == "None" and obj.status == AGENT_STATUS_ONLINE

    class Meta:
        model = Agent
        fields = [
            "agent_id",
            "alert_template",
            "hostname",
            "site_name",
            "client_name",
            "monitoring_type",
            "description",
            "needs_reboot",
            "pending_actions_count",
            "status",
            "overdue_text_alert",
            "overdue_email_alert",
            "overdue_dashboard_alert",
            "last_seen",
            "boot_time",
            "checks",
            "maintenance_mode",
            # Feature 036: alimentan el tooltip "desde cuándo y quién" de la celda de
            # estado. No agregan consultas — la vista usa .defer(), no .only().
            "maintenance_mode_since",
            "maintenance_mode_by",
            "logged_username",
            "italic",
            "policy",
            "block_policy_inheritance",
            "plat",
            "goarch",
            # No agrega consultas: `plat`, `goarch` y `operating_system` —los tres
            # datos de los que sale— ya están en esta misma lista.
            "wrong_arch_install",
            "has_patches_pending",
            "version",
            "operating_system",
            "public_ip",
            "cpu_model",
            "graphics",
            "local_ips",
            "make_model",
            "physical_disks",
            "custom_fields",
            "serial_number",
        ]


class AgentHostnameSerializer(serializers.ModelSerializer):
    client = serializers.ReadOnlyField(source="client.name")
    site = serializers.ReadOnlyField(source="site.name")

    class Meta:
        model = Agent
        fields = (
            "id",
            "hostname",
            "agent_id",
            "client",
            "site",
        )


class AgentNoteSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")
    agent_id = serializers.ReadOnlyField(source="agent.agent_id")

    class Meta:
        model = Note
        fields = ("pk", "entry_time", "agent", "user", "note", "username", "agent_id")
        extra_kwargs = {"agent": {"write_only": True}, "user": {"write_only": True}}


class AgentHistorySerializer(serializers.ModelSerializer):
    script_name = serializers.ReadOnlyField(source="script.name")

    class Meta:
        model = AgentHistory
        fields = "__all__"


class AgentAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        exclude = ["disks", "services", "wmi_detail"]


class LostModeStateSerializer(serializers.ModelSerializer):
    """Feature 030: una fila del índice de equipos perdidos.

    Trae el hostname y el nombre de quien marcó porque el índice es una tabla
    plana: sin eso la consola tendría que pedir un agente por fila.
    """

    agent_id = serializers.ReadOnlyField(source="agent.agent_id")
    hostname = serializers.ReadOnlyField(source="agent.hostname")
    plat = serializers.ReadOnlyField(source="agent.plat")
    client_name = serializers.ReadOnlyField(source="agent.client.name")
    site_name = serializers.ReadOnlyField(source="agent.site.name")
    marked_by = serializers.ReadOnlyField(source="marked_by.username")
    # Feature 038 · T013 (RF-11): el índice del caso REPORTA el estado de cifrado
    # del equipo, sin activarlo. Es el mismo veredicto del panel de la 037
    # (RN-A02), derivado acá para que quien opera un robo lo vea sin cambiar de
    # pantalla. `derivar_estado` lee `agent.disk_encryption` + su volumen de
    # sistema; la vista prepara ambos con `select_related`/`Prefetch` para no
    # caer en un N+1 por fila. Un equipo mac/Linux (sin BitLocker) sale "sin
    # dato", nunca "sin cifrar" — la honestidad de RN-A03 vale también acá.
    encryption_state = serializers.SerializerMethodField()

    class Meta:
        model = LostModeState
        fields = (
            "agent_id",
            "hostname",
            "plat",
            "client_name",
            "site_name",
            "active",
            "reason",
            "marked_by",
            "marked_at",
            "recovered_at",
            "interval_min",
            "encryption_state",
        )

    def get_encryption_state(self, obj) -> str:
        return derivar_estado(obj.agent)


class LostModePolicySerializer(serializers.ModelSerializer):
    """Feature 038: los defaults de la cascada POR EQUIPO (nivel intermedio).

    Cada campo es NULO = "heredar del global" o un valor que pisa al global para
    este equipo. La UI de la ficha edita exactamente estos overrides; el caso
    concreto puede a su vez pisarlos al marcar. NO expone el valor resuelto: eso
    lo calcula `resolve_lost_mode_cascade()`, único dueño de la precedencia (W002),
    y la vista lo adjunta aparte para que la UI muestre lo heredado.
    """

    class Meta:
        model = LostModePolicy
        fields = (
            "auto_lock",
            "lock_delay_min",
            "no_hibernate",
            "webcam_override",
            "alarm",
        )


class LostModeEvidenceSerializer(serializers.ModelSerializer):
    """Feature 030 · Fase 1: una pieza de la línea de tiempo del caso.

    NO expone la ruta del archivo. `asset.url` sería una URL servida por el
    almacenamiento, y esta evidencia no se sirve así a propósito: se descarga
    por su fila, con la sesión del operador y el permiso comprobado (ADR-025).
    La consola sabe armar la URL de descarga a partir del `id`; lo que necesita
    saber de acá es sólo SI hay archivo.
    """

    has_asset = serializers.SerializerMethodField()

    class Meta:
        model = LostModeEvidence
        fields = (
            "id",
            "cycle",
            "kind",
            "note",
            "has_asset",
            "lat",
            "lng",
            "accuracy_m",
            "source",
            "session_user",
            "captured_at",
            "created",
        )

    def get_has_asset(self, obj) -> bool:
        return bool(obj.asset)


class DiskEncryptionVolumeSerializer(serializers.ModelSerializer):
    """Feature 037 · un volumen del detalle del agente (RF-05).

    Los códigos van crudos (RN-A05): la consola traduce. Y `measured_at` viaja
    por volumen porque es lo que contesta «¿qué tan viejo es esto?», que en un
    panel de cumplimiento es parte del dato y no un adorno — por `agent-wmi` la
    latencia normal es de 50 a 66 minutos.
    """

    class Meta:
        model = DiskEncryptionVolume
        fields = (
            "device_id",
            "drive_letter",
            "protection_status",
            "conversion_status",
            "encryption_method",
            "encryption_percentage",
            "volume_type",
            "is_system_volume",
            "key_protector_count",
            "key_protector_types",
            "measured_at",
        )


class DiskEncryptionHistorySerializer(serializers.ModelSerializer):
    """Feature 037 · una línea del registro de cambios (RF-09/RN-A09)."""

    class Meta:
        model = DiskEncryptionHistory
        fields = ("device_id", "previous_status", "new_status", "changed_at")


class DiskEncryptionFleetSerializer(serializers.ModelSerializer):
    """Feature 037 · una fila del panel de flota (RF-04).

    El sujeto es el AGENTE y no el volumen, y ahí está la decisión: un equipo
    ocupa una línea con el veredicto de su volumen de sistema (RN-A02). Si la
    fila fuera el volumen, un equipo con tres unidades apareceria tres veces y el
    conteo de cumplimiento —«cuántos equipos incumplen»— dejaría de ser legible.

    `state` NO es una columna: se deriva en `diskencryption.py`, que es también
    donde vive la versión SQL que usa el filtro.
    """

    hostname = serializers.ReadOnlyField()
    client_name = serializers.ReadOnlyField(source="client.name")
    site_name = serializers.ReadOnlyField(source="site.name")
    state = serializers.SerializerMethodField()
    supported = serializers.SerializerMethodField()
    query_error = serializers.SerializerMethodField()
    measured_at = serializers.SerializerMethodField()
    system_volume = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = (
            "agent_id",
            "hostname",
            "plat",
            "client_name",
            "site_name",
            "state",
            "supported",
            "query_error",
            "measured_at",
            "system_volume",
        )

    def get_state(self, obj) -> str:
        return derivar_estado(obj)

    def get_supported(self, obj) -> Optional[bool]:
        estado = getattr(obj, "disk_encryption", None)
        # Un equipo que nunca reportó no es "soportado" ni "no soportado": no
        # sabemos. El nulo lo dice; un `True` por omisión afirmaría de más.
        return estado.supported if estado else None

    def get_query_error(self, obj):
        estado = getattr(obj, "disk_encryption", None)
        return estado.query_error if estado else None

    def get_measured_at(self, obj):
        estado = getattr(obj, "disk_encryption", None)
        return estado.measured_at if estado else None

    def get_system_volume(self, obj):
        volumen = volumen_de_sistema(obj)
        if volumen is None:
            return None
        return DiskEncryptionVolumeSerializer(volumen).data
