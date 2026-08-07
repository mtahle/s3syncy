"""SQLite-backed metadata index for synced files.

Stores per-file metadata so we can:
  • detect local changes without re-hashing every file
  • search / list the remote tree without calling S3
  • pull individual files quickly by looking up their S3 key
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional

log = logging.getLogger(__name__)

# Each row in the ``files`` table.
SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    rel_path       TEXT    PRIMARY KEY,
    sync_root      TEXT    NOT NULL,
    size           INTEGER NOT NULL DEFAULT 0,
    local_mtime    REAL    NOT NULL DEFAULT 0,
    local_hash     TEXT    NOT NULL DEFAULT '',
    s3_key         TEXT    NOT NULL DEFAULT '',
    s3_etag        TEXT    NOT NULL DEFAULT '',
    s3_mtime       TEXT    NOT NULL DEFAULT '',
    last_synced    TEXT    NOT NULL DEFAULT '',
    status         TEXT    NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_files_s3key   ON files (s3_key);
CREATE INDEX IF NOT EXISTS idx_files_status  ON files (status);
CREATE INDEX IF NOT EXISTS idx_files_root    ON files (sync_root);

-- Full-text search on paths
CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
    USING fts5(rel_path, content=files, content_rowid=rowid);

-- Triggers to keep FTS in sync with the main table
CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
    INSERT INTO files_fts(rowid, rel_path) VALUES (new.rowid, new.rel_path);
END;
CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, rel_path) VALUES('delete', old.rowid, old.rel_path);
END;
CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, rel_path) VALUES('delete', old.rowid, old.rel_path);
    INSERT INTO files_fts(rowid, rel_path) VALUES (new.rowid, new.rel_path);
END;
"""


class FileRecord:
    """Plain data object returned by queries."""

    __slots__ = (
        "rel_path", "sync_root", "size", "local_mtime", "local_hash",
        "s3_key", "s3_etag", "s3_mtime", "last_synced", "status",
    )

    def __init__(self, row: tuple) -> None:
        (
            self.rel_path, self.sync_root, self.size, self.local_mtime,
            self.local_hash, self.s3_key, self.s3_etag, self.s3_mtime,
            self.last_synced, self.status,
        ) = row

    def __repr__(self) -> str:
        return f"<FileRecord {self.rel_path!r} status={self.status}>"


class SyncIndex:
    """Thread-safe SQLite index manager."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._local = threading.local()
        # Initialise schema on first open.
        with self._conn() as conn:
            conn.executescript(SCHEMA)
        log.info("Index opened at %s", db_path)

    # ── connection management ───────────────────────────────────────────

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        """One connection per thread, auto-commit."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path), timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # ── CRUD ────────────────────────────────────────────────────────────

    def upsert(
        self,
        rel_path: str,
        sync_root: str,
        *,
        size: int = 0,
        local_mtime: float = 0.0,
        local_hash: str = "",
        s3_key: str = "",
        s3_etag: str = "",
        s3_mtime: str = "",
        status: str = "synced",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO files
                    (rel_path, sync_root, size, local_mtime, local_hash,
                     s3_key, s3_etag, s3_mtime, last_synced, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    sync_root   = excluded.sync_root,
                    size        = excluded.size,
                    local_mtime = excluded.local_mtime,
                    local_hash  = excluded.local_hash,
                    s3_key      = excluded.s3_key,
                    s3_etag     = excluded.s3_etag,
                    s3_mtime    = excluded.s3_mtime,
                    last_synced = excluded.last_synced,
                    status      = excluded.status
                """,
                (rel_path, sync_root, size, local_mtime, local_hash,
                 s3_key, s3_etag, s3_mtime, now, status),
            )

    def get(self, rel_path: str) -> Optional[FileRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM files WHERE rel_path = ?", (rel_path,)
            ).fetchone()
        return FileRecord(row) if row else None

    def delete(self, rel_path: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM files WHERE rel_path = ?", (rel_path,))

    def all_records(self, sync_root: Optional[str] = None) -> List[FileRecord]:
        with self._conn() as conn:
            if sync_root:
                rows = conn.execute(
                    "SELECT * FROM files WHERE sync_root = ?", (sync_root,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM files").fetchall()
        return [FileRecord(r) for r in rows]

    # ── search / query ─────────────────────────────────────────────────

    def search(self, query: str, limit: int = 50) -> List[FileRecord]:
        """Full-text search on file paths.  Supports ``*`` wildcards."""
        fts_query = query.replace("*", " ").strip()
        if not fts_query:
            return []
        # Wrap each token with * for prefix matching.
        tokens = [f'"{t}"*' for t in fts_query.split()]
        fts_expr = " AND ".join(tokens)
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT f.* FROM files f
                JOIN files_fts ON files_fts.rowid = f.rowid
                WHERE files_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_expr, limit),
            ).fetchall()
        return [FileRecord(r) for r in rows]

    def list_folder(self, prefix: str, limit: int = 200) -> List[FileRecord]:
        """List files whose path starts with *prefix*."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM files WHERE rel_path LIKE ? LIMIT ?",
                (prefix.rstrip("/") + "/%", limit),
            ).fetchall()
        return [FileRecord(r) for r in rows]

    def stats(self) -> dict:
        """Return quick aggregate stats."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            synced = conn.execute(
                "SELECT COUNT(*) FROM files WHERE status = 'synced'"
            ).fetchone()[0]
            total_size = conn.execute(
                "SELECT COALESCE(SUM(size), 0) FROM files"
            ).fetchone()[0]
        return {"total_files": total, "synced": synced, "total_size_bytes": total_size}

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None
