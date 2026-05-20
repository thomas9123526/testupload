#!/usr/bin/env python3
"""Print auto_upload_retry_seconds from config.json or upload_config.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT = 300
KEYS = ("auto_upload_retry_seconds", "loop_upload_interval")


def main() -> int:
    for name in ("config.json", "upload_config.json"):
        path = SCRIPT_DIR / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for key in KEYS:
            if key in data:
                print(int(data[key]))
                return 0
    print(DEFAULT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
