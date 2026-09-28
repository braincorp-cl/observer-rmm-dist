"""Configuración del servicio, leída del entorno (ver data-delta de la feature 045)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Mapping

Transport = Literal["http", "stdio"]


class ConfigError(ValueError):
    pass


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} debe ser entero, llegó {raw!r}") from exc
    if value <= 0:
        raise ConfigError(f"{name} debe ser > 0, llegó {value}")
    return value


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    observer_url: str
    transport: Transport = "http"
    # Host que se manda a la REST cuando observer_url apunta a loopback (el
    # server_name de nginx es el dominio del API, no 127.0.0.1).
    host_header: str | None = None
    verify_tls: bool = True
    # Solo en stdio: la credencial viene del entorno. En http viene por request.
    api_key: str | None = None
    port: int = 8765
    max_agents: int = 10
    rate_per_min: int = 60
    max_response_chars: int = 100_000
    rest_timeout: float = 30.0
    auth_cache_seconds: int = 30
    disabled_tools: frozenset[str] = field(default_factory=frozenset)
    # Protección contra DNS rebinding del SDK: Host/Origin aceptados en /mcp.
    allowed_hosts: tuple[str, ...] = ("127.0.0.1:*", "localhost:*")
    allowed_origins: tuple[str, ...] = ()


def load_settings(env: Mapping[str, str] | None = None, transport: Transport = "http") -> Settings:
    env = os.environ if env is None else env

    url = env.get("OBSERVER_URL", "").strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ConfigError("OBSERVER_URL es obligatorio y debe empezar con http:// o https://")

    api_key = env.get("OBSERVER_API_KEY", "").strip() or None
    if transport == "stdio" and not api_key:
        raise ConfigError("En stdio OBSERVER_API_KEY es obligatorio")
    if transport == "http" and api_key:
        # En http cada request trae su credencial: una key de entorno sería una
        # credencial compartida que cualquiera sin Bearer terminaría usando.
        raise ConfigError("OBSERVER_API_KEY no se admite en modo http")

    disabled = frozenset(t.strip() for t in env.get("MCP_DISABLED_TOOLS", "").split(",") if t.strip())

    def _csv(name: str) -> tuple[str, ...]:
        return tuple(v.strip() for v in env.get(name, "").split(",") if v.strip())

    return Settings(
        observer_url=url,
        transport=transport,
        host_header=env.get("OBSERVER_HOST_HEADER", "").strip() or None,
        verify_tls=_bool(env, "OBSERVER_VERIFY_TLS", True),
        api_key=api_key,
        port=_int(env, "MCP_PORT", 8765),
        max_agents=_int(env, "MCP_MAX_AGENTS", 10),
        rate_per_min=_int(env, "MCP_RATE_PER_MIN", 60),
        max_response_chars=_int(env, "MCP_MAX_RESPONSE_CHARS", 100_000),
        rest_timeout=float(_int(env, "MCP_REST_TIMEOUT", 30)),
        auth_cache_seconds=_int(env, "MCP_AUTH_CACHE_SECONDS", 30),
        disabled_tools=disabled,
        allowed_hosts=("127.0.0.1:*", "localhost:*") + _csv("MCP_ALLOWED_HOSTS"),
        allowed_origins=_csv("MCP_ALLOWED_ORIGINS"),
    )
