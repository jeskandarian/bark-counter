import datetime
import sqlite3
import time
from typing import Optional


def insert_episode(
    conn: sqlite3.Connection,
    started_at: float,
    ended_at: float,
    duration_ms: int,
    bark_count: int,
    peak_db: float,
    avg_db: float,
    confidence: float,
    wav_file: Optional[str],
) -> int:
    cur = conn.execute(
        "INSERT INTO episodes"
        " (started_at,ended_at,duration_ms,bark_count,peak_db,avg_db,confidence,wav_file)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (started_at, ended_at, duration_ms, bark_count, peak_db, avg_db, confidence, wav_file),
    )
    conn.commit()
    return cur.lastrowid


def query_episodes(
    conn: sqlite3.Connection,
    start: Optional[float] = None,
    end: Optional[float] = None,
) -> list:
    if start is not None and end is not None:
        return conn.execute(
            "SELECT * FROM episodes WHERE started_at>=? AND started_at<=? ORDER BY started_at",
            (start, end),
        ).fetchall()
    return conn.execute("SELECT * FROM episodes ORDER BY started_at").fetchall()


def query_stats(conn: sqlite3.Connection) -> dict:
    now = time.time()
    today = datetime.datetime.now(datetime.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).timestamp()

    def _agg(since: float) -> dict:
        r = conn.execute(
            "SELECT COUNT(*) episodes, SUM(bark_count) barks, MAX(peak_db) peak_db"
            " FROM episodes WHERE started_at>=?",
            (since,),
        ).fetchone()
        return {"episodes": r["episodes"] or 0, "barks": r["barks"] or 0, "peak_db": r["peak_db"]}

    all_r = conn.execute(
        "SELECT COUNT(*) episodes, SUM(bark_count) barks, MAX(peak_db) peak_db FROM episodes"
    ).fetchone()

    return {
        "last_hour": _agg(now - 3600),
        "today":     _agg(today),
        "this_week": _agg(now - 7 * 86400),
        "all_time":  {
            "episodes": all_r["episodes"] or 0,
            "barks":    all_r["barks"] or 0,
            "peak_db":  all_r["peak_db"],
        },
    }
