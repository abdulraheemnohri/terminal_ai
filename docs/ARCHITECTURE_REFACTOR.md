# Architecture Refactor Plan

## First extraction delivered
- app.py delegates Command Control Center HTTP/WebSocket endpoints to routers/control.py.
- Chat run observability (`GET /api/chat/runs`) is extracted to `routers/chat.py` with an injected metadata provider; the primary chat execution handler remains in `app.py`.
- api_schemas.py defines bounded Pydantic v2 request contracts for policy updates, operation approvals, skill packages, chat, and memory writes.
- Cloud provider construction is extracted to `application/backend_factory.py`; selected-provider ordering, credential skipping, and redacted initialization failures are covered by focused tests.
- Provider model discovery is isolated in `application/provider_models.py`; `POST /api/providers/models` reads model IDs from Gemini, Anthropic, and OpenAI-compatible model-list APIs without sending inference prompts. Provider pagination is bounded to ten pages and 2,000 model entries, with cursor-loop protection. The Settings model field uses API results as suggestions while still allowing manual IDs; saving Settings persists `provider_model` locally.
- Command-control routes remain approval-only: approving a record does not execute it.
- The action stream exposes operational event summaries and status metadata, not private chain-of-thought or raw prompts.
- SQLite stores use WAL, busy timeouts, and append-only hash-chained audit records.
- Self-X supports optional ARQ/Redis offload when TERMINAL_AI_ARQ_ENABLED=1; local worker fallback remains available.

## Next refactor boundaries
Keep terminal_ai.py as a compatibility facade while extracting code in small, testable slices:
1. agent/core.py: orchestration and turn lifecycle.
2. agent/tools.py: tool metadata, permission checks, and dispatch interfaces.
3. agent/memory.py: JSON-memory compatibility plus SQLite-backed stores.
4. agent/planning.py: typed task plans and bounded recovery policy.
5. routers/chat.py, routers/selfx.py, routers/workspace.py, routers/settings.py: route groups with injected services.
6. services/jobs.py: ARQ worker definitions and a bounded in-process fallback.

Move one subsystem at a time and retain compatibility imports until tests prove callers no longer depend on the legacy module. Avoid a big-bang rewrite.

## Security invariants
- Auto-execution remains disabled globally; a UI toggle is not permission to bypass policy.
- Human approval is scoped to the exact queued operation and is not a general-purpose execution token.
- Imported skills are unverified procedure text and never executable code.
- Keep the audit table append-only and verify its hash chain during diagnostics.
- Bind the server to localhost unless authentication, CSRF protection, and network access controls are configured.
