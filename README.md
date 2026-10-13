# ⬢ terminal-ai — Hybrid Self-Evolving Terminal Agent (v4.2.0)

A single-file Python terminal AI agent that combines **Google Gemini (cloud)** with
**LiteRT-LM (local 1B models)**, learns from every conversation, and evolves itself
through goals, skills, tool forging, and memory consolidation.

## Features

- 🧭 **Task Router** — auto-selects the best model per prompt (coding → Pro, math → 3 Pro, privacy → local)
- 🔄 **Hybrid Mode** — cloud + local with automatic fallback (no duplicate output on mid-stream failure)
- 📥 **Auto Downloader** — fetches local models from Hugging Face on demand
- 🩺 **Self-Diagnosis** — `/diagnose` checks cloud, local, memory, and disk health
- 📈 **Pattern Learner** — learns your task patterns over time (`/patterns`)
- 🧠 **Memory + Knowledge Graph** — persistent facts, entities, relations
- 🎯 **Goals + Journal** — multi-step planning with self-reflection
- 🛠 **Skills + Tool Forge** — learned procedures, self-written tools
- 💤 **Dreamer** — offline memory consolidation (`/dream`)
- 👁 **Observer** — auto-extracts learnings from each turn
- 🪞 **Self-Critique** — critique + refine pass (`--self-critique`)
- ⚙️ **Settings Manager** — persistent `settings.json`, `/set`, `/settings`
- 📊 **Usage Stats** — per-backend turns/chars/time, `/usage`
- 💾 **Sessions** — save/load conversations, `--resume last`
- 🗂 **File Tools** — `list_dir`, `edit_file`, `append_file`, `delete_file`, `copy_file`, `grep_files`, `web_search`
- ♻️ **Cloud Retries** — exponential backoff on Gemini stream failures
- 🗄 **Auto-Backup** — periodic memory snapshots (`--auto-backup-every N`)
- 🔐 **Env Manager** *(new in 4.2)* — `.env` file support: autoload at startup,
  `/env`, `/env-set`, `/env-get`, `/env-unset`, `/env-save`, `--env-file`;
  secrets are masked in output
- 🖥 **System Tools** *(new in 4.2)* — `sys_info`, `now`, `find_files`,
  `read_lines`, `env` agent tools
- ⚙️ **More Settings** *(new in 4.2)* — `debug`, `history_limit`, `tool_rounds`,
  `ask_delete`, `env_autoload` (all live or persisted)

## Install

```bash
pip install google-genai litert-lm huggingface_hub
```

## Quick Start

```bash
export GEMINI_API_KEY="..."      # cloud (required for cloud/hybrid/auto)
export HF_TOKEN="hf_..."         # optional, for gated HF models

# …or put them in a .env file (loaded automatically, see .env.example)
cp .env.example .env

python terminal_ai.py                        # auto mode (default)
python terminal_ai.py --mode hybrid           # cloud + local fallback
python terminal_ai.py --mode local            # offline only
python terminal_ai.py --auto-download        # fetch local model if missing
python terminal_ai.py --resume last          # resume last conversation
python terminal_ai.py --diagnose             # health check and exit
python terminal_ai.py --env-file secrets.env # use a custom .env file
python terminal_ai.py -p "explain quicksort" # one-shot prompt
```

## Modes

| Mode | Behaviour |
|---|---|
| `auto` | Task Router picks the best model per prompt (DEFAULT) |
| `cloud` | Force Gemini only |
| `local` | Force LiteRT-LM only |
| `hybrid` | Try cloud, automatically fall back to local on failure |

## Key Commands

```
/help            all commands        /set k v        change a setting
/models          list models         /settings       show settings
/route <text>    preview routing     /usage          usage stats
/diagnose        self-diagnostic     /save-session   save conversation
/backup          backup memory       /load-session n load a session
/goal <text>     set a goal          /sessions       list sessions
/dream           memory consolidation /export f.md  export transcript
/env [pattern]   list env vars       /env-set k v    set + persist var
/env-get k       show one var        /env-unset k    remove a var
/env-save        write .env file     /history [n]    show recent messages
/sysinfo         system info         /debug on|off   toggle debug logs
/reset           factory reset       /quit           exit
```

## Settings (persisted in `~/.terminal_ai/settings.json`)

`mode`, `gemini_model`, `system`, `autonomy`, `temperature`, `top_p`, `top_k`,
`max_tokens`, `chat_template`, `max_ctx_chars`, `self_critique`, `proactive`,
`confirm_shell`, `shell_timeout`, `auto_backup_every`, `cloud_retries`,
`debug`, `history_limit`, `tool_rounds`, `ask_delete`, `env_autoload`

```bash
/set temperature 0.5      # live-changeable
/set mode local           # applies on next restart
/set tool_rounds 5        # live: max agent tool-call rounds per turn
/set history_limit 20     # caps kept conversation messages
/set debug on             # live: verbose debug logging
```

## Environment (.env) Support

`EnvManager` loads a `.env` file at startup (search order: `TERMINAL_AI_ENV`,
`./.env`, `~/.terminal_ai/.env`) and exports it into the environment without
overwriting existing variables. See `.env.example`. The agent also has an
`env` tool for reading/setting env vars (secrets like API keys/tokens/passwords
are always masked).

## State

Everything lives in `~/.terminal_ai/` (override with `TERMINAL_AI_STATE`):
memory.json, graph.json, goals.json, journal.md, skills.json, meta.json,
patterns.json, tools.json, settings.json, stats.json, sessions/, backups/

Local models live in `~/terminal-ai/models/` (override with `TERMINAL_AI_MODELS`).

## Security

- Shell tool denies destructive commands (`rm -rf /`, `mkfs`, `dd if=`, fork bombs)
- and asks confirmation for `sudo`, `pip install`, `rm`, `chmod`, …
- `delete_file` asks for confirmation (toggle with `ask_delete` setting);
  forged tools reject `import`/`exec`/`eval`
- File tools resolve paths safely; `~` expansion fixed in 4.1
- `.env` values with secret-looking names are masked in all output;
  `.env` is git-ignored
- Secrets are never hardcoded: `GEMINI_API_KEY` / `HF_TOKEN` env vars or `.env` only

## Tests

```bash
pip install pytest
pytest tests/ -v
```

CI runs the full suite on every push to `main` and reports results to the
"CI Test Report" issue.

## License

MIT

---

## اردو میں

**terminal-ai** ایک واحد فائل Python ٹرمینل ایجنٹ ہے جو Gemini (کلاؤڈ) اور LiteRT-LM
(لوکل ماڈل) کو ملاتا ہے۔ ہر بات چیت سے یہ سیکھتا ہے — فیکٹس، صلاحیتیں، اور اہداف
محفوظ کرتا ہے۔

v4.2 نئے فیچرز: **`.env` فائل سپورٹ** (apikeyز `.env` میں رکھیں، خودکار لوڈ ہوتی ہیں)،
نئے سسٹم ٹولز (`sys_info`، `now`، `find_files`، `read_lines`، `env`)، اور مزید
سیٹنگز (`debug`، `history_limit`، `tool_rounds`، `ask_delete`، `env_autoload`)۔
سیکرٹ کلیدز (`/env`) آؤٹ پٹ میں ہمیشہ ماسک رہتی ہیں۔

چلانے کے لیے: `pip install google-genai litert-lm huggingface_hub`، پھر
`GEMINI_API_KEY` سیٹ کریں (یا `.env` فائل بنائیں) اور `python terminal_ai.py` چلائیں۔
