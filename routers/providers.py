"""Provider discovery, model-listing, and connection-test routes."""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Callable

from litestar import Router, get, post
from litestar.exceptions import HTTPException

from application.settings_validation import SettingsValidationError


def create_provider_router(
    core: Any,
    load_env: Callable[[], None],
    gemini_key: Callable[[], str | None],
    settings_reader: Callable[[], dict[str, Any]],
    validate_base_url: Callable[[object], str],
    validation_error: type[Exception] = SettingsValidationError,
) -> Router:
    """Build provider routes with application dependencies injected explicitly."""

    @get("/api/providers")
    async def providers() -> dict[str, Any]:
        """Discover available provider integrations and configuration state."""
        load_env()
        local_files = [p for p in core.MODELS_DIR.glob("*.litertlm") if p.is_file()]
        from api_provider_backend import PROVIDERS
        cloud_providers = [
            {"id": "gemini", "label": "Google Gemini", "kind": "cloud",
             "configured": gemini_key() is not None, "requires_network": True},
        ]
        cloud_providers.extend(
            {"id": pid, "label": info["label"], "kind": "cloud",
             "configured": bool(os.environ.get(info["env"])), "requires_network": True,
             "protocol": info["protocol"], "default_model": info["default_model"]}
            for pid, info in PROVIDERS.items()
        )
        cloud_providers.extend([
            {"id": "litert-lm", "label": "LiteRT-LM Python API", "kind": "local",
             "configured": bool(local_files), "requires_network": False},
            {"id": "huggingface-hub", "label": "Hugging Face Hub", "kind": "model-source",
             "configured": True, "requires_network": True,
             "token_configured": bool(os.environ.get("HF_TOKEN") or core.HF_TOKEN_FILE.exists())},
        ])
        settings = settings_reader()
        return {"providers": cloud_providers, "active_mode": settings["mode"],
                "active_provider": settings.get("active_provider", "gemini")}

    @post("/api/providers/models", status_code=200)
    async def discover_provider_models(data: dict[str, Any]) -> dict[str, Any]:
        """Fetch available model IDs without running inference."""
        load_env()
        provider_value = data.get("provider_id", "gemini")
        api_key_value = data.get("api_key", "")
        base_url_value = data.get("base_url", "")
        if not isinstance(provider_value, str) or not provider_value.strip() or len(provider_value) > 80:
            raise HTTPException(status_code=400, detail="provider_id must be a non-empty string of at most 80 characters.")
        if not isinstance(api_key_value, str) or len(api_key_value) > 4096:
            raise HTTPException(status_code=400, detail="api_key must be text of at most 4096 characters.")
        if not isinstance(base_url_value, str) or len(base_url_value) > 500:
            raise HTTPException(status_code=400, detail="base_url must be text of at most 500 characters.")
        from application.provider_models import ModelDiscoveryError, fetch_provider_models
        try:
            return await asyncio.to_thread(
                fetch_provider_models, provider_value.strip().lower(),
                api_key=api_key_value, base_url=base_url_value,
            )
        except ModelDiscoveryError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @post("/api/providers/test")
    async def test_provider_connection(data: dict[str, Any]) -> dict[str, Any]:
        """Check a provider using a minimal prompt; never return credentials."""
        load_env()
        provider_value = data.get("provider_id", "gemini")
        model_value = data.get("model", "")
        api_key_value = data.get("api_key", "")
        if not isinstance(provider_value, str) or not provider_value.strip() or len(provider_value) > 80:
            raise HTTPException(status_code=400, detail="provider_id must be a non-empty string of at most 80 characters.")
        if not isinstance(model_value, str) or len(model_value) > 200:
            raise HTTPException(status_code=400, detail="model must be text of at most 200 characters.")
        if not isinstance(api_key_value, str) or len(api_key_value) > 4096:
            raise HTTPException(status_code=400, detail="api_key must be text of at most 4096 characters.")
        provider_id = provider_value.strip().lower()
        model = model_value.strip() or None
        api_key = api_key_value.strip()
        started = time.time()
        backend = None
        try:
            if provider_id == "gemini":
                key = api_key or gemini_key()
                backend = core.GeminiBackend(
                    model=model or os.environ.get("TERMINAL_AI_GEMINI_MODEL", "gemini-3.8-flash"),
                    api_key=key,
                )
            else:
                from api_provider_backend import APIProviderBackend, PROVIDERS
                info = PROVIDERS.get(provider_id)
                if info is None:
                    raise HTTPException(status_code=400, detail="Unknown provider.")
                key = api_key or os.environ.get(info["env"], "")
                endpoint_value = data.get("base_url", "")
                if provider_id == "custom-openai":
                    if not isinstance(endpoint_value, str):
                        raise HTTPException(status_code=400, detail="base_url must be text.")
                    if len(endpoint_value) > 500:
                        raise HTTPException(status_code=400, detail="Custom endpoint URL is too long.")
                    endpoint = endpoint_value.strip() or None
                    if endpoint:
                        try:
                            endpoint = validate_base_url(endpoint)
                        except validation_error as exc:
                            raise HTTPException(status_code=400, detail=str(exc)) from exc
                else:
                    endpoint = None
                backend = APIProviderBackend(
                    provider_id, key, model=model,
                    base_url=endpoint if provider_id == "custom-openai" else None, timeout=30,
                )
            answer = "".join(backend.stream(
                "Reply with OK only.", [core.Msg("user", "Connection test. Reply OK.")], tools=None
            )).strip()
            if not answer:
                raise RuntimeError("Provider returned an empty response.")
            return {"ok": True, "provider_id": provider_id, "model": model,
                    "elapsed_ms": round((time.time() - started) * 1000),
                    "message": "Connection successful."}
        except HTTPException:
            raise
        except Exception as exc:
            # Do not return raw provider exceptions; they may contain endpoint or credential details.
            raise HTTPException(status_code=502, detail=f"Provider connection failed ({type(exc).__name__}).") from exc
        finally:
            if backend is not None:
                try:
                    backend.close()
                except Exception:
                    pass

    return Router(path="", route_handlers=[providers, discover_provider_models, test_provider_connection])
