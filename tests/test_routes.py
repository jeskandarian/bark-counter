import time
import pytest
from src.storage.db import get_connection, init_db
from src.storage.models import insert_episode
from src.web.app import create_app


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    conn = init_db(path)
    now  = time.time()
    insert_episode(conn, now - 100, now - 95, 5000, 3, -18.0, -22.0, 0.6, "bark_a.wav")
    insert_episode(conn, now - 50,  now - 45, 5000, 2, -20.0, -24.0, 0.5, None)
    conn.close()
    return path


@pytest.fixture
def client(db_path, tmp_path):
    app = create_app(db_path=db_path, recordings_dir=str(tmp_path / "rec"))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_dashboard_200(client):
    assert client.get("/").status_code == 200


def test_api_barks_all(client):
    data = client.get("/api/barks").get_json()
    assert isinstance(data, list) and len(data) == 2


def test_api_barks_range(client):
    now  = time.time()
    data = client.get(f"/api/barks?start={now - 75}&end={now}").get_json()
    assert len(data) == 1 and data[0]["bark_count"] == 2


def test_export_csv_headers(client):
    resp = client.get("/api/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.content_type
    header = resp.data.decode().splitlines()[0]
    assert "started_at_local" in header and "bark_count" in header


def test_export_csv_row_count(client):
    lines = client.get("/api/export.csv").data.decode().strip().splitlines()
    assert len(lines) == 3  # header + 2 rows


def test_stats_structure(client):
    data = client.get("/api/stats").get_json()
    for key in ("last_hour", "today", "this_week", "all_time"):
        assert key in data
    assert data["last_hour"]["episodes"] == 2
    assert data["last_hour"]["barks"] == 5


def test_recording_missing_returns_404(client):
    assert client.get("/recordings/no_such.wav").status_code == 404
