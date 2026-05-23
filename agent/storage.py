import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "config.db"


class Storage:
    """Lightweight SQLite-backed key-value store for persisting config and credentials."""

    def __init__(self, db_path: Path = _DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init()

    def _init(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def get(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def delete(self, key: str) -> None:
        self.conn.execute("DELETE FROM config WHERE key = ?", (key,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
