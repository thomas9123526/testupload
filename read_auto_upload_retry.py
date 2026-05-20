#!/usr/bin/env python3
"""Print auto_upload_retry_seconds from status store (default 300)."""
from __future__ import annotations

import sys
from pathlib import Path

from status_store import read_auto_upload_retry_seconds

SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    print(read_auto_upload_retry_seconds(script_dir=SCRIPT_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
