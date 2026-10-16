from __future__ import annotations

import pytest

from application.settings_validation import SettingsValidationError, validate_custom_base_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("  ", ""),
        ("https://api.example.com/v1", "https://api.example.com/v1"),
        ("http://localhost:1234/v1", "http://localhost:1234/v1"),
        ("http://127.0.0.1:1234/v1", "http://127.0.0.1:1234/v1"),
        ("http://[::1]:1234/v1", "http://[::1]:1234/v1"),
    ],
)
def test_validate_custom_base_url_accepts_safe_endpoints(value, expected):
    assert validate_custom_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://localhost.attacker.example/v1",
        "http://127.0.0.2.attacker.example/v1",
        "http://192.168.1.10:1234/v1",
        "ftp://api.example.com/v1",
        "https://user:password@api.example.com/v1",
        "https://api.example.com/v1?token=secret",
        "https://api.example.com/v1#fragment",
        "https://api.example.com:99999/v1",
        "https:///missing-host",
        "https://" + "a" * 510 + ".example",
        None,
        123,
    ],
)
def test_validate_custom_base_url_rejects_unsafe_or_malformed_endpoints(value):
    with pytest.raises(SettingsValidationError):
        validate_custom_base_url(value)
