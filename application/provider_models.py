"""Provider model discovery for common API protocols.

Only fetches model metadata; it never sends prompts or performs inference.
Pagination is bounded to avoid unbounded network work against provider APIs.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from application.settings_validation import SettingsValidationError, validate_custom_base_url


class ModelDiscoveryError(ValueError):
    """A provider model-list request failed safely."""


_MAX_RESPONSE_BYTES = 2_000_000
_MAX_PAGES = 10
_MAX_MODELS = 2_000


def _get_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={**headers, "Accept": "application/json"}, method="GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=max(2, min(float(timeout), 20))) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ModelDiscoveryError("Provider model-list response exceeded 2 MB.")
        payload = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise ModelDiscoveryError(
                f"Provider rejected the API key or model-list permission (HTTP {exc.code})."
            ) from exc
        raise ModelDiscoveryError(f"Provider model-list request failed (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ModelDiscoveryError("Could not reach the provider model-list endpoint.") from exc
    except (TimeoutError, OSError):
        raise ModelDiscoveryError("Provider model-list request timed out or failed.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ModelDiscoveryError("Provider returned invalid JSON for its model list.") from None
    if not isinstance(payload, dict):
        raise ModelDiscoveryError("Provider returned an unsupported model-list format.")
    return payload


def _with_query(url: str, params: dict[str, str]) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.extend(params.items())
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment)
    )


def _collect_items(url: str, headers: dict[str, str], protocol: str, timeout: float) -> list[dict[str, Any]]:
    """Fetch a bounded number of pages from Gemini, Anthropic, or OpenAI APIs."""
    items: list[dict[str, Any]] = []
    cursor = ""
    seen_cursors: set[str] = set()
    for _ in range(_MAX_PAGES):
        page_url = url
        if cursor:
            if protocol == "gemini":
                page_url = _with_query(url, {"pageToken": cursor})
            elif protocol == "anthropic":
                page_url = _with_query(url, {"after_id": cursor, "limit": "1000"})
            else:
                page_url = _with_query(url, {"after": cursor})
        elif protocol == "anthropic":
            page_url = _with_query(url, {"limit": "1000"})
        payload = _get_json(page_url, headers, timeout)
        page_items = payload.get("models", payload.get("data", []))
        if not isinstance(page_items, list):
            raise ModelDiscoveryError("Provider returned an unsupported model-list format.")
        items.extend(item for item in page_items if isinstance(item, dict))
        if len(items) >= _MAX_MODELS:
            return items[:_MAX_MODELS]
        next_cursor = ""
        if protocol == "gemini":
            next_cursor = payload.get("nextPageToken", "") or ""
        elif protocol == "anthropic":
            if payload.get("has_more"):
                next_cursor = payload.get("last_id", "") or ""
        elif payload.get("has_more"):
            # OpenAI-compatible list endpoints paginate by the last returned ID.
            next_cursor = str(page_items[-1].get("id", "")) if page_items and isinstance(page_items[-1], dict) else ""
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    return items


def fetch_provider_models(
    provider_id: str,
    *,
    api_key: str = "",
    base_url: str = "",
    environ: dict[str, str] | None = None,
    timeout: float = 15,
) -> dict[str, Any]:
    """Fetch model IDs from Gemini, Anthropic, or OpenAI-compatible APIs."""
    from api_provider_backend import PROVIDERS

    environment = os.environ if environ is None else environ
    if not isinstance(provider_id, str):
        raise ModelDiscoveryError("Unknown provider.")
    provider_id = provider_id.strip().lower()
    if provider_id == "gemini":
        key = api_key.strip() or environment.get("GEMINI_API_KEY", "").strip() or environment.get("GOOGLE_API_KEY", "").strip()
        if not key:
            raise ModelDiscoveryError("Add a Gemini API key in Settings first.")
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        headers = {"x-goog-api-key": key}
        protocol = "gemini"
        default_model = environment.get("TERMINAL_AI_GEMINI_MODEL", "gemini-3.8-flash")
    else:
        info = PROVIDERS.get(provider_id)
        if not info:
            raise ModelDiscoveryError("Unknown provider.")
        key = api_key.strip() or environment.get(info["env"], "").strip()
        if not key:
            raise ModelDiscoveryError(f"Add an API key for {info['label']} in Settings first.")
        configured_url = base_url.strip() if provider_id == "custom-openai" else info["base_url"]
        if provider_id == "custom-openai":
            try:
                configured_url = validate_custom_base_url(configured_url)
            except SettingsValidationError as exc:
                raise ModelDiscoveryError(str(exc)) from exc
        if not configured_url:
            raise ModelDiscoveryError("Enter the custom API base URL first.")
        url = configured_url.rstrip("/") + "/models"
        headers = (
            {"x-api-key": key, "anthropic-version": "2023-06-01"}
            if info["protocol"] == "anthropic"
            else {"Authorization": f"Bearer {key}"}
        )
        protocol = info["protocol"]
        default_model = environment.get(info["model_env"], info["default_model"])

    items = _collect_items(url, headers, protocol, timeout)
    models: dict[str, str] = {}
    for item in items:
        raw_id = item.get("id") or item.get("name")
        if not isinstance(raw_id, str):
            continue
        model_id = raw_id.removeprefix("models/").strip()
        if not model_id or len(model_id) > 200 or any(ord(c) < 32 for c in model_id):
            continue
        if protocol == "gemini":
            methods = item.get("supportedGenerationMethods", [])
            if isinstance(methods, list) and "generateContent" not in methods:
                continue
        label = item.get("display_name") or item.get("displayName") or model_id
        models[model_id] = str(label)[:200]
    result = [
        {"id": model_id, "label": label}
        for model_id, label in sorted(models.items(), key=lambda pair: pair[0].casefold())
    ]
    if not result:
        raise ModelDiscoveryError("No usable model IDs were returned. Check provider access and API endpoint.")
    preferred = default_model if any(item["id"] == default_model for item in result) else result[0]["id"]
    return {"provider_id": provider_id, "models": result, "count": len(result), "default_model": preferred}
