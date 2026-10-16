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

    from api_provider_backend import APIProviderBackend, PROVIDERS

    order = [selected_provider]
    order.extend(
        provider_id
        for provider_id in ["gemini", *PROVIDERS.keys()]
        if provider_id not in order
    )
    backends: list[core.Backend] = []
    for provider_id in order:
        try:
            if provider_id == "gemini":
                key = gemini_key()
                if not key:
                    continue
                backend = core.GeminiBackend(
                    model=(
                        selected_model
                        if provider_id == selected_provider and selected_model
                        else environment.get("TERMINAL_AI_GEMINI_MODEL", "gemini-3.8-flash")
                    ),
                    api_key=key,
                    temperature=float(settings.get("provider_temperature", 0.7)),
                    top_p=float(settings.get("provider_top_p", 0.95)),
                    max_tokens=int(settings.get("provider_max_tokens", 2048)),
                )
            else:
                provider = PROVIDERS.get(provider_id)
                if provider is None:
                    continue
                key = environment.get(provider["env"], "").strip()
                if not key and provider.get("auth") != "none":
                    continue
                backend = APIProviderBackend(
                    provider_id=provider_id,
                    api_key=key,
                    model=selected_model if provider_id == selected_provider else None,
                    base_url=(
                        (settings.get("custom_base_url") or None)
                        if provider.get("endpoint_configurable") == "true" else None
                    ),
                    timeout=int(settings.get("provider_timeout_seconds", 60)),
                    temperature=float(settings.get("provider_temperature", 0.7)),
                    top_p=float(settings.get("provider_top_p", 0.95)),
                    max_tokens=int(settings.get("provider_max_tokens", 2048)),
                )
            backends.append(backend)
        except Exception as exc:
            log.warning(
                "Cloud provider %s could not initialize (%s)",
                provider_id,
                type(exc).__name__,
            )
    return backends
