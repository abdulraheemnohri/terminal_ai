"""Validation helpers for user-configurable provider endpoints."""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


class SettingsValidationError(ValueError):
    """A settings value is malformed or violates a security boundary."""


def validate_custom_base_url(value: object) -> str:
    """Accept HTTPS endpoints, or plain HTTP only on an exact loopback host."""
    if not isinstance(value, str):
        raise SettingsValidationError("Custom endpoint must be text.")
    url = value.strip()
    if not url:
        return ""
    if len(url) > 500:
        raise SettingsValidationError("Custom endpoint URL is too long.")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port  # Accessing port validates numeric syntax and range.
    except ValueError as exc:
        raise SettingsValidationError("Custom endpoint URL is malformed.") from exc
    if parsed.scheme not in {"https", "http"} or not hostname:
        raise SettingsValidationError("Custom endpoint must use HTTPS, or localhost for a local endpoint.")
    if parsed.username is not None or parsed.password is not None:
        raise SettingsValidationError("Custom endpoint URL must not contain credentials.")
    if parsed.query or parsed.fragment:
        raise SettingsValidationError("Custom endpoint URL must not contain a query or fragment.")
    if parsed.scheme == "https":
        return url
    loopback = hostname.lower() == "localhost"
    if not loopback:
        try:
            loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            loopback = False
    if not loopback:
        raise SettingsValidationError("Plain HTTP is allowed only for an exact localhost or loopback IP address.")
    return url
