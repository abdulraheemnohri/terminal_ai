# Changelog

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
