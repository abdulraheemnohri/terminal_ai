"""Provider backend construction with deterministic, testable failover ordering."""
from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from typing import Any

import terminal_ai as core


def build_cloud_backends(
    settings: Mapping[str, Any],
    *,
    gemini_key: Callable[[], str | None],
    environ: Mapping[str, str] | None = None,
    logger: logging.Logger | None = None,
) -> list[core.Backend]:
    """Build configured cloud providers in deterministic preference order.

    The selected provider is tried first, followed by Gemini and the remaining
    registered providers. Missing credentials are skipped. Initialization
    failures are logged by type only so secrets and request details are not
    copied into diagnostics.
    """
    mode = settings.get("mode", "auto")
    if mode not in {"auto", "cloud", "hybrid"}:
        return []

    environment = os.environ if environ is None else environ
    log = logger or logging.getLogger("terminal_ai.provider_factory")
    selected_provider = str(settings.get("active_provider", "gemini"))
    selected_model = str(settings.get("provider_model", "")).strip() or None
    profiles = settings.get("provider_profiles", {})
    if not isinstance(profiles, Mapping):
        profiles = {}

    from api_provider_backend import APIProviderBackend, PROVIDERS

    order = [selected_provider]
    fallback_ids = [pid for pid in ["gemini", *PROVIDERS.keys()] if pid != selected_provider]
    fallback_ids.sort(key=lambda pid: (
        int(profiles.get(pid, {}).get("failover_priority", 100))
        if isinstance(profiles.get(pid, {}), Mapping) else 100,
        ["gemini", *PROVIDERS.keys()].index(pid),
    ))
    order.extend(fallback_ids)
    backends: list[core.Backend] = []
    for provider_id in order:
        try:
            raw_profile = profiles.get(provider_id, {})
            profile = raw_profile if isinstance(raw_profile, Mapping) else {}
            is_selected = provider_id == selected_provider
            model = str(profile.get("model", selected_model if is_selected else "")).strip() or None
            temperature = float(profile.get("temperature", settings.get("provider_temperature", 0.7) if is_selected else 0.7))
            top_p = float(profile.get("top_p", settings.get("provider_top_p", 0.95) if is_selected else 0.95))
            max_tokens = int(profile.get("max_tokens", settings.get("provider_max_tokens", 2048) if is_selected else 2048))
            timeout = int(profile.get("timeout_seconds", settings.get("provider_timeout_seconds", 60) if is_selected else 60))
            if provider_id == "gemini":
                key = gemini_key()
                if not key:
                    continue
                backend = core.GeminiBackend(
                    model=model or environment.get("TERMINAL_AI_GEMINI_MODEL", "gemini-3.8-flash"),
                    api_key=key,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                )
            else:
                provider = PROVIDERS.get(provider_id)
                if provider is None:
                    continue
                key = environment.get(provider["env"], "").strip()
                if not key and provider.get("auth") != "none":
                    continue
                endpoint = profile.get("base_url") or (settings.get("custom_base_url") if is_selected else None)
                backend = APIProviderBackend(
                    provider_id=provider_id,
                    api_key=key,
                    model=model,
                    base_url=(endpoint or None) if (provider.get("endpoint_configurable") == "true" or provider_id == "custom-openai") else None,
                    timeout=timeout,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                )
            backends.append(backend)
        except Exception as exc:
            log.warning(
                "Cloud provider %s could not initialize (%s)",
                provider_id,
                type(exc).__name__,
            )
    return backends
