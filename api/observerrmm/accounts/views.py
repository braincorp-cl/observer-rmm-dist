import datetime

import pyotp
from allauth.socialaccount.models import SocialAccount, SocialApp
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone as djangotime
from knox.models import AuthToken
from knox.views import LoginView as KnoxLoginView
from python_ipware import IpWare
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import (
    ModelSerializer,
    ReadOnlyField,
    SerializerMethodField,
)
from rest_framework.views import APIView

from accounts.utils import (
    can_assign_role,
    can_manage_user,
    is_root_user,
    is_superuser,
)
from core.tasks import sync_mesh_perms_task
from logs.models import AuditLog
from observerrmm.helpers import notify_denied, notify_error
from observerrmm.mixins import GenericPermsViewMixin
from observerrmm.throttles import (
    CheckCredsDayThrottle,
    CheckCredsMinThrottle,
    LoginDayThrottle,
    LoginMinThrottle,
)
from observerrmm.utils import get_core_settings

from .models import APIKey, Role, User
from .permissions import (
    AccountsPerms,
    APIKeyPerms,
    LocalUserPerms,
    RolesPerms,
    SelfResetSSOPerms,
)
from .serializers import (
    APIKeySerializer,
    RoleSerializer,
    TOTPSetupSerializer,
    UserSerializer,
    UserUISerializer,
)


class CheckCredsV2(KnoxLoginView):
    permission_classes = (AllowAny,)
    throttle_classes = [CheckCredsMinThrottle, CheckCredsDayThrottle]

    # restrict time on tokens issued by this view to 3 min
    def get_token_ttl(self):
        return datetime.timedelta(seconds=180)

    def post(self, request, format=None):
        # check credentials
        serializer = AuthTokenSerializer(data=request.data)
        if not serializer.is_valid():
            # .get() avoids a KeyError → HTTP 500 when the payload is empty or
            # missing "username"; an invalid body returns 400 "Bad credentials".
            AuditLog.audit_user_failed_login(
                request.data.get("username", ""),
                debug_info={"ip": request._client_ip},
            )
            return notify_error("Bad credentials")

        user = serializer.validated_data["user"]

        if user.block_dashboard_login or user.is_sso_user:
            return notify_error("Bad credentials")

        # block local logon if configured
        core_settings = get_core_settings()
        if not user.is_superuser and core_settings.block_local_user_logon:
            return notify_error("Bad credentials")

        # if totp token not set modify response to notify frontend
        if not user.totp_key:
            login(request, user)
            response = super().post(request, format=None)
            response.data["totp"] = False
            return response

        return Response({"totp": True})


class LoginViewV2(KnoxLoginView):
    permission_classes = (AllowAny,)
    throttle_classes = [LoginMinThrottle, LoginDayThrottle]

    def post(self, request, format=None):
        valid = False

        serializer = AuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        if user.block_dashboard_login:
            return notify_error("Bad credentials")

        # block local logon if configured
        core_settings = get_core_settings()
        if not user.is_superuser and core_settings.block_local_user_logon:
            return notify_error("Bad credentials")

        if user.is_sso_user:
            return notify_error("Bad credentials")

        # A user with no TOTP key has not completed 2FA setup — the real flow
        # routes them through CheckCredsV2 → TOTP setup first. Guard here so a
        # direct POST to /v2/login/ returns a clean 400 instead of crashing
        # pyotp.TOTP(None) → HTTP 500 (caught on greenfield staging 2026-06-23).
        # Same hardening family as GAP-029/GAP-031 (F009).
        if not user.totp_key:
            return notify_error("Bad credentials")

        # .get() avoids a KeyError → HTTP 500 when "twofactor" is absent (valid
        # username/password but no TOTP key in the body); "" fails verification
        # and falls through to a clean 400 "Bad credentials" (GAP-031).
        token = request.data.get("twofactor", "")
        totp = pyotp.TOTP(user.totp_key)

        if settings.DEBUG and token == "sekret":
            valid = True
        elif getattr(settings, "DEMO", False):
            valid = True
        elif totp.verify(token, valid_window=10):
            valid = True

        if valid:
            login(request, user)

            # save ip information
            ipw = IpWare()
            client_ip, _ = ipw.get_client_ip(request.META)
            if client_ip:
                user.last_login_ip = str(client_ip)
                user.save()

            AuditLog.audit_user_login_successful(
                request.data["username"], debug_info={"ip": request._client_ip}
            )
            response = super().post(request, format=None)
            response.data["username"] = request.user.username
            response.data["name"] = None

            return Response(response.data)
        else:
            AuditLog.audit_user_failed_twofactor(
                request.data["username"], debug_info={"ip": request._client_ip}
            )
            return notify_error("Bad credentials")


class GetDeleteActiveLoginSessionsPerUser(APIView):
    permission_classes = [IsAuthenticated, AccountsPerms]

    class TokenSerializer(ModelSerializer):
        user = ReadOnlyField(source="user.username")

        class Meta:
            model = AuthToken
            fields = (
                "digest",
                "user",
                "created",
                "expiry",
            )

    def get(self, request, pk):
        tokens = get_object_or_404(User, pk=pk).auth_token_set.filter(
            expiry__gt=djangotime.now()
        )

        return Response(self.TokenSerializer(tokens, many=True).data)

    def delete(self, request, pk):
        tokens = get_object_or_404(User, pk=pk).auth_token_set.filter(
            expiry__gt=djangotime.now()
        )

        tokens.delete()
        return Response("ok")


class DeleteActiveLoginSession(APIView):
    permission_classes = [IsAuthenticated, AccountsPerms]

    def delete(self, request, pk):
        token = get_object_or_404(AuthToken, digest=pk)

        token.delete()

        return Response("ok")


class GetAddUsers(APIView):
    permission_classes = [IsAuthenticated, AccountsPerms]

    class UserSerializerSSO(ModelSerializer):
        social_accounts = SerializerMethodField()

        def get_social_accounts(self, obj):
            accounts = SocialAccount.objects.filter(user_id=obj.pk)

            if accounts:
                social_accounts = []
                for account in accounts:
                    try:
                        provider_account = account.get_provider_account()
                        display = provider_account.to_str()
                    except SocialApp.DoesNotExist:
                        display = "Orphaned Provider"
                    except Exception:
                        display = "Unknown"

                    social_accounts.append(
                        {
                            "uid": account.uid,
                            "provider": account.provider,
                            "display": display,
                            "last_login": account.last_login,
                            "date_joined": account.date_joined,
                            "extra_data": account.extra_data,
                        }
                    )

                return social_accounts

            return []

        class Meta:
            model = User
            fields = [
                "id",
                "username",
                "first_name",
                "last_name",
                "email",
                "is_active",
                "last_login",
                "last_login_ip",
                "role",
                "block_dashboard_login",
                "date_format",
                "social_accounts",
            ]

    def get(self, request):
        search = request.GET.get("search", None)

        if search:
            users = User.objects.filter(agent=None, is_installer_user=False).filter(
                username__icontains=search
            )
        else:
            users = User.objects.filter(agent=None, is_installer_user=False)

        return Response(self.UserSerializerSSO(users, many=True).data)

    def post(self, request):
        # add new user
        validate_username = UnicodeUsernameValidator()
        try:
            validate_username(request.data["username"])
        except ValidationError as e:
            return notify_error(str(e))

        # Feature 052: el perfil se valida ANTES de crear la cuenta. Hacerlo
        # después dejaría un usuario a medio crear —sin perfil, pero existente y
        # con el nombre ocupado— cada vez que alguien intenta otorgar de más.
        #
        # 🔑 Este es el único de los cinco puntos de escritura que no llama a
        # `is_root_user`: no aparece al buscarlo, y es justo el que permite
        # fabricarse un superusuario nuevo en vez de modificar uno existente.
        requested_role = None
        if "role" in request.data.keys() and isinstance(request.data["role"], int):
            requested_role = get_object_or_404(Role, pk=request.data["role"])
            allowed, reason = can_assign_role(request.user, requested_role)
            if not allowed:
                AuditLog.audit_delegation_denied(
                    username=request.user.username,
                    target=request.data["username"],
                    reason=reason,
                    attempted_role=requested_role.name,
                )
                return notify_denied(reason)

        try:
            user = User.objects.create_user(  # type: ignore
                request.data["username"],
                request.data["email"],
                request.data["password"],
            )
        except IntegrityError:
            return notify_error(
                f"ERROR: User {request.data['username']} already exists!"
            )

        if "first_name" in request.data.keys():
            user.first_name = request.data["first_name"]
        if "last_name" in request.data.keys():
            user.last_name = request.data["last_name"]
        if requested_role is not None:
            user.role = requested_role

        user.save()
        sync_mesh_perms_task.delay()
        return Response(user.username)


class GetUpdateDeleteUser(APIView):
    permission_classes = [IsAuthenticated, AccountsPerms]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        return Response(UserSerializer(user).data)

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        if is_root_user(request=request, user=user):
            return notify_error("The root user cannot be modified from the UI")

        # Feature 052, RN-04 y RN-09: sobre quién se puede escribir.
        allowed, reason = can_manage_user(request.user, user)
        if not allowed:
            AuditLog.audit_delegation_denied(
                username=request.user.username, target=user.username, reason=reason
            )
            return notify_denied(reason)

        if "role" in request.data.keys():
            new_role = request.data["role"]
            current_role_pk = user.role.pk if user.role else None

            if new_role != current_role_pk:
                # RN-03: nadie se cambia su propio rol. Va antes que el resto
                # porque cambiarse el rol a uno mismo es la elevación directa, y
                # `can_manage_user` deja pasar la propia cuenta a propósito
                # —para el auto-servicio— así que acá no hay quien lo frene.
                if user.pk == request.user.pk:
                    reason = "No puedes cambiar tu propio perfil."
                    AuditLog.audit_delegation_denied(
                        username=request.user.username,
                        target=user.username,
                        reason=reason,
                    )
                    return notify_denied(reason)

                if new_role is not None:
                    target_role = get_object_or_404(Role, pk=new_role)
                    allowed, reason = can_assign_role(request.user, target_role)
                    if not allowed:
                        AuditLog.audit_delegation_denied(
                            username=request.user.username,
                            target=user.username,
                            reason=reason,
                            attempted_role=target_role.name,
                        )
                        return notify_denied(reason)

        serializer = UserSerializer(instance=user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        sync_mesh_perms_task.delay()

        return Response("ok")

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if is_root_user(request=request, user=user):
            return notify_error("The root user cannot be deleted from the UI")

        allowed, reason = can_manage_user(request.user, user)
        if not allowed:
            AuditLog.audit_delegation_denied(
                username=request.user.username, target=user.username, reason=reason
            )
            return notify_denied(reason)

        user.delete()
        sync_mesh_perms_task.delay()
        return Response("ok")


class UserActions(APIView):
    permission_classes = [IsAuthenticated, AccountsPerms, LocalUserPerms]

    # reset password
    def post(self, request):
        user = get_object_or_404(User, pk=request.data["id"])
        if is_root_user(request=request, user=user):
            return notify_error("The root user cannot be modified from the UI")

        # Feature 052: resetear la contraseña de otra persona es tomar su cuenta.
        # `can_manage_user` deja pasar la propia, con lo que la excepción de
        # auto-servicio del issue #686 que vive en `AccountsPerms` sigue intacta.
        allowed, reason = can_manage_user(request.user, user)
        if not allowed:
            AuditLog.audit_delegation_denied(
                username=request.user.username, target=user.username, reason=reason
            )
            return notify_denied(reason)

        user.set_password(request.data["password"])
        user.save()

        return Response("ok")

    # reset two factor token
    def put(self, request):
        user = get_object_or_404(User, pk=request.data["id"])
        if is_root_user(request=request, user=user):
            return notify_error("The root user cannot be modified from the UI")

        # Feature 052: borrar el segundo factor de otra persona deja su cuenta a
        # merced de quien tenga la contraseña. Misma regla que el reset de
        # contraseña, y el auto-servicio del #686 se conserva igual.
        allowed, reason = can_manage_user(request.user, user)
        if not allowed:
            AuditLog.audit_delegation_denied(
                username=request.user.username, target=user.username, reason=reason
            )
            return notify_denied(reason)

        user.totp_key = ""
        user.save()

        return Response(
            f"{user.username}'s Two-Factor key was reset. Have them sign in again to setup"
        )


class TOTPSetup(GenericPermsViewMixin, APIView):
    # totp setup
    def post(self, request):
        user = request.user
        if not user.totp_key:
            code = pyotp.random_base32()
            user.totp_key = code
            user.save(update_fields=["totp_key"])
            return Response(TOTPSetupSerializer(user).data)

        return Response(False)


class UserUI(GenericPermsViewMixin, APIView):
    def patch(self, request):
        serializer = UserUISerializer(
            instance=request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response("ok")


class GetAddRoles(APIView):
    permission_classes = [IsAuthenticated, RolesPerms]

    def get(self, request):
        # Feature 052, RF-06: un no superusuario solo ve los perfiles que puede
        # otorgar. Así el selector de la consola se acota sin lógica propia en el
        # frontend —ya pinta tal cual lo que llega de acá— y el backend sigue
        # siendo la única autoridad.
        #
        # Nótese el contraste deliberado con el listado de USUARIOS, que no se
        # filtra (RN-09): ocultar perfiles evita otorgarlos por error, ocultar
        # cuentas rompería la trazabilidad y provocaría colisiones de nombre.
        # Las dos ramas ordenan por `name` (unico) porque esto alimenta un
        # selector: si cada peticion lo devolviera en otro orden, la lista
        # saltaria sola en pantalla. Ordenar en ambas ademas evita que el
        # selector cambie de criterio segun quien lo abra.
        if request.user.is_superuser or is_superuser(request.user):
            roles = Role.objects.order_by("name")
        elif request.user.role:
            # Se filtra con `can_assign_role()`, la MISMA función que valida al
            # asignar, y no solo por la lista. Si se filtrara solo por la lista, un
            # rol agregado a mano con permisos que el solicitante no tiene
            # aparecería en el selector y el backend lo rechazaría recién al
            # guardar: la consola ofrecería algo imposible.
            #
            # Usar la misma función es lo que garantiza que el filtro y la
            # validación no puedan desincronizarse al cambiar una de las dos.
            roles = [
                role
                for role in request.user.role.assignable_roles.order_by("name")
                if can_assign_role(request.user, role)[0]
            ]
        else:
            roles = Role.objects.none()

        return Response(RoleSerializer(roles, many=True).data)

    def post(self, request):
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response("Role was added")


class GetUpdateDeleteRole(APIView):
    permission_classes = [IsAuthenticated, RolesPerms]

    def get(self, request, pk):
        role = get_object_or_404(Role, pk=pk)
        return Response(RoleSerializer(role).data)

    def put(self, request, pk):
        role = get_object_or_404(Role, pk=pk)
        serializer = RoleSerializer(instance=role, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        sync_mesh_perms_task.delay()
        return Response("Role was edited")

    def delete(self, request, pk):
        role = get_object_or_404(Role, pk=pk)
        role.delete()
        sync_mesh_perms_task.delay()
        return Response("Role was removed")


class GetAddAPIKeys(APIView):
    permission_classes = [IsAuthenticated, APIKeyPerms]

    def get(self, request):
        # `name` es unico, asi que ordenar por el deja el listado estable sin
        # necesidad de desempate.
        apikeys = APIKey.objects.order_by("name")
        return Response(APIKeySerializer(apikeys, many=True).data)

    def post(self, request):
        # generate a random API Key
        from django.utils.crypto import get_random_string

        request.data["key"] = get_random_string(length=32).upper()
        serializer = APIKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response("The API Key was added")


class GetUpdateDeleteAPIKey(APIView):
    permission_classes = [IsAuthenticated, APIKeyPerms]

    def put(self, request, pk):
        apikey = get_object_or_404(APIKey, pk=pk)

        # remove API key is present in request data
        if "key" in request.data.keys():
            request.data.pop("key")

        serializer = APIKeySerializer(instance=apikey, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response("The API Key was edited")

    def delete(self, request, pk):
        apikey = get_object_or_404(APIKey, pk=pk)
        apikey.delete()
        return Response("The API Key was deleted")


class ResetPass(APIView):
    permission_classes = [IsAuthenticated, SelfResetSSOPerms]

    def put(self, request):
        user = request.user
        user.set_password(request.data["password"])
        user.save()
        return Response("Password was reset.")


class Reset2FA(APIView):
    permission_classes = [IsAuthenticated, SelfResetSSOPerms]

    def put(self, request):
        user = request.user
        user.totp_key = ""
        user.save()
        return Response("2FA was reset. Log out and back in to setup.")
