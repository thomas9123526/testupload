#!/usr/bin/env python3
"""
Resumable SFTP uploader for the material/ folder.

- Mirrors the local material/ folder tree on the server (same subfolders)
- Tracks per-file upload status in config.json (including uploaded_success filename list)
- Caches local SHA-256 scans in cache.json (append-only material/ — skip re-hash for known files)
- Exits on network/server failure or transfer stall (progress saved in config.json)
- Skips remote files that match local content (SHA-256 + size)
- Optional server-side hash via linux/calculate_hash.py over SSH exec (see server_calculate_hash_script)
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
    settings.setdefault("scan_cache_file", "cache.json")
    settings.setdefault("network_check_interval_seconds", 10)
    settings.setdefault("ssh_connect_timeout_seconds", 30)
    settings.setdefault("stall_timeout_seconds", 600)
    merge_config_json_settings(settings)
    script = str(settings.get("server_calculate_hash_script", "")).strip().replace("\\", "/")
    settings["server_calculate_hash_script"] = script
    return settings


def merge_config_json_settings(settings: dict[str, Any]) -> None:
    """Apply optional keys from local config.json (e.g. server_calculate_hash_script)."""
    path = status_path(settings)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if data.get("server_calculate_hash_script"):
        settings["server_calculate_hash_script"] = str(
            data["server_calculate_hash_script"]
        ).strip()


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
        return {
            "version": 1,
            "auto_upload_retry_seconds": 300,
            "uploaded_success": [],
            "files": {},
        }

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    data.setdefault("version", 1)
    data.setdefault("files", {})
    data.setdefault("auto_upload_retry_seconds", 300)
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


def scan_cache_path(settings: dict[str, Any]) -> Path:
    path = Path(settings["scan_cache_file"])
    if not path.is_absolute():
        path = SCRIPT_DIR / path
    return path


def load_scan_cache(settings: dict[str, Any]) -> dict[str, Any]:
    path = scan_cache_path(settings)
    if not path.exists():
        return {"version": 1, "files": {}}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    data.setdefault("version", 1)
    data.setdefault("files", {})
    return data


def save_scan_cache(settings: dict[str, Any], cache: dict[str, Any]) -> None:
    path = scan_cache_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(path)


def prune_scan_cache(cache: dict[str, Any], known_paths: set[str]) -> None:
    cache["files"] = {
        rel_path: record
        for rel_path, record in cache.get("files", {}).items()
        if rel_path in known_paths
    }


def local_file_info(
    rel_path: str,
    path: Path,
    status: dict[str, Any],
    cache: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Return file size/hash; reuse config.json or cache.json when size unchanged."""
    stat = path.stat()
    size = stat.st_size

    status_record = status.get("files", {}).get(rel_path)
    if (
        status_record
        and status_record.get("size") == size
        and status_record.get("sha256")
    ):
        return {"size": size, "sha256": status_record["sha256"]}, True

    cache_record = cache.get("files", {}).get(rel_path)
    if (
        cache_record
        and cache_record.get("size") == size
        and cache_record.get("sha256")
    ):
        return {"size": size, "sha256": cache_record["sha256"]}, True

    digest = sha256_file(path)
    cache.setdefault("files", {})[rel_path] = {
        "size": size,
        "sha256": digest,
        "cached_at": utc_now(),
    }
    return {"size": size, "sha256": digest}, False


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


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

    _IDLE_SHOW_AFTER_SECONDS = 2

    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds
        self._last_at = time.time()
        self._lock = threading.Lock()
        self._abort = threading.Event()
        self._activity = "Starting"
        self._detail = ""
        self._last_status_line = ""

    def set_activity(self, activity: str, detail: str = "") -> None:
        with self._lock:
            self._activity = activity
            self._detail = detail
            self._last_status_line = ""

    def note(self, nbytes: int) -> None:
        if nbytes > 0:
            with self._lock:
                self._last_at = time.time()
                self._last_status_line = ""

    def touch(self) -> None:
        with self._lock:
            self._last_at = time.time()
            self._last_status_line = ""

    def idle_seconds(self) -> float:
        with self._lock:
            return time.time() - self._last_at

    def remaining_seconds(self) -> int:
        return max(0, int(self.timeout_seconds - self.idle_seconds()))

    def _format_status_line(self) -> str:
        with self._lock:
            activity = self._activity
            detail = self._detail
        idle = int(self.idle_seconds())
        remaining = self.remaining_seconds()
        if detail:
            reason = f"{activity} — {detail}"
        else:
            reason = activity
        return (
            f"      Waiting: {reason} "
            f"(idle {idle}s, stall in {remaining}s) "
        )

    def clear_countdown(self) -> None:
        if self._last_status_line:
            print("\r" + (" " * len(self._last_status_line)) + "\r", end="", flush=True)
            self._last_status_line = ""

    def _show_status_if_idle(self) -> None:
        if self.idle_seconds() < self._IDLE_SHOW_AFTER_SECONDS:
            if self._last_status_line:
                self.clear_countdown()
            return
        line = self._format_status_line()
        if line == self._last_status_line:
            return
        self._last_status_line = line
        print(f"\r{line}", end="", flush=True)

    def check(self) -> None:
        idle = self.idle_seconds()
        if idle > self.timeout_seconds:
            self.clear_countdown()
            with self._lock:
                activity = self._activity
                detail = self._detail
            where = f"{activity}: {detail}" if detail else activity
            raise TransferStalledError(
                f"No data transferred for {int(idle)}s while {where} "
                f"(limit: {self.timeout_seconds}s in upload_config.json)"
            )

    def start_watchdog(
        self,
        on_stall: Callable[[], None] | None = None,
    ) -> threading.Event:
        stop = threading.Event()

        def watcher() -> None:
            while not stop.wait(1):
                if self._abort.is_set():
                    return
                self._show_status_if_idle()
                if self.idle_seconds() > self.timeout_seconds:
                    self.clear_countdown()
                    if on_stall is not None:
                        on_stall()
                    self._abort.set()
                    return
            self.clear_countdown()

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


def connect_ssh(
    settings: dict[str, Any],
    tracker: TransferTracker | None = None,
) -> tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    """Connect with retries; SFTP-only (no shell) for shared-host compatibility."""
    max_attempts = 3
    last_error: BaseException | None = None
    connect_kwargs = ssh_connect_kwargs(settings)
    target = f"{settings['username']}@{settings['host']}:{settings['port']}"

    for attempt in range(1, max_attempts + 1):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if tracker is not None:
                detail = target if attempt == 1 else f"{target} (retry {attempt}/{max_attempts})"
                tracker.set_activity("Connecting SSH/SFTP", detail)
            if attempt > 1:
                print(f"  Retry {attempt}/{max_attempts} ...")
            client.connect(**connect_kwargs)
            transport = client.get_transport()
            if transport is not None:
                transport.set_keepalive(30)
            if tracker is not None:
                tracker.set_activity("Opening SFTP session", target)
            print("  Opening SFTP session...")
            sftp = client.open_sftp()
            if tracker is not None:
                tracker.touch()
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
    tracker: TransferTracker | None = None,
) -> None:
    """Create the same folder tree on the server as inside material/."""
    remote_base = resolve_remote_path(server_upload_path, "")
    local_dirs = scan_local_directories(local_root)

    if tracker is not None:
        tracker.set_activity("Creating remote folders", remote_base)

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


def connect_exec_client(settings: dict[str, Any]) -> paramiko.SSHClient:
    """SSH connection for remote commands only (separate from SFTP session)."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(**ssh_connect_kwargs(settings))
    transport = client.get_transport()
    if transport is not None:
        transport.set_keepalive(30)
    return client


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def remote_file_info_via_script(
    exec_client: paramiko.SSHClient,
    script_path: str,
    remote_path: str,
    settings: dict[str, Any],
    tracker: TransferTracker | None = None,
    label: str = "",
) -> dict[str, Any] | None:
    """Run calculate_hash.py on the server via SSH exec (not SFTP)."""
    display = label or remote_path
    if tracker is not None:
        tracker.set_activity("Server hash script running", display)
        tracker.touch()

    timeout = int(settings["ssh_connect_timeout_seconds"])
    quoted_script = shell_quote(script_path)
    quoted_file = shell_quote(remote_path)
    last_error = ""

    for python_bin in ("python3", "python"):
        command = f"{python_bin} {quoted_script} {quoted_file}"
        try:
            _, stdout, stderr = exec_client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
        except Exception as error:
            last_error = str(error)
            if is_ssh_disconnect(error):
                raise SSHDisconnectedError(str(error)) from error
            continue

        if exit_code != 0:
            last_error = err or output or f"exit {exit_code}"
            if "not_found" in output or exit_code == 1:
                return None
            continue

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            last_error = f"invalid JSON from server script: {output[:200]}"
            continue

        if data.get("error") == "not_found":
            return None

        if "size" in data and "sha256" in data:
            if tracker is not None:
                tracker.note(len(output.encode("utf-8")))
            return {"size": int(data["size"]), "sha256": str(data["sha256"])}

        last_error = f"unexpected script output: {output[:200]}"

    raise RuntimeError(
        f"Server hash script failed for {remote_path}: {last_error or 'unknown error'}"
    )


def remote_file_info_via_sftp(
    sftp: paramiko.SFTPClient,
    remote_path: str,
    tracker: TransferTracker | None = None,
    label: str = "",
) -> dict[str, Any] | None:
    """Download file over SFTP and hash locally (fallback when server script unavailable)."""
    display = label or remote_path
    if tracker is not None:
        tracker.set_activity("Checking remote file on server", display)
    try:
        attr = sftp.stat(remote_path)
    except OSError:
        return None

    digest = hashlib.sha256()
    try:
        if tracker is not None:
            tracker.set_activity("Reading remote file hash (SFTP)", display)
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


def remote_file_info(
    sftp: paramiko.SFTPClient,
    remote_path: str,
    tracker: TransferTracker | None = None,
    label: str = "",
    *,
    settings: dict[str, Any] | None = None,
    exec_client: paramiko.SSHClient | None = None,
    use_server_hash_script: bool = False,
) -> dict[str, Any] | None:
    script_path = ""
    if settings is not None:
        script_path = str(settings.get("server_calculate_hash_script", "")).strip()

    if use_server_hash_script and exec_client is not None and script_path:
        try:
            return remote_file_info_via_script(
                exec_client,
                script_path,
                remote_path,
                settings,
                tracker,
                label,
            )
        except (SSHDisconnectedError, TransferStalledError):
            raise
        except Exception as error:
            print(f"  {FAIL} Server hash script failed: {error}")
            print("  Falling back to SFTP hash for this file.")

    return remote_file_info_via_sftp(sftp, remote_path, tracker, label)


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


def format_progress_line(label: str, done: int, total: int, speed: float) -> str:
    percent = (done / total * 100) if total else 100.0
    return (
        f"{label} — {format_bytes(done)} / {format_bytes(total)} "
        f"({percent:5.1f}%) @ {format_speed(speed)}"
    )


def upload_with_retry(
    settings: dict[str, Any],
    sftp: paramiko.SFTPClient,
    local_path: Path,
    remote_path: str,
    total_size: int,
    tracker: TransferTracker,
    label: str,
) -> None:
    if tracker is not None:
        tracker.set_activity("Preparing remote path", label)
    ensure_remote_dir(sftp, remote_path)
    if tracker is not None:
        tracker.set_activity("Uploading", label)
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
        line = format_progress_line(label, done, total, speed)
        print(f"\r{line}", end="", flush=True)

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
        if tracker is not None:
            tracker.set_activity("Uploading (no bytes yet)", label)
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
    print(f"\r{format_progress_line(label, total_size, total_size, avg_speed)} (avg)")
    print()


def process_files(settings: dict[str, Any]) -> int:
    local_root = SCRIPT_DIR / settings["local_dir"]
    status = load_status(settings)
    cache = load_scan_cache(settings)
    all_files = scan_local_files(local_root)

    if not all_files:
        print(f"No files found in {local_root}")
        return 0

    print("Scanning local files...")
    queue: list[tuple[str, Path, dict[str, Any]]] = []
    cached_count = 0
    hashed_count = 0
    known_paths = {rel_path for rel_path, _ in all_files}

    for rel_path, path in all_files:
        info, from_cache = local_file_info(rel_path, path, status, cache)
        if from_cache:
            cached_count += 1
        else:
            hashed_count += 1
        if needs_upload(rel_path, info, status):
            queue.append((rel_path, path, info))

    prune_scan_cache(cache, known_paths)
    save_scan_cache(settings, cache)

    total = len(all_files)
    pending = len(queue)
    print(
        f"Found {total} file(s). "
        f"{cached_count} from cache, {hashed_count} hashed. "
        f"{pending} need upload/check, {total - pending} already marked uploaded.\n"
    )

    if pending == 0:
        print("Nothing to do.")
        return 0

    server_path = settings["server_upload_path"]
    remote_base = resolve_remote_path(server_path, "")
    client: paramiko.SSHClient | None = None
    sftp: paramiko.SFTPClient | None = None
    exec_client: paramiko.SSHClient | None = None
    use_server_hash_script = False
    tracker = TransferTracker(int(settings["stall_timeout_seconds"]))
    watchdog_stop: threading.Event | None = None
    hash_script = str(settings.get("server_calculate_hash_script", "")).strip()

    def open_session() -> None:
        nonlocal client, sftp, exec_client, use_server_hash_script, watchdog_stop
        close_ssh(client, sftp)
        if exec_client is not None:
            close_ssh(exec_client, None)
            exec_client = None
        use_server_hash_script = False
        if watchdog_stop is not None:
            watchdog_stop.set()
        tracker.set_activity(
            "Checking network",
            f"{settings['host']}:{settings['port']}",
        )
        ensure_network(settings)
        print(f"Connecting to {settings['username']}@{settings['host']}:{settings['port']} ...")
        client, sftp = connect_ssh(settings, tracker)
        tracker.touch()

        if hash_script:
            if not hash_script.startswith("/"):
                print(
                    f"{FAIL} server_calculate_hash_script must be an absolute path, "
                    f"got: {hash_script!r}"
                )
            else:
                try:
                    sftp.stat(hash_script)
                    exec_client = connect_exec_client(settings)
                    use_server_hash_script = True
                    print(f"Server hash script: {hash_script}")
                except OSError:
                    print(f"{FAIL} Server hash script not found: {hash_script}")
                    print("  Upload linux/calculate_hash.py to that path on the server.")
                    print("  Falling back to SFTP hash (slower for large files).")
                except Exception as error:
                    print(f"{FAIL} Could not open SSH exec session for hash script: {error}")
                    print("  Falling back to SFTP hash.")

        def on_stall() -> None:
            close_ssh(client, sftp)
            if exec_client is not None:
                close_ssh(exec_client, None)

        watchdog_stop = tracker.start_watchdog(on_stall=on_stall)

    open_session()
    print(f"Connected. Server upload path: {remote_base}\n")
    print(f"Stall timeout: {settings['stall_timeout_seconds']}s without data transfer\n")

    uploaded_count = 0
    skipped_count = 0
    processed = 0

    try:
        sync_remote_directory_tree(sftp, server_path, local_root, tracker)

        for rel_path, local_path, info in queue:
            tracker.check()
            processed += 1
            remote_path = resolve_remote_path(settings["server_upload_path"], rel_path)
            prefix = f"[{processed}/{pending}] {rel_path}"

            tracker.set_activity("Pending", f"compare with server: {rel_path}")
            remote_info = remote_file_info(
                sftp,
                remote_path,
                tracker,
                label=prefix,
                settings=settings,
                exec_client=exec_client,
                use_server_hash_script=use_server_hash_script,
            )
            if (
                remote_info is not None
                and remote_info["size"] == info["size"]
                and remote_info["sha256"] == info["sha256"]
            ):
                mark_uploaded(settings, status, rel_path, info, action="skipped_identical")
                skipped_count += 1
                print(f"{prefix} ... {SKIP} skipped (identical on server)")
                continue

            upload_with_retry(
                settings, sftp, local_path, remote_path, info["size"], tracker, prefix
            )

            tracker.set_activity("Verifying upload", prefix)
            verify = remote_file_info(
                sftp,
                remote_path,
                tracker,
                label=prefix,
                settings=settings,
                exec_client=exec_client,
                use_server_hash_script=use_server_hash_script,
            )
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
        tracker.clear_countdown()
        close_ssh(client, sftp)
        if exec_client is not None:
            close_ssh(exec_client, None)

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
