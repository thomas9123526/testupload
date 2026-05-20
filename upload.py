#!/usr/bin/env python3
"""
Resumable SFTP uploader for the material/ folder.

- Mirrors the local material/ folder tree on the server (same subfolders)
- Tracks per-file upload status in config.json (including uploaded_success filename list)
- Exits on network/server failure or transfer stall (progress saved in config.json)
- Skips remote files that match local content (SHA-256 + size)
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent


def _reexec_in_project_venv() -> None:
    """Use .venv Python when present so `python upload.py` finds installed deps."""
    if os.environ.get("UPLOAD_NO_VENV_REEXEC") == "1":
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
        os.environ["UPLOAD_NO_VENV_REEXEC"] = "1"
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


_reexec_in_project_venv()

try:
    import paramiko
    from paramiko.ssh_exception import (
        AuthenticationException,
        NoValidConnectionsError,
        SSHException,
    )
except ImportError:
    venv_python = SCRIPT_DIR / ".venv" / "Scripts" / "python.exe"
    print("Missing dependency: paramiko")
    if venv_python.is_file():
        print(f"Project venv not used. Run: {venv_python} upload.py")
        print("Or: .\\.venv\\Scripts\\Activate.ps1  then  python upload.py")
    else:
        print("Create venv: python -m venv .venv")
        print("Then: .\\.venv\\Scripts\\pip.exe install -r requirements.txt")
    sys.exit(1)

SETTINGS_FILE = SCRIPT_DIR / "upload_config.json"
CHECK = "\u2713"  # ✓
SKIP = "\u2298"   # ⊘
FAIL = "\u2717"   # ✗


class SSHDisconnectedError(Exception):
    """Raised when the SSH session is lost."""


class NetworkUnavailableError(Exception):
    """Raised when the server cannot be reached."""


class TransferStalledError(Exception):
    """Raised when no data is transferred within the configured timeout."""


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        example = SCRIPT_DIR / "upload_config.example.json"
        print(f"Settings file not found: {SETTINGS_FILE}")
        if example.exists():
            print(f"Copy {example.name} to {SETTINGS_FILE.name} and edit it.")
        sys.exit(1)

    with SETTINGS_FILE.open("r", encoding="utf-8") as handle:
        settings = json.load(handle)

    required = ("host", "port", "username", "local_dir")
    missing = [key for key in required if not settings.get(key)]
    upload_path = (settings.get("server_upload_path") or settings.get("remote_dir") or "").strip()
    if not upload_path:
        missing.append("server_upload_path")
    password = str(settings.get("password", "")).strip()
    key_path = str(settings.get("private_key_path", "")).strip()
    if not password and not key_path:
        missing.append("password or private_key_path")
    if missing:
        print(f"Missing settings in {SETTINGS_FILE.name}: {', '.join(missing)}")
        sys.exit(1)

    settings["password"] = password
    if key_path:
        key_file = Path(key_path)
        if not key_file.is_absolute():
            key_file = SCRIPT_DIR / key_file
        settings["private_key_path"] = str(key_file)

    settings["server_upload_path"] = upload_path.replace("\\", "/").rstrip("/")
    if not settings["server_upload_path"].startswith("/"):
        print(
            f"server_upload_path must be an absolute server path (start with /), "
            f"got: {settings['server_upload_path']!r}"
        )
        sys.exit(1)
    settings.setdefault("status_file", "config.json")
    settings.setdefault("network_check_interval_seconds", 10)
    settings.setdefault("ssh_connect_timeout_seconds", 30)
    settings.setdefault("stall_timeout_seconds", 600)
    return settings


def status_path(settings: dict[str, Any]) -> Path:
    path = Path(settings["status_file"])
    if not path.is_absolute():
        path = SCRIPT_DIR / path
    return path


def sync_uploaded_success_list(status: dict[str, Any]) -> None:
    """Rebuild flat list of successfully uploaded filenames for config.json."""
    status["uploaded_success"] = sorted(
        rel_path
        for rel_path, record in status.get("files", {}).items()
        if record.get("status") == "uploaded"
    )


def load_status(settings: dict[str, Any]) -> dict[str, Any]:
    path = status_path(settings)
    if not path.exists():
        return {"version": 1, "uploaded_success": [], "files": {}}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    data.setdefault("version", 1)
    data.setdefault("files", {})
    sync_uploaded_success_list(data)
    return data


def save_status(settings: dict[str, Any], status: dict[str, Any]) -> None:
    sync_uploaded_success_list(status)
    path = status_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(status, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def local_file_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "size": stat.st_size,
        "sha256": sha256_file(path),
    }


def scan_local_files(local_root: Path) -> list[tuple[str, Path]]:
    if not local_root.exists():
        print(f"Local folder not found: {local_root}")
        sys.exit(1)

    files: list[tuple[str, Path]] = []
    for path in sorted(local_root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(local_root).as_posix()
            files.append((rel, path))
    return files


def scan_local_directories(local_root: Path) -> list[str]:
    """Return relative directory paths under local_root, deepest paths last."""
    directories: set[str] = set()
    for path in local_root.rglob("*"):
        if path.is_dir():
            directories.add(path.relative_to(local_root).as_posix())
    return sorted(directories, key=lambda value: (value.count("/"), value))


def needs_upload(rel_path: str, info: dict[str, Any], status: dict[str, Any]) -> bool:
    record = status["files"].get(rel_path)
    if not record:
        return True
    if record.get("status") != "uploaded":
        return True
    if record.get("size") != info["size"]:
        return True
    if record.get("sha256") != info["sha256"]:
        return True
    return False


def mark_uploaded(
    settings: dict[str, Any],
    status: dict[str, Any],
    rel_path: str,
    info: dict[str, Any],
    action: str,
) -> None:
    status["files"][rel_path] = {
        "status": "uploaded",
        "size": info["size"],
        "sha256": info["sha256"],
        "action": action,
        "updated_at": utc_now(),
    }
    save_status(settings, status)


def is_ssh_disconnect(error: BaseException) -> bool:
    if isinstance(error, (SSHException, EOFError, ConnectionResetError, BrokenPipeError)):
        return True
    if isinstance(error, OSError) and getattr(error, "errno", None) in {
        104,  # ECONNRESET on Linux
        10054,  # WSAECONNRESET on Windows
        10053,  # WSAECONNABORTED
    }:
        return True
    message = str(error).lower()
    markers = (
        "not connected",
        "connection lost",
        "connection reset",
        "broken pipe",
        "eof",
        "channel closed",
        "socket is closed",
        "server connection dropped",
        "transport is not active",
    )
    return any(marker in message for marker in markers)


def ensure_network(settings: dict[str, Any]) -> None:
    """Verify host:port is reachable; exit path if not."""
    host = settings["host"]
    port = int(settings["port"])
    try:
        with socket.create_connection((host, port), timeout=5):
            return
    except OSError as error:
        raise NetworkUnavailableError(
            f"Cannot connect to {host}:{port} ({error})"
        ) from error


class TransferTracker:
    """Tracks time since last byte moved; aborts if idle too long."""

    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds
        self._last_at = time.time()
        self._lock = threading.Lock()
        self._abort = threading.Event()

    def note(self, nbytes: int) -> None:
        if nbytes > 0:
            with self._lock:
                self._last_at = time.time()

    def touch(self) -> None:
        with self._lock:
            self._last_at = time.time()

    def idle_seconds(self) -> float:
        with self._lock:
            return time.time() - self._last_at

    def check(self) -> None:
        idle = self.idle_seconds()
        if idle > self.timeout_seconds:
            raise TransferStalledError(
                f"No data transferred for {int(idle)}s "
                f"(limit: {self.timeout_seconds}s in upload_config.json)"
            )

    def start_watchdog(
        self,
        on_stall: Callable[[], None] | None = None,
    ) -> threading.Event:
        stop = threading.Event()

        def watcher() -> None:
            while not stop.wait(5):
                if self.idle_seconds() > self.timeout_seconds:
                    if on_stall is not None:
                        on_stall()
                    self._abort.set()
                    return

        threading.Thread(target=watcher, daemon=True).start()
        return stop

    @property
    def aborted(self) -> bool:
        return self._abort.is_set()



def close_ssh(
    client: paramiko.SSHClient | None,
    sftp: paramiko.SFTPClient | None,
) -> None:
    if sftp is not None:
        try:
            sftp.close()
        except Exception:
            pass
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


def ssh_connect_kwargs(settings: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "hostname": settings["host"],
        "port": int(settings["port"]),
        "username": settings["username"],
        "timeout": int(settings["ssh_connect_timeout_seconds"]),
        "banner_timeout": int(settings["ssh_connect_timeout_seconds"]),
        "auth_timeout": int(settings["ssh_connect_timeout_seconds"]),
        "look_for_keys": False,
        "allow_agent": False,
    }
    key_path = settings.get("private_key_path")
    if key_path:
        kwargs["key_filename"] = key_path
        if settings.get("password"):
            kwargs["password"] = settings["password"]
    else:
        kwargs["password"] = settings["password"]
    return kwargs


def connect_ssh(settings: dict[str, Any]) -> tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    """Connect with retries; SFTP-only (no shell) for shared-host compatibility."""
    max_attempts = 3
    last_error: BaseException | None = None
    connect_kwargs = ssh_connect_kwargs(settings)

    for attempt in range(1, max_attempts + 1):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if attempt > 1:
                print(f"  Retry {attempt}/{max_attempts} ...")
            client.connect(**connect_kwargs)
            transport = client.get_transport()
            if transport is not None:
                transport.set_keepalive(30)
            print("  Opening SFTP session...")
            sftp = client.open_sftp()
            return client, sftp
        except AuthenticationException:
            close_ssh(client, None)
            raise
        except (NoValidConnectionsError, SSHException, OSError) as error:
            last_error = error
            close_ssh(client, None)
            if attempt < max_attempts:
                time.sleep(min(5 * attempt, 15))
                continue
            if is_ssh_disconnect(error):
                raise SSHDisconnectedError(str(error)) from error
            raise SSHDisconnectedError(f"Could not open SFTP session: {error}") from error
        except Exception as error:
            last_error = error
            close_ssh(client, None)
            if attempt < max_attempts:
                time.sleep(min(5 * attempt, 15))
                continue
            raise SSHDisconnectedError(str(error)) from error

    raise SSHDisconnectedError(str(last_error or "connection failed"))


def resolve_remote_path(server_upload_path: str, rel_path: str) -> str:
    """Build full remote path: absolute server_upload_path + path under material/."""
    base = server_upload_path.replace("\\", "/").rstrip("/")
    rel_path = rel_path.replace("\\", "/").strip("/")
    if not rel_path:
        return base
    return f"{base}/{rel_path}"


def ensure_remote_directory(sftp: paramiko.SFTPClient, remote_directory: str) -> None:
    """Create remote_directory and every parent directory (mkdir -p)."""
    remote_directory = remote_directory.replace("\\", "/").rstrip("/")
    if not remote_directory:
        return

    parts = remote_directory.split("/")
    current_parts: list[str] = []
    for part in parts:
        if not part:
            current_parts = [""]
            continue
        current_parts.append(part)

        if current_parts == [""]:
            current = "/"
        elif current_parts[0] == "":
            current = "/" + "/".join(current_parts[1:])
        else:
            current = "/".join(current_parts)

        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_path: str) -> None:
    remote_directory = remote_path.rsplit("/", 1)[0]
    ensure_remote_directory(sftp, remote_directory)


def sync_remote_directory_tree(
    sftp: paramiko.SFTPClient,
    server_upload_path: str,
    local_root: Path,
) -> None:
    """Create the same folder tree on the server as inside material/."""
    remote_base = resolve_remote_path(server_upload_path, "")
    local_dirs = scan_local_directories(local_root)

    print(f"Creating remote folder tree under {remote_base} ...")
    ensure_remote_directory(sftp, remote_base)
    print(f"  {CHECK} {remote_base}/")

    for rel_dir in local_dirs:
        remote_directory = resolve_remote_path(server_upload_path, rel_dir)
        ensure_remote_directory(sftp, remote_directory)
        print(f"  {CHECK} {remote_directory}/")

    if not local_dirs:
        print("  (no subfolders; files upload directly into remote base)")
    print()


def remote_file_info(
    sftp: paramiko.SFTPClient,
    remote_path: str,
    tracker: TransferTracker | None = None,
) -> dict[str, Any] | None:
    """Compare remote file via SFTP only (avoids extra SSH exec channels on shared hosts)."""
    try:
        attr = sftp.stat(remote_path)
    except OSError:
        return None

    digest = hashlib.sha256()
    try:
        with sftp.open(remote_path, "rb") as remote_file:
            while True:
                if tracker is not None:
                    tracker.check()
                chunk = remote_file.read(1024 * 1024)
                if not chunk:
                    break
                if tracker is not None:
                    tracker.note(len(chunk))
                digest.update(chunk)
    except TransferStalledError:
        raise
    except Exception as error:
        if is_ssh_disconnect(error):
            raise SSHDisconnectedError(str(error)) from error
        raise

    return {
        "size": attr.st_size,
        "sha256": digest.hexdigest(),
    }


def format_bytes(num: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(num)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{num} B"


def format_speed(bytes_per_sec: float) -> str:
    if bytes_per_sec <= 0:
        return "0 B/s"
    return f"{format_bytes(int(bytes_per_sec))}/s"


def upload_with_retry(
    settings: dict[str, Any],
    sftp: paramiko.SFTPClient,
    local_path: Path,
    remote_path: str,
    total_size: int,
    tracker: TransferTracker,
) -> None:
    ensure_remote_dir(sftp, remote_path)
    start_time = time.time()
    last_report = start_time
    last_done = 0
    put_finished = threading.Event()
    put_error: list[BaseException] = []

    def callback(done: int, total: int) -> None:
        nonlocal last_report, last_done
        if done > last_done:
            tracker.note(done - last_done)
        if tracker.aborted:
            raise TransferStalledError(
                f"No data transferred for {settings['stall_timeout_seconds']}s "
                f"(limit in upload_config.json)"
            )
        tracker.check()
        now = time.time()
        if now - last_report < 0.2 and done != total:
            return
        elapsed = max(now - start_time, 0.001)
        interval = max(now - last_report, 0.001)
        avg_speed = done / elapsed
        instant_speed = (done - last_done) / interval
        speed = instant_speed if last_done > 0 else avg_speed
        last_report = now
        last_done = done
        percent = (done / total * 100) if total else 100.0
        print(
            f"\r      progress: {format_bytes(done)} / {format_bytes(total)} "
            f"({percent:5.1f}%) @ {format_speed(speed)}",
            end="",
            flush=True,
        )

    def do_put() -> None:
        try:
            sftp.put(str(local_path), remote_path, callback=callback, confirm=True)
        except BaseException as error:
            put_error.append(error)
        finally:
            put_finished.set()

    tracker.touch()
    put_thread = threading.Thread(target=do_put, daemon=True)
    put_thread.start()
    while not put_finished.wait(1.0):
        tracker.check()

    put_thread.join()
    if put_error:
        error = put_error[0]
        if isinstance(error, TransferStalledError):
            raise error
        if is_ssh_disconnect(error):
            raise SSHDisconnectedError(str(error)) from error
        raise error

    elapsed = max(time.time() - start_time, 0.001)
    avg_speed = total_size / elapsed if total_size else 0
    print(
        f"\r      progress: {format_bytes(total_size)} / {format_bytes(total_size)} "
        f"(100.0%) @ {format_speed(avg_speed)} (avg)"
    )


def process_files(settings: dict[str, Any]) -> int:
    local_root = SCRIPT_DIR / settings["local_dir"]
    status = load_status(settings)
    all_files = scan_local_files(local_root)

    if not all_files:
        print(f"No files found in {local_root}")
        return 0

    print("Scanning local files...")
    queue: list[tuple[str, Path, dict[str, Any]]] = []
    for rel_path, path in all_files:
        info = local_file_info(path)
        if needs_upload(rel_path, info, status):
            queue.append((rel_path, path, info))

    total = len(all_files)
    pending = len(queue)
    print(f"Found {total} file(s). {pending} need upload/check, {total - pending} already marked uploaded.\n")

    if pending == 0:
        print("Nothing to do.")
        return 0

    ensure_network(settings)

    server_path = settings["server_upload_path"]
    remote_base = resolve_remote_path(server_path, "")
    client: paramiko.SSHClient | None = None
    sftp: paramiko.SFTPClient | None = None
    tracker = TransferTracker(int(settings["stall_timeout_seconds"]))
    watchdog_stop: threading.Event | None = None

    def open_session() -> None:
        nonlocal client, sftp, watchdog_stop
        close_ssh(client, sftp)
        if watchdog_stop is not None:
            watchdog_stop.set()
        ensure_network(settings)
        print(f"Connecting to {settings['username']}@{settings['host']}:{settings['port']} ...")
        client, sftp = connect_ssh(settings)
        tracker.touch()

        def on_stall() -> None:
            close_ssh(client, sftp)

        watchdog_stop = tracker.start_watchdog(on_stall=on_stall)

    open_session()
    print(f"Connected. Server upload path: {remote_base}\n")
    print(f"Stall timeout: {settings['stall_timeout_seconds']}s without data transfer\n")

    uploaded_count = 0
    skipped_count = 0
    processed = 0

    try:
        sync_remote_directory_tree(sftp, server_path, local_root)

        for rel_path, local_path, info in queue:
            tracker.check()
            processed += 1
            remote_path = resolve_remote_path(settings["server_upload_path"], rel_path)
            prefix = f"[{processed}/{pending}] {rel_path}"

            remote_info = remote_file_info(sftp, remote_path, tracker)
            if (
                remote_info is not None
                and remote_info["size"] == info["size"]
                and remote_info["sha256"] == info["sha256"]
            ):
                mark_uploaded(settings, status, rel_path, info, action="skipped_identical")
                skipped_count += 1
                print(f"{prefix} ... {SKIP} skipped (identical on server)")
                continue

            if remote_info is not None:
                print(f"{prefix} ... remote differs, uploading")
            else:
                print(f"{prefix} ... uploading")

            upload_with_retry(
                settings, sftp, local_path, remote_path, info["size"], tracker
            )

            verify = remote_file_info(sftp, remote_path, tracker)
            if (
                verify is None
                or verify["size"] != info["size"]
                or verify["sha256"] != info["sha256"]
            ):
                raise RuntimeError("Upload finished but remote verification failed.")

            mark_uploaded(settings, status, rel_path, info, action="uploaded")
            uploaded_count += 1
            print(f"{prefix} ... {CHECK} success")
    finally:
        if watchdog_stop is not None:
            watchdog_stop.set()
        close_ssh(client, sftp)

    print(
        f"\nDone. Uploaded: {uploaded_count}, skipped (identical): {skipped_count}, "
        f"total in material/: {total}"
    )
    success_list = status.get("uploaded_success", [])
    if success_list:
        print(f"Successful files in {settings['status_file']}: {len(success_list)}")
    return 0


def main() -> int:
    settings = load_settings()
    try:
        return process_files(settings)
    except AuthenticationException:
        auth = "private key" if settings.get("private_key_path") else "password"
        print(
            f"\n{FAIL} SSH authentication failed for "
            f"{settings['username']}@{settings['host']}:{settings['port']} ({auth})."
        )
        print(f"Check {auth} in {SETTINGS_FILE.name}.")
        print("Confirm SFTP/SSH login works in FileZilla or: ssh user@host")
        return 1
    except SSHDisconnectedError as error:
        print(f"\n{FAIL} SSH connection failed: {error}")
        print(f"Progress saved in {settings['status_file']}. Restart to resume.")
        return 2
    except NetworkUnavailableError as error:
        print(f"\n{FAIL} Network unavailable: {error}")
        print(f"Progress saved in {settings['status_file']}. Restart to resume.")
        return 3
    except TransferStalledError as error:
        print(f"\n{FAIL} Transfer stalled: {error}")
        print(f"Progress saved in {settings['status_file']}. Restart to resume.")
        return 4
    except KeyboardInterrupt:
        print(f"\nInterrupted. Progress saved in {settings['status_file']}.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
