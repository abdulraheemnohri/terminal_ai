# Terminal AI

<p align="center">
  <strong>A local-first, self-hosted AI workspace with a Litestar web UI, pluggable model providers, persistent memory, and human-approved agent workflows.</strong>
</p>

<p align="center">
  <a href="https://github.com/abdulraheemnohri/terminal_ai/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/abdulraheemnohri/terminal_ai/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Litestar" src="https://img.shields.io/badge/API-Litestar-5B5BD6">
  <img alt="Self-hosted" src="https://img.shields.io/badge/deployment-self--hosted-16825D">
  <img alt="Local-first" src="https://img.shields.io/badge/design-local--first-555555">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#features">Features</a> ·
  <a href="#security-model">Security</a> ·
  <a href="#documentation">Documentation</a>
</p>

Terminal AI is a Python application for running an AI assistant from your own machine. It provides a responsive browser dashboard, configurable cloud and local model backends, persistent local data, and an evolving set of agent workflows.

The project uses a **modular-monolith architecture**: a Litestar application, separated route and application modules, provider/browser adapters, local persistence, and a plain HTML/CSS/JavaScript UI. The existing runtime is being split incrementally rather than moved in a risky one-shot rewrite.

> **Scope note:** Terminal AI combines selected workflow patterns found in modern AI assistants and agent frameworks. It is not a feature-complete clone of ChatGPT, Hermes, or OpenClaw. “Self-awareness” and “Self-X” refer to operational status, diagnostics, reflection, evidence, and controlled adaptation—not sentience or subjective experience.

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick start](#quick-start)
  - [Linux, macOS, and WSL](#linux-macos-and-wsl)
  - [Windows PowerShell](#windows-powershell)
  - [Android / Termux](#android--termux)
- [Configuration](#configuration)
- [Local inference](#local-inference)
- [Self-X task lifecycle](#self-x-task-lifecycle)
- [Run at login or boot](#run-at-login-or-boot-opt-in)
- [Development and tests](#development-and-tests)
- [API and observability](#api-and-observability)
- [Security model](#security-model)
- [Documentation](#documentation)
- [Known boundaries](#known-boundaries)

## Features

### Chat and model backends

- Multi-turn chat, saved sessions, active-session restoration, and configurable response personas.
- Provider configuration for Google Gemini, OpenAI, Anthropic Claude, OpenRouter, Groq, DeepSeek, Together AI, Mistral, xAI, Fireworks AI, Cerebras, and custom OpenAI-compatible endpoints.
- Backend modes: **Auto**, **Cloud**, **Local**, and **Hybrid**.
- Local LiteRT-LM inference through the Python API when the installed runtime, model artifact, Python version, and platform are compatible.
- Model catalog, explicit model-download requests, provider connection checks, and runtime diagnostics.
- API keys and tokens are not returned by settings responses; keep real credentials in local environment configuration.

### Workspace and persistent context

- Local memory and a SQLite knowledge base with deterministic lexical search.
- Goals, workspace tools, task scheduling, archived conversations, and diagnostics.
- Model-generated skill drafts and settings proposals remain proposals until reviewed.
- Explicit controls for memory, conversation archiving, and local state.

### Agentic workflows and Self-X

- Typed structured tool-call parsing and allowlisted browser-side helpers.
- Bounded planning and recovery signals, with clear separation between planning and action execution.
- Persistent evidence observations with source, confidence, timestamps, and optional expiry.
- Reviewed learning from explicitly verified outcomes; learning adjusts recommendations, not permissions.
- Plain-text skill proposals, static validation, review, and promotion to a reviewed catalog.
- Local diagnostics, operational evaluation, research notes, goals, recovery checkpoints, and bounded maintenance profiles.
- Task lifecycle records connecting a plan to an existing Command Control operation, recorded execution status, operator verification, and reviewed outcomes.
- Action summaries and audit events without exposing private chain-of-thought or secrets.

### Human control and operations

- Command Control Center for pending operations, approvals, policy visibility, and audit history.
- Global auto-execution stays disabled by default. An approval decision is not itself an execution event.
- Responsive dashboard with pages for Chat, Sessions, Models, Memory, Knowledge Base, Workspace Tools, Command Control, Scheduler, Goals, Skills, Learning, Self-improvement, Self-X, Diagnostics, and Settings.
- Optional per-user startup integrations for Linux/systemd, macOS/launchd, Windows Task Scheduler, and Termux:Boot.
- Update helpers are separate from startup and are opt-in; automatic project updates are not silently enabled.

## Architecture

```text
terminal_ai/
├── app.py                    # Litestar application and compatibility surface
├── terminal_ai.py            # Core agent/runtime (incremental refactor target)
├── terminal_ai_runtime.py    # Framework-neutral planning/world-model primitives
├── routers/                  # HTTP/API route modules
├── agent/                    # Browser, dispatch, and agent adapters
├── application/              # Learning, skill evolution, task lifecycle, services
├── web/
│   ├── index.html            # Dashboard structure
│   ├── app.js                # Client behavior and API wiring
│   └── app.css               # Responsive UI styling
├── tests/                    # Unit and API regression tests
├── scripts/                  # Structure, install, service, and update helpers
└── docs/                     # Architecture, deployment, API, and safety guides
```

The exact set of modules evolves as refactoring progresses. See [Architecture and capability map](docs/ARCHITECTURE.md) and [incremental refactor plan](docs/ARCHITECTURE_REFACTOR.md).

## Quick start

### Requirements

- Python **3.10+** (CI currently uses Python 3.12).
- Git and a modern browser.
- Internet access to install dependencies; cloud APIs and model downloads also need network access.
- A key for your chosen cloud provider, or a compatible LiteRT-LM runtime and model for local inference.

### Linux, macOS, and WSL

```bash
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
sh install.sh
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

### Windows PowerShell

```powershell
git clone https://github.com/abdulraheemnohri/terminal_ai.git
Set-Location terminal_ai
.\install.ps1
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

### Android / Termux

```bash
pkg update
pkg install python git
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
sh install.sh
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Stop the foreground server with `Ctrl+C`. The installer prepares the environment and checks source syntax; it does not silently register a background service or run the full test suite. LiteRT-LM availability varies by platform, especially on Android/Termux.

If the install has provided the Litestar CLI, you can also use `litestar --app app:app run --reload --host 127.0.0.1 --port 8000` for development.

## Configuration

The installer creates `.env` from `.env.example` only when a local `.env` does not already exist. Edit it locally and never commit real secrets.

Example:

```dotenv
GEMINI_API_KEY=replace_with_your_key
HF_TOKEN=replace_with_your_huggingface_token
# TERMINAL_AI_MODE=auto
```

Common settings:

| Variable | Purpose |
|---|---|
| `TERMINAL_AI_MODE` | Initial backend mode: `auto`, `cloud`, `local`, or `hybrid` |
| `TERMINAL_AI_STATE` | Override the local application state directory |
| `TERMINAL_AI_MODELS` | Override the local model directory |
| `TERMINAL_AI_GEMINI_MODEL` | Override the Gemini model |
| `GEMINI_API_KEY` | Gemini API credentials |
| `HF_TOKEN` | Optional Hugging Face token for gated model downloads |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `TOGETHER_API_KEY`, `MISTRAL_API_KEY`, `XAI_API_KEY`, `FIREWORKS_API_KEY`, `CEREBRAS_API_KEY` | Optional credentials for supported providers |

Additional provider and custom endpoint configuration is available in Settings and the provider backend. Restart the server after changing environment variables. Custom remote endpoints should use HTTPS; plain HTTP is intended only for loopback/local endpoints.

## Local inference

For an offline setup, first download a compatible LiteRT-LM model artifact while connected to the internet. Place it in the configured model directory (by default `~/terminal-ai/models/`), choose **Local** in Settings, and restart the server if required. For example, the repository documents a Qwen3-0.6B `.litertlm` workflow.

Local inference requires a compatible LiteRT-LM Python runtime and model artifact; model format and hardware support are platform-dependent. The application uses the Python API, not a shell subprocess, for LiteRT-LM inference. No model is silently downloaded at startup.

## Self-X task lifecycle

The Self-X dashboard includes a tracked task lifecycle designed to connect planning, operator-controlled actions, verification, and learning without adding a hidden execution path.

```text
Plan created
    ↓
Link an existing Command Control operation
    ↓
Operation status is observed (approval remains separate)
    ↓
Recorded execution → operator supplies verification evidence
    ↓
Passing verification → human-reviewed outcome → learning record
```

Key boundaries:

- `POST /api/agentic/tasks` stores a plan; it does not execute steps.
- A task can link one existing Command Control operation. Linking does not approve or run it.
- Verification requires the linked operation to be recorded as executed.
- Failed verification cannot enter the learning review stage.
- Only a passing verified task can be reviewed for a learning record.
- Learning changes future recommendations; it does not grant permissions, rewrite source code, or train model weights.
- Operator-entered evidence is an attestation, not cryptographic proof of independent verification.

See [Agentic API](docs/AGENTIC_API.md), [Agentic architecture](docs/AGENTIC_ARCHITECTURE.md), and [approved tool execution](docs/APPROVED_TOOL_EXECUTION.md).

## Run at login or boot (opt-in)

Install and test the project before enabling startup. The service runs as the current user by default and binds to loopback.

| Platform | Install / enable | Inspect or disable |
|---|---|---|
| Linux (systemd user service) | `sh scripts/install-service.sh` | `systemctl --user status terminal-ai.service` |
| macOS (LaunchAgent) | `sh scripts/install-service.sh` | See [deployment guide](docs/DEPLOYMENT.md) |
| Windows (Task Scheduler) | Run `./scripts/install-service.ps1` in PowerShell | `Get-ScheduledTask -TaskName 'Terminal AI Web Server'` |
| Android / Termux | Install Termux:Boot and follow [the guide](docs/DEPLOYMENT.md) | Remove the copied Termux boot entry |

Startup and automatic updates are separate settings. The updater scripts update **Terminal AI source and Python dependencies**, not the operating system. Review the repository, keep backups, and understand the rollback path before enabling any scheduled updater. See [Deployment](docs/DEPLOYMENT.md) and [Automatic startup](docs/AUTOSTART.md).

## Development and tests

Create/activate the environment, then run:

```bash
# Compile the application and main packages
.venv/bin/python -m compileall -q app.py terminal_ai.py application agent routers

# Validate required repository structure
.venv/bin/python scripts/check_structure.py

# Run the test suite
.venv/bin/python -m pytest tests/ -v
```

On Windows, use `.venv\Scripts\python.exe`. Unit and API tests should not require live cloud-provider credentials. CI additionally checks dependency consistency and POSIX startup/update script syntax.

## API and observability

- Main application API: `/api/*`
- Agentic planning, evidence, learning, skills, and task lifecycle: `/api/agentic/*`
- Command Control Center: `/api/control/*`
- Health probe: `/healthz`
- Readiness probe: `/readyz`
- OpenAPI / Swagger: `/schema/swagger`
- ReDoc: `/schema`
- Operational event WebSocket: `/ws/events`

Useful agentic endpoints include:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/agentic/status` | Capability and safety status |
| `POST` | `/api/agentic/plan` | Preview a bounded plan |
| `GET` | `/api/agentic/learning/summary` | Aggregate reviewed learning |
| `GET` | `/api/agentic/world-model` | Query active evidence facts |
| `POST` | `/api/agentic/world-model/observe` | Record an evidence observation |
| `POST` | `/api/agentic/tasks` | Create a tracked plan |
| `GET` | `/api/agentic/tasks` | List tracked tasks |
| `GET` | `/api/agentic/tasks/{task_id}` | Read and sync a task's operation status |
| `POST` | `/api/agentic/tasks/{task_id}/operation` | Link an existing operation |
| `POST` | `/api/agentic/tasks/{task_id}/verify` | Record verification evidence |
| `POST` | `/api/agentic/tasks/{task_id}/review` | Review a passing verified task |

Interactive API documentation is available at `/schema/swagger` while the app is running.

## Storage locations

- State, settings, SQLite stores, audit records, and world-model data: `~/.terminal_ai/` by default.
- Model artifacts: `~/terminal-ai/models/` by default.
- Override directories with `TERMINAL_AI_STATE` and `TERMINAL_AI_MODELS`.

Back up the state directory before upgrades or checkpoint restores. Store backups securely because local state can include conversation and operational history.

## Bounded failure recovery

Tracked tasks can collect up to three recovery proposals after a linked Command Control operation is recorded as failed or expired. Recovery guidance uses explicit categories and distinguishes transient failures, failures requiring a change, and unsafe/unknown cases. A human can review a proposal, then queue one new Command Control operation with exact arguments. The new operation remains pending and requires separate human approval; approval of the recovery proposal itself never executes anything. After the separately approved operation is executed, the Self-X dashboard can record one independent verification result and a separate human-reviewed outcome. Only that reviewed outcome enters learning, with an idempotency key to prevent duplicate samples. Do not include secrets in failure summaries. See [Agentic API](docs/AGENTIC_API.md) for endpoints and policy details.

## Security model

**Keep the server on `127.0.0.1` unless you have deliberately configured a secure remote deployment.**

- Do not expose the dashboard to untrusted networks without authentication, authorization, CSRF/origin protections, rate limits, TLS, and firewall/reverse-proxy controls.
- Never commit `.env`, provider keys, Hugging Face tokens, cookies, local databases, logs, or model artifacts.
- Treat model output, retrieved web pages, imported skills, and user-supplied verification text as untrusted input.
- Approval is scoped to an operation; it is not blanket permission and does not imply execution.
- Global autonomous command execution remains disabled by default. Deny rules and risk policy must override agent suggestions.
- Browser automation is optional and should use a domain allowlist plus host/network egress controls. Application checks alone are not a complete sandbox against DNS rebinding or local-network attacks.
- Static skill validation is not a sandbox. Declarative skill procedures remain untrusted until reviewed.
- Audit hash chaining can reveal unexpected record changes but is not a digital signature against a privileged attacker who can rewrite the database.
- Self-X features provide operational introspection and controlled adaptation—not consciousness, autonomous source-code mutation, or model-weight training.

## Maintenance scripts

The dashboard now supports browser-local light/dark theme switching, transient API status notifications, a bounded local health timeline, searchable collections, and interface preferences for compact layout, larger text, and reduced motion. Presentation history stays in this browser and does not alter agent permissions or backend configuration.

The `scripts/` directory is the central operational entrypoint catalog. Start with [scripts/README.md](scripts/README.md).

```sh
python scripts/doctor.py
python scripts/backup_state.py
sh scripts/validate.sh
```

Restore is intentionally explicit and refuses overwriting files unless you pass `--overwrite` after making a backup:

```sh
python scripts/restore_state.py /path/to/terminal-ai-state.zip --confirm
```

Backups can contain sensitive state and credentials; keep them in a private directory. Operational implementations now live in `scripts/`; root-level install/update/startup commands are small compatibility wrappers so existing instructions and shortcuts keep working.

## Documentation

| Guide | Description |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Components, data stores, APIs, invariants, and current boundaries |
| [Architecture refactor plan](docs/ARCHITECTURE_REFACTOR.md) | Incremental modularization strategy |
| [Agentic API](docs/AGENTIC_API.md) | Planning, evidence, learning, and task lifecycle endpoints |
| [Agentic architecture](docs/AGENTIC_ARCHITECTURE.md) | Planner, world model, approvals, audit, and skills |
| [Adaptive agent guide](docs/ADAPTIVE_AGENT.md) | Adaptive planning, world model, browser, and skill principles |
| [Approved tool execution](docs/APPROVED_TOOL_EXECUTION.md) | One-time approvals and optional browser adapter |
| [Deployment](docs/DEPLOYMENT.md) | Startup, operational hardening, and safe updates |
| [Autostart and updates](docs/AUTOSTART.md) | Platform startup options and update guidance |
| [Production readiness](docs/PRODUCTION_READINESS.md) | Capability matrix, limitations, and production checklist |
| [UI responsive audit](docs/UI_RESPONSIVE_AUDIT.md) | Responsive layout checks and manual regression checklist |
| [Installation guide](INSTALL.md) | Installation and troubleshooting |
| [Changelog](CHANGELOG.md) | Repository change history |

## Known boundaries

- Provider/model behavior and local inference availability depend on credentials, model compatibility, operating system, Python version, and hardware.
- Some agentic components are foundations or review workflows, not a universal autonomous executor wired to every tool.
- Learning is based on bounded reviewed outcomes and heuristic signals; it is not model training and scores are not calibrated probabilities.
- Verification evidence is currently operator-supplied text and requires trusted human process.
- The project is not a hardened multi-tenant SaaS service. Secure remote access requires additional deployment controls.
- Background workers and scheduling are optional; supported job types and runtime mode determine which jobs can be offloaded.

---

**Contributions and bug reports:** please include your operating system, Python version, reproducible steps, relevant redacted logs, and whether the issue occurs with cloud or local inference. Never attach secrets or private conversation data.
