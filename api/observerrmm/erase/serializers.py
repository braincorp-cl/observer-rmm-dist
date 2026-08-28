from rest_framework import serializers

from erase.models import (
    AssetIntake,
    EraseAuditRecord,
    EraseCertificate,
    FileRetrievalOrder,
    RetrievedFile,
    WipeOrder,
)


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
    method = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    operator = serializers.CharField(required=False, allow_blank=True, default="")


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
