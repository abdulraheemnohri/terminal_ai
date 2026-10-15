# Changelog

## Unreleased — fresh operation handoff for recovery

- Register all recovery API routes and add a one-shot transition from an approved recovery proposal to a new pending Command Control operation.
- Persist the new operation ID, block duplicate queue attempts, expose queue/review controls in Self-X, and test that the new operation remains pending with fresh approval required.

## Unreleased — bounded failure recovery proposals

- Add a bounded SQLite recovery proposal ledger with structured operator-supplied failure categories, a maximum of three proposals per task, and bounded global retention.
- Add proposal/list/review API routes and Self-X UI controls; proposal approval authorizes replanning only and never dispatches or repeats an operation.
- Block retry approval for permission, destructive-risk, and unknown failures; require corrections and fresh approval for dependency/validation failures.
- Require a new Command Control operation and fresh human approval for any retry or changed arguments; add lifecycle and API regression tests and document the boundary.


## Unreleased — tracked task lifecycle and documentation refresh

- Add a persistent, bounded task lifecycle ledger for plan, existing-operation link, execution-status sync, verification evidence, and reviewed outcome.
- Add agentic task API endpoints and Self-X UI controls; plan creation and operation linking do not dispatch tools or approve operations.
- Require a linked operation to be recorded as executed before verification, and a passing verification before learning review.
- Add regression tests for lifecycle transitions, blocked premature verification, failed verification handling, and one-time operation linking.
- Replace the duplicated README with a modern guide covering features, architecture, cross-platform setup, provider configuration, local inference, task lifecycle, API, security, and deployment.
- Expand the agentic API guide and architecture map with lifecycle routes, request examples, state boundaries, and operational caveats.

## Unreleased — deployment and operational readiness

- Add explicit Linux systemd/macOS launchd startup installation, Windows Task Scheduler startup, and optional Termux:Boot entry point.
- Add a guarded Linux/macOS updater with source-bundle backup, fast-forward-only Git updates, dependency installation, compilation, tests, and managed-service restart.
- Add liveness (`/healthz`) and readiness (`/readyz`) probes for supervisors and deployment checks.
- Expand CI to compile the extracted agent/router modules and validate POSIX deployment scripts.
- Document that ChatGPT/Hermes/OpenClaw feature inspiration is not complete product parity; retain local-first safety boundaries and avoid exposing private chain-of-thought.


## Unreleased — Command Control Center and operational audit

- Add a dedicated Command Control Center to the existing web presentation layer with global auto-execution locked off, per-tool rule toggles, command allowlists/blocklists, and one-click approval/rejection.
- Add persistent pending-operation records; approval endpoints record a decision only and never launch commands.
- Enforce the Command Control Center allowlist/blocklist in the existing workspace command endpoint and audit approved, blocked, completed, timed-out, and rejected operations without recording command output or secrets.
- Add SQLite WAL/busy-timeout configuration, append-only audit triggers, and a serialized SHA-256 hash chain with integrity verification.
- Add a Litestar WebSocket at `/ws/events` for operational stage summaries without exposing hidden chain-of-thought, prompts, or answers.
- Add versioned JSON and safe YAML skill package import/export; imported workflows remain unverified procedure text.
- Add optional ARQ/Redis workers for Self-X maintenance, checkpoints, and supported scheduled jobs. Local mode remains available without Redis.
- Add focused tests for policy defaults, approval semantics, audit integrity, skill packages, API routes, and blocked commands.


## Unreleased

- Add session creation, selection/restoration, deletion, and active-session persistence to the web UI.
- Add reviewed AI-generated skill drafts and natural-language settings proposals with explicit user approval.
- Add regression tests for new API routes and browser controls.


## Unreleased — Self-X Evolution Engine

- Add local Self-X dashboard for diagnostics, operational evaluation, research notes, recovery checkpoints, capability status, and activity history.
- Add configurable self-diagnostics, advisory repair, research, evaluation, goal, skill, recovery, maintenance, and guarded-autonomy preferences.
- Add checksummed state checkpoints and explicitly confirmed restore with a safety checkpoint; exclude token and secret files.
- Add tests for local diagnostics, evaluation, research URL validation, checkpoint security, and recovery.

This file records notable changes to Terminal AI. Dates describe repository changes, not guarantees of compatibility with every platform.

## Unreleased — bounded Self-X autonomy and control fixes

- Hardened session name validation against both slash styles and NUL characters.
- Validated AI-proposed settings as untrusted input and clamped numeric settings to the same bounds enforced by the settings API.
- Expanded opt-in local autonomy to create periodic state checkpoints, enforce checkpoint retention, and convert failed local diagnostics into deduplicated goals.
- Recorded autonomous maintenance events in the Self-X audit history. No autonomous shell execution, source-code mutation, permission changes, or model-weight training was added.

## Unreleased — local LiteRT-LM inference fixes

- Fix the duplicate module header block that caused Python import/syntax failures.
- Handle LiteRT-LM 0.18 Message stream chunks and return the visible answer channel instead of dropping all output.
- Disable Qwen3 thinking for concise chat inference so the output budget is not consumed by hidden reasoning tokens.
- Add regression tests for LiteRT-LM message parsing and thinking configuration.
- Document how to use the already-downloaded Qwen3-0.6B model with no cloud API while offline.

## Unreleased — documentation and installer maintenance

- Updated README and installation guide to match the Litestar web-first architecture, supported provider controls, LiteRT-LM Python API, current UI/API routes, and local storage behavior.
- Improved Linux/macOS/WSL/Termux and Windows PowerShell setup scripts with repository-root handling, Python version checks, dependency validation, syntax checks, and clear run instructions.
- Updated CI to install the actual project dependencies and fail when compilation or tests fail.
- Clarified Termux and LiteRT-LM platform compatibility limitations and local deployment security guidance.

## v4.2.0 — 2026-10-13

### New features

- Environment manager and local `.env` support with secret masking.
- Additional system/file tools and agent settings.
- Persistent settings, usage stats, sessions, and cloud retry behavior.
- Offline unit-test coverage for agent engine functionality.

### Bug fixes

- Fixed several v4.1 test issues and corrected router, registry, and goal-tool expectations.
- Fixed hybrid fallback behavior, tool path expansion, journal entry selection, goal validation, and one-shot agent execution.

## v4.1.0 — 2026-10-13

### New features

- Persistent settings and usage statistics.
- Session save/load/autosave.
- Additional file and web-search tools.
- Cloud retry configuration, periodic backups, transcript export, and additional CLI flags.

### Bug fixes

- Avoid duplicate output after hybrid backend failures.
- Improve ToolForge import/eval rejection matching.
- Validate Hugging Face tokens before persisting.
- Fix home-directory path expansion and journal entry selection.

## v4.0.0

- Initial public release of the hybrid agent engine, model registry, memory, goals, skills, self-diagnostics, and learning-oriented utilities.
