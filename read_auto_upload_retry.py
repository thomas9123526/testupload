#!/usr/bin/env python3
"""Print auto_upload_retry_seconds from config.json (default 300)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG = SCRIPT_DIR / "config.json"
DEFAULT = 300


def main() -> int:
    if CONFIG.is_file():
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            if "auto_upload_retry_seconds" in data:
                print(int(data["auto_upload_retry_seconds"]))
                return 0
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    print(DEFAULT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
