from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import ModelSerializer, ReadOnlyField

from automation.serializers import PolicySerializer
from clients.serializers import ClientMinimumSerializer, SiteMinimumSerializer
from observerrmm.constants import AlertTemplateActionType

from .models import Alert, AlertTemplate


class AlertSerializer(ModelSerializer):
    # Estos cuatro salían de `ReadOnlyField(source="assigned_agent.hostname")` y
    # compañía. Cuando la alerta no tiene agente —las `custom`, y ahora las de
    # desinstalación manual, que nacen con `agent=None` a propósito porque el
    # agente está por borrarse— el encadenamiento revienta con AttributeError y
    # DRF resuelve OMITIENDO la clave del payload. El frontend recibía entonces
    # objetos con forma distinta según la alerta. Ahora la clave está siempre y
    # vale null cuando no hay de dónde sacarla.
    hostname = SerializerMethodField()
    agent_id = SerializerMethodField()
    client = SerializerMethodField()
    site = SerializerMethodField()
    alert_time = ReadOnlyField()

    class Meta:
        model = Alert
        fields = "__all__"

    def get_hostname(self, obj):
        return obj.agent.hostname if obj.agent else None

    def get_agent_id(self, obj):
        return obj.agent.agent_id if obj.agent else None

    def get_client(self, obj):
        return obj.agent.client.name if obj.agent else None

    def get_site(self, obj):
        return obj.agent.site.name if obj.agent else None


class AlertTemplateSerializer(ModelSerializer):
    agent_settings = ReadOnlyField(source="has_agent_settings")
    check_settings = ReadOnlyField(source="has_check_settings")
    task_settings = ReadOnlyField(source="has_task_settings")
    core_settings = ReadOnlyField(source="has_core_settings")
    default_template = ReadOnlyField(source="is_default_template")
    action_name = SerializerMethodField()
    resolved_action_name = SerializerMethodField()
    applied_count = SerializerMethodField()

    class Meta:
        model = AlertTemplate
        fields = "__all__"

    def get_action_name(self, obj):
        if obj.action_type == AlertTemplateActionType.REST and obj.action_rest:
            return obj.action_rest.name

        return obj.action.name if obj.action else ""

    def get_resolved_action_name(self, obj):
        if (
            obj.resolved_action_type == AlertTemplateActionType.REST
            and obj.resolved_action_rest
        ):
            return obj.resolved_action_rest.name

        return obj.resolved_action.name if obj.resolved_action else ""

    def get_applied_count(self, instance):
        return (
            instance.policies.count()
            + instance.clients.count()
            + instance.sites.count()
        )


class AlertTemplateRelationSerializer(ModelSerializer):
    policies = PolicySerializer(read_only=True, many=True)
    clients = ClientMinimumSerializer(read_only=True, many=True)
    sites = SiteMinimumSerializer(read_only=True, many=True)

    class Meta:
        model = AlertTemplate
        fields = "__all__"


class AlertTemplateAuditSerializer(ModelSerializer):
    class Meta:
        model = AlertTemplate
        fields = "__all__"
