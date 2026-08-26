from rest_framework import serializers

from erase.models import (
    AssetIntake,
    EraseAuditRecord,
    EraseCertificate,
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
