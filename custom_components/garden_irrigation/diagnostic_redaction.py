"""Pure diagnostic redaction helpers for Garden Irrigation."""

from __future__ import annotations

import re
from typing import Any

REDACTED_VALUE = "<redacted>"

_SENSITIVE_KEY_TOKENS = frozenset(
    {
        "apikey",
        "auth",
        "credential",
        "credentials",
        "key",
        "password",
        "passwd",
        "private",
        "secret",
        "signing",
        "signature",
        "token",
    }
)
_KEY_TOKEN_RE = re.compile(r"[a-z0-9]+")


def redact_diagnostics_payload(value: Any) -> Any:
    """Return a diagnostics-safe copy of a JSON-like value."""
    if isinstance(value, dict):
        return {
            key: REDACTED_VALUE
            if isinstance(key, str) and _is_sensitive_key(key)
            else redact_diagnostics_payload(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_diagnostics_payload(child) for child in value]
    if isinstance(value, tuple):
        return tuple(redact_diagnostics_payload(child) for child in value)
    return value


def _is_sensitive_key(key: str) -> bool:
    tokens = set(_KEY_TOKEN_RE.findall(key.lower()))
    return bool(tokens & _SENSITIVE_KEY_TOKENS)
