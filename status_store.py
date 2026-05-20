#!/usr/bin/env python3
"""SQLite-backed upload status (scales to millions of files without full JSON load/save)."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RETRY_SECONDS = 300
_SCHEMA_VERSION = 1


class StatusStore:
    """Per-file status in SQLite; meta keys in meta table."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS files (
                    rel_path TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    action TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
                """
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('version', ?)",
                (str(_SCHEMA_VERSION),),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return default
        raw = row[0]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def set_meta(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO meta(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, payload),
            )
            self._conn.commit()

    def get_file(self, rel_path: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT status, size, sha256, action, updated_at
                FROM files WHERE rel_path = ?
                """,
                (rel_path,),
            ).fetchone()
        if not row:
            return None
        return {
            "status": row[0],
            "size": int(row[1]),
            "sha256": row[2],
            "action": row[3],
            "updated_at": row[4],
        }

    def upsert_file(self, rel_path: str, record: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO files(rel_path, status, size, sha256, action, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    status = excluded.status,
                    size = excluded.size,
                    sha256 = excluded.sha256,
                    action = excluded.action,
                    updated_at = excluded.updated_at
                """,
                (
                    rel_path,
                    str(record["status"]),
                    int(record["size"]),
                    str(record["sha256"]),
                    record.get("action"),
                    str(record["updated_at"]),
                ),
            )
            self._conn.commit()

    def count_uploaded(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM files WHERE status = 'uploaded'"
            ).fetchone()
        return int(row[0]) if row else 0

    def migrate_from_json(self, json_path: Path) -> int:
        """Import legacy config.json into this database. Returns rows imported."""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        imported = 0
        with self._lock:
            for key in (
                "version",
                "auto_upload_retry_seconds",
                "local_dir",
                "server_calculate_hash_script",
            ):
                if key in data and data[key] is not None:
                    self._conn.execute(
                        """
                        INSERT INTO meta(key, value) VALUES(?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                        (key, json.dumps(data[key], ensure_ascii=False)),
                    )

            files = data.get("files") or {}
            batch: list[tuple[Any, ...]] = []
            for rel_path, record in files.items():
                if not record:
                    continue
                batch.append(
                    (
                        rel_path,
                        str(record.get("status", "uploaded")),
                        int(record.get("size", 0)),
                        str(record.get("sha256", "")),
                        record.get("action"),
                        str(record.get("updated_at", "")),
                    )
                )
                if len(batch) >= 5000:
                    self._conn.executemany(
                        """
                        INSERT OR REPLACE INTO files(
                            rel_path, status, size, sha256, action, updated_at
                        ) VALUES(?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    imported += len(batch)
                    batch.clear()
            if batch:
                self._conn.executemany(
                    """
                    INSERT OR REPLACE INTO files(
                        rel_path, status, size, sha256, action, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                imported += len(batch)
            self._conn.commit()
        return imported


def resolve_status_db_path(settings: dict[str, Any], script_dir: Path = SCRIPT_DIR) -> Path:
    path = Path(settings["status_file"])
    if not path.is_absolute():
        path = script_dir / path
    if path.suffix.lower() == ".json":
        return path.with_suffix(".sqlite")
    if path.suffix.lower() in (".sqlite", ".db"):
        return path
    return path.with_suffix(".sqlite")


def status_json_path(settings: dict[str, Any], script_dir: Path = SCRIPT_DIR) -> Path:
    path = Path(settings["status_file"])
    if not path.is_absolute():
        path = script_dir / path
    if path.suffix.lower() == ".json":
        return path
    return path.with_suffix(".json")


def open_status_store(settings: dict[str, Any], script_dir: Path = SCRIPT_DIR) -> StatusStore:
    db_path = resolve_status_db_path(settings, script_dir)
    json_path = status_json_path(settings, script_dir)
    store = StatusStore(db_path)
    if json_path.is_file():
        migrate = not db_path.is_file()
        if not migrate:
            try:
                migrate = json_path.stat().st_mtime > db_path.stat().st_mtime
            except OSError:
                migrate = False
        if migrate:
            count = store.migrate_from_json(json_path)
            print(f"Migrated {count} file record(s) from {json_path.name} -> {db_path.name}")
    if store.get_meta("auto_upload_retry_seconds") is None:
        store.set_meta("auto_upload_retry_seconds", DEFAULT_RETRY_SECONDS)
    return store


def read_auto_upload_retry_seconds(
    settings: dict[str, Any] | None = None,
    script_dir: Path = SCRIPT_DIR,
) -> int:
    """Read retry interval from status store (SQLite or legacy JSON)."""
    if settings:
        db_path = resolve_status_db_path(settings, script_dir)
        if db_path.is_file():
            store = StatusStore(db_path)
            try:
                value = store.get_meta("auto_upload_retry_seconds")
                if value is not None:
                    return max(1, int(value))
            finally:
                store.close()
        json_path = status_json_path(settings, script_dir)
        if json_path.is_file():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if "auto_upload_retry_seconds" in data:
                    return max(1, int(data["auto_upload_retry_seconds"]))
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        return DEFAULT_RETRY_SECONDS

    for name in ("config.sqlite", "config.json"):
        path = script_dir / name
        if not path.is_file():
            continue
        if path.suffix == ".sqlite":
            store = StatusStore(path)
            try:
                value = store.get_meta("auto_upload_retry_seconds")
                if value is not None:
                    return max(1, int(value))
            finally:
                store.close()
        else:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if "auto_upload_retry_seconds" in data:
                    return max(1, int(data["auto_upload_retry_seconds"]))
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
    return DEFAULT_RETRY_SECONDS
