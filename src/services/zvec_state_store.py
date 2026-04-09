"""Local-first metadata store backed by a zvec-designated SQLite file."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

try:
    import zvec  # type: ignore  # noqa: F401
    ZVEC_AVAILABLE = True
except Exception:
    ZVEC_AVAILABLE = False


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1


class ZvecStateStore:
    """Persist app metadata (recent files + sync state) in a local DB."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or (Path.home() / ".fastmoviemaker" / "state.zvec")
        self._conn: sqlite3.Connection | None = None
        self._error: str = ""
        self._connect()

    @property
    def available(self) -> bool:
        return self._conn is not None

    @property
    def error(self) -> str:
        return self._error

    def close(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = None

    def get_recent_files(self) -> list[str]:
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT path FROM recent_files ORDER BY sort_index ASC"
        ).fetchall()
        return [str(row[0]) for row in rows if row and str(row[0]).strip()]

    def set_recent_files(self, paths: list[str]) -> None:
        conn = self._require_conn()
        normalized = _normalize_path_list(paths)
        with conn:
            conn.execute("DELETE FROM recent_files")
            for idx, path in enumerate(normalized):
                conn.execute(
                    "INSERT INTO recent_files(path, sort_index) VALUES(?, ?)",
                    (path, idx),
                )

    def clear_recent_files(self) -> None:
        conn = self._require_conn()
        with conn:
            conn.execute("DELETE FROM recent_files")

    def get_sync_state_map(self) -> dict[str, dict[str, str]]:
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT file_key, last_hash, updated_at FROM sync_state"
        ).fetchall()
        out: dict[str, dict[str, str]] = {}
        for row in rows:
            file_key = str(row[0]).strip()
            if not file_key:
                continue
            out[file_key] = {
                "last_hash": str(row[1]).strip(),
                "updated_at": str(row[2]).strip(),
            }
        return out

    def set_sync_state_map(self, state: dict[str, dict[str, str]]) -> None:
        conn = self._require_conn()
        normalized = _normalize_sync_state(state)
        with conn:
            conn.execute("DELETE FROM sync_state")
            for file_key, entry in normalized.items():
                conn.execute(
                    (
                        "INSERT INTO sync_state(file_key, last_hash, updated_at) "
                        "VALUES(?, ?, ?)"
                    ),
                    (
                        file_key,
                        entry.get("last_hash", ""),
                        entry.get("updated_at", ""),
                    ),
                )

    def _connect(self) -> None:
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._db_path))
            if not ZVEC_AVAILABLE:
                LOGGER.warning("zvec module is unavailable; using sqlite-compatible mode.")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._ensure_schema(conn)
            self._conn = conn
        except Exception as exc:
            self._error = str(exc)
            LOGGER.warning("Failed to initialize zvec state store: %s", exc)
            self._conn = None

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recent_files (
                path TEXT PRIMARY KEY,
                sort_index INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                file_key TEXT PRIMARY KEY,
                last_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.commit()

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError(self._error or "zvec state store is unavailable")
        return self._conn


def _normalize_path_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
        token = str(item).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _normalize_sync_state(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for raw_key, raw_entry in value.items():
        key = str(raw_key).strip()
        if not key or not isinstance(raw_entry, dict):
            continue
        out[key] = {
            "last_hash": str(raw_entry.get("last_hash", "")).strip(),
            "updated_at": str(raw_entry.get("updated_at", "")).strip(),
        }
    return out
