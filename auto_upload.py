#!/usr/bin/env python3
"""
Run upload.py in a loop until success.

- Exit 0 from upload.py → print green success and stop
- Any error → print red reason, countdown (auto_upload_retry_seconds from config.sqlite), retry
- Press any key during countdown → retry immediately
- Ctrl+C → stop (exit 130)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from status_store import StatusStore, read_auto_upload_retry_seconds

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_SQLITE = SCRIPT_DIR / "config.sqlite"
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
    return read_auto_upload_retry_seconds(script_dir=SCRIPT_DIR)


def ensure_config_default() -> None:
    """Ensure status store has auto_upload_retry_seconds default."""
    if not CONFIG_SQLITE.is_file():
        return
    store = StatusStore(CONFIG_SQLITE)
    try:
        if store.get_meta("auto_upload_retry_seconds") is None:
            store.set_meta("auto_upload_retry_seconds", DEFAULT_RETRY_SECONDS)
    finally:
        store.close()


def error_message(exit_code: int) -> str:
    messages = {
        1: "Upload failed: authentication error (exit 1). Check upload_config.json credentials.",
        2: "Upload failed: SSH connection lost (exit 2). Progress saved in config.sqlite.",
        3: "Upload failed: network unavailable (exit 3). Progress saved in config.sqlite.",
        4: "Upload failed: transfer stalled - no data moved (exit 4). Progress saved in config.sqlite.",
        130: "Upload interrupted (Ctrl+C). Auto upload stopped.",
    }
    return messages.get(
        exit_code,
        f"Upload failed with exit code {exit_code}. Progress saved in config.sqlite.",
    )


def run_upload() -> int:
    print("\n=== Starting upload.py ===", flush=True)
    result = subprocess.run(
        [sys.executable, str(UPLOAD_PY)],
        cwd=str(SCRIPT_DIR),
    )
    return int(result.returncode)


def wait_one_second_or_key() -> bool:
    """Sleep up to one second; return True if a key was pressed."""
    if sys.platform == "win32":
        try:
            import msvcrt
        except ImportError:
            time.sleep(1)
            return False

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                msvcrt.getch()
                return True
            time.sleep(0.05)
        return False

    if not sys.stdin.isatty():
        time.sleep(1)
        return False

    try:
        import select
        import termios
        import tty
    except ImportError:
        time.sleep(1)
        return False

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ready, _, _ = select.select([sys.stdin], [], [], 1.0)
        if ready:
            sys.stdin.read(1)
            return True
        return False
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def countdown(seconds: int) -> bool:
    """Count down retry delay. Returns True if the user skipped with a keypress."""
    for remaining in range(seconds, 0, -1):
        print(
            f"\r{YELLOW}Retrying upload in {remaining} seconds... "
            f"(press any key to retry now){RESET}",
            end="",
            flush=True,
        )
        if wait_one_second_or_key():
            print(flush=True)
            cprint("Retrying upload now (key pressed).", YELLOW)
            return True
    print(flush=True)
    return False


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
        print(f"Retry interval: {interval}s (config.sqlite: auto_upload_retry_seconds)")

        try:
            countdown(interval)
        except KeyboardInterrupt:
            print()
            cprint(error_message(130), RED)
            return 130


if __name__ == "__main__":
    sys.exit(main())
