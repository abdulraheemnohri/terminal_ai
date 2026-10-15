# Terminal AI — Local-First Web Agent

Terminal AI is a Python agent served through a Litestar web dashboard. The browser UI is the primary interface; `terminal_ai.py` is the internal agent engine imported by `app.py`.

## Autonomy profiles and redesigned settings

The Settings workspace groups runtime/model configuration, Self-X autonomy, and safety controls. The API validates types and ranges, rejects unknown keys, and keeps secret values out of settings responses. AI proposals can include only whitelisted settings and remain unapplied until the user reviews and confirms them.

- **Observe:** local diagnostics and deterministic evaluation only; no scheduled checkpoint creation or automatic diagnostic-goal generation.
- **Maintain:** diagnostics/evaluation plus scheduled local recovery checkpoints, subject to the checkpoint interval and retention settings.
- **Goal-driven:** Maintain behavior plus deduplicated goals from failed local diagnostics, capped by the per-cycle goal limit.
- **Run now:** an explicit on-demand cycle runs local diagnostics/evaluation and, according to the selected profile and toggles, creates a retained checkpoint and a bounded number of deduplicated diagnostic goals. It records a maintenance event.
- **Safe reset:** disables autonomous maintenance, selects Observe, disables automatic goal generation, and keeps risky-tool approval enabled without changing provider/model settings.

All profiles remain local and bounded. They do not enable arbitrary command execution, automatic source edits, permission escalation, dependency installation, cloud-provider switching, or model-weight training.

## Self-X Evolution Engine

The **Self-X** web dashboard adds operational self-identity/status, local diagnostics, deterministic readiness evaluation, an unverified research notebook, and state recovery checkpoints.

- **Self-identity/reflection:** user-configured identity and mission; operational reflection must not claim sentience.
- **Self-diagnostics:** local checks for Python/platform, writable state, model inventory, LiteRT-LM API availability, disk space, and required project files.
- **Self-repair:** evidence-based proposals only; no automatic source edits, shell execution, dependency installation, or permission changes.
- **Self-research:** manually curated local research notes with optional HTTP(S) source references; notes remain unverified and URLs are not fetched automatically.
- **Self-evaluation:** deterministic operational readiness checks, not an intelligence benchmark.
- **Self-goals / self-skills:** existing goal planner and reviewed reusable procedure library, controlled by independent settings. AI can draft a skill from a described workflow; the user reviews/edits it before saving. Generated skills are instructions, never executable code.
- **Self-learning:** local memories, skill procedures, and outcome records; no model-weight training.
- **Self-recovery:** checksummed allowlisted state checkpoints and explicitly confirmed restore; restores create a safety checkpoint first and exclude Hugging Face tokens and other secret files.
- **Self-maintenance:** advisory proposals and manual update review. When explicitly enabled, a background worker runs local diagnostics/evaluation at the configured interval, creates scheduled state checkpoints when checkpointing is enabled, enforces checkpoint retention, and creates deduplicated goals from failed local checks. Autonomous activity is recorded in the Self-X event history. It does not execute commands, apply repairs, install dependencies, or update source code.

Self-X data is stored locally in the Terminal AI state directory. Keep the web UI on localhost unless authentication and network access controls are configured.

## Hermes-style agentic capabilities

Terminal AI includes a dependency-free agentic runtime inspired by common agent-framework patterns; it is not a claim of model equivalence to Hermes.

- **Structured tool calls:** parses tagged JSON (including nested objects), validates tool names, argument objects and declared types, then dispatches only accepted calls.
- **Browser tool allowlist:** the Web UI can use bounded, read-only helpers for current time, system information, local memory/knowledge lookup, goals, and journal context. Shell execution, filesystem path tools, network fetching, environment mutation, deletion, file writes, and tool forging are not exposed through browser tool calling.
- **Private task planning:** complex requests get an internal planning instruction covering assumptions, dependencies, edge cases, and verification. Hidden chain-of-thought is not displayed or stored as a feature.
- **Multi-turn continuity and personas:** recent session history and existing local memory are supplied as context; Settings supports helpful, technical, coach, concise, and creative response styles. Memory is not invented, and persona never grants permissions.
- **Bounded error recovery:** model-stream failures can be retried up to two times with a sanitized error category. Tool calls are revalidated before dispatch; rejected calls are returned to the model for correction within the existing tool-round limit.
- **Configurable controls:** Settings exposes planning/recovery toggles and conversation style. Defaults enable planning and recovery while keeping browser tool execution restricted to the safe allowlist.

These features improve orchestration, not the underlying model weights. Actual reasoning quality and tool-call reliability still depend on the selected model/backend.

## UI audit and responsive layouts

The dashboard source has been statically checked for navigation/view parity, missing static JavaScript element references, and duplicate IDs. Responsive layout rules cover compact phones through wide desktop screens, including scrollable mobile navigation, safe-area insets, keyboard focus, and reduced-motion preferences. See [the UI responsive audit and manual regression checklist](docs/UI_RESPONSIVE_AUDIT.md). Static checks do not replace browser-based visual regression testing.

## What it includes

- Responsive dashboard pages: Overview, Chat, Sessions, Models, Diagnostics, Memory, Knowledge Base, Workspace Tools, Command Control Center, Task Scheduler, Goals, Self-awareness, Skills, Tools, Learning, Self-improvement, Self-X, and Settings.
- Local-first state and model storage; no Firebase or mandatory hosted database.
- Cloud providers: Google Gemini, OpenAI, Anthropic Claude, OpenRouter, Groq, DeepSeek, Together AI, Mistral, xAI, Fireworks AI, Cerebras, and custom OpenAI-compatible endpoints.
- Local inference through the LiteRT-LM **Python API** when a compatible `.litertlm` model and runtime are available. The app does not use a CLI subprocess for inference.
- Auto, Cloud, Local, and Hybrid backend modes.
- Persistent sessions with create/open/delete and active conversation restoration, memory facts, goals, provider configuration, and operational self-review.
- Natural-language AI settings proposals with a strict allowlist and explicit review/apply step; the assistant cannot change credentials or tool-approval policy.
- Explicitly confirmed model downloads from the registered model catalog; no silent model downloads on startup.
- OpenAPI docs at `/schema/swagger` and ReDoc at `/schema`.

The self-awareness page displays the configured identity, mission, runtime state, and user-triggered operational review. This is software introspection, not evidence of sentience or subjective experience. Reflection cannot grant the agent new permissions.

## Requirements

- Python 3.10 or newer (Python 3.12 is used by CI).
- Git and a modern browser.
- Internet access for package installation and cloud APIs / model downloads.
- For cloud inference, a key for the selected provider.
- For local inference, a compatible LiteRT-LM Python runtime and model supported by the target platform. LiteRT-LM support varies by operating system, Python version, and CPU architecture.

## Quick start

### Linux / macOS / WSL

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

### Termux

```bash
pkg update
pkg install python git
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
sh install.sh
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Keep the server running while using the UI. Stop it with Ctrl+C. The setup scripts install dependencies and run Python syntax checks; they do not automatically start the server or run the full test suite.

If the `litestar` executable is installed, the equivalent development command is:

```bash
.venv/bin/litestar --app app:app run --reload --host 127.0.0.1 --port 8000
```

On Windows, use `.venv\Scripts\litestar.exe` with the same arguments. Uvicorn is the documented portable fallback.

## Configuration

The setup script creates `.env` from `.env.example` only when `.env` does not already exist. Edit `.env` locally; never commit real credentials.

Example:

```dotenv
GEMINI_API_KEY=replace_with_your_real_gemini_api_key
HF_TOKEN=replace_with_your_huggingface_token
# TERMINAL_AI_MODE=auto
```

- `GEMINI_API_KEY`: Gemini cloud inference.
- `HF_TOKEN`: optional token for gated Hugging Face model downloads.
- `TERMINAL_AI_MODE`: optional initial mode: `auto`, `cloud`, `local`, or `hybrid`.
- `TERMINAL_AI_STATE`: override local state directory.
- `TERMINAL_AI_MODELS`: override local model directory.
- `TERMINAL_AI_GEMINI_MODEL`: override Gemini model.
- Provider-specific keys are listed in Settings and in `api_provider_backend.py`; examples include `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `TOGETHER_API_KEY`, `MISTRAL_API_KEY`, `XAI_API_KEY`, `FIREWORKS_API_KEY`, `CEREBRAS_API_KEY`, and `TERMINAL_AI_CUSTOM_API_KEY`.

Cloud mode uses the selected provider. Auto and Hybrid may combine cloud and local inference according to the configured backend behavior. API keys are stored in the local environment configuration and are not returned by the settings API. Custom remote endpoints must use HTTPS; HTTP is permitted only for loopback/local endpoints.

### Run fully offline with Qwen3-0.6B

1. Download the compatible `Qwen3-0.6B.litertlm` artifact before disconnecting from the internet.
2. Put it in `~/terminal-ai/models/` (or the directory selected by `TERMINAL_AI_MODELS`).
3. In **Settings**, set **Mode** to **Local**. This mode does not initialize a cloud provider and does not need a Gemini/API key.
4. Restart the web server if you changed environment variables, then open Chat and send a prompt.

The LiteRT-LM adapter uses the Python API, not a `litert-lm` shell command. It disables Qwen3 thinking for concise chat responses and extracts the final text channel from streamed `Message` objects. Model download and Python package installation still require internet access if they have not already been completed.

## Main UI pages

| Page | Purpose |
|---|---|
| Overview | Runtime and agent status |
| Chat | Conversation with the configured backend |
| Sessions | Saved conversation sessions |
| Models | Registry, installed local models, and confirmed downloads |
| Diagnostics | Runtime, storage, and backend diagnostics |
| Memory | View, add, and forget memory facts |
| Goals | Create and complete goals |
| Self-awareness | Identity, mission, status, and manual operational review |
| Settings | Backend mode, providers, model, endpoint, and agent preferences |

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/status` | Runtime and backend status |
| POST | `/api/chat` | Send a chat message |
| POST | `/api/chat/clear` | Clear active conversation |
| GET / POST | `/api/memory` | Read or save memory |
| POST | `/api/memory/forget` | Forget matching memory facts |
| GET / POST | `/api/goals` | List or create goals |
| POST | `/api/goals/{goal_id}/complete` | Complete a goal |
| GET | `/api/sessions` | List sessions and active session |
| POST | `/api/sessions/new` | Create and activate a session |
| POST | `/api/sessions/select` | Load a saved session into chat |
| POST | `/api/sessions/delete` | Delete a saved session |
| POST | `/api/skills/generate` | Generate an unverified skill draft |
| POST | `/api/ai/settings/propose` | Propose whitelisted settings changes; never applies them directly |
| GET | `/api/models` | Model catalog and installation state |
| GET | `/api/models/{model_id}` | One model's metadata/state |
| GET | `/api/providers` | Provider inventory and configuration status |
| POST | `/api/providers/test` | Test the selected provider connection |
| POST | `/api/models/download` | Queue an explicitly requested model download |
| GET | `/api/downloads` | Download job status |
| GET | `/api/diagnostics` | Local diagnostics |
| GET / PATCH | `/api/settings` | Read or update settings |
| GET | `/api/self/status` | Operational self-model and review status |
| POST | `/api/self/reflect` | Run a manual operational self-review |

## Storage locations

- State and web settings: `~/.terminal_ai/` by default.
- Model files: `~/terminal-ai/models/` by default.
- Override these locations with `TERMINAL_AI_STATE` and `TERMINAL_AI_MODELS`.

## Development and tests

Activate the virtual environment, then run:

```bash
.venv/bin/python -m py_compile app.py terminal_ai.py litert_api_backend.py api_provider_backend.py
.venv/bin/python -m pytest -q
```

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`. Tests isolate application state using temporary directories. Live cloud provider credentials are not required for the unit tests.

## Security notes

- Default documented commands bind to `127.0.0.1`; keep this for a private local deployment.
- Never commit `.env`, API keys, tokens, or model files.
- Do not expose the dashboard to untrusted networks without authentication, CSRF protections, rate limiting, and TLS/reverse-proxy configuration.
- Tool execution should remain disabled unless you understand and trust the enabled capabilities.
- Treat model outputs and internet research as untrusted input.

## Documentation

- Installation and troubleshooting: [INSTALL.md](INSTALL.md)
- Architecture, API map, storage and offline guarantees: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Release history: [CHANGELOG.md](CHANGELOG.md)
- Litestar docs: https://docs.litestar.dev/2/
- LiteRT-LM upstream: https://github.com/google-ai-edge/LiteRT-LM


## Persistent memory, workspace tools, and scheduling

### Long-term memory and knowledge base
- A local SQLite database at `~/.terminal_ai/long_term_memory.sqlite3` stores titled knowledge items, tags, and successful chat turns.
- The Knowledge Base view supports create, list, lexical search, and delete. The API search also returns relevant archived turns.
- Search is deterministic lexical ranking and works offline. No Chroma, FAISS, embeddings download, or external service is required. This release does not claim semantic vector search.
- Use Settings to disable the knowledge store or conversation archiving. Disabling archiving prevents new chat turns from being recorded; it does not erase existing records.

### Real workspace tools and safety boundaries
- Workspace Tools is confined to the repository root and rejects absolute paths and path traversal.
- File reads have a size limit. Writes use an atomic temporary-file replacement and require an explicit approval field plus UI confirmation.
- Commands use argument arrays with `shell=False`, an allowlist, bounded arguments, and a 60-second maximum timeout. Shell operators and `-c` command strings are rejected.
- This is a safety boundary, not a full OS/container sandbox. Keep the dashboard bound to localhost and do not expose it to untrusted users. Approved commands run with the same operating-system permissions as the Terminal AI process.

### Background task scheduler
- Tasks persist in `~/.terminal_ai/scheduled_tasks.sqlite3` and run while the web server is running.
- Supported task types: `diagnostics`, `backup_memory`, and `cleanup_temp`. Arbitrary shell tasks are intentionally unsupported.
- Minimum interval is five minutes. Jobs are checked every 15 seconds, and each result is recorded. The scheduler pauses when disabled in Settings and resumes when enabled.
- Backups are written under the application state directory's `backups/` folder.

### New API routes
- `GET/POST /api/knowledge`, `POST /api/knowledge/search`, `POST /api/knowledge/{item_id}/delete`
- `GET /api/workspace`, `POST /api/workspace/read`, `POST /api/workspace/write`, `POST /api/workspace/execute`
- `GET/POST /api/scheduled-tasks`, `PATCH /api/scheduled-tasks/{task_id}`, `POST /api/scheduled-tasks/{task_id}/delete`

The Knowledge Base, Workspace Tools, and Task Scheduler are available as separate UI pages. Review the exact command or file content before approving it.

## Hermes-style agent runtime

Terminal AI now includes provider-neutral foundations for structured tool calls,
explicit tool allowlists, JSON argument validation, approval-gated actions, bounded
self-correction/recovery, and bounded multi-turn conversation context.

- [Runtime implementation](agentic_runtime.py)
- [Feature guide, usage example, and safety boundaries](docs/HERMES_FEATURES.md)
- [Runtime unit tests](tests/test_agentic_runtime.py)

These primitives do not expose hidden chain-of-thought and do not execute model-generated
code. They are integration building blocks; provider-native tool-call responses still
need to be adapted into the normalized tool-call envelope before the chat endpoint can
use the registry end-to-end.

Run the focused tests with:

```bash
pytest -q tests/test_agentic_runtime.py
```


### Roleplay and conversation personas

Settings → Conversation style now includes **Roleplay**. It maintains fictional character and scene continuity while keeping fictional events distinct from real-world facts. It does not claim the assistant is a real person, and it does not change tool permissions.


## Command Control Center, audit, and background queue

Open **Command Control** in the web UI or visit `/command-control`. The endpoints are grouped in `routers/control.py`; bounded Pydantic v2 request contracts are in `api_schemas.py`.

- Policy settings store executable-name allowlists, blocklists, and per-tool rule metadata. The web runtime keeps global auto-execution disabled; the UI cannot turn it on.
- Pending operations support explicit approve/reject decisions. Approval is a recorded decision, not a command launcher; execution remains a separate, bounded operation.
- The local `command_control.sqlite3` database uses SQLite WAL, a busy timeout, and a SHA-256 hash-chained append-only audit table. The UI verifies the chain and displays operational events.
- `/api/control/events` streams operational action summaries and chat-stage metadata. It deliberately excludes hidden chain-of-thought, prompt bodies, and model answers.
- Skill packages use versioned JSON (`terminal-ai-skills`, schema version 1). Imported procedures are unverified text and are not executed automatically.

### Optional ARQ worker for Self-X

The default install remains local-first and does not require Redis. For installations that need Self-X maintenance/checkpoint work outside the web process:

```bash
pip install -r requirements-queue.txt
export REDIS_URL=redis://127.0.0.1:6379/0
export TERMINAL_AI_ARQ_ENABLED=1
arq arq_worker.WorkerSettings
```

Start the web application with the same environment variables. The manual Self-X maintenance and checkpoint endpoints enqueue ARQ jobs when queue mode is enabled; otherwise they retain the local fallback. Keep Redis private and use authentication/TLS if it is hosted remotely. The interval scheduler dispatches the three documented safe job types to ARQ when queue mode is enabled; otherwise it runs them in the web process as a local fallback.

Run the focused tests with:

```bash
pytest -q tests/test_command_control.py tests/test_control_center_api.py
```


## Automatic server startup and updates

The server can start automatically at user login without running with administrator/root privileges. Autostart is **opt-in** and binds to `127.0.0.1` by default so the dashboard is not exposed to your network.

### Linux with systemd

After running `sh install.sh`, run:

```sh
sh install-service.sh
systemctl --user status terminal-ai.service
```

Stop/disable autostart with `sh uninstall-service.sh`. To start the service before logging in, optionally enable systemd lingering with `loginctl enable-linger "$USER"` (this changes your user service lifecycle).

### Windows 10/11

After running `install.ps1`, open PowerShell in the project directory and run:

```powershell
.\\install-startup.ps1
```

Remove autostart with `./uninstall-startup.ps1`. The task runs as the current user at logon.

### Start manually

- Linux/macOS/WSL: `sh start-server.sh`
- Windows PowerShell: `./start-server.ps1`

Open `http://127.0.0.1:8000`. The service restarts after a process failure. Android/Termux does not provide a universal boot-service mechanism; use a Termux-compatible startup workflow if supported by the device.

### Update the project safely

- Linux/macOS/WSL: `sh update.sh`
- Windows PowerShell: `./update.ps1`

The update helper refuses to run with uncommitted changes, performs a fast-forward-only Git update, refreshes Python dependencies, checks dependencies and syntax, and runs tests before restarting a configured service. Review and back up local state before updating. These scripts update **Terminal AI only**, not the host operating system. OS security updates should be managed through the operating system's own trusted update mechanism. Updates are manual by default. On Linux with systemd, weekly project updates can be explicitly enabled with `sh install-auto-update.sh`; remove the timer with `sh uninstall-auto-update.sh`. This pulls code and dependencies from `origin/main`, so enable it only after reviewing the repository and your rollback policy. macOS can opt in with `sh install-auto-update-macos.sh` and disable with `sh uninstall-auto-update-macos.sh`; its LaunchAgent runs Sundays at 04:30 while the user is logged in. Windows can opt in with `./install-auto-update.ps1` and disable with `./uninstall-auto-update.ps1`. These helpers update Terminal AI only, not OS packages.

### macOS

After installation, run `sh install-launchagent.sh` to start the server at login and keep it running. Remove it with `sh uninstall-launchagent.sh`. Logs are written to `~/Library/Logs/terminal-ai.log` and `terminal-ai-error.log`.


### Optional weekly automatic project updates (Linux/systemd)

After reviewing the update policy, run `sh install-auto-update.sh`. The user timer runs the existing guarded `update.sh` every Sunday around 04:30 local system time; it refuses a dirty working tree and runs dependency, syntax, and test checks. Disable it with `sh uninstall-auto-update.sh`. This updates Terminal AI, **not Linux or other operating-system packages**. For the timer to run before login, systemd user lingering may be needed; use it only if you understand its lifecycle implications. On Windows, opt in with `./install-auto-update.ps1` and remove the task with `./uninstall-auto-update.ps1`; the current user must be signed in for the scheduled task to run. macOS updates can be enabled with `sh install-auto-update-macos.sh` and disabled with `sh uninstall-auto-update-macos.sh`. The macOS updater restarts the configured Terminal AI LaunchAgent after successful checks.


On Windows, the equivalent opt-in weekly task is installed from PowerShell with `./install-auto-update.ps1` and removed with `./uninstall-auto-update.ps1`. It runs only while the current user is signed in. macOS automatic project updates are not configured by these scripts.


### Termux boot startup

For Android/Termux, automatic start requires the separate Termux:Boot add-on. Open that add-on once, then run `mkdir -p ~/.termux/boot && cp termux-boot/com.terminal-ai.start.sh ~/.termux/boot/ && chmod 700 ~/.termux/boot/com.terminal-ai.start.sh`. Edit `PROJECT_DIR` in the copied script if your checkout is elsewhere. It starts the server on localhost and logs to `~/.terminal_ai/logs/termux-server.log`. It does not enable unattended project or OS updates.


## Automatic startup and safe updates

Install Terminal AI as a user service after running the normal installer:

- **Linux (systemd):** `sh scripts/install-service.sh` — starts at user login and restarts on failure. For boot before login, use `TERMINAL_AI_ENABLE_LINGER=1 sh scripts/install-service.sh` only on a machine/account you administer; system policy may require approval.
- **macOS (launchd):** `sh scripts/install-service.sh` — installs a LaunchAgent that starts at login and keeps the server alive.
- **Windows (Task Scheduler):** run `.\\scripts\\install-service.ps1` from PowerShell after installation; it starts at logon and retries failures.
- **Termux:** install Termux:Boot and follow [the deployment guide](docs/DEPLOYMENT.md).

The service defaults to `127.0.0.1:8000`. Keep it local unless you add authentication, TLS, and network access controls. Startup installation is explicit; the package installer does not silently register a persistent background service.

Update checking is advisory. Review changes before applying them. On Linux/macOS, `sh scripts/update.sh` makes a source bundle backup, refuses a dirty/non-fast-forward checkout, updates dependencies, compiles the code, runs tests, and restarts a managed service if found. It is not scheduled to apply unattended updates. See [Production deployment](docs/DEPLOYMENT.md).

## Production scope and compatibility

Terminal AI implements selected ChatGPT-like UX patterns (multi-turn sessions, provider/model selection, memory, settings, tool-mediated workflows) and Hermes/OpenClaw-inspired agent patterns (structured tool calls, bounded planning/recovery, skills, scheduled work, workspace controls and event/audit visibility). It is **not** a feature-complete clone of ChatGPT, Hermes, or OpenClaw. Availability depends on the configured provider/model and platform. The local-first runtime intentionally avoids unrestricted autonomous shell execution and does not expose private chain-of-thought; the live feed reports operational plans/stages, tool activity, errors and outcomes. See [architecture](docs/ARCHITECTURE.md) and [refactor plan](docs/ARCHITECTURE_REFACTOR.md).


## Production operations

See [Production Readiness and Agent Capability Matrix](docs/PRODUCTION_READINESS.md) for current capabilities, security invariants, known gaps, and deployment guidance.

### Start automatically at login or boot

- Linux/systemd: `sh install-service.sh`
- Windows PowerShell: `./install-startup.ps1`
- macOS: `sh install-launchagent.sh`
- Termux/Android: install the Termux:Boot add-on and copy `termux-boot/com.terminal-ai.start.sh` into `~/.termux/boot/`

These integrations run the web server as the current user and bind to loopback by default. They do not enable autonomous command execution.

### Update the project

Run `sh update.sh` on Linux/macOS/WSL or `./update.ps1` on Windows. Opt-in weekly project updates are available through the platform-specific `install-auto-update*` scripts. They update Terminal AI source and Python dependencies, not operating-system packages. Review the Git remote and maintain backups before enabling unattended code updates. The updater requires a clean worktree and validates dependencies/source/tests before restarting a configured service.




## Adaptive planning API

The Litestar API now exposes bounded adaptive planning and a persistent evidence world model at `/api/agentic`. See [the API guide](docs/AGENTIC_API.md). Plan requests return a strategy and verification steps but never execute the plan; evidence observations retain source, confidence, and optional expiry. Skill validation is read-only. All side effects remain subject to the Command Control Center approval boundary.

## Adaptive agent runtime and world model

The new framework-neutral runtime module provides reusable foundations for dynamic planning, evidence-based world-state tracking, approval gating, declarative skills, action event fan-out, SQLite WAL initialization, and a hash-chained audit ledger.

- [Runtime module](terminal_ai_runtime.py)
- [Agentic architecture and Command Control Center integration guide](docs/AGENTIC_ARCHITECTURE.md)
- [Runtime tests](tests/test_terminal_ai_runtime.py)
- [Boot startup and update guide](docs/AUTOSTART.md)
- [systemd service template](systemd/terminal-ai.service)

The planner chooses a bounded strategy based on complexity, risk, and external side effects. The world model stores explicit observations with source, confidence and expiry; this is operational state tracking, not sentience or human-like consciousness. Skills are declarative JSON/YAML procedures, not executable code, and imported skills remain untrusted until reviewed. High-risk operations always require explicit approval. The module is an integration foundation; it is not yet a claim that all these primitives are wired into every existing route or React page.

### Boot startup (opt-in)

Linux systems using systemd can review the unit and installer in systemd/ and scripts/. Windows users can register per-user sign-in startup with scripts/install_autostart_windows.ps1 after installing the project. These options start the web server as an unprivileged user and bind to loopback by default. See [docs/AUTOSTART.md](docs/AUTOSTART.md). Automatic application updates remain separate from startup and are not silently enabled.


## Browser tools and one-time approvals

Terminal AI now includes an optional Playwright adapter in `agent/playwright_browser.py` and a one-time approved tool dispatcher in `agent/approved_dispatch.py`. Browser access requires an explicit domain allowlist; form submission and other state-changing tools must use a reviewed, unexpired approval bound to the exact tool and arguments. See [approved tool execution and browser setup](docs/APPROVED_TOOL_EXECUTION.md). The adapter is optional and is not automatically started by the web server.
