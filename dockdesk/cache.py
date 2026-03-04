"""
SQLite-backed result cache for DockDesk.

Replaces the per-file JSON cache with a single SQLite database.
Handles 100K+ entries without filesystem metadata thrashing.
Thread-safe for concurrent worker access.

Schema:
    cache_key TEXT PRIMARY KEY  -- SHA-256(file_path|model|content)
    result    TEXT              -- JSON-serialized analysis result
    model     TEXT              -- Model name used
    file_path TEXT              -- Original file path (for debugging)
    created   REAL              -- Unix timestamp
"""

import os
import json
import time
import sqlite3
import hashlib
import threading
from typing import Optional

CACHE_DB_NAME = ".dockdesk_cache.db"

# Thread-local connections for safe concurrent access
_local = threading.local()


def _get_conn(db_path: str) -> sqlite3.Connection:
    """Get or create a thread-local SQLite connection."""
    key = f"conn_{db_path}"
    if not hasattr(_local, key) or getattr(_local, key) is None:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")  # Allow concurrent reads
        conn.execute("PRAGMA synchronous=NORMAL")
        setattr(_local, key, conn)
    return getattr(_local, key)


class ResultCache:
    """SQLite-backed cache for LLM analysis results."""

    def __init__(self, workspace: str):
        self.db_path = os.path.join(workspace, CACHE_DB_NAME)
        self._init_db()

    def _init_db(self):
        """Create table if it doesn't exist."""
        conn = _get_conn(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                result    TEXT NOT NULL,
                model     TEXT,
                file_path TEXT,
                created   REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_model ON cache(model)
        """)
        conn.commit()

    @staticmethod
    def make_key(file_path: str, content: str, model: str) -> str:
        """SHA-256 of file content + model = deterministic cache key."""
        return hashlib.sha256(f"{file_path}|{model}|{content}".encode()).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        """Read cached result. Returns None on miss."""
        try:
            conn = _get_conn(self.db_path)
            row = conn.execute(
                "SELECT result FROM cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if row:
                return json.loads(row[0])
        except Exception:
            pass
        return None

    def put(self, key: str, result: dict, model: str = "", file_path: str = ""):
        """Write result to cache."""
        try:
            conn = _get_conn(self.db_path)
            conn.execute(
                """INSERT OR REPLACE INTO cache (cache_key, result, model, file_path, created)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, json.dumps(result, default=str), model, file_path, time.time()),
            )
            conn.commit()
        except Exception:
            pass

    def clear(self, model: Optional[str] = None):
        """Clear cache. If model specified, only clear entries for that model."""
        try:
            conn = _get_conn(self.db_path)
            if model:
                conn.execute("DELETE FROM cache WHERE model = ?", (model,))
            else:
                conn.execute("DELETE FROM cache")
            conn.commit()
        except Exception:
            pass

    def stats(self) -> dict:
        """Return cache statistics."""
        try:
            conn = _get_conn(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            models = conn.execute(
                "SELECT model, COUNT(*) FROM cache GROUP BY model"
            ).fetchall()
            oldest = conn.execute("SELECT MIN(created) FROM cache").fetchone()[0]
            return {
                "total_entries": total,
                "models": {m: c for m, c in models},
                "oldest_entry": oldest,
                "db_size_mb": os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0,
            }
        except Exception:
            return {"total_entries": 0}

    def evict_older_than(self, max_age_seconds: int):
        """Remove entries older than max_age_seconds."""
        try:
            conn = _get_conn(self.db_path)
            cutoff = time.time() - max_age_seconds
            conn.execute("DELETE FROM cache WHERE created < ?", (cutoff,))
            conn.commit()
        except Exception:
            pass

    def migrate_from_json_cache(self, cache_dir: str):
        """
        One-time migration: import existing .dockdesk_cache/*.json files
        into SQLite, then remove the directory.
        """
        import shutil
        if not os.path.isdir(cache_dir):
            return 0

        count = 0
        try:
            conn = _get_conn(self.db_path)
            for fname in os.listdir(cache_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(cache_dir, fname)
                try:
                    with open(fpath, "r") as f:
                        data = json.load(f)
                    key = fname.replace(".json", "")
                    conn.execute(
                        """INSERT OR IGNORE INTO cache (cache_key, result, model, file_path, created)
                           VALUES (?, ?, ?, ?, ?)""",
                        (key, json.dumps(data, default=str),
                         data.get("code_model", ""), data.get("file", ""), time.time()),
                    )
                    count += 1
                except Exception:
                    continue
            conn.commit()

            # Remove old cache directory
            shutil.rmtree(cache_dir, ignore_errors=True)
        except Exception:
            pass
        return count
