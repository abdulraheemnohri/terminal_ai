# ⬢ Terminal AI — Litestar Web Agent (v4.2.0)

Terminal AI is a local-first Python AI agent with a **Litestar web application** as its primary interface. It supports Google Gemini for cloud inference and LiteRT-LM for compatible local models, with persistent memory, goals, sessions, and agent settings.

The terminal REPL is no longer the user interface. `terminal_ai.py` remains the internal agent engine used by the web app; start the application with `app.py`.

## Features

- **Litestar web server** with typed HTTP endpoints and generated OpenAPI docs.
- **Responsive dark dashboard** with directly addressable Overview (`/overview`), AI Chat (`/chat`), Sessions (`/sessions`), Models (`/models`), Diagnostics (`/diagnostics`), Memory (`/memory`), Goals (`/goals`), Self-awareness (`/self`), and Settings (`/settings`) pages; shared CSS/JavaScript are served from `/static/app.css` and `/static/app.js`.
- **Cloud AI providers:** Gemini, OpenAI, Anthropic Claude, OpenRouter, Groq, DeepSeek, Together AI, Mistral, xAI, Fireworks AI, Cerebras, and custom OpenAI-compatible endpoints.
- **LiteRT-LM Python API** local inference (`litert_lm.Engine` / `create_conversation`; no CLI subprocess for inference).
- **Auto / Cloud / Local / Hybrid** backend modes.
- **Persistent conversation history**, memory facts, goals, and sessions.
- **Memory manager** to add and forget saved facts.
- **Goal tracker** to create and complete goals.
- **Self-critique and proactive settings** persisted locally.
- **Provider control panel** for provider selection, model override, API key setup, custom HTTPS/local endpoint, and configured-key status without exposing secrets.
- **Self-awareness / Self-X page** for agent identity, mission, operational state, and explicit self-review; this is operational introspection, not a claim of sentience.
- **Dynamic provider discovery API** (`/api/providers`) and background model-download jobs with status polling (`/api/downloads`).
- **Explicitly confirmed model downloads** from registry-listed Hugging Face `.litertlm` artifacts; no automatic download at startup.
- **API documentation** at `/schema/swagger` and ReDoc at `/schema`.
- **Local-first storage** under `~/.terminal_ai/`; local models under `~/terminal-ai/models/`.
- **Safe default:** web chat starts with agent tool execution disabled. Do not expose the server to untrusted networks.

## Install

Python 3.10+ is recommended. From the repository root:

### Linux / macOS / WSL

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` locally and add your own `GEMINI_API_KEY`. Keep real credentials out of Git.

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

### Setup helpers

- Linux/macOS/WSL: `sh install.sh`
- Windows PowerShell: `./install.ps1`

## Run the web application

```bash
# Development mode (reload on code changes)
.venv/bin/litestar --app app:app run --reload --host 127.0.0.1 --port 8000

# Or use Uvicorn directly
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

On Windows, use `.venv\Scripts\litestar.exe` or `.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000`.

Open **http://127.0.0.1:8000** in your browser. API docs: **http://127.0.0.1:8000/schema/swagger**.

For development, you can also run `python -m litestar --app app:app run --reload` where supported by the installed Litestar CLI.

## Configure models

Example local `.env` file:

```dotenv
GEMINI_API_KEY=replace_with_your_real_key
HF_TOKEN=replace_with_your_huggingface_token
# Optional: TERMINAL_AI_MODE=auto
```

- `GEMINI_API_KEY`: required for Gemini cloud mode.
- `HF_TOKEN`: optional; needed only for gated Hugging Face downloads.
- `TERMINAL_AI_MODE`: optional initial mode: `auto`, `cloud`, `local`, or `hybrid`.
- `TERMINAL_AI_STATE`: override the state directory.
- `TERMINAL_AI_MODELS`: override the local model directory.
- `TERMINAL_AI_GEMINI_MODEL`: override the Gemini model name.

The application loads environment values from the process environment and the local `.env` file. Existing process environment variables take precedence. A local `.litertlm` model must already be installed and supported by the LiteRT-LM Python API; the web app does not silently download large model files on startup.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/status` | Health and backend status |
| POST | `/api/chat` | Send a chat message |
| POST | `/api/chat/clear` | Clear the active conversation |
| GET | `/api/memory` | Read saved memory |
| POST | `/api/memory` | Save a fact |
| POST | `/api/memory/forget` | Forget facts matching a key |
| GET | `/api/goals` | List goals |
| POST | `/api/goals` | Create a goal |
| POST | `/api/goals/{goal_id}/complete` | Complete a goal |
| GET | `/api/sessions` | List saved sessions |
| GET | `/api/models` | List supported models and installed local files |
| GET | `/api/models/{model_id}` | Get one registered model and installation state |
| GET | `/api/providers` | Discover provider integrations and configuration |
| POST | `/api/models/download` | Queue an explicitly confirmed registered `.litertlm` download |
| GET | `/api/downloads` | List background download jobs and observed progress |
| GET | `/api/diagnostics` | Local app, runtime, storage, and backend diagnostics |
| GET / PATCH | `/api/settings` | Read/update app settings |

## Storage

- State: `~/.terminal_ai/` (or `TERMINAL_AI_STATE`)
- Local models: `~/terminal-ai/models/` (or `TERMINAL_AI_MODELS`)
- Web settings: `~/.terminal_ai/web_settings.json`

## Security notes

- The web app binds to `127.0.0.1` in the documented run commands.
- Tool execution is disabled in the web chat by default.
- Never put real API keys in source files, issues, screenshots, or commits.
- Before exposing the service on a LAN or public host, add authentication, CSRF protections, rate limiting, and a reverse proxy/TLS configuration.
- The app is self-hosted; it does not require Firebase or a mandatory hosted database.

## Development and tests

```bash
python -m py_compile app.py terminal_ai.py
python -m pytest
```

Litestar documentation: https://docs.litestar.dev/2/


## Cloud API provider configuration

Open Settings → Cloud AI provider, choose a provider, optionally enter a model ID, and paste its API key. The app writes credentials to the local .env file and never returns the key to the browser. Cloud mode uses the selected provider; Auto and Hybrid can use it alongside a local .litertlm model. LiteRT-LM remains the local inference runtime.

Supported provider environment keys include OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY, DEEPSEEK_API_KEY, TOGETHER_API_KEY, MISTRAL_API_KEY, XAI_API_KEY, FIREWORKS_API_KEY, CEREBRAS_API_KEY, and TERMINAL_AI_CUSTOM_API_KEY. Custom endpoints require HTTPS, except loopback URLs for local servers.

## Operational self-awareness

The Self-awareness page exposes the agent identity, mission, backend/mode state, and a user-triggered operational self-review. Reviews are saved locally in ~/.terminal_ai/self_reflection.json. This is a software self-model and reflection workflow; it does not imply subjective experience or consciousness. The review cannot execute tools or grant itself additional permissions.
