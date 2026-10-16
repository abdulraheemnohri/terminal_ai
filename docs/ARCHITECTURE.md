# Terminal AI architecture and capability map

## Runtime
- app.py: Litestar app lifecycle, provider orchestration, sessions, settings, and still-unextracted chat/Self-X/scheduler routes.
- routers/control.py: Command Control Center, audit, skill exchange, and WebSocket event summaries.
- routers/knowledge.py and routers/workspace.py: modular local-knowledge and workspace APIs with typed Pydantic request contracts.
- agent/planning.py and agent/tools.py: task planning, persona/recovery guidance, structured tool-call validation, and strict JSON parsing.
- agent/memory.py: typed SQLite knowledge and conversation storage; memory_store.py remains a compatibility import shim.
- terminal_ai.py: core agent, backend abstractions, conversation/session management, skill library, tools, memory and provider integration.
- litert_api_backend.py: local LiteRT-LM Python API adapter. Local inference does not require Gemini or network access when a local model is selected and available.
- application/provider_fallback.py: ordered cloud-first provider chain; it tries the selected provider, then other configured cloud providers, and only then local inference in Auto/Hybrid modes. It refuses to switch after partial output to prevent duplicate answers.
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

The WebSocket at `/api/control/events` polls durable audit entries and streams only action summaries. It does not reveal hidden chain-of-thought or copy chat prompts into the audit database. Human approval endpoints only update queue state and never execute an operation. The web UI includes a mandatory approval gate, a reviewer-note field recorded with decisions, and a confirmation before applying configuration. \`tool_approval_required\` is a hard invariant: legacy state is normalized to \`true\`, and API attempts to disable it are rejected. Approval does not itself dispatch an operation; any future dispatch must be a separate, authenticated action tied to the exact approved arguments.

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



## Current task lifecycle data flow

```text
UI / client
   │
   ▼
Litestar agentic routes
   ├── AdaptivePlanner + task-intelligence heuristics
   ├── TaskLifecycleStore (bounded SQLite ledger)
   ├── CommandControl (authoritative operation status + audit)
   └── LearningStore (verified, human-reviewed outcomes)
```

The task ledger is an orchestration record, not a tool runner. It stores a bounded goal and plan, then may link to one existing Command Control operation. A detail read synchronizes task status with the linked operation. Verification is accepted only for an operation recorded as executed; learning review is accepted only after passing verification. Failed verification cannot be reset by a later status sync.

| API | Responsibility | Does not do |
|---|---|---|
| `POST /api/agentic/tasks` | Store a bounded plan | Execute plan steps |
| `GET /api/agentic/tasks` | List/filter task records | Dispatch tools |
| `GET /api/agentic/tasks/{task_id}` | Read and sync linked operation status | Approve or execute |
| `POST /api/agentic/tasks/{task_id}/operation` | Link one existing operation | Create or approve an operation |
| `POST /api/agentic/tasks/{task_id}/verify` | Store operator verification evidence | Prove evidence authenticity |
| `POST /api/agentic/tasks/{task_id}/review` | Add a reviewed outcome to learning | Change permissions or train model weights |

## Approval-aware task lifecycle

- `application/task_lifecycle.py` persists bounded task records in `task_lifecycle.sqlite3`, including the goal, plan steps, task category, selected algorithm, risk, linked Command Control operation, execution status, verification evidence, and reviewed outcome.
- `POST /api/agentic/tasks` creates a plan record only. It does not dispatch tools. A task may link exactly one existing operation from Command Control Center; linking does not approve or execute it.
- The task status is synchronized from the authoritative operation record: pending, approved, executing, executed, failed, rejected, or expired. This ledger does not provide a new tool-execution endpoint.
- Independent verification is rejected until the linked operation is recorded as executed. A passing verification stores the operator's evidence summary and identity; a failed verification remains failed and cannot be sent to learning review.
- Only a passing verified task can be reviewed. The review records an explicit outcome and 1–5 rating in the bounded verified-outcome learning store, and adds an audit event. Learning changes recommendations only; it does not grant permissions.
- The task ledger is capped at 2,000 recent records. The operator must still ensure that the verifier is genuinely independent; text evidence entered by a user is an attestation, not cryptographic proof.
- The task lifecycle and Command Control APIs require authentication and authorization before deployment on an untrusted network. The UI does not bypass the existing human approval boundary.

## Self-X adaptive planning and evidence dashboard

- The Self-X page exposes the agentic status, aggregate verified-outcome learning summary, pending approval count, and bounded world-model facts in one operational console.
- Plan preview calls `POST /api/agentic/plan`; it returns a strategy and steps but explicitly reports `execution_started=false`. The UI does not dispatch plan steps or start browser/tool actions.
- World-model observations are stored as bounded evidence records with subject, predicate, value, source, confidence, and optional TTL. Values are data only; they are not instructions. Expired facts retain their original absolute expiry across restarts.
- The console reads pending items from the Command Control Center. Reviewing or approving a queue item is separate from executing it. Global auto-execution remains disabled.
- Learning cards display aggregate task-family/algorithm sample counts, success scores, and reviewer ratings. The values are coarse heuristic signals, not calibrated probabilities or proof of correctness. Only explicitly verified outcomes are eligible for adaptation.
- This UI improves observability and operator review; it does not make the agent sentient, self-modify source code, train model weights, or autonomously grant permissions.

## Human-reviewed skill evolution

- \`application/skill_evolution.py\` stores bounded plain-text skill proposals in \`skill_proposals.sqlite3\`; it stores no task prompts or credentials by design.
- The UI in **Self-improvement → Skill evolution review queue** supports manual proposal submission, draft generation from aggregate reviewed outcomes, static validation, explicit approval, rejection, and promotion to a reviewed-catalog state.
- The reviewed-learning generator requires at least three outcomes per strategy group. It can draft a repeatable checklist from strong positive results or a recovery checklist from recurring low-success/low-rating results; recurring failures are prioritized for review. It stores only aggregate counts/scores in the generated proposal, not raw task prompts or credentials.
- The lifecycle is \`proposed → validated → approved → promoted\`; rejection is available before promotion. Invalid state transitions are rejected. Static checks validate structure and reject a small set of executable-code patterns, but are not a security sandbox and do not prove a procedure is safe.
- Promotion only changes proposal state; it does not install tools, change permissions, execute a skill, or rewrite source code. Skills remain non-executable procedure text.
- The proposal store is capped at 1,000 records; each proposal has bounded fields and at most 20 steps.
- The API routes under \`/api/agentic/skills/proposals\` must be placed behind authenticated, authorized access before exposing the application to an untrusted network. Human approval is a UI workflow, not a substitute for server-side identity and access control.


## Failure recovery boundary

Recovery proposals are stored separately from task records. They require a linked operation with a recorded terminal `failed` or `expired` status, allow at most three proposals per task, and retain at most 5,000 proposals. Timeout/network/rate-limit categories can be approved for replanning after review; dependency/validation issues require correction and a fresh operation; permission, destructive, and unknown failures are not retry-approvable. This is proposal metadata only: the prior operation is never re-opened, and a new operation must go through Command Control's exact-argument approval gate. Operator-supplied categories are not an automated root-cause diagnosis.


Approved recovery continuation is a one-shot state transition: `approved_for_replanning → queueing → operation_queued`. The API queues a separate pending Command Control operation with the supplied exact tool and arguments, records its ID on the proposal, and never dispatches it. A failed queue request releases the reservation; duplicate queue attempts are rejected. The new operation must be reviewed and approved independently.


After the fresh operation is separately approved and executed through the existing dispatch workflow, the recovery verification route accepts one bounded operator attestation and only when Command Control reports `executed`. The proposal records `verified` or `verification_failed`; verification never dispatches tools and never automatically retries a failed recovery.


After a passing recovery verification, `POST .../review-outcome` requires a separate human outcome review before adding the result to the learning ledger. Learning records use a stable source reference for idempotency, preventing duplicate samples if a client retries after a lost response. Only the explicitly reviewed result is learned; a verified state alone does not automatically change recommendations.
