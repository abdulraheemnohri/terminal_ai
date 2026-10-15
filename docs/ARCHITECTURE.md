# Terminal AI architecture and capability map

## Runtime
- app.py: Litestar app lifecycle, provider orchestration, sessions, settings, and still-unextracted chat/Self-X/scheduler routes.
- routers/control.py: Command Control Center, audit, skill exchange, and WebSocket event summaries.
- routers/knowledge.py and routers/workspace.py: modular local-knowledge and workspace APIs with typed Pydantic request contracts.
- agent/planning.py and agent/tools.py: task planning, persona/recovery guidance, structured tool-call validation, and strict JSON parsing.
- agent/memory.py: typed SQLite knowledge and conversation storage; memory_store.py remains a compatibility import shim.
- terminal_ai.py: core agent, backend abstractions, conversation/session management, skill library, tools, memory and provider integration.
- litert_api_backend.py: local LiteRT-LM Python API adapter. Local inference does not require Gemini or network access when a local model is selected and available.
- selfx_engine.py: local diagnostics, evaluation, research notes, recovery checkpoints and bounded maintenance.
- memory_store.py: compatibility shim re-exporting `agent.memory.MemoryStore` for existing imports.
- workspace_tools.py: workspace-confined file operations and approval-gated subprocess execution.
- task_scheduler.py: persistent allowlisted interval jobs.
- web/index.html, web/app.js, web/app.css: browser dashboard and client interactions.

## Data locations
- Existing core state and session files: core.STATE_DIR.
- Long-term knowledge and chat archive: long_term_memory.sqlite3.
- Scheduled jobs: scheduled_tasks.sqlite3.
- Memory backup jobs write snapshots into core.STATE_DIR/backups/.
- Downloaded LiteRT-LM models are managed under core.MODELS_DIR.

## Main API surfaces
| Area | Routes | Responsibility |
|---|---|---|
| Chat | POST /api/chat, GET /api/chat/runs | Execute a serialized turn and inspect metadata-only traces |
| Sessions | GET /api/sessions, POST /api/sessions/new, POST /api/sessions/select, POST /api/sessions/delete | Select, create, persist and delete conversations |
| Knowledge | GET/POST /api/knowledge, POST /api/knowledge/search | Save and search local knowledge and archived turns |
| Workspace | GET /api/workspace, POST /api/workspace/read, POST /api/workspace/write, POST /api/workspace/execute | Inspect workspace and explicitly approve writes/commands |
| Scheduler | GET/POST /api/scheduled-tasks, PATCH /api/scheduled-tasks/{id} | Create, pause, resume and delete built-in maintenance tasks |
| Self-X | GET /api/selfx/status, POST /api/selfx/maintenance/run | Diagnostics, evaluation, checkpointing and guarded maintenance |
| Settings | GET/PATCH /api/settings, POST /api/ai/settings/propose | Validated settings, reviewed AI proposals, explicit application |
| Health | GET /healthz, GET /readyz | Liveness and readiness checks for process supervisors |

## Offline guarantees and boundaries
- SQLite knowledge and lexical search are local and do not call a model or web service.
- A chat turn uses the currently configured backend. Cloud backends require network access; LiteRT-LM requires a compatible local model and installed runtime.
- Conversation archiving can be disabled independently from the general knowledge store.
- Search in this version is lexical, not embedding/vector semantic retrieval. No FAISS or Chroma service is required.
- The scheduler runs only while the web application process is running. It does not install an OS cron entry or run when the process is stopped.
- Workspace commands run as the same OS user as the app. Approval prompts are not equivalent to OS-level isolation. Bind to localhost and do not expose the dashboard to untrusted networks without authentication and additional security controls.

## Verification checklist
1. Install dependencies and run python -m compileall -q app.py terminal_ai.py agent agentic_features.py api_schemas.py routers selfx_engine.py memory_store.py workspace_tools.py task_scheduler.py.
2. Run pytest -q.
3. Verify GET /api/knowledge works without provider credentials.
4. Save and search a knowledge item, then restart the app and verify persistence.
5. Confirm path traversal is rejected and writes/commands fail without explicit approval.
6. Create a diagnostics job with a five-minute interval, pause it, then delete it.
7. Disconnect the network and verify local knowledge operations still work. For offline chat, explicitly select a compatible local LiteRT-LM model before disconnecting.


## Agentic runtime and tool-call policy

`agentic_features.py` provides small, dependency-free helpers for complex-task planning instructions, persona guidance, structured tool-call validation, and bounded retry prompts. It does not persist private scratchpads or expose hidden chain-of-thought.

The core agent parses tagged JSON tool calls and validates the decoded structure against the declared tool schema before dispatch. Nested JSON objects/arrays are supported. Malformed, unknown, disallowed, or type-invalid calls are rejected instead of being executed.

The browser agent enables multi-turn tool use only for a strict allowlist: current time, system information, local memory/knowledge lookup, active goals, journal reading, and the final-answer tool. Shell commands, filesystem path tools, network fetches, file writes/deletes, environment mutation, and dynamic tool forging are excluded from browser tool calling. Workspace Tools remains a separate interface with its own approval flow.

Settings keys:
- `agentic_planning_enabled` (boolean, default true)
- `agentic_recovery_enabled` (boolean, default true; maximum two retries per failed turn)
- `agentic_persona` (`helpful`, `technical`, `coach`, `concise`, or `creative`)

Error logs record exception categories rather than exception messages in retry instructions, reducing the chance of accidentally copying credentials into prompts. Backend-specific retries may also apply; the agent-level retry limit is independently bounded.


## Command policy and action audit

The Command Control Center stores policy, pending review decisions, skill packages, and an append-only hash chain in `command_control.sqlite3`. SQLite connections use WAL mode and bounded busy timeouts. A valid hash chain detects accidental or unauthorized edits but is not a cryptographic signature against an administrator who can rewrite the database and recompute every hash; back up/export audit records to trusted external storage for stronger assurance.

The WebSocket at `/api/control/events` polls durable audit entries and streams only action summaries. It does not reveal hidden chain-of-thought or copy chat prompts into the audit database. Human approval endpoints only update queue state and never execute an operation.

ARQ is optional. When `TERMINAL_AI_ARQ_ENABLED=1`, manual Self-X maintenance and checkpoint requests are submitted to Redis through ARQ. Run `arq maintenance_worker.WorkerSettings` separately. Without this flag, existing local processing remains available. The interval scheduler remains a lightweight poller in the application process, but dispatches diagnostics, memory backup, and temporary-file cleanup to ARQ when queue mode is enabled. Without ARQ, those bounded jobs run locally.


## Startup and update lifecycle

- Linux: `scripts/install-service.sh` installs a user systemd service and enables restart-on-failure. Boot-before-login requires optional systemd lingering.
- macOS: `scripts/install-service.sh` installs a launchd LaunchAgent for user login and restart-on-exit.
- Windows: `scripts/install-service.ps1` registers a Task Scheduler task at user logon with bounded restart attempts.
- Termux: copy `scripts/termux-boot-start.sh` into `~/.termux/boot/terminal-ai` after installing Termux:Boot. Android background restrictions may still interrupt the process.
- `scripts/update.sh` is a guarded, explicit Linux/macOS updater. It requires a clean Git worktree and fast-forward-only update, creates a source bundle, installs dependencies, compiles modules, runs tests, and restarts a detected service. It is not scheduled to apply unattended updates.
- These helpers update the Terminal AI project only; they do not install operating-system updates. All startup helpers bind to localhost by default. The health probes `/healthz` and `/readyz` support process supervisors and readiness checks without exposing credentials.

## Refactoring status and target module boundaries

Some responsibilities are already separated into `routers/control.py`, `api_schemas.py`, `agentic_features.py`, `command_control.py`, `memory_store.py`, `selfx_engine.py`, `workspace_tools.py`, `task_scheduler.py`, and the optional `maintenance_worker.py`. However, `app.py` still owns many HTTP handlers and lifecycle functions, and `terminal_ai.py` remains the legacy core module. The target structure for the next refactor is:

- `routers/chat.py`, `routers/selfx.py`, `routers/workspace.py`, `routers/settings.py`: route factories receive typed services/dependencies rather than importing globals from `app.py`.
- `agent/core.py`: orchestration and run lifecycle; `agent/tools.py`: tool registry and validation; `agent/memory.py`: memory interfaces/adapters; `agent/planning.py`: planning and bounded recovery helpers.
- Pydantic v2 models in `api_schemas.py` (or a dedicated `schemas/` package) remain the boundary for request/response validation.
- Preserve compatibility with existing state files and API paths while moving one route family at a time; run the complete test suite after each extraction.

This section documents the remaining refactor work accurately; the large legacy modules have not yet been fully decomposed.


## Verified-outcome learning loop

- `application/learning.py` stores only coarse task family, selected algorithm, outcome, 1–5 rating, explicit verification flag, and timestamp in `learning.sqlite3`; it does not store task prompts or credentials.
- `GET /api/agentic/learning/summary` returns aggregated reviewed outcomes. `POST /api/agentic/learning/outcome` records a result only when `verified=true` and all fields match the supported enumerations.
- The store retains at most 5,000 newest outcomes. Strategy adaptation requires at least three reviewed examples; a strategy with no baseline must have a high repeated outcome score before it can replace the default.
- Learning changes recommendations only. It never grants tool permissions, skips user approval, executes a task, or modifies safety policy. Treat the verification flag as a review assertion from a trusted UI/operator; production deployments should authenticate and authorize these endpoints.
