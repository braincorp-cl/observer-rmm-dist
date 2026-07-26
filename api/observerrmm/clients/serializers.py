from rest_framework.serializers import (
    ModelSerializer,
    ReadOnlyField,
    SerializerMethodField,
    ValidationError,
)

from .models import Client, ClientCustomField, Deployment, Site, SiteCustomField


class SiteCustomFieldSerializer(ModelSerializer):
    class Meta:
        model = SiteCustomField
        fields = (
            "id",
            "field",
            "site",
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


class SiteSerializer(ModelSerializer):
    client_name = ReadOnlyField(source="client.name")
    custom_fields = SiteCustomFieldSerializer(many=True, read_only=True)
    maintenance_mode = ReadOnlyField()
    agent_count = ReadOnlyField()

    class Meta:
        model = Site
        fields = (
            "id",
            "name",
            "server_policy",
            "workstation_policy",
            "alert_template",
            "client_name",
            "client",
            "custom_fields",
            "agent_count",
            "block_policy_inheritance",
            "maintenance_mode",
            "failing_checks",
            "latitude",
            "longitude",
        )

    def validate(self, val):
        if "name" in val.keys() and "|" in val["name"]:
            raise ValidationError("Site name cannot contain the | character")

        # Coordenadas del sitio (feature 026): opcionales, pero no a medias. Se toma
        # el valor entrante si viene en el payload y el ya guardado si no, porque los
        # PATCH parciales de la consola mandan un solo campo a la vez.
        lat = val.get("latitude", getattr(self.instance, "latitude", None))
        lng = val.get("longitude", getattr(self.instance, "longitude", None))

        if (lat is None) != (lng is None):
            raise ValidationError(
                "Latitude and longitude must be set together, or both left empty"
            )

        if lat is not None and not (-90 <= lat <= 90):
            raise ValidationError("Latitude must be between -90 and 90")

        if lng is not None and not (-180 <= lng <= 180):
            raise ValidationError("Longitude must be between -180 and 180")

        # (0, 0) es el "null island" del Atlántico: en la práctica siempre es un campo
        # a medio llenar, nunca una oficina. Se rechaza para que no active la geocerca.
        if lat == 0 and lng == 0:
            raise ValidationError("Coordinates (0, 0) are not a valid site location")

        return val


class SiteMinimumSerializer(ModelSerializer):
    client_name = ReadOnlyField(source="client.name")

    class Meta:
        model = Site
        fields = "__all__"


class ClientMinimumSerializer(ModelSerializer):
    class Meta:
        model = Client
        fields = "__all__"


class ClientCustomFieldSerializer(ModelSerializer):
    class Meta:
        model = ClientCustomField
        fields = (
            "id",
            "field",
            "client",
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


class ClientSerializer(ModelSerializer):
    sites = SerializerMethodField()
    custom_fields = ClientCustomFieldSerializer(many=True, read_only=True)
    maintenance_mode = ReadOnlyField()
    agent_count = ReadOnlyField()

    def get_sites(self, obj):
        return SiteSerializer(
            obj.filtered_sites,
            many=True,
        ).data

    class Meta:
        model = Client
        fields = (
            "id",
            "name",
            "server_policy",
            "workstation_policy",
            "alert_template",
            "block_policy_inheritance",
            "sites",
            "custom_fields",
            "agent_count",
            "maintenance_mode",
            "failing_checks",
        )

    def validate(self, val):
        if "name" in val.keys() and "|" in val["name"]:
            raise ValidationError("Client name cannot contain the | character")

        return val


class DeploymentSerializer(ModelSerializer):
    client_id = ReadOnlyField(source="client.id")
    site_id = ReadOnlyField(source="site.id")
    client_name = ReadOnlyField(source="client.name")
    site_name = ReadOnlyField(source="site.name")

    class Meta:
        model = Deployment
        fields = [
            "id",
            "uid",
            "client_id",
            "site_id",
            "client_name",
            "site_name",
            "mon_type",
            "goarch",
            "expiry",
            "install_flags",
            "created",
        ]


class SiteAuditSerializer(ModelSerializer):
    class Meta:
        model = Site
        fields = "__all__"


class ClientAuditSerializer(ModelSerializer):
    class Meta:
        model = Client
        fields = "__all__"
