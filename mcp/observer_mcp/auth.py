"""Credenciales (F1: API key de Observer) y puerta HTTP delante del transporte MCP.

F2 (OAuth 2.1 con Authentik) reemplaza `resolve_credential` por la validación del
JWT (issuer + audiencia) y el mapeo sub -> credencial propia; el resto no cambia.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import parse_qs

from . import __version__
from .config import Settings
from .rest_client import AuthError, ObserverREST, RESTError
from .safety import RateLimiter

REALM = 'Bearer realm="observer-mcp"'
_QUERY_CREDENTIAL_PARAMS = {"access_token", "token", "api_key", "apikey", "key"}


class MissingCredential(Exception):
    pass


def bearer_from_headers(headers: Mapping[str, str] | None) -> str | None:
    if not headers:
        return None
    raw = headers.get("authorization") or headers.get("Authorization") or ""
    scheme, _, value = raw.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def resolve_credential(headers: Mapping[str, str] | None, settings: Settings) -> str:
    """Credencial con la que se llama a la REST en nombre de este request."""
    if settings.transport == "stdio":
        assert settings.api_key
        return settings.api_key
    key = bearer_from_headers(headers)
    if not key:
        raise MissingCredential("missing bearer credential")
    return key


def fingerprint(key: str) -> str:
    """Identificador no reversible para logs y rate limit (nunca se loguea la key)."""
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def client_ip_from_headers(headers: Mapping[str, str] | None) -> str | None:
    if not headers:
        return None
    # X-Real-IP lo fija el proxy perimetral con la IP que ve; el primer salto de
    # X-Forwarded-For lo puede escribir el propio cliente. Es dato informativo
    # para la auditoría, no se usa para decidir nada.
    real = (headers.get("x-real-ip") or "").strip()
    if real:
        return real
    first = (headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return first or None


ASGIApp = Callable[[dict, Callable[[], Awaitable[dict]], Callable[[dict], Awaitable[None]]], Awaitable[None]]


class AuthGate:
    """Middleware ASGI delante de /mcp: health, 401, 400 por token en la query,
    405 en GET, 429 por rate limit. Valida la key contra la REST (GET /core/version/,
    liviano y autenticado) con caché positiva corta; la revocación igual se aplica
    al instante porque cada tool vuelve a presentar la key a la REST."""

    def __init__(self, app: ASGIApp, settings: Settings, rest: ObserverREST, clock=time.monotonic):
        self.app = app
        self.settings = settings
        self.rest = rest
        self.limiter = RateLimiter(settings.rate_per_min, clock=clock)
        self._clock = clock
        self._valid_until: dict[str, float] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        path, method = scope["path"], scope["method"]
        if path == "/mcp/health":
            if method != "GET":
                await _respond(send, 405, {"error": "method not allowed"})
                return
            await _respond(send, 200, {"status": "ok", "version": __version__})
            return

        query = parse_qs(scope.get("query_string", b"").decode(errors="replace"))
        if _QUERY_CREDENTIAL_PARAMS & {k.lower() for k in query}:
            await _respond(send, 400, {"error": "credentials must not be sent in the query string"})
            return

        if method == "GET":
            await _respond(send, 405, {"error": "method not allowed"}, {"allow": "POST"})
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        key = bearer_from_headers(headers)
        if not key:
            await _respond(send, 401, {"error": "unauthorized"}, {"www-authenticate": REALM})
            return

        fp = fingerprint(key)
        wait = self.limiter.acquire(fp)
        if wait > 0:
            await _respond(send, 429, {"error": "rate limit exceeded"}, {"retry-after": str(max(1, int(wait + 0.999)))})
            return

        if self._valid_until.get(fp, 0.0) < self._clock():
            try:
                await self.rest.request(
                    "GET",
                    "/core/version/",
                    key=key,
                    tool="auth-check",
                    client_ip=client_ip_from_headers(headers),
                )
            except AuthError:
                self._valid_until.pop(fp, None)
                await _respond(
                    send,
                    401,
                    {"error": "invalid or expired API key"},
                    {"www-authenticate": REALM + ', error="invalid_token"'},
                )
                return
            except RESTError:
                await _respond(send, 502, {"error": "upstream unavailable"})
                return
            self._valid_until[fp] = self._clock() + self.settings.auth_cache_seconds

        await self.app(scope, receive, send)


async def _respond(send, status: int, body: dict[str, Any], extra: dict[str, str] | None = None) -> None:
    payload = json.dumps(body).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
    for k, v in (extra or {}).items():
        headers.append((k.encode(), v.encode()))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": payload})
