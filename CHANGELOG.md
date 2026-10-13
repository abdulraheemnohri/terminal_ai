# Changelog

## v4.2.0 — 2026-10-13

### New Features
- **EnvManager (.env support)**: loads a `.env` file at startup
  (search: `$TERMINAL_AI_ENV` → `./.env` → `~/.terminal_ai/.env`) and exports
  it without overwriting existing environment variables. `--env-file` flag,
  `--no` autoload via `env_autoload` setting.
- **Env REPL commands**: `/env [pattern]`, `/env-set <k> <v>`,
  `/env-get <k>`, `/env-unset <k>`, `/env-save`. Secret-looking keys
  (key/token/secret/password/credential) are always masked in output.
- **New agent tools**: `sys_info` (python/platform/cpu/disk), `now`
  (date/time with optional strftime format), `find_files` (recursive glob),
  `read_lines` (numbered line ranges), `env` (list/get/set/unset/save env
  vars, secrets masked).
- **New settings**: `debug` (live), `tool_rounds` (live; caps agent tool
  rounds per turn), `history_limit` (caps kept conversation messages),
  `ask_delete` (live; separate confirmation for file deletion),
  `env_autoload` (autoload .env at startup).
- **New REPL commands**: `/history [n]`, `/sysinfo`, `/debug on|off`.
- `.env.example` template; banner now shows env-file status.
- **Full offline test suite** (~75 tests): parsing, router, registry, memory,
  graph, goals, patterns, meta-learner, settings, stats, sessions, env
  manager, forge, journal, file/system tools, hybrid backend, Gemini retry
  logic, and agent turn behavior (including max-rounds and history trim).

### Bug Fixes
- Test-suite issues from the v4.1 rewrite fixed: removed broken
  `builtins` monkeypatch line, replaced fragile chunk-constructing
  `}}}}` replacements, verified router/registry/goal-tool expectations
  against the implementation.

## v4.1.0 — 2026-10-13

### New Features
- **SettingsManager**: persistent `settings.json`; `/settings`, `/set <k> <v>`;
  `--no-settings` flag; live-changeable keys applied immediately.
- **StatsTracker**: usage stats (turns, chars, seconds, tool calls) per backend;
  `/usage` command.
- **SessionManager**: save/load/autosave conversations; `/save-session`,
  `/load-session`, `/sessions`, `--resume <name>` (autosaved as `last` on quit).
- **New agent tools**: `list_dir`, `edit_file`, `append_file`, `delete_file`,
  `copy_file`, `grep_files`, `web_search` (DuckDuckGo, no API key).
- **Cloud retries**: Gemini stream failures retry with exponential backoff
  (`cloud_retries` setting / `--cloud-retries`).
- **Auto-backup**: periodic memory snapshots every N turns
  (`auto_backup_every` setting / `--auto-backup-every`).
- **Transcript export**: `/export <file>` writes markdown or JSON;
  `/save` shares the same implementation.
- **New CLI flags**: `--resume`, `--diagnose`, `--shell-timeout`.
- `/reset` factory reset (backs up memory first, requires typing RESET).

### Bug Fixes
- **Hybrid backend**: mid-stream cloud failure no longer duplicates already
  printed output — fallback only happens when nothing was yielded yet.
- **ToolForge**: `import`/`exec`/`eval` rejection now uses word boundaries;
  words like "important" or "execute" no longer falsely rejected.
- **HFManager.login**: token is now validated *before* being persisted to disk.
- **ToolRegistry._safe_path**: `~` paths are expanded correctly (previously
  relative `~` paths were joined onto the workspace).
- **Journal.read**: returns the last N *entries* properly instead of a
  crude line-window approximation.
- **TaskRouter.classify**: removed dead branch (both paths returned the same).
- **Shell tool**: timeout is configurable (`shell_timeout` setting).
- **`/complete <id>`**: now validates the goal ID exists instead of silently
  claiming success.
- **One-shot mode (`-p`)**: now runs the full agent loop (tools, critique,
  learning) instead of bypassing tools in non-tty mode.

## v4.0.0
- Initial public version: hybrid self-evolving agent, task router, model
  registry, auto downloader, self-diagnosis, pattern learner, memory,
  knowledge graph, goals, journal, skills, tool forge, dreamer, observer,
  critic, proactive advisor.
