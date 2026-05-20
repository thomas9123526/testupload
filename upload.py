#!/usr/bin/env python3
"""
Resumable SFTP uploader for the material/ folder.

- Mirrors the local material/ folder tree on the server (same subfolders)
- Tracks per-file upload status in config.json
- Retries when the network drops (waits until connectivity returns)
- Exits immediately if the SSH session is lost (restart manually to resume)
- Skips remote files that match local content (SHA-256 + size)
"""

from __future__ import annotations

import hashlib
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import paramiko
    from paramiko.ssh_exception import (
        AuthenticationException,
        NoValidConnectionsError,
        SSHException,
    )
except ImportError:
    print("Missing dependency: paramiko")
    print("Install with: pip install paramiko")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = SCRIPT_DIR / "upload_config.json"
CHECK = "\u2713"  # ✓
SKIP = "\u2298"   # ⊘
FAIL = "\u2717"   # ✗


class SSHDisconnectedError(Exception):
    """Raised when the SSH session is lost and the script must exit."""


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        example = SCRIPT_DIR / "upload_config.example.json"
        print(f"Settings file not found: {SETTINGS_FILE}")
        if example.exists():
            print(f"Copy {example.name} to {SETTINGS_FILE.name} and edit it.")
        sys.exit(1)

    with SETTINGS_FILE.open("r", encoding="utf-8") as handle:
        settings = json.load(handle)

    required = ("host", "port", "username", "password", "local_dir", "remote_dir")
    missing = [key for key in required if not settings.get(key)]
    if missing:
        print(f"Missing settings in {SETTINGS_FILE.name}: {', '.join(missing)}")
        sys.exit(1)

    settings.setdefault("status_file", "config.json")
    settings.setdefault("network_check_interval_seconds", 10)
    settings.setdefault("ssh_connect_timeout_seconds", 30)
    return settings


def status_path(settings: dict[str, Any]) -> Path:
    path = Path(settings["status_file"])
    if not path.is_absolute():
        path = SCRIPT_DIR / path
    return path


def load_status(settings: dict[str, Any]) -> dict[str, Any]:
    path = status_path(settings)
    if not path.exists():
        return {"version": 1, "files": {}}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    data.setdefault("version", 1)
    data.setdefault("files", {})
    return data


def save_status(settings: dict[str, Any], status: dict[str, Any]) -> None:
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
        "socket is closed",
        "server connection dropped",
        "transport is not active",
    )
    return any(marker in message for marker in markers)


def wait_for_network(settings: dict[str, Any]) -> None:
    host = settings["host"]
    port = int(settings["port"])
    interval = int(settings["network_check_interval_seconds"])

    print(f"\nNetwork unavailable. Waiting for {host}:{port} ...")
    while True:
        try:
            with socket.create_connection((host, port), timeout=5):
                print("Network is back.\n")
                return
        except OSError:
            time.sleep(interval)


def connect_ssh(settings: dict[str, Any]) -> tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=settings["host"],
            port=int(settings["port"]),
            username=settings["username"],
            password=settings["password"],
            timeout=int(settings["ssh_connect_timeout_seconds"]),
            banner_timeout=int(settings["ssh_connect_timeout_seconds"]),
            auth_timeout=int(settings["ssh_connect_timeout_seconds"]),
            look_for_keys=False,
            allow_agent=False,
        )
        transport = client.get_transport()
        if transport is not None:
            transport.set_keepalive(30)
        sftp = client.open_sftp()
        return client, sftp
    except (NoValidConnectionsError, AuthenticationException, SSHException, OSError) as error:
        if is_ssh_disconnect(error):
            raise SSHDisconnectedError(str(error)) from error
        raise


def remote_home(client: paramiko.SSHClient) -> str:
    _, stdout, _ = client.exec_command("printf %s \"$HOME\"")
    home = stdout.read().decode("utf-8", errors="replace").strip()
    if not home:
        raise SSHDisconnectedError("Could not determine remote home directory.")
    return home


def resolve_remote_path(remote_home_dir: str, remote_dir: str, rel_path: str) -> str:
    base = remote_dir.replace("\\", "/")
    if base.startswith("~/"):
        base = f"{remote_home_dir}/{base[2:]}"
    elif base == "~":
        base = remote_home_dir
    elif not base.startswith("/"):
        base = f"{remote_home_dir}/{base}"

    base = base.rstrip("/")
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
    remote_home_dir: str,
    remote_dir: str,
    local_root: Path,
) -> None:
    """Create the same folder tree on the server as inside material/."""
    remote_base = resolve_remote_path(remote_home_dir, remote_dir, "")
    local_dirs = scan_local_directories(local_root)

    print(f"Creating remote folder tree under {remote_base} ...")
    ensure_remote_directory(sftp, remote_base)
    print(f"  {CHECK} {remote_base}/")

    for rel_dir in local_dirs:
        remote_directory = resolve_remote_path(remote_home_dir, remote_dir, rel_dir)
        ensure_remote_directory(sftp, remote_directory)
        print(f"  {CHECK} {remote_directory}/")

    if not local_dirs:
        print("  (no subfolders; files upload directly into remote base)")
    print()


def remote_file_info(client: paramiko.SSHClient, remote_path: str) -> dict[str, Any] | None:
    quoted = remote_path.replace("'", "'\"'\"'")
    command = (
        f"if [ -f '{quoted}' ]; then "
        f"stat -c '%s' '{quoted}' && sha256sum '{quoted}' | awk '{{print $1}}'; "
        f"else echo '__MISSING__'; fi"
    )
    _, stdout, stderr = client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        err = stderr.read().decode("utf-8", errors="replace").strip()
        raise SSHDisconnectedError(f"Remote check failed for {remote_path}: {err or exit_code}")

    lines = stdout.read().decode("utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() == "__MISSING__":
        return None

    if len(lines) < 2:
        raise SSHDisconnectedError(f"Unexpected remote check output for {remote_path}")

    return {
        "size": int(lines[0].strip()),
        "sha256": lines[1].strip(),
    }


def format_bytes(num: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(num)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{num} B"


def upload_with_retry(
    settings: dict[str, Any],
    sftp: paramiko.SFTPClient,
    local_path: Path,
    remote_path: str,
    total_size: int,
) -> None:
    transferred = 0
    last_report = 0.0

    def callback(done: int, total: int) -> None:
        nonlocal transferred, last_report
        transferred = done
        now = time.time()
        if now - last_report < 0.2 and done != total:
            return
        last_report = now
        percent = (done / total * 100) if total else 100.0
        print(
            f"\r      progress: {format_bytes(done)} / {format_bytes(total)} ({percent:5.1f}%)",
            end="",
            flush=True,
        )

    while True:
        try:
            ensure_remote_dir(sftp, remote_path)
            sftp.put(str(local_path), remote_path, callback=callback, confirm=True)
            print()
            return
        except Exception as error:
            if is_ssh_disconnect(error):
                raise SSHDisconnectedError(str(error)) from error
            print(f"\n      upload error: {error}")
            wait_for_network(settings)
            print("      retrying upload...")


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

    print(f"Connecting to {settings['username']}@{settings['host']}:{settings['port']} ...")
    client, sftp = connect_ssh(settings)
    home = remote_home(client)
    remote_base = resolve_remote_path(home, settings["remote_dir"], "")
    print(f"Connected. Remote base: {remote_base}\n")

    sync_remote_directory_tree(sftp, home, settings["remote_dir"], local_root)

    uploaded_count = 0
    skipped_count = 0
    processed = 0

    try:
        for rel_path, local_path, info in queue:
            processed += 1
            remote_path = resolve_remote_path(home, settings["remote_dir"], rel_path)
            prefix = f"[{processed}/{pending}] {rel_path}"

            while True:
                try:
                    remote_info = remote_file_info(client, remote_path)
                    if (
                        remote_info is not None
                        and remote_info["size"] == info["size"]
                        and remote_info["sha256"] == info["sha256"]
                    ):
                        mark_uploaded(settings, status, rel_path, info, action="skipped_identical")
                        skipped_count += 1
                        print(f"{prefix} ... {SKIP} skipped (identical on server)")
                        break

                    if remote_info is not None:
                        print(f"{prefix} ... remote differs, uploading")
                    else:
                        print(f"{prefix} ... uploading")

                    upload_with_retry(settings, sftp, local_path, remote_path, info["size"])

                    verify = remote_file_info(client, remote_path)
                    if (
                        verify is None
                        or verify["size"] != info["size"]
                        or verify["sha256"] != info["sha256"]
                    ):
                        raise RuntimeError("Upload finished but remote verification failed.")

                    mark_uploaded(settings, status, rel_path, info, action="uploaded")
                    uploaded_count += 1
                    print(f"{prefix} ... {CHECK} success")
                    break

                except SSHDisconnectedError:
                    raise
                except Exception as error:
                    if is_ssh_disconnect(error):
                        raise SSHDisconnectedError(str(error)) from error
                    print(f"{prefix} ... error: {error}")
                    wait_for_network(settings)
                    print(f"{prefix} ... retrying")
    finally:
        sftp.close()
        client.close()

    print(
        f"\nDone. Uploaded: {uploaded_count}, skipped (identical): {skipped_count}, "
        f"total in material/: {total}"
    )
    return 0


def main() -> int:
    settings = load_settings()
    try:
        return process_files(settings)
    except SSHDisconnectedError as error:
        print(f"\n{FAIL} SSH session lost: {error}")
        print("Script stopped. Start it again manually to resume from config.json.")
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted. Progress saved in config.json.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
