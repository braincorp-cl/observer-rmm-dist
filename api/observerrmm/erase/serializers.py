import os

from django.conf import settings
from rest_framework import serializers

from erase.models import (
    AssetIntake,
    CustodyEvent,
    CustodyEventKind,
    DestructionVerification,
    EraseAuditRecord,
    EraseCertificate,
    FileRetrievalOrder,
    RetrievedFile,
    WipeOrder,
    WipePathTemplate,
)

# Tope y tipos del adjunto que acredita una destrucción física. Es la foto que
# saca un técnico con el teléfono, no un informe: 15 MiB sobra y evita que un
# video de varios minutos entre por este camino. Configurable por settings.
DEFAULT_DESTRUCTION_EVIDENCE_MAX_BYTES = 15 * 2**20
DESTRUCTION_EVIDENCE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".heic", ".webp", ".pdf")


class EraseAuditRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = EraseAuditRecord
        fields = [
            "id",
            "created_at",
            "event",
            "actor",
            "detail",
            "prev_hash",
            "record_hash",
        ]


class WipeOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = WipeOrder
        fields = "__all__"


class WipePathTemplateSerializer(serializers.ModelSerializer):
    """Plantilla de rutas base para poblar el selector del diálogo de wipe
    (feature 043 · T017). Sólo lectura: las plantillas se administran aparte, la
    consola las consume para precargar rutas en una orden nueva."""

    class Meta:
        model = WipePathTemplate
        fields = [
            "id",
            "name",
            "client",
            "site",
            "os_scope",
            "paths",
            "created_at",
        ]


class WipeOrderCreateSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[c[0] for c in WipeOrder._meta.get_field("action").choices]
    )
    scope = serializers.JSONField(required=False, default=dict)
    dry_run = serializers.BooleanField(required=False, default=True)
    reason = serializers.CharField(required=True, allow_blank=False)
    lost_mode_cycle = serializers.IntegerField(required=False, allow_null=True)
    # Rutas del wipe (feature 043 · RN-07): plantilla base + ajustes del ordenante.
    # La vista resuelve `plantilla.paths + paths_add − paths_remove` y lo materializa
    # en `scope["paths"]`. Ignorados para acciones que no son `wipe`.
    template = serializers.IntegerField(required=False, allow_null=True)
    paths_add = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    paths_remove = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )


class WipeOrderConfirmSerializer(serializers.Serializer):
    recovery_seconds = serializers.IntegerField(required=False, min_value=0)


class WipeOrderCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class EraseCertificateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = EraseCertificate
        fields = [
            "id",
            "certificate_id",
            "kind",
            "tenant",
            "asset_tag",
            "method_applied",
            "standard_ref",
            "verification_result",
            "operator",
            "created_at",
            "document_hash",
            "signing_key_id",
        ]


class EraseCertificateDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EraseCertificate
        fields = "__all__"


class AssetIntakeSerializer(serializers.ModelSerializer):
    routes_to_physical_destruction = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssetIntake
        fields = "__all__"
        read_only_fields = ["process_id", "created_at", "received_by"]


class CertifyDestructionSerializer(serializers.Serializer):
    """Datos con los que se certifica una destrucción física (C7).

    Lo que acredita la destrucción es **declarativo** (L-03): método, nota y
    testigo, más una fotografía OPCIONAL. La foto no se exige a propósito —
    exigirla bloquearía la destrucción en planta de un tercero, donde el operador
    no siempre puede fotografiar, y empujaría a subir fotos de relleno para pasar
    la validación. Lo que el módulo garantiza no es que haya evidencia, sino que
    el certificado **diga la verdad sobre si la hay**: sin método acreditado y sin
    testigo nombrado el veredicto es `NOT_VERIFIED`, no `PASS`.
    """

    method = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    operator = serializers.CharField(required=False, allow_blank=True, default="")

    # Segunda persona que da fe (Concurrence del Apéndice C).
    concurrence_name = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )
    concurrence_role = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )
    concurrence_contact = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )

    # Cómo se acreditó. `none` es un valor legítimo y explícito, no un hueco.
    verification_method = serializers.ChoiceField(
        choices=DestructionVerification.choices,
        required=False,
        allow_blank=True,
        default="",
    )
    verification_evidence = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=1000
    )
    evidence_file = serializers.FileField(required=False, allow_null=True)

    def validate_evidence_file(self, archivo):
        if archivo is None:
            return archivo
        tope = getattr(
            settings,
            "DESTRUCTION_EVIDENCE_MAX_BYTES",
            DEFAULT_DESTRUCTION_EVIDENCE_MAX_BYTES,
        )
        if archivo.size > tope:
            raise serializers.ValidationError(
                f"el adjunto supera el tope de {tope // 2**20} MiB"
            )
        ext = os.path.splitext(archivo.name or "")[1].lower()
        if ext not in DESTRUCTION_EVIDENCE_EXTENSIONS:
            raise serializers.ValidationError(
                "formato no aceptado; se admiten "
                + ", ".join(DESTRUCTION_EVIDENCE_EXTENSIONS)
            )
        return archivo

    def validate(self, data):
        """Un método presenciado exige nombrar a quien presenció.

        Es la única combinación incoherente: declarar `witnessed` sin decir quién
        es afirmar que alguien dio fe y no poder decir su nombre. El resto de las
        combinaciones son válidas, incluida la de no acreditar nada — eso el
        certificado lo declara, no lo rechaza.
        """
        if (
            data.get("verification_method") == DestructionVerification.WITNESSED
            and not (data.get("concurrence_name") or "").strip()
        ):
            raise serializers.ValidationError(
                {
                    "concurrence_name": "una destrucción presenciada tiene que "
                    "nombrar a quien la presenció"
                }
            )
        return data


# --- fileretrieval (feature 042) --------------------------------------------


class RetrievedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetrievedFile
        fields = ["id", "source_path", "size", "uploaded_at"]


class FileRetrievalOrderSerializer(serializers.ModelSerializer):
    file_count = serializers.SerializerMethodField()

    class Meta:
        model = FileRetrievalOrder
        fields = "__all__"

    def get_file_count(self, obj) -> int:
        return obj.files.count()


class FileRetrievalOrderCreateSerializer(serializers.Serializer):
    paths = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        allow_empty=False,
    )
    dry_run = serializers.BooleanField(required=False, default=False)
    lost_mode_cycle = serializers.IntegerField(required=False, allow_null=True)


class CustodyEventSerializer(serializers.ModelSerializer):
    """Un eslabón de la cadena de custodia (RF-06).

    `kind_label` viaja resuelto por el servidor: la consola no tiene por qué
    conocer el vocabulario, y un token nuevo se pinta igual sin tocar el
    frontend. Mismo criterio que los helpers de `utils/erase.ts`.

    `actor` es de sólo lectura: lo pone el servidor desde la sesión. Aceptarlo
    del cliente permitiría firmar un traslado a nombre de otro.
    """

    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = CustodyEvent
        fields = [
            "id",
            "kind",
            "kind_label",
            "at",
            "actor",
            "location",
            "detail",
            "created_at",
            "prev_hash",
            "record_hash",
        ]
        read_only_fields = [
            "id",
            "actor",
            "created_at",
            "prev_hash",
            "record_hash",
        ]


class CustodyEventCreateSerializer(serializers.Serializer):
    """Lo que el cliente PUEDE mandar al registrar un eslabón.

    Deliberadamente no es un `ModelSerializer`: `actor`, los hashes y la
    identidad denormalizada del expediente **no se aceptan del cliente**, y un
    `ModelSerializer` con `exclude` dejaría la puerta abierta a que un campo
    nuevo entre por omisión.
    """

    kind = serializers.ChoiceField(choices=CustodyEventKind.choices)
    at = serializers.DateTimeField(required=False, allow_null=True)
    location = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )
    detail = serializers.JSONField(required=False, default=dict)


class ReconciliationFilaSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()
    client = serializers.CharField()
    intakes = serializers.IntegerField()
    certified = serializers.IntegerField()
    missing = serializers.IntegerField()
    stalled = serializers.IntegerField()


class ReconciliationFaltanteSerializer(serializers.Serializer):
    intake_id = serializers.IntegerField()
    process_id = serializers.CharField()
    equipment_serial = serializers.CharField()
    received_at = serializers.DateTimeField()
    days_open = serializers.IntegerField()
    # Dónde se detuvo el activo. 🔑 Es lo que convierte el número en una acción;
    # sin RF-06 esta clave no existiría.
    last_event = serializers.DictField(allow_null=True)
    stalled = serializers.BooleanField()


class ReconciliationSerializer(serializers.Serializer):
    period = serializers.DictField()
    totals = serializers.DictField()
    by_client = ReconciliationFilaSerializer(many=True)
    # 🔑 `missing_items` trae SOLO la página pedida; `missing_page` dice cuántos
    # hay en total para que la consola pagine sin adivinar. Devolverlos todos
    # era una respuesta de miles de ítems que ningún test veía.
    missing_items = ReconciliationFaltanteSerializer(many=True)
    missing_page = serializers.DictField()
