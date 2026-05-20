#!/usr/bin/env python3
"""Print loop_upload_interval (seconds) from upload_config.json or config.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT = 300


def main() -> int:
    for name in ("upload_config.json", "config.json"):
        path = SCRIPT_DIR / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "loop_upload_interval" in data:
            print(int(data["loop_upload_interval"]))
            return 0
    print(DEFAULT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
