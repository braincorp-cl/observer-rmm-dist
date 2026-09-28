"""Salvaguardas comunes a todas las tools: redacción, truncado, fan-out y rate limit."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

# Claves que nunca salen hacia el LLM, se comparan en minúsculas y por subcadena
# (p. ej. "bitlocker_recovery_key", "mesh_password").
SENSITIVE_KEY_PARTS = (
    "recovery_key",
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "keystore",
    "private_key",
    "totp",
)
REDACTED = "[redacted]"


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (REDACTED if _is_sensitive(k) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def _is_sensitive(key: Any) -> bool:
    k = str(key).lower()
    return any(part in k for part in SENSITIVE_KEY_PARTS)


def pick(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Lista blanca de campos: lo que no está listado no llega al LLM."""
    return {f: item.get(f) for f in fields if f in item}


def truncate_list(items: list[Any], max_chars: int) -> dict[str, Any]:
    """Devuelve la mayor cantidad de elementos que cabe en max_chars (JSON)."""
    total = len(items)
    out: list[Any] = []
    size = 2
    for item in items:
        chunk = len(json.dumps(item, default=str, ensure_ascii=False)) + 1
        if size + chunk > max_chars:
            break
        out.append(item)
        size += chunk
    result: dict[str, Any] = {"items": out, "returned": len(out), "total": total}
    if len(out) < total:
        result["truncated"] = True
    return result


class FanOutError(ValueError):
    pass


def check_fan_out(agent_ids: list[str], max_agents: int) -> list[str]:
    unique = list(dict.fromkeys(a.strip() for a in agent_ids if a and a.strip()))
    if not unique:
        raise FanOutError("agent_ids está vacío")
    if len(unique) > max_agents:
        raise FanOutError(f"too many agents: {len(unique)} requested, limit is {max_agents} per call")
    return unique


class RateLimiter:
    """Token bucket en memoria por credencial (hash). Aproximado por worker."""

    def __init__(self, per_minute: int, clock=time.monotonic):
        self.capacity = float(per_minute)
        self.refill_per_sec = per_minute / 60.0
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> float:
        """0.0 si se permite; si no, segundos a esperar."""
        now = self._clock()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return 0.0
            self._buckets[key] = (tokens, now)
            return (1.0 - tokens) / self.refill_per_sec
