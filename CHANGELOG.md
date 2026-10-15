# Changelog

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
