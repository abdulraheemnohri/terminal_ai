"""Execute one approved browser operation from a trusted local terminal.

This is deliberately not an HTTP endpoint. The operation must already be approved
in Command Control, and the operator must also pass --confirm.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import terminal_ai as core
from application.browser_dispatch import execute_approved_browser_operation
from command_control import CommandControl


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation-id", required=True, help="Exact Command Control operation ID")
    parser.add_argument(
        "--confirm", action="store_true", required=True,
        help="Explicitly confirm that the approved browser operation may run now",
    )
    args = parser.parse_args(argv)

    state_dir = Path(core.STATE_DIR)
    settings_path = state_dir / "web_settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise ValueError("Web settings file must contain a JSON object.")
        control = CommandControl(state_dir / "command_control.sqlite3")
        result = execute_approved_browser_operation(
            control, settings, args.operation_id, confirmed=args.confirm
        )
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"Browser dispatch blocked: {str(exc)[:300]}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
