# Modular API Management and Model Validation UI

The dashboard now links to three standalone, independently styled sections. Each section has its own HTML, CSS, and JavaScript files under `web/pages/`, `web/css/`, and `web/js/` respectively.

## API Management

Open `/static/pages/api-management.html`. Each registered provider receives a separate configuration card with model discovery, connection testing, per-provider generation settings, endpoint configuration where supported, failover priority, credential save/remove, and default-provider selection.

Provider credentials are managed by `POST /api/providers/credentials`. The request must identify a registered `provider_id`; it may contain a new `api_key` or `clear: true`, but not both. Responses contain only configuration metadata and never echo a secret. Keys are written through the existing local environment manager and the active agent backend is invalidated so subsequent chat turns can reinitialize with current credentials.

Profiles are stored in the existing `provider_profiles` setting and validated by `PATCH /api/settings`. Provider model discovery uses `POST /api/providers/models`; connection checks use `POST /api/providers/test`.

## Chat & Model Lab

Open `/static/pages/chat-model-lab.html`. The configuration summary shows the active provider, model profile, credential state, generation parameters, and failover priority. The real-output test uses `POST /api/chat` and shows the actual answer, backend label, elapsed time, persistence status, request ID, and recent metadata-only execution traces.

The user must explicitly confirm that a real test turn may be stored in the active conversation and local archive before running it. Do not represent a provider connectivity smoke test as a full model-output test.

## WhatsApp Agent API

Open `/static/pages/whatsapp-agent.html`. This section exposes status, API-key save/remove, poller enable/disable, connection testing, and manual text messaging through the existing `/api/whatsapp-agent/*` endpoints. The key is write-only in the UI; it is never returned by status endpoints.

This integration targets Meta's WhatsApp Agent Platform, not WhatsApp Web QR pairing or the WhatsApp Business Cloud API. V1 is text-only and restricts outbound sends to the creator identity verified by Meta.

## Validation

CI validates the standalone JavaScript files with Node syntax checks, compiles Python modules, validates repository structure, and runs the pytest suite. Tests verify that provider credentials are not echoed, unknown providers are rejected, and each standalone section has separate assets and valid local links.
