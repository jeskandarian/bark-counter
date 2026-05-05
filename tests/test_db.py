from src.storage.db import init_db, get_connection


def test_init_db_creates_episodes_table(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='episodes'"
    ).fetchone()
    assert row is not None
    conn.close()


def test_init_db_enables_wal(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_init_db_creates_index(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_episodes_started'"
    ).fetchone()
    assert row is not None
    conn.close()


def test_get_connection_row_factory(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    conn = get_connection(db)
    conn.execute(
        "INSERT INTO episodes (started_at,ended_at,duration_ms,bark_count,peak_db,avg_db,confidence)"
        " VALUES (1.0,2.0,1000,3,-20.0,-25.0,0.6)"
    )
    conn.commit()
    row = conn.execute("SELECT * FROM episodes").fetchone()
    assert row["bark_count"] == 3
    conn.close()
