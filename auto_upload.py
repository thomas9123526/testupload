#!/usr/bin/env python3
"""
Run upload.py in a loop until success.

- Exit 0 from upload.py → print green success and stop
- Any error → print red reason, countdown (auto_upload_retry_seconds from config.json), retry
- Ctrl+C → stop (exit 130)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_JSON = SCRIPT_DIR / "config.json"
UPLOAD_PY = SCRIPT_DIR / "upload.py"
DEFAULT_RETRY_SECONDS = 300

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def _reexec_in_project_venv() -> None:
    if os.environ.get("AUTO_UPLOAD_NO_VENV_REEXEC") == "1":
        return
    for venv_python in (
        SCRIPT_DIR / ".venv" / "Scripts" / "python.exe",
        SCRIPT_DIR / ".venv" / "bin" / "python",
    ):
        if not venv_python.is_file():
            continue
        try:
            if Path(sys.executable).resolve() == venv_python.resolve():
                return
        except OSError:
            return
        os.environ["AUTO_UPLOAD_NO_VENV_REEXEC"] = "1"
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


_reexec_in_project_venv()


def enable_ansi_colors() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 4)
    except (AttributeError, OSError):
        pass


def cprint(message: str, color: str) -> None:
    print(f"{color}{message}{RESET}", flush=True)


def read_retry_seconds() -> int:
    if CONFIG_JSON.is_file():
        try:
            data = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
            value = data.get("auto_upload_retry_seconds", DEFAULT_RETRY_SECONDS)
            return max(1, int(value))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    return DEFAULT_RETRY_SECONDS


def ensure_config_default() -> None:
    """Ensure config.json contains auto_upload_retry_seconds default."""
    if not CONFIG_JSON.is_file():
        return
    try:
        data = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
        if "auto_upload_retry_seconds" not in data:
            data["auto_upload_retry_seconds"] = DEFAULT_RETRY_SECONDS
            CONFIG_JSON.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    except (json.JSONDecodeError, OSError):
        pass


def error_message(exit_code: int) -> str:
    messages = {
        1: "Upload failed: authentication error (exit 1). Check upload_config.json credentials.",
        2: "Upload failed: SSH connection lost (exit 2). Progress saved in config.json.",
        3: "Upload failed: network unavailable (exit 3). Progress saved in config.json.",
        4: "Upload failed: transfer stalled - no data moved (exit 4). Progress saved in config.json.",
        130: "Upload interrupted (Ctrl+C). Auto upload stopped.",
    }
    return messages.get(
        exit_code,
        f"Upload failed with exit code {exit_code}. Progress saved in config.json.",
    )


def run_upload() -> int:
    print("\n=== Starting upload.py ===", flush=True)
    result = subprocess.run(
        [sys.executable, str(UPLOAD_PY)],
        cwd=str(SCRIPT_DIR),
    )
    return int(result.returncode)


def countdown(seconds: int) -> None:
    for remaining in range(seconds, 0, -1):
        print(f"\r{YELLOW}Retrying upload in {remaining} seconds...{RESET}", end="", flush=True)
        time.sleep(1)
    print(flush=True)


def main() -> int:
    enable_ansi_colors()

    if not UPLOAD_PY.is_file():
        cprint("upload.py not found.", RED)
        return 1

    ensure_config_default()

    while True:
        try:
            exit_code = run_upload()
        except KeyboardInterrupt:
            print()
            cprint(error_message(130), RED)
            return 130

        if exit_code == 0:
            print()
            cprint("Auto Upload Is Finished", GREEN)
            return 0

        if exit_code == 130:
            print()
            cprint(error_message(130), RED)
            return 130

        print()
        cprint(error_message(exit_code), RED)

        interval = read_retry_seconds()
        print(f"Retry interval: {interval}s (config.json: auto_upload_retry_seconds)")

        try:
            countdown(interval)
        except KeyboardInterrupt:
            print()
            cprint(error_message(130), RED)
            return 130


if __name__ == "__main__":
    sys.exit(main())
