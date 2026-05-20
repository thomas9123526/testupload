#!/usr/bin/env python3
"""Compute SHA-256 and size for a file on the Linux server (used by upload.py)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: calculate_hash.py FILEPATH"}))
        return 2

    target = Path(sys.argv[1])
    if not target.is_file():
        print(json.dumps({"error": "not_found", "path": str(target)}))
        return 1

    stat = target.stat()
    result = {
        "path": str(target),
        "size": stat.st_size,
        "sha256": sha256_file(target),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
