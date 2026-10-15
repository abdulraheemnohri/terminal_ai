# Agentic Runtime and Command Control Center

The framework-neutral primitives in terminal_ai_runtime.py provide guarded building blocks. They are not a claim that every existing dashboard route has already been wired to them.

## Dynamic planning and world model

AdaptivePlanner chooses a deterministic strategy based on task complexity, risk, and whether external side effects are involved: direct-and-verify, research-then-act, decompose-and-verify, or plan-review-execute. Store a concise strategy/rationale, not private chain-of-thought.

WorldModel stores explicit facts with source, confidence, observation time, and optional expiry. Facts are evidence with uncertainty, not a complete simulation of reality or proof of consciousness. Contradictory observations should be preserved in a future history layer instead of silently overwriting important facts.

## Tools and browser access

Register named tools with typed argument schemas and risk labels. Separate read-only browsing (search/read pages) from state-changing actions (submitting forms, downloading files, clicking destructive controls, writing files). All operations must pass through policy and approval checks. Unknown tools are denied. This runtime does not itself execute shell commands or browser actions.

## Approval and audit

- Global auto-execution defaults off.
- Per-tool auto-run must be explicitly enabled and limited to reviewed, low-risk tools.
- High/critical-risk actions always require a fresh human decision.
- Denylist wins over allowlist; approval requests expire.
- Record actor, time, tool, sanitized arguments, decision, result and verification in the audit ledger.
- Hash chaining detects changes to records but is not a digital signature; protect file permissions and back up the ledger.

## Skills marketplace

Import/export declarative JSON/YAML steps only. Imported skills are untrusted until reviewed. A skill is a procedure, not executable code. Each tool request from a skill re-enters the same policy gate. YAML support uses safe_load/safe_dump and requires PyYAML.

## Live activity

Publish short summaries for plan selected, approval requested, tool start/progress/result, verification and errors. Adapt ActionEventBus to a Litestar WebSocket endpoint. Authenticate before subscribing and redact secrets, cookies, private page content, and raw model scratchpads. Do not stream private chain-of-thought.

## SQLite and background work

Use init_sqlite for WAL mode, busy_timeout, foreign keys and bounded waits. WAL improves reader/writer concurrency but still allows one writer at a time. Keep transactions short and use separate connections per worker/task where practical. Move scheduled maintenance into a separate worker process (ARQ/Redis is one option) only after adding lifecycle, retry, idempotency and shutdown handling.

## Modular refactoring

Extract app.py into routers/chat.py, routers/selfx.py, routers/workspace.py, routers/settings.py and routers/control_center.py. Extract agent logic into agent/core.py, agent/tools.py, agent/memory.py, agent/planning.py, agent/world_model.py, agent/approvals.py and agent/audit.py. Use Pydantic v2 request/response models at API boundaries and strict validation for tool names, arguments, and settings. Refactor incrementally and retain compatibility tests.

## Safe self-improvement

Collect opt-in task outcomes, tool reliability, evaluation results and user feedback. Let the agent propose code changes and run tests in an isolated workspace. Require explicit review before source changes, dependency installation, deployment, privilege changes or updates to safety policies. “Self-awareness” here means a transparent operational status/reflection model, not sentience.

## Command Control Center UI

1. Overview: global auto-execution switch (off by default), active jobs and pending approvals.
2. Tools: per-tool enabled state, risk level, read-only/state-changing classification and auto-run eligibility.
3. Policies: allowlist and blocklist editor; deny wins.
4. Approval queue: action summary, redacted arguments, risk, expiry, approve/reject controls.
5. Live activity: WebSocket stream with reconnect, filters and bounded history.
6. Skills: import, inspect, validate, edit, export, trust state and version history.
7. World model: evidence, confidence, source, freshness and expiry.
8. Audit: chronological actions and chain verification status.
9. System: service status, update checks, logs and administrator-gated restart.

Keep the UI on localhost unless authentication, TLS, CSRF protection and network access controls are configured.
