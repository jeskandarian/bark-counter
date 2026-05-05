import sqlite3
from pathlib import Path


def init_db(db_path: str) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id          INTEGER PRIMARY KEY,
            started_at  REAL NOT NULL,
            ended_at    REAL NOT NULL,
            duration_ms INTEGER NOT NULL,
            bark_count  INTEGER NOT NULL,
            peak_db     REAL NOT NULL,
            avg_db      REAL NOT NULL,
            confidence  REAL NOT NULL,
            wav_file    TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_episodes_started ON episodes(started_at)"
    )
    conn.commit()
    return conn


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
