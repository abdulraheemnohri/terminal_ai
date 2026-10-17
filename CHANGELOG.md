## Unreleased — cross-origin request protection

- Reject cross-origin browser mutations and WebSocket upgrades when an Origin header is supplied.
- Preserve same-origin browser requests and non-browser clients that do not send Origin; this is defense in depth, not a replacement for authentication or TLS.
- Add regression tests for cross-origin rejection, safe GETs, same-origin default ports, WebSockets, and CLI compatibility.

## Unreleased — audit ledger schema validation

- Reject audit entries with missing or incorrectly typed required fields, invalid hash encodings, or malformed hash links even if the entry hash was recomputed.
- Add regression coverage proving schema-invalid records fail verification.

## Unreleased — CI compatibility coverage

- Run the full CI validation suite on Python 3.11 and 3.12 to catch version-specific regressions.

## Unreleased — approval race regression coverage

- Verify only one concurrent worker can claim a reviewed operation.
- Verify an approval cannot be reused with altered operation arguments.

## Unreleased — WebSocket event replay coverage

- Verify newly queued operations appear in the action stream as replayable audit summaries.
- Assert raw operation arguments and private payload values are not included in streamed events.

## Unreleased — restore recovery regression coverage

- Verify restores without `--overwrite` leave all existing and new destination files untouched when conflicts exist.
- Verify `--overwrite` replaces only the explicitly requested existing file.
- Reject empty backups without creating a state directory.

## Unreleased — audit ledger integrity handling

- Treat malformed or unreadable audit-chain records as integrity failures instead of crashing diagnostics.
- Refuse to append new events when existing audit history fails integrity verification.
- Add regression tests for event tampering, malformed JSON, valid chains, and fail-closed append behavior.

## Unreleased — restore path regression coverage

- Add regression tests for traversal paths with malformed checksums and Windows backslash paths.

## Unreleased — restore path validation regression

- Validate archive paths before checksum values so path traversal is rejected consistently, including malformed-checksum archives.
- Reject Windows path separators correctly during manifest validation.
- Fixes a legacy restore regression test and closes a Windows-style path validation gap.

## Unreleased — state restore hardening

- Reject duplicate ZIP members, missing/extra archive entries, malformed checksums, unsafe paths, oversized manifests, and archives beyond the configured safety limits before restoring state.
- Preflight every destination, including symlink resolution, before writing the first file to avoid partial restores caused by a later path escape.
- Add regression tests for confirmation requirements, valid restore, duplicate/unlisted members, traversal, and symlink escape.

## Unreleased — WebSocket authentication regression coverage

- Add tests proving unauthenticated WebSocket connections are rejected when the server is remotely bound without credentials.
- Add tests proving configured HTTP Basic authentication is enforced for WebSocket upgrades as well as ordinary HTTP requests.

## Unreleased — cloud-first multi-provider fallback and LiteRT role fix

- Add a deterministic cloud-first fallback chain: selected provider first, then other configured cloud providers, then local LiteRT-LM in Auto/Hybrid modes.
- Keep Cloud mode cloud-only while allowing provider-to-provider failover; Local mode remains local-only.
- Buffer each provider's response and discard failed or empty partial streams before failover, preventing mixed or duplicated answers.
- Normalize internal tool results into marked user-context messages for LiteRT-LM using only supported `user`/`model` roles; never send unsupported `tool` or OpenAI-style `assistant` roles to the local API.
- Update Settings help text and add regression tests for provider failover order, local fallback, empty responses, partial-stream failures, and role normalization.

## Unreleased — Gemini conversation-role compatibility

- Normalize internal tool results into labelled user-context messages before sending chat history to Gemini SDKs, which accept only user/model content roles in this text-only adapter.
- Keep assistant/model turns mapped to the provider's model role and omit unknown internal roles instead of forwarding them to the API.
- Add regression tests covering tool-result history, unsupported internal roles, and SDK typed-content construction.

## Unreleased — health timeline and collection search

- Add a browser-local health timeline for API reachability and inference readiness, bounded to 48 recent samples and never uploaded to the server.
- Add live search and matching counts to sessions, models, memories, skills, tools, scheduler jobs, diagnostics, task lifecycle, Command Control, and other dashboard collections.
- Reapply collection filters as results refresh, and keep search controls keyboard accessible and responsive.
- Add regression checks for the health chart and collection-search UI.

## Unreleased — dashboard themes and operations toolkit

- Add browser-local light/dark theme switching with accessible labels and persisted preference.
- Add a bounded, dismissible status-toast region and notify users when system readiness changes.
- Add read-only installation doctor checks plus checksum-verified state backup and explicit-confirmation restore utilities.
- Harden restore against path traversal, excessive archive sizes, and overwrite-by-default; skip symlinks during backup.
- Add shell and PowerShell validation entrypoints, a scripts catalog with compatibility wrappers for legacy root scripts, and CI coverage for script syntax and dashboard assets.
- Add regression tests for theme/notification UI and backup/restore safety.

## Unreleased — dashboard interface personalization

- Add browser-local interface preferences for compact layout, larger text, and reduced motion, with immediate application and reset controls.
- Persist presentation preferences in local browser storage without sending them to the server or changing agent/security settings.
- Add accessible toggle styling, responsive preference layout, and regression tests for the settings UI and served assets.

## Unreleased — dashboard navigation and browser visibility

- Add a searchable command palette covering every dashboard page, opened with Ctrl/Cmd+K and navigable by keyboard.
- Add dialog semantics, escape/outside-click closing, focus restoration, responsive layout, and visible keyboard focus styles.
- Add a live Overview browser-security card showing allowlist count and Playwright availability while explicitly reporting remote actions as disabled.
- Add a manual refresh action and regression tests for the new dashboard markup and served UI assets.

## Unreleased — local approved browser dispatch

- Add a trusted local-only dispatch service and CLI for browser operations already approved in Command Control.
- Require an explicit `--confirm`, configured domain allowlist, an unused human approval, and an allowlisted `browser.*` tool name.
- Consume approvals once, record execution outcomes, close browser resources, and keep browser execution unavailable through the web API.
- Add tests for missing confirmation, missing allowlist, unapproved and non-browser operations, successful one-shot dispatch, and replay prevention.

## Unreleased — browser settings regression coverage

- Extend web-app tests for configured browser status, normalized/deduplicated domain settings, malformed entry types, and the 50-domain cap.
- Verify status reporting never enables browser execution and restore browser settings after tests to avoid cross-test state leakage.

## Unreleased — browser allowlist settings

- Add Settings UI for a configurable browser DNS allowlist with strict server-side normalization and rejection of wildcard, URL-shaped, port-bearing, malformed, and IP-literal entries.
- Add a status-only browser endpoint that reports configuration and optional Playwright availability without launching a browser or enabling remote actions.
- Add regression tests for accepted normalization, invalid entries, persistence, and the disabled execution boundary.

## Unreleased — browser URL and allowlist hardening

- Normalize internationalized DNS names and reject wildcard, URL-shaped, IP-literal, and malformed allowlist entries.
- Convert malformed URL authorities and ports into explicit policy rejections before DNS resolution.
- Add regression tests for malformed URLs, allowlist edge cases, and DNS responses resolving to private addresses.
- Add `application/browser_runtime.py` to wire the optional Playwright adapter into `ToolRegistry`, exposing only implemented handlers and preserving approval requirements for state-changing browser tools.
- Add registry-wiring tests and document that DNS validation is defense-in-depth; network egress controls are still required against DNS rebinding.

## Unreleased — reviewed recovery learning

- Add a separate outcome-review step after successful recovery verification; verification alone does not feed learning.
- Add idempotent learning source references and database migration so retries of the review request cannot create duplicate samples.
- Add a Self-X review control, API documentation, and regression coverage for pre-verification blocking and repeated requests.

## Unreleased — chat display preference fix

- Apply the selected chat font size directly to the message container so the UI control changes rendered message text, while retaining the existing 12–19 px bounds and browser-local persistence.
- Add regression coverage for the font-size control wiring.

# Changelog

## Unreleased — recovery execution tracking and verification

- Expose the new recovery operation status in task history and allow one-time independent verification only after Command Control records successful execution.
- Persist bounded verification evidence and block premature or duplicate verification; never auto-retry after a failed verification.

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
