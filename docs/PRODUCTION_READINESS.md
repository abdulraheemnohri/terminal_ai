# Production Readiness and Agent Capability Matrix

This document defines the production target for Terminal AI and distinguishes implemented local-first features from optional integrations and features that still need engineering work. It is not a claim that Terminal AI is a byte-for-byte clone of ChatGPT, Hermes, or OpenClaw; those products have different models, services, and licensing.

## Implemented foundation

- **Chat and model backends:** Litestar web dashboard, multi-turn sessions, configurable provider/model settings, local LiteRT-LM integration when supported, cloud-provider adapters, model inventory/download workflow, and provider connection checks.
- **Agent patterns:** structured tool-call parsing, tool allowlists, bounded planning/recovery, persona settings, local memory/knowledge retrieval, and observable execution summaries.
- **Control Center:** per-tool policy metadata, executable allowlist/blocklist, pending-operation review, and an explicit global auto-execution policy. Approval records are not execution tokens; approving a queued item does not run a command.
- **Action stream:** WebSocket event feed for operational summaries and policy/approval events. It must not stream private chain-of-thought, raw system prompts, environment variables, or credentials.
- **Audit:** SQLite WAL, busy timeouts, append-only audit rows, and a hash chain with integrity verification. This detects changes to the stored chain but is not a signature against a privileged attacker who can rewrite the database and recompute hashes. Export critical audit records to a separately controlled destination.
- **Skills:** import/export of versioned JSON/YAML procedure packages. Imported skill steps are untrusted text until reviewed; they are not executable Python or shell scripts.
- **Memory and jobs:** local SQLite memory, conversation archive, persistent task scheduling, and optional ARQ/Redis offload for supported background maintenance jobs.
- **Bounded autonomy jobs:** persistent SQLite queue, single-process background worker, status/progress endpoints, cooperative cancellation, restart recovery, and bounded retries. The worker only invokes registered read-only actions or creates plans; it does not execute planned steps.
- **Approved plan dispatch:** an operator may attach an exact allowlisted terminal argv to a tracked plan. The operation is queued pending review, and execution remains a separate explicit action after approval. Task status is synchronized from Command Control; independent verification is required before review can create a learning record. Shell operators, shell command flags, blocked executables, and workspace escapes are rejected.
- **Self-X:** local diagnostics, deterministic evaluation, reviewed repair proposals, local research notes, goals, skill procedures, checksummed checkpoints, and bounded maintenance. It does not claim sentience or automatically rewrite source code.
- **Operations:** per-user startup integrations for systemd, Windows Task Scheduler, macOS LaunchAgents, and optional Termux:Boot; opt-in project update helpers; local state backups; syntax/dependency/test validation before the updater restarts a configured service. The Settings dashboard can create, list, download, and checksum-validate state archives; actual restore remains an explicit CLI action while the service is stopped to avoid replacing live SQLite files.

## ChatGPT-/Hermes-/OpenClaw-inspired capability groups

The project should implement comparable *workflow categories* where technically and legally appropriate, rather than claim exact feature parity with a proprietary hosted service or a specific model.

1. **Conversation:** streaming responses, session lifecycle, context management, configurable personas, explicit memory controls, and export/delete tools.
2. **Tool use:** typed tool schemas, tool discovery, per-tool permissions, approval queue, timeouts, bounded output, cancellation, idempotency for retryable operations, and structured errors.
3. **Planning and recovery:** private internal planning; public progress events; bounded retries for safe, idempotent operations; no blind retries for writes, purchases, deletion, or other side effects.
4. **Knowledge and skills:** local retrieval, source attribution, versioned procedure packages, import validation, review state, provenance, and regression checks for verified skills.
5. **Automation:** scheduled jobs, event-driven triggers, resumable job records, limits, cancellation, and a durable queue for deployments that need multiple workers.
6. **System integration:** optional browser, filesystem, terminal, and external channel adapters only behind a permission boundary. Run risky tools in a separately restricted process/container where possible; an allowlist alone is not a complete sandbox.
7. **Observability:** action events, latency and error metrics, redacted logs, audit verification, readiness/liveness probes, and backup/restore drills.
8. **Security:** local-only defaults, authentication and authorization before remote exposure, CSRF/origin protections for browser sessions, rate limits, secret redaction, dependency scanning, and documented recovery procedures.

## Production deployment invariants

- Bind to `127.0.0.1` by default. Do not expose the app directly to the public internet without authentication, authorization, TLS, CSRF/origin checks, rate limiting, and a reviewed reverse-proxy configuration.
- Keep `.env`, model artifacts, SQLite databases, logs, backups, and user content out of source control. Use fake placeholders only in templates.
- Global autonomous command execution stays disabled by default. A UI control must not bypass server-side policy.
- Require explicit confirmation for updates, model downloads, checkpoint restore, and other consequential operations.
- Project auto-updates are **opt-in** and update Terminal AI source/dependencies, not operating-system packages. Review the origin and update policy before enabling unattended updates.
- Use the same OS account for the server and its files, apply least privilege, and do not run the agent as root/Administrator for convenience.
- Backups should be stored outside the live database directory and tested by restoring to a disposable state directory.
- SQLite WAL improves reader/writer concurrency but does not make SQLite a multi-host database. Use a dedicated database and queue for multi-instance deployment.

## Startup and update commands

| Platform | Start at login/boot | Disable |
|---|---|---|
| Linux with systemd | `sh install-service.sh` | `sh uninstall-service.sh` |
| Windows PowerShell | `./install-startup.ps1` | `./uninstall-startup.ps1` |
| macOS | `sh install-launchagent.sh` | `sh uninstall-launchagent.sh` |
| Termux/Android | Install Termux:Boot, then copy `termux-boot/com.terminal-ai.start.sh` to `~/.termux/boot/` | Remove the copied boot script |
| Linux weekly project updates | `sh install-auto-update.sh` | `sh uninstall-auto-update.sh` |
| Windows weekly project updates | `./install-auto-update.ps1` | `./uninstall-auto-update.ps1` |
| macOS weekly project updates | `sh install-auto-update-macos.sh` | `sh uninstall-auto-update-macos.sh` |

Manual update helpers are `sh update.sh` and `./update.ps1`. They require a clean Git working tree and the expected official Git origin. The Windows updater additionally backs up local state when present, rejects diverged history, validates dependencies/source/tests, and restores the previous source commit if validation fails. Always review the update output and backup path.

## Bounded autonomous decision loop

The Self-X dashboard exposes `GET /api/agentic/autonomy/status` and `POST /api/agentic/autonomy/run`.

- Uses task classification and the verified-outcome learning store to recommend a workflow strategy. This is an explainable, empirical strategy recommender—not model-weight training or a claim of general intelligence.
- Automatically runs only registered read-only actions: bounded workspace file listing, learning-summary retrieval, and world-model summary retrieval.
- Creates a persistent task plan for general work and records a decision/audit summary. It does not claim a plan is a completed task.
- Detects common side-effect intent phrases and defers them. File writes, shell commands, browser actions, network requests, deployments, and high-risk work are not autonomously executed by this loop.
- Does not change allowlists, permissions, approval policy, credentials, or global terminal auto-execution settings.
- Uses bounded request sizes, action allowlists, and a capped SQLite history. An independent security review is still required before exposing these endpoints remotely.

This is an initial autonomous control loop, not unrestricted autonomous execution. Broader autonomy requires explicit action adapters with their own validation, idempotency, timeout, resource limits, independent verification, and policy enforcement. The run history is operational metadata; do not store secrets or sensitive personal data in goal text.

## Settings controls and portable backup

The Settings dashboard exposes the persisted Self-X identity, mission, and operational reflection toggle. These values are editable through the same validated settings API used by the runtime; they do not grant permissions or disable human approval.

The Settings page also supports versioned JSON backup and restore for an explicit allowlist of non-secret configuration values. Exports exclude API keys and Hugging Face tokens. Imports must match the supported format/version, reject unknown keys and approval-policy weakening, show a preview, require a separate user confirmation, and pass through the server's normal settings validation. Credentials are configured separately on each machine.

## Remaining production gates

These must be completed and verified before describing a deployment as enterprise-grade:

- Authentication/authorization and multi-user tenant isolation for remote access.
- A robust isolated execution worker for any future shell/browser/computer-control tools.
- End-to-end tests for WebSocket reconnect/replay, operation approval races, audit-chain corruption, update rollback, and backup restore.
- CI coverage across supported Python/OS combinations, static typing/linting, dependency and secret scanning, and release artifact signing.
- Operational metrics, structured redacted logs, retention controls, migration policy, and documented disaster recovery.
- Optional integrations such as voice, image generation, external messaging channels, browser automation, and multi-agent coordination should be separate adapters with explicit configuration, not silently enabled capabilities.

A feature is production-ready only when the API contract, UI behavior, permission checks, tests, documentation, and failure recovery are all present. A roadmap item or UI placeholder is not proof that a backend capability exists.
