# Project Structure and Modularization Plan

## Current source layout

Terminal AI currently uses a **modular monolith**. This is intentional: one process can host the Litestar UI and API while agent, storage, policy, and self-maintenance features are split into focused modules.

```text
terminal_ai/
├── app.py                    # Litestar composition root; currently large and being decomposed
├── terminal_ai.py             # legacy-compatible core/runtime API
├── application/              # runtime service container and dependency wiring
├── agent/                     # memory, planning, tools, browser and agent primitives
├── routers/                   # Litestar feature routers (chat, agentic, control, knowledge, workspace, health)
├── web/                       # static HTML, CSS and JavaScript dashboard
├── tests/                     # unit, API and regression tests
├── docs/                      # architecture, security, setup and operational guides
├── scripts/                   # install, service, update and maintenance scripts
├── command_control.py         # approvals, policy and append-only audit
├── selfx_engine.py            # diagnostics, checkpoints and bounded Self-X maintenance
├── workspace_tools.py         # constrained workspace operations
├── task_scheduler.py          # persisted scheduled task definitions
├── api_schemas.py              # request validation models
├── requirements.txt            # runtime/test dependencies
└── pyproject.toml              # test and static-analysis configuration
```

The first extraction is now implemented in `application/container.py`: `RuntimeServices` constructs the long-lived memory, workspace, scheduler, and command-control services from explicit filesystem roots. `app.py` keeps compatibility aliases while route modules are migrated incrementally.

## Root-level Python module inventory

The following modules remain at the repository root because they are public import surfaces used by the current app and test suite. Keep them stable during refactors; extract implementations behind compatibility imports rather than moving them in bulk.

| Module | Responsibility |
|---|---|
| `app.py` | Litestar application composition and lifecycle |
| `terminal_ai.py` | Legacy-compatible agent/runtime API |
| `terminal_ai_runtime.py`, `agentic_runtime.py`, `agentic_features.py` | Runtime wiring and agentic feature coordination |
| `command_control.py`, `api_schemas.py` | Approval policy, audit, and API contracts |
| `memory_store.py` | Persistent memory compatibility layer |
| `workspace_tools.py`, `task_scheduler.py` | Constrained workspace actions and scheduled tasks |
| `selfx_engine.py` | Diagnostics, checkpoints, and bounded self-maintenance |
| `litert_api_backend.py`, `api_provider_backend.py` | Local LiteRT and external provider adapters |
| `arq_worker.py`, `maintenance_worker.py` | Background worker entrypoints |

## Operational script organization

Operational implementations are canonical under `scripts/`: installation, update, service management, login/boot autostart, backup/restore, diagnostics, and validation. Root-level `.sh` and `.ps1` files are compatibility wrappers only. This keeps existing documented commands and desktop shortcuts working without maintaining duplicate implementations.

The structure checker verifies that every root-level operational wrapper has a matching script and that the canonical scripts are not themselves forwarding wrappers. New operational tooling belongs in `scripts/`, with cross-platform behavior documented in `scripts/README.md` and covered by syntax/structure checks in CI.

## Runtime boundaries

- **Presentation:** `web/` calls JSON APIs; it must not contain credentials or enforce security on its own.
- **HTTP/API:** `app.py` composes Litestar handlers and `routers/` owns feature endpoints.
- **Agent orchestration:** `agent/` owns schemas, bounded planning, memory, and explicit tool dispatch.
- **Policy and security:** `command_control.py` owns approval lifecycle and audit history. A UI approval is not itself an execution request.
- **Persistence:** SQLite and JSON state live under the configured state directory, not in source folders.
- **Self-X:** `selfx_engine.py` provides bounded local diagnostics, checkpoints, and proposals. It must not silently install packages, modify source code, or escalate privileges.
- **Integrations:** browser/provider adapters are optional, disabled unless explicitly configured, and constrained by allowlists and timeouts.

## Target layout (incremental migration)

Do not move every module in one breaking change. Extract one boundary at a time, preserving public imports until compatibility tests prove the new location works.

```text
terminal_ai/
├── app.py                     # thin application factory and startup lifecycle
├── api/
│   ├── routes/                # route handlers grouped by feature
│   └── schemas/               # request/response contracts
├── application/
│   ├── container.py           # dependency wiring
│   └── services/              # use cases, no HTTP response objects
├── domain/
│   ├── agent/                 # planner, policy, task and skill models
│   └── memory/                # domain-level memory interfaces
├── infrastructure/
│   ├── persistence/           # SQLite/JSON adapters
│   ├── providers/             # model provider adapters
│   ├── browser/               # isolated Playwright adapter
│   └── system/                # OS/platform integration
├── web/                       # independently testable static frontend
└── tests/
    ├── unit/
    ├── integration/
    └── security/
```

The target tree is a roadmap, not a claim that all modules have already been moved. Existing root imports remain supported while extraction is incremental.

## Import and dependency rules

1. Domain/agent logic must not import Litestar or render HTML.
2. Route modules validate requests, call services, and translate results into HTTP responses.
3. Infrastructure adapters implement narrow interfaces; they do not decide policy.
4. UI state is never an authorization boundary.
5. Model output, imported skills, browser content, and persisted settings are untrusted input.
6. Tools declare schemas, timeouts, and approval requirements. No model-generated Python or shell string is evaluated directly.
7. Side effects require an explicit policy decision; approved operations are bound to exact arguments, expire, and cannot be replayed.
8. Persistent user state and secrets must never be committed as source files.

## Quality gates

- `python -m compileall -q app.py terminal_ai.py agent routers`
- `python scripts/check_structure.py`
- `python -m pytest tests/ -q`
- `python -m pip check`
- `ruff check .` (optional during legacy cleanup; new code should pass)

See [ARCHITECTURE.md](ARCHITECTURE.md) for the component and trust-boundary view.
