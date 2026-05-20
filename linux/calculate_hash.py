#!/usr/bin/env python3
"""Compute SHA-256 and size for a file on the Linux server (used by upload.py)."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime
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


def usage_file_path() -> Path:
    override = os.environ.get("CALCULATE_HASH_USAGE_FILE", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "usage.json"


def current_user() -> str:
    for key in ("LOGNAME", "USER", "USERNAME"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    try:
        import getpass

        return getpass.getuser()
    except Exception:
        return "unknown"


def load_usage(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    if "files" in data and isinstance(data["files"], dict):
        return data["files"]
    return data


def save_usage(path: Path, files: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(files, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(path)


def record_usage(path: Path, absolute_file_path: str, user: str, when: str) -> None:
    files = load_usage(path)
    record = files.setdefault(
        absolute_file_path,
        {"execution_count": 0, "executions": []},
    )
    record["execution_count"] = int(record.get("execution_count", 0)) + 1
    executions = record.setdefault("executions", [])
    if isinstance(executions, list):
        executions.append({"user": user, "time": when})
    save_usage(path, files)


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: calculate_hash.py FILEPATH"}))
        return 2

    target = Path(sys.argv[1]).resolve()
    if not target.is_file():
        print(json.dumps({"error": "not_found", "path": str(target)}))
        return 1

    user = current_user()
    timestamp = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    record_usage(usage_file_path(), str(target), user, timestamp)

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
