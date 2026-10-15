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

## What it includes

- Responsive dashboard pages: Overview, Chat, Sessions, Models, Diagnostics, Memory, Goals, Self-awareness, and Settings.
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
