from django.utils import timezone as djangotime
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import HTTP_HEADER_ENCODING, BaseAuthentication

from accounts.models import APIKey

# Feature 045: prefijo con que observer-mcp marca sus requests (X-Observer-Client).
MCP_CLIENT_PREFIX = "mcp/"


def is_mcp_request(request) -> bool:
    raw = request.META.get("HTTP_X_OBSERVER_CLIENT", "")
    if isinstance(raw, bytes):
        raw = raw.decode(HTTP_HEADER_ENCODING, errors="replace")
    return str(raw).strip().lower().startswith(MCP_CLIENT_PREFIX)


def check_mcp_access(user) -> None:
    """Corta el canal MCP si está apagado en la plataforma o el rol no lo permite.

    Gobierna el canal del asistente, no la clave: la misma clave sigue sirviendo
    para la API REST directa. 403 con `code` para que observer-mcp explique el
    motivo al técnico en vez de un error genérico.
    """
    from core.utils import get_core_settings

    if not get_core_settings().mcp_enabled:
        raise exceptions.PermissionDenied(
            {
                "detail": "AI assistants (MCP) are disabled on this platform.",
                "code": "mcp_disabled",
            }
        )
    role = getattr(user, "role", None)
    if user.is_superuser or (role and role.is_superuser):
        return
    if not role or not role.can_use_mcp:
        raise exceptions.PermissionDenied(
            {
                "detail": "Your role is not allowed to use AI assistants (MCP).",
                "code": "mcp_not_permitted",
            }
        )


def get_authorization_header(request) -> str:
    """
    Return request's 'Authorization:' header, as a bytestring.

    Hide some test client ickyness where the header can be unicode.
    """
    auth = request.META.get("HTTP_X_API_KEY", b"")
    if isinstance(auth, str):
        # Work around django test client oddness
        auth = auth.encode(HTTP_HEADER_ENCODING)
    return auth


class APIAuthentication(BaseAuthentication):
    """
    Simple token based authentication for stateless api access.

    Clients should authenticate by passing the token key in the "X-API-KEY"
    HTTP header.  For example:

        X-API-KEY: ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789
    """

    def get_model(self):
        return APIKey

    def authenticate(self, request):
        auth = get_authorization_header(request)

        if not auth:
            return None

        try:
            apikey = auth.decode()  # type: ignore
        except UnicodeError:
            msg = _(
                "Invalid token header. Token string should not contain invalid characters."
            )
            raise exceptions.AuthenticationFailed(msg)

        user, key = self.authenticate_credentials(apikey)
        if is_mcp_request(request):
            check_mcp_access(user)
        return user, key

    def authenticate_credentials(self, key):
        try:
            apikey = APIKey.objects.select_related("user").get(key=key)
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed(_("Invalid token."))

        if not apikey.user.is_active:
            raise exceptions.AuthenticationFailed(_("User inactive or deleted."))

        # check if token is expired
        if apikey.expiration and apikey.expiration < djangotime.now():
            raise exceptions.AuthenticationFailed(_("The token has expired."))

        return apikey.user, apikey.key
