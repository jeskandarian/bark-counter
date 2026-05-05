import time
import pytest
from src.storage.db import init_db
from src.storage.models import insert_episode, query_episodes, query_stats


@pytest.fixture
def db(tmp_path):
    return init_db(str(tmp_path / "test.db"))


def test_insert_returns_id(db):
    now = time.time()
    row_id = insert_episode(db, now, now + 5, 5000, 4, -18.0, -22.0, 0.62, "bark.wav")
    assert isinstance(row_id, int) and row_id > 0


def test_query_filters_by_range(db):
    now = 1000.0
    insert_episode(db, now,       now + 5,   5000, 2, -20.0, -24.0, 0.5, None)
    insert_episode(db, now + 100, now + 105, 5000, 3, -18.0, -22.0, 0.6, None)
    insert_episode(db, now + 200, now + 205, 5000, 1, -25.0, -28.0, 0.4, None)
    rows = query_episodes(db, start=now + 50, end=now + 150)
    assert len(rows) == 1
    assert rows[0]["bark_count"] == 3


def test_query_no_range_returns_all(db):
    now = 1000.0
    for i in range(5):
        insert_episode(db, now + i * 100, now + i * 100 + 5, 5000, 1, -20.0, -24.0, 0.5, None)
    assert len(query_episodes(db)) == 5


def test_stats_counts(db):
    now = time.time()
    insert_episode(db, now - 1800, now - 1795, 5000, 3, -18.0, -22.0, 0.6, None)
    insert_episode(db, now - 30,   now - 25,   5000, 2, -20.0, -24.0, 0.5, None)
    stats = query_stats(db)
    assert stats["last_hour"]["episodes"] == 2
    assert stats["last_hour"]["barks"] == 5


def test_stats_peak_db(db):
    now = time.time()
    insert_episode(db, now - 100, now - 95, 5000, 1, -10.0, -15.0, 0.7, None)
    insert_episode(db, now - 50,  now - 45, 5000, 1,  -5.0, -10.0, 0.8, None)
    assert query_stats(db)["last_hour"]["peak_db"] == -5.0
