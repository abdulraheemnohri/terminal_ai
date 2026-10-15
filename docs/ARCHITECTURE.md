# Terminal AI architecture and capability map

## Runtime
- app.py: Litestar HTTP routes, web UI, provider orchestration, session management, settings validation, Self-X jobs, chat execution traces, memory/workspace/scheduler APIs.
- terminal_ai.py: core agent, backend abstractions, conversation/session management, skill library, tools, memory and provider integration.
- litert_api_backend.py: local LiteRT-LM Python API adapter. Local inference does not require Gemini or network access when a local model is selected and available.
- selfx_engine.py: local diagnostics, evaluation, research notes, recovery checkpoints and bounded maintenance.
- memory_store.py: local SQLite knowledge and conversation archive.
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

## Offline guarantees and boundaries
- SQLite knowledge and lexical search are local and do not call a model or web service.
- A chat turn uses the currently configured backend. Cloud backends require network access; LiteRT-LM requires a compatible local model and installed runtime.
- Conversation archiving can be disabled independently from the general knowledge store.
- Search in this version is lexical, not embedding/vector semantic retrieval. No FAISS or Chroma service is required.
- The scheduler runs only while the web application process is running. It does not install an OS cron entry or run when the process is stopped.
- Workspace commands run as the same OS user as the app. Approval prompts are not equivalent to OS-level isolation. Bind to localhost and do not expose the dashboard to untrusted networks without authentication and additional security controls.

## Verification checklist
1. Install dependencies and run python -m compileall -q app.py terminal_ai.py selfx_engine.py memory_store.py workspace_tools.py task_scheduler.py.
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

The WebSocket at `/ws/events` polls durable audit entries and streams only action summaries. It does not reveal hidden chain-of-thought or copy chat prompts into the audit database. Human approval endpoints only update queue state and never execute an operation.

ARQ is optional. When `TERMINAL_AI_ARQ_ENABLED=1`, manual Self-X maintenance and checkpoint requests are submitted to Redis through ARQ. Run `arq maintenance_worker.WorkerSettings` separately. Without this flag, existing local processing remains available. The interval scheduler remains a lightweight poller in the application process, but dispatches diagnostics, memory backup, and temporary-file cleanup to ARQ when queue mode is enabled. Without ARQ, those bounded jobs run locally.
