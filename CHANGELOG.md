# Changelog

This file records notable changes to Terminal AI. Dates describe repository changes, not guarantees of compatibility with every platform.

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
