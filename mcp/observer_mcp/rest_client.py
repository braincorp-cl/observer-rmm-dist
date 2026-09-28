"""Cliente de la API REST de Observer. El MCP no toca la BD: todo pasa por aquí."""

from __future__ import annotations

from typing import Any

import httpx

from . import __version__
from .config import Settings


class RESTError(Exception):
    """Error de la REST ya traducido a un mensaje apto para el LLM."""


class AuthError(RESTError):
    pass


class PermissionDenied(RESTError):
    pass


class ChannelClosed(PermissionDenied):
    """El canal MCP está cerrado: plataforma apagada o rol sin can_use_mcp."""


# Motivos del 403 con que la REST corta el canal MCP (observerrmm/auth.py).
_CHANNEL_CLOSED = {
    "mcp_disabled": "AI assistants (MCP) are disabled on this Observer RMM platform. "
    "An administrator can turn them on in Settings > Global Settings > AI Assistant tab.",
    "mcp_not_permitted": "Your Observer RMM role is not allowed to use AI assistants (MCP). "
    "Ask an administrator to enable 'Use AI assistants (MCP)' on your role in Settings > Permissions Manager.",
}


class NotFound(RESTError):
    pass


class UpstreamError(RESTError):
    pass


class ObserverREST:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.observer_url,
                timeout=self._settings.rest_timeout,
                verify=self._settings.verify_tls,
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self, key: str, tool: str, client_ip: str | None) -> dict[str, str]:
        headers = {
            "X-API-KEY": key,
            "X-Observer-Client": f"mcp/{__version__} tool={tool}",
            "Accept": "application/json",
        }
        if self._settings.host_header:
            headers["Host"] = self._settings.host_header
        if client_ip:
            headers["X-Forwarded-For"] = client_ip
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        key: str,
        tool: str,
        client_ip: str | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        client = self._get_client()
        headers = self._headers(key, tool, client_ip)
        # Solo las lecturas se reintentan: repetir una acción no es seguro.
        attempts = 2 if method == "GET" else 1
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                resp = await client.request(method, path, headers=headers, params=params, json=json)
            except httpx.TimeoutException as exc:
                last_exc = UpstreamError("upstream timeout")
                last_exc.__cause__ = exc
                continue
            except httpx.HTTPError as exc:
                last_exc = UpstreamError(f"upstream unreachable: {type(exc).__name__}")
                last_exc.__cause__ = exc
                continue
            if resp.status_code >= 500:
                last_exc = UpstreamError(f"upstream error HTTP {resp.status_code}")
                continue
            return self._parse(resp)
        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _parse(resp: httpx.Response) -> Any:
        code = resp.status_code
        if code == 401:
            raise AuthError("authentication failed: invalid or expired API key")
        if code == 403:
            try:
                reason = (resp.json() or {}).get("code")
            except (ValueError, AttributeError):
                reason = None
            if reason in _CHANNEL_CLOSED:
                raise ChannelClosed(_CHANNEL_CLOSED[reason])
            raise PermissionDenied("permission denied for this operation")
        if code == 404:
            raise NotFound("not found")
        if code >= 400:
            # notify_error de la REST devuelve el motivo como texto o JSON corto.
            detail = resp.text[:300].strip() or f"HTTP {code}"
            raise RESTError(f"request rejected (HTTP {code}): {detail}")
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text
