import re
import threading
from contextlib import suppress
from typing import Any, Dict, Optional

from django.conf import settings
from python_ipware import IpWare
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from observerrmm.constants import DEMO_NOT_ALLOWED
from observerrmm.helpers import notify_error

request_local = threading.local()


def get_username() -> Optional[str]:
    return getattr(request_local, "username", None)


def get_debug_info() -> Dict[str, Any]:
    return getattr(request_local, "debug_info", {})


# Feature 045: cliente que originó el request (p. ej. "mcp/0.1.0 tool=add_note").
# Informativo, NO es control de seguridad: cualquier cliente puede enviarlo.
CLIENT_HEADER_MAX_LEN = 128
_CLIENT_HEADER_ALLOWED = re.compile(r"[^A-Za-z0-9 ._/=:-]")


def sanitize_client_header(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    clean = _CLIENT_HEADER_ALLOWED.sub("", str(raw))[:CLIENT_HEADER_MAX_LEN].strip()
    return clean or None


def jsonizable(valor: Any) -> Any:
    """Deja `view_args`/`view_kwargs` en algo que `json.dumps` sí acepte.

    Los convertidores de ruta de Django devuelven objetos, no primitivos: `uuid`
    entrega un `uuid.UUID`, y eso NO es serializable. `AuditLog.debug_info` es un
    `JSONField` y `AuditLog.save()` envuelve el `json.dumps` en un `try/except`
    que, al fallar, reemplaza el campo entero por
    `{"error": "could not process audit value"}`. O sea que un audit escrito
    desde una ruta con `<uuid:...>` no perdía sólo el kwarg: perdía también la
    IP, la URL y el método, en silencio y sin excepción que lo delate.

    No había ocurrido porque hasta ahora ninguna vista con kwarg UUID escribía
    `AuditLog` (las de `fileretrieval` no auditaban nada). La descarga de un
    archivo recuperado sí, así que acá se arregla la causa en vez de esquivarla
    en el llamador.
    """
    if isinstance(valor, (str, int, float, bool, type(None))):
        return valor
    if isinstance(valor, dict):
        return {str(k): jsonizable(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [jsonizable(v) for v in valor]
    return str(valor)


EXCLUDE_PATHS = (
    "/api/v3",
    "/api/v4",
    "/logs/audit",
    f"/{settings.ADMIN_URL}",
    "/logout",
    "/agents/installer",
    "/api/schema",
    "/accounts/ssoproviders/token",
    "/_allauth/browser/v1/config",
    "/_allauth/browser/v1/auth/provider/redirect",
)

DEMO_EXCLUDE_PATHS = (
    "/api/v4",
    "/api/schema",
)


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # El `finally` es la ÚNICA limpieza garantizada, y tiene que estar.
        #
        # `process_view` deja el usuario del request en `request_local`, que es
        # estado de PROCESO: un `threading.local()` de módulo, creado al
        # importar. No se reinicia solo entre requests. Y mientras siga puesto,
        # `BaseAuditModel.save()` (logs/models.py) escribe un `AuditLog` por
        # CADA save de un modelo auditado —Agent, Client, Site, User,
        # CoreSettings…— aunque ya no haya ningún request en curso.
        #
        # Los dos hooks de abajo no alcanzan a cubrir todas las respuestas:
        # `process_template_response` sólo corre si la respuesta sabe
        # renderizarse (las `Response` de DRF, sí; una `FileResponse` o un
        # `HttpResponse` plano, no) y `process_exception` sólo si la vista
        # revienta. O sea que todo endpoint de descarga dejaba el usuario
        # pegado: el instalador .ps1, el XLSX de actividad, el PDF del informe
        # de extravío, los certificados de borrado, los assets de reportería.
        #
        # En producción eso le atribuye al último usuario que bajó un archivo
        # los audit de cualquier save posterior del worker. En la suite se ve
        # como filas de `AuditLog` que aparecen de la nada en tests que no
        # tienen nada que ver: el 2026-10-28, `logs/tests.py` contó 99 filas
        # donde esperaba 86. Las trece de más no sobrevivían a ningún rollback,
        # las creaba el propio fixture del test al arrancar con el usuario de
        # otro test todavía puesto. Ver `logs/test_audit_isolation.py` y
        # `observerrmm/test_audit_request_local.py`.
        try:
            return self.get_response(request)
        finally:
            self.limpiar_request_local()

    @staticmethod
    def limpiar_request_local():
        request_local.debug_info = None
        request_local.username = None

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.path.startswith(EXCLUDE_PATHS):
            # https://stackoverflow.com/questions/26240832/django-and-middleware-which-uses-request-user-is-always-anonymous
            try:
                # DRF saves the class of the view function as the .cls property
                view_class = view_func.cls
                # We need to instantiate the class
                view = view_class()
                # And give it an action_map. It's not relevant for us, but otherwise it errors.
                view.action_map = {}
                # Here's our fully formed and authenticated (or not, depending on credentials) request
                request = view.initialize_request(request)
            except (AttributeError, TypeError):
                from rest_framework.views import APIView

                # Can't initialize the request from this view. Fallback to using default permission classes
                request = APIView().initialize_request(request)

            # check if user is authenticated. PermissionDenied: el canal MCP cerrado
            # (feature 045) se rechaza en la autenticación; la vista lo responde 403.
            with suppress(AuthenticationFailed, PermissionDenied):
                if hasattr(request, "user") and request.user.is_authenticated:
                    try:
                        view_Name = view_func.__dict__["view_class"].__name__
                    except:
                        view_Name = view_func.__name__
                    debug_info = {}
                    # gather and save debug info
                    debug_info["url"] = request.path
                    debug_info["method"] = request.method
                    debug_info["view_class"] = (
                        view_func.cls.__name__ if hasattr(view_func, "cls") else None
                    )
                    debug_info["view_func"] = view_Name
                    debug_info["view_args"] = jsonizable(view_args)
                    debug_info["view_kwargs"] = jsonizable(view_kwargs)
                    debug_info["ip"] = request._client_ip
                    client = sanitize_client_header(
                        request.META.get("HTTP_X_OBSERVER_CLIENT")
                    )
                    if client:
                        debug_info["client"] = client

                    request_local.debug_info = debug_info

                    # get authenticated user after request
                    request_local.username = request.user.username

    # Estos dos quedan por una razón: limpian ANTES de que la respuesta se
    # renderice, que es el momento en que lo hacían hasta ahora. El `finally`
    # de `__call__` corre DESPUÉS del render, así que sacarlos cambiaría que
    # `AuditLog.save()` alcance a ver el `debug_info` durante el render. No
    # reemplazan al `finally`: no cubren las respuestas que no se renderizan.
    def process_exception(self, request, exception):
        self.limpiar_request_local()

    def process_template_response(self, request, response):
        self.limpiar_request_local()
        return response


class LogIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ipw = IpWare()
        client_ip, _ = ipw.get_client_ip(request.META)

        request._client_ip = str(client_ip) if client_ip else ""
        response = self.get_response(request)
        return response


class DemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

        self.not_allowed = DEMO_NOT_ALLOWED

    def __call__(self, request):
        return self.get_response(request)

    def drf_mock_response(self, request, resp):
        from rest_framework.views import APIView

        view = APIView()
        view.headers = view.default_response_headers
        return view.finalize_response(request, resp).render()

    def process_view(self, request, view_func, view_args, view_kwargs):
        err = "Not available in demo"
        if request.path.startswith(DEMO_EXCLUDE_PATHS):
            return self.drf_mock_response(request, notify_error(err))

        try:
            view_Name = view_func.__dict__["view_class"].__name__
        except:
            return
        for i in self.not_allowed:
            if view_Name == i["name"] and request.method in i["methods"]:
                return self.drf_mock_response(request, notify_error(err))
