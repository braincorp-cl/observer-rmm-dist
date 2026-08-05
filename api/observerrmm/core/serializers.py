from django.conf import settings
from rest_framework import serializers

from observerrmm.constants import ALL_TIMEZONES

from .models import (
    CodeSignToken,
    CoreSettings,
    CustomField,
    GlobalKVStore,
    MonthlyType,
    Schedule,
    ScheduleType,
    URLAction,
)


class HostedCoreMixin:
    def to_representation(self, instance):
        ret = super().to_representation(instance)  # type: ignore
        if getattr(settings, "HOSTED", False):
            for field in ("mesh_site", "mesh_token", "mesh_username"):
                ret[field] = "n/a"

            ret["sync_mesh_with_ormm"] = True
            ret["enable_server_scripts"] = False
            ret["enable_server_webterminal"] = False

        return ret


# Credenciales que nunca vuelven al navegador: una vez guardadas sólo se pueden
# reemplazar o quitar, jamás leer desde la consola ni desde el log de auditoría.
SECRET_FIELDS = (
    "smtp_host_password",
    "twilio_auth_token",
    "mesh_token",
    "open_ai_token",
)

# La consola manda este centinela para pedir el borrado explícito de un secreto.
# Vacío significa "no lo toqué", así que hace falta una señal aparte para borrar.
CLEAR_SECRET = "__ORMM_SECRET_CLEAR__"

# La integración con MeshCentral no se configura desde la consola. Editarla ahí
# nunca fue la vía correcta y siempre pudo dejar el control remoto roto, así que
# el serializer la rechaza entera. Lo único que queda editable de esa pestaña es
# `mesh_company_name`, que es cosmético (el nombre visible de los usuarios espejo
# dentro de MeshCentral, vía build_mesh_display_name).
#
# Son dos motivos distintos:
#
# 1. Datos de conexión. El valor que manda vive en local_settings.py, que Ansible
#    renderiza desde el vault del rol observer_mesh, y `manage.py
#    initial_mesh_setup` lo copia acá en cada corrida del rol completo. La copia
#    editada no persiste, y hasta el próximo despliegue con el rol deja "Tomar
#    control" roto (el deploy-api.yml del día a día NO corre initial_mesh_setup).
#
# 2. Topología y política, que NADIE resincroniza:
#    - mesh_device_group lo leen la generación de instaladores (agents/utils.py)
#      y el registro de agentes nuevos (apiv3/views.py). initial_mesh_setup crea
#      el grupo con el nombre HARDCODEADO "ObserverRMM" y no toca este campo, así
#      que un nombre equivocado no se sana nunca.
#    - sync_mesh_with_ormm en falso borra todos los usuarios de MeshCentral
#      (core/tasks.py) y abre los permisos por completo: la única jugada posible
#      era empeorar la seguridad. Si alguna vez hace falta apagarlo, va por shell.
MESH_READ_ONLY_FIELDS = (
    "mesh_site",
    "mesh_username",
    "mesh_token",
    "mesh_device_group",
    "sync_mesh_with_ormm",
)


class MaskedSecretsMixin:
    """Los secretos salen vacíos y entran sólo cuando traen un valor nuevo.

    En la salida, cada campo de `SECRET_FIELDS` se reemplaza por `""` y se
    acompaña de un booleano `<campo>_set` para que la consola pueda decir si
    hay algo guardado sin conocer el valor.

    En la entrada, un campo vacío conserva lo que ya estaba guardado. Sin esto,
    el PUT completo del formulario borraría todos los secretos apenas la consola
    dejara de conocerlos, y guardar una pestaña se llevaría por delante los
    secretos de las otras.
    """

    def to_representation(self, instance):
        ret = super().to_representation(instance)  # type: ignore
        for field in SECRET_FIELDS:
            if field in ret:
                ret[f"{field}_set"] = bool(ret[field])
                ret[field] = ""

        return ret

    def update(self, instance, validated_data):
        for field in SECRET_FIELDS:
            if field not in validated_data:
                continue

            incoming = validated_data[field]
            if incoming == CLEAR_SECRET:
                validated_data[field] = ""
            elif not incoming:
                validated_data[field] = getattr(instance, field)

        return super().update(instance, validated_data)  # type: ignore


class CoreSettingsSerializer(
    HostedCoreMixin, MaskedSecretsMixin, serializers.ModelSerializer
):
    all_timezones = serializers.SerializerMethodField("all_time_zones")

    def all_time_zones(self, obj):
        return ALL_TIMEZONES

    class Meta:
        model = CoreSettings
        fields = "__all__"
        read_only_fields = MESH_READ_ONLY_FIELDS


# for audting
class CoreSerializer(HostedCoreMixin, MaskedSecretsMixin, serializers.ModelSerializer):
    class Meta:
        model = CoreSettings
        fields = "__all__"


class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomField
        fields = "__all__"


class CodeSignTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeSignToken
        fields = "__all__"


class KeyStoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalKVStore
        fields = "__all__"


class URLActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = URLAction
        fields = "__all__"


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = "__all__"

    def to_representation(self, instance):
        # we only need to show data for the schedule type, so this function strips out irrelevant fields
        # could have also done this on the frontend instead of here, but this is a bit cleaner
        ret = super().to_representation(instance)

        # need empty states so frontend doesn't break
        empty_states = {
            "run_time_weekdays": [],
            "monthly_months_of_year": [],
            "monthly_days_of_month": [],
            "monthly_weeks_of_month": [],
        }

        if instance.schedule_type == ScheduleType.DAILY:
            fields_to_clear = [
                "run_time_weekdays",
                "monthly_months_of_year",
                "monthly_days_of_month",
                "monthly_weeks_of_month",
            ]
            for field in fields_to_clear:
                ret[field] = empty_states[field]

        elif instance.schedule_type == ScheduleType.WEEKLY:
            fields_to_clear = [
                "monthly_months_of_year",
                "monthly_days_of_month",
                "monthly_weeks_of_month",
            ]
            for field in fields_to_clear:
                ret[field] = empty_states[field]

        elif instance.schedule_type == ScheduleType.MONTHLY:
            if instance.monthly_type == MonthlyType.DAYS:
                fields_to_clear = [
                    "monthly_weeks_of_month",
                    "run_time_weekdays",
                ]
                for field in fields_to_clear:
                    ret[field] = empty_states[field]

            elif instance.monthly_type == MonthlyType.WEEKS:
                fields_to_clear = [
                    "monthly_days_of_month",
                ]
                for field in fields_to_clear:
                    ret[field] = empty_states[field]

        return ret


class ScheduleAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = "__all__"
