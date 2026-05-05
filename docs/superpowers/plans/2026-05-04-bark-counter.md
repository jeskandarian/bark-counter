# Bark Counter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Raspberry Pi 4-based bark counter that detects dog barking via I2S microphone, stores events in SQLite, serves a web dashboard with CSV export, and renders a live summary on a 4" TFT display.

**Architecture:** Three independent systemd services (bark-detector, bark-web, bark-display) share a SQLite database in WAL mode. The detector runs at elevated priority and never yields CPU to the web or display services.

**Tech Stack:** Python 3.11+, sounddevice, numpy, flask, pygame, evdev, sqlite3 (stdlib), wave (stdlib), tomllib (stdlib 3.11+)

---

## File Map

```
bark-counter/
├── config.toml                      # Tunable detection parameters + timezone
├── requirements.txt                 # Python dependencies
├── setup.sh                         # System setup (I2S driver, systemd, avahi, dirs)
├── src/
│   ├── __init__.py
│   ├── config.py                    # Config loader (reads config.toml)
│   ├── detector/
│   │   ├── __init__.py
│   │   ├── capture.py               # sounddevice I2S capture + pre-roll deque
│   │   ├── spectral.py              # FFT band energy, dBFS, chunk flagging
│   │   ├── state_machine.py         # Episode state machine + individual bark counter
│   │   ├── recorder.py              # 16-bit PCM WAV clip writer
│   │   └── __main__.py              # Detector process entry point
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py                    # SQLite connection factory, WAL setup, schema init
│   │   └── models.py                # insert_episode(), query_episodes(), query_stats()
│   ├── web/
│   │   ├── __init__.py
│   │   ├── app.py                   # Flask app factory
│   │   ├── routes.py                # All HTTP endpoints
│   │   ├── __main__.py              # Web process entry point
│   │   └── static/
│   │       ├── chart.min.js         # Bundled Chart.js (downloaded by setup.sh)
│   │       └── dashboard.html       # Single-file dashboard
│   └── display/
│       ├── __init__.py
│       ├── layout.py                # Screen constants and drawing primitives
│       ├── renderer.py              # pygame framebuffer rendering
│       ├── touch.py                 # evdev XPT2046 touch + calibration
│       └── __main__.py              # Display process entry point
├── systemd/
│   ├── bark-detector.service
│   ├── bark-web.service
│   └── bark-display.service
└── tests/
    ├── conftest.py
    ├── test_spectral.py
    ├── test_state_machine.py
    ├── test_db.py
    ├── test_models.py
    └── test_routes.py
```

---

## Task 1: Project Scaffolding and Config

**Files:**
- Create: `requirements.txt`
- Create: `config.toml`
- Create: `src/config.py`
- Create: `src/__init__.py`, `src/detector/__init__.py`, `src/storage/__init__.py`, `src/web/__init__.py`, `src/display/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create requirements.txt**

```
sounddevice==0.4.7
numpy==1.26.4
flask==3.0.3
pygame==2.5.2
evdev==1.7.1
pytest==8.2.0
pytest-flask==1.3.0
```

- [ ] **Step 2: Create config.toml**

```toml
[detection]
bark_band_low = 500
bark_band_high = 2000
total_band_low = 80
total_band_high = 8000
spectral_ratio_threshold = 0.45
db_floor = -30.0
onset_chunks = 3
offset_chunks = 8
dip_chunks = 2
sample_rate = 16000
chunk_size = 1024
pre_roll_seconds = 2.0
post_roll_seconds = 1.0

[storage]
db_path = "/var/lib/bark-counter/barks.db"
recordings_dir = "/var/lib/bark-counter/recordings"

[web]
host = "0.0.0.0"
port = 80

[display]
refresh_seconds = 5
calibration_file = "/var/lib/bark-counter/touch_cal.txt"

[general]
timezone = "America/Los_Angeles"
```

- [ ] **Step 3: Create src/config.py**

```python
import tomllib
from dataclasses import dataclass
from pathlib import Path

_DEFAULT = Path(__file__).parent.parent / "config.toml"


@dataclass
class DetectionConfig:
    bark_band_low: float
    bark_band_high: float
    total_band_low: float
    total_band_high: float
    spectral_ratio_threshold: float
    db_floor: float
    onset_chunks: int
    offset_chunks: int
    dip_chunks: int
    sample_rate: int
    chunk_size: int
    pre_roll_seconds: float
    post_roll_seconds: float


@dataclass
class StorageConfig:
    db_path: str
    recordings_dir: str


@dataclass
class WebConfig:
    host: str
    port: int


@dataclass
class DisplayConfig:
    refresh_seconds: int
    calibration_file: str


@dataclass
class AppConfig:
    detection: DetectionConfig
    storage: StorageConfig
    web: WebConfig
    display: DisplayConfig
    timezone: str


def load_config(path: Path = _DEFAULT) -> AppConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return AppConfig(
        detection=DetectionConfig(**raw["detection"]),
        storage=StorageConfig(**raw["storage"]),
        web=WebConfig(**raw["web"]),
        display=DisplayConfig(**raw["display"]),
        timezone=raw["general"]["timezone"],
    )
```

- [ ] **Step 4: Create empty package files**

```bash
mkdir -p src/detector src/storage src/web/static src/display systemd tests
touch src/__init__.py src/detector/__init__.py src/storage/__init__.py \
      src/web/__init__.py src/display/__init__.py
```

- [ ] **Step 5: Create tests/conftest.py**

```python
import pytest
from pathlib import Path


@pytest.fixture
def tmp_config(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("""\
[detection]
bark_band_low = 500
bark_band_high = 2000
total_band_low = 80
total_band_high = 8000
spectral_ratio_threshold = 0.45
db_floor = -30.0
onset_chunks = 3
offset_chunks = 8
dip_chunks = 2
sample_rate = 16000
chunk_size = 1024
pre_roll_seconds = 2.0
post_roll_seconds = 1.0

[storage]
db_path = ":memory:"
recordings_dir = "/tmp/recordings"

[web]
host = "0.0.0.0"
port = 8080

[display]
refresh_seconds = 5
calibration_file = "/tmp/touch_cal.txt"

[general]
timezone = "UTC"
""")
    return cfg
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt config.toml src/ tests/conftest.py
git commit -m "feat: project scaffolding and config loader"
```

---

## Task 2: Database Layer

**Files:**
- Create: `src/storage/db.py`
- Create: `src/storage/models.py`
- Create: `tests/test_db.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for db.py**

Create `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/test_db.py -v
```

- [ ] **Step 3: Implement src/storage/db.py**

```python
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
```

- [ ] **Step 4: Run tests — expect 4 PASS**

```bash
python -m pytest tests/test_db.py -v
```

- [ ] **Step 5: Write failing tests for models.py**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 6: Run tests — expect ImportError**

```bash
python -m pytest tests/test_models.py -v
```

- [ ] **Step 7: Implement src/storage/models.py**

```python
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
```

- [ ] **Step 8: Run all storage tests — expect all PASS**

```bash
python -m pytest tests/test_db.py tests/test_models.py -v
```

- [ ] **Step 9: Commit**

```bash
git add src/storage/ tests/test_db.py tests/test_models.py
git commit -m "feat: SQLite storage layer with WAL mode"
```

---

## Task 3: Spectral Analysis

**Files:**
- Create: `src/detector/spectral.py`
- Create: `tests/test_spectral.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_spectral.py`:

```python
import numpy as np
import pytest
from src.detector.spectral import compute_band_energy, samples_to_dbfs, is_bark_chunk

SR = 16000
N  = 1024


def _sine(hz: float, amp: float = 0.3) -> np.ndarray:
    t = np.arange(N) / SR
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def test_band_energy_concentrates_on_target():
    samples = _sine(1000.0)
    assert compute_band_energy(samples, SR, 500, 2000) > \
           compute_band_energy(samples, SR, 80, 400) * 10


def test_band_energy_zero_for_silence():
    assert compute_band_energy(np.zeros(N, np.float32), SR, 500, 2000) == pytest.approx(0, abs=1e-6)


def test_dbfs_sine_near_minus_three():
    # full-scale sine RMS = 1/sqrt(2) → -3 dBFS
    samples = np.sin(2 * np.pi * 1000 * np.arange(N) / SR).astype(np.float32)
    assert samples_to_dbfs(samples) == pytest.approx(-3.01, abs=0.1)


def test_dbfs_silence_very_negative():
    assert samples_to_dbfs(np.zeros(N, np.float32)) < -100


def test_bark_chunk_flags_1khz():
    flagged, ratio, _ = is_bark_chunk(_sine(1000.0), SR, 500, 2000, 80, 8000, 0.45, -30.0)
    assert flagged and ratio > 0.45


def test_bark_chunk_ignores_100hz():
    flagged, _, _ = is_bark_chunk(_sine(100.0), SR, 500, 2000, 80, 8000, 0.45, -30.0)
    assert not flagged


def test_bark_chunk_ignores_quiet():
    flagged, _, _ = is_bark_chunk(_sine(1000.0, amp=0.0001), SR, 500, 2000, 80, 8000, 0.45, -30.0)
    assert not flagged
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/test_spectral.py -v
```

- [ ] **Step 3: Implement src/detector/spectral.py**

```python
import numpy as np


def compute_band_energy(samples: np.ndarray, sample_rate: int, low_hz: float, high_hz: float) -> float:
    windowed = samples * np.hanning(len(samples))
    fft = np.fft.rfft(windowed)
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)
    psd = np.abs(fft) ** 2
    return float(np.sum(psd[(freqs >= low_hz) & (freqs <= high_hz)]))


def samples_to_dbfs(samples: np.ndarray) -> float:
    rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
    return float(20.0 * np.log10(rms)) if rms > 0.0 else -120.0


def is_bark_chunk(
    samples: np.ndarray,
    sample_rate: int,
    bark_low: float,
    bark_high: float,
    total_low: float,
    total_high: float,
    ratio_threshold: float,
    db_floor: float,
) -> tuple[bool, float, float]:
    bark  = compute_band_energy(samples, sample_rate, bark_low, bark_high)
    total = compute_band_energy(samples, sample_rate, total_low, total_high)
    ratio = bark / total if total > 0.0 else 0.0
    dbfs  = samples_to_dbfs(samples)
    return ratio > ratio_threshold and dbfs > db_floor, ratio, dbfs
```

- [ ] **Step 4: Run tests — expect 7 PASS**

```bash
python -m pytest tests/test_spectral.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/detector/spectral.py tests/test_spectral.py
git commit -m "feat: FFT spectral analysis for bark chunk detection"
```

---

## Task 4: Episode State Machine

**Files:**
- Create: `src/detector/state_machine.py`
- Create: `tests/test_state_machine.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_state_machine.py`:

```python
import pytest
from src.detector.state_machine import BarkStateMachine, StateMachineResult


def feed(sm, seq: list[bool], dbfs=-20.0, conf=0.6) -> list[StateMachineResult]:
    return [sm.process(f, dbfs, conf, 0.064) for f in seq]


def test_silence_produces_no_episode():
    sm = BarkStateMachine(3, 8, 2)
    assert not any(r.episode_complete for r in feed(sm, [False] * 20))


def test_two_flagged_chunks_do_not_trigger():
    sm = BarkStateMachine(3, 8, 2)
    assert not any(r.episode_complete for r in feed(sm, [True, True, False] * 6))


def test_episode_completes_after_offset_chunks():
    sm = BarkStateMachine(3, 8, 2)
    results = feed(sm, [True] * 5 + [False] * 8)
    assert sum(1 for r in results if r.episode_complete) == 1


def test_continuous_bark_is_one_bark():
    sm = BarkStateMachine(3, 8, 2)
    results = feed(sm, [True] * 10 + [False] * 8)
    ep = next(r for r in results if r.episode_complete)
    assert ep.bark_count == 1


def test_dip_then_bark_counts_two():
    sm = BarkStateMachine(3, 8, 2)
    # onset(5) + dip(2 = dip_chunks) + second bark(3) + offset(8)
    seq = [True] * 5 + [False] * 2 + [True] * 3 + [False] * 8
    results = feed(sm, seq)
    ep = next(r for r in results if r.episode_complete)
    assert ep.bark_count == 2


def test_peak_db_is_maximum():
    sm = BarkStateMachine(3, 8, 2)
    sm.process(True, -30.0, 0.5, 0.064)
    sm.process(True, -10.0, 0.5, 0.064)
    sm.process(True, -20.0, 0.5, 0.064)
    last = None
    for _ in range(8):
        last = sm.process(False, -40.0, 0.0, 0.064)
    assert last.peak_db == pytest.approx(-10.0)


def test_state_resets_for_second_episode():
    sm = BarkStateMachine(3, 8, 2)
    feed(sm, [True] * 5 + [False] * 8)
    results = feed(sm, [True] * 5 + [False] * 8)
    assert sum(1 for r in results if r.episode_complete) == 1
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/test_state_machine.py -v
```

- [ ] **Step 3: Implement src/detector/state_machine.py**

```python
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class _State(Enum):
    IDLE    = "idle"
    BARKING = "barking"


@dataclass
class StateMachineResult:
    episode_complete: bool = False
    started_at: float  = 0.0
    ended_at:   float  = 0.0
    duration_ms: int   = 0
    bark_count:  int   = 0
    peak_db:     float = 0.0
    avg_db:      float = 0.0
    confidence:  float = 0.0


@dataclass
class _Acc:
    started_at:     float
    peak_db:        float = -120.0
    total_db:       float = 0.0
    chunk_count:    int   = 0
    confidence_sum: float = 0.0
    bark_count:     int   = 1
    in_dip:         bool  = False
    dip_count:      int   = 0


class BarkStateMachine:
    def __init__(self, onset_chunks: int, offset_chunks: int, dip_chunks: int):
        self._onset   = onset_chunks
        self._offset  = offset_chunks
        self._dip     = dip_chunks
        self._state   = _State.IDLE
        self._on_run  = 0   # consecutive flagged chunks
        self._off_run = 0   # consecutive unflagged chunks
        self._acc: Optional[_Acc] = None

    def process(self, flagged: bool, dbfs: float, confidence: float, chunk_duration_s: float) -> StateMachineResult:
        if self._state == _State.IDLE:
            return self._idle(flagged, dbfs, confidence)
        return self._barking(flagged, dbfs, confidence)

    def _idle(self, flagged: bool, dbfs: float, conf: float) -> StateMachineResult:
        if flagged:
            self._on_run += 1
            if self._on_run >= self._onset:
                self._state   = _State.BARKING
                self._off_run = 0
                self._acc     = _Acc(started_at=time.time())
                self._tick(dbfs, conf)
        else:
            self._on_run = 0
        return StateMachineResult()

    def _barking(self, flagged: bool, dbfs: float, conf: float) -> StateMachineResult:
        if flagged:
            if self._acc.in_dip and self._acc.dip_count >= self._dip:
                self._acc.bark_count += 1
            self._acc.in_dip  = False
            self._acc.dip_count = 0
            self._off_run = 0
            self._tick(dbfs, conf)
            return StateMachineResult()

        self._off_run += 1
        self._acc.in_dip = True
        self._acc.dip_count += 1

        if self._off_run >= self._offset:
            return self._finish()
        return StateMachineResult()

    def _finish(self) -> StateMachineResult:
        acc = self._acc
        ended_at = time.time()
        result = StateMachineResult(
            episode_complete=True,
            started_at=acc.started_at,
            ended_at=ended_at,
            duration_ms=int((ended_at - acc.started_at) * 1000),
            bark_count=acc.bark_count,
            peak_db=acc.peak_db,
            avg_db=acc.total_db / acc.chunk_count if acc.chunk_count else 0.0,
            confidence=acc.confidence_sum / acc.chunk_count if acc.chunk_count else 0.0,
        )
        self._state   = _State.IDLE
        self._on_run  = 0
        self._off_run = 0
        self._acc     = None
        return result

    def _tick(self, dbfs: float, conf: float) -> None:
        self._acc.peak_db        = max(self._acc.peak_db, dbfs)
        self._acc.total_db      += dbfs
        self._acc.chunk_count   += 1
        self._acc.confidence_sum += conf
```

- [ ] **Step 4: Run tests — expect all PASS**

```bash
python -m pytest tests/test_state_machine.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/detector/state_machine.py tests/test_state_machine.py
git commit -m "feat: episode state machine with individual bark counter"
```

---

## Task 5: WAV Recorder

**Files:**
- Create: `src/detector/recorder.py`
- Create: `tests/test_recorder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_recorder.py`:

```python
import wave
import numpy as np
from collections import deque
from src.detector.recorder import save_wav_clip

SR = 16000
N  = 1024


def chunk(val=0.1) -> np.ndarray:
    return np.full(N, val, dtype=np.float32)


def test_creates_file(tmp_path):
    out = tmp_path / "out.wav"
    save_wav_clip(str(out), deque([chunk()]), [chunk(0.5)], [chunk()], SR)
    assert out.exists()


def test_valid_wav_params(tmp_path):
    out = tmp_path / "out.wav"
    save_wav_clip(str(out), deque([chunk()]), [chunk(0.5)], [chunk()], SR)
    with wave.open(str(out)) as wf:
        assert wf.getsampwidth() == 2   # 16-bit
        assert wf.getnchannels() == 1   # mono
        assert wf.getframerate() == SR


def test_correct_frame_count(tmp_path):
    out = tmp_path / "out.wav"
    save_wav_clip(str(out), deque([chunk()] * 3), [chunk()] * 5, [chunk()] * 2, SR)
    with wave.open(str(out)) as wf:
        assert wf.getnframes() == N * 10


def test_clips_overflow_to_int16_max(tmp_path):
    out = tmp_path / "clip.wav"
    save_wav_clip(str(out), deque(), [np.full(N, 2.0, np.float32)], [], SR)
    with wave.open(str(out)) as wf:
        raw = wf.readframes(N)
    assert np.all(np.frombuffer(raw, dtype=np.int16) == 32767)
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/test_recorder.py -v
```

- [ ] **Step 3: Implement src/detector/recorder.py**

```python
import wave
from collections import deque
from pathlib import Path

import numpy as np


def save_wav_clip(
    path: str,
    pre_roll: deque,
    episode_chunks: list,
    post_roll: list,
    sample_rate: int,
) -> None:
    all_chunks = list(pre_roll) + episode_chunks + post_roll
    if not all_chunks:
        return
    combined = np.concatenate(all_chunks).astype(np.float64)
    pcm = (np.clip(combined, -1.0, 1.0) * 32767).astype(np.int16)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
```

- [ ] **Step 4: Run tests — expect 4 PASS**

```bash
python -m pytest tests/test_recorder.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/detector/recorder.py tests/test_recorder.py
git commit -m "feat: 16-bit PCM WAV clip recorder"
```

---

## Task 6: Audio Capture and Detector Entry Point

**Files:**
- Create: `src/detector/capture.py`
- Create: `src/detector/__main__.py`
- Create: `systemd/bark-detector.service`

No unit tests — hardware callback. Integration testing requires the Pi.

- [ ] **Step 1: Create src/detector/capture.py**

```python
import collections
from typing import Callable

import numpy as np
import sounddevice as sd


class AudioCapture:
    def __init__(
        self,
        sample_rate: int,
        chunk_size: int,
        pre_roll_chunks: int,
        on_chunk: Callable[[np.ndarray, collections.deque], None],
    ):
        self._sr      = sample_rate
        self._chunk   = chunk_size
        self._pre     = collections.deque(maxlen=pre_roll_chunks)
        self._on_chunk = on_chunk
        self._stream  = None

    def start(self) -> None:
        self._stream = sd.InputStream(
            samplerate=self._sr,
            channels=1,
            dtype="float32",
            blocksize=self._chunk,
            callback=self._cb,
            device=None,   # ALSA default set by /etc/asound.conf on Pi
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()

    def _cb(self, indata, frames, time_info, status):
        chunk = indata[:, 0].copy()
        self._on_chunk(chunk, self._pre)
        self._pre.append(chunk)
```

- [ ] **Step 2: Create src/detector/__main__.py**

```python
import collections
import datetime
import os
import signal
import sys

import numpy as np

from src.config import load_config
from src.detector.capture import AudioCapture
from src.detector.recorder import save_wav_clip
from src.detector.spectral import is_bark_chunk
from src.detector.state_machine import BarkStateMachine
from src.storage.db import get_connection, init_db
from src.storage.models import insert_episode


def main():
    cfg = load_config()
    d, s = cfg.detection, cfg.storage

    os.makedirs(s.recordings_dir, exist_ok=True)
    init_db(s.db_path)
    conn = get_connection(s.db_path)

    sm = BarkStateMachine(d.onset_chunks, d.offset_chunks, d.dip_chunks)

    pre_roll_len   = int(d.pre_roll_seconds  * d.sample_rate / d.chunk_size)
    post_roll_len  = int(d.post_roll_seconds * d.sample_rate / d.chunk_size)
    chunk_dur      = d.chunk_size / d.sample_rate

    episode_buf: list[np.ndarray] = []
    post_remaining = [0]

    def on_chunk(chunk: np.ndarray, pre_roll: collections.deque) -> None:
        flagged, ratio, dbfs = is_bark_chunk(
            chunk, d.sample_rate,
            d.bark_band_low, d.bark_band_high,
            d.total_band_low, d.total_band_high,
            d.spectral_ratio_threshold, d.db_floor,
        )
        result = sm.process(flagged, dbfs, ratio, chunk_dur)

        if sm._state.value == "barking":
            episode_buf.append(chunk)

        if post_remaining[0] > 0:
            episode_buf.append(chunk)
            post_remaining[0] -= 1

        if result.episode_complete:
            post_remaining[0] = post_roll_len
            _persist(result, list(pre_roll), list(episode_buf), conn, s, d)
            episode_buf.clear()

    capture = AudioCapture(d.sample_rate, d.chunk_size, pre_roll_len, on_chunk)

    def _shutdown(sig, frame):
        capture.stop()
        conn.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)
    capture.start()
    signal.pause()


def _persist(result, pre_snap, ep_chunks, conn, s, d):
    ts       = datetime.datetime.fromtimestamp(result.started_at, tz=datetime.timezone.utc)
    filename = "bark_" + ts.strftime("%Y-%m-%dT%H-%M-%S") + ".wav"
    wav_path = os.path.join(s.recordings_dir, filename)
    save_wav_clip(wav_path, collections.deque(pre_snap), ep_chunks, [], d.sample_rate)
    insert_episode(
        conn,
        started_at=result.started_at,
        ended_at=result.ended_at,
        duration_ms=result.duration_ms,
        bark_count=result.bark_count,
        peak_db=result.peak_db,
        avg_db=result.avg_db,
        confidence=result.confidence,
        wav_file=filename,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create systemd/bark-detector.service**

```ini
[Unit]
Description=Bark Counter - Audio Detector
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bark-counter
ExecStart=/home/pi/bark-counter/venv/bin/python -m src.detector
Restart=always
RestartSec=5
Nice=-5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Commit**

```bash
git add src/detector/capture.py src/detector/__main__.py systemd/bark-detector.service
git commit -m "feat: audio capture and detector process"
```

---

## Task 7: Flask Web Server

**Files:**
- Create: `src/web/app.py`
- Create: `src/web/routes.py`
- Create: `src/web/__main__.py`
- Create: `src/web/static/dashboard.html` (placeholder)
- Create: `tests/test_routes.py`
- Create: `systemd/bark-web.service`

- [ ] **Step 1: Write failing tests**

Create `tests/test_routes.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/test_routes.py -v
```

- [ ] **Step 3: Create src/web/app.py**

```python
from flask import Flask


def create_app(db_path: str, recordings_dir: str) -> Flask:
    app = Flask(__name__, static_folder="static")
    app.config["DB_PATH"]        = db_path
    app.config["RECORDINGS_DIR"] = recordings_dir
    from src.web.routes import bp
    app.register_blueprint(bp)
    return app
```

- [ ] **Step 4: Create src/web/routes.py**

```python
import csv
import datetime
import io
import zoneinfo

from flask import Blueprint, current_app, jsonify, make_response, request, send_from_directory

from src.storage.db import get_connection
from src.storage.models import query_episodes, query_stats

bp = Blueprint("main", __name__)


def _conn():
    return get_connection(current_app.config["DB_PATH"])


@bp.route("/")
def dashboard():
    return current_app.send_static_file("dashboard.html")


@bp.route("/api/barks")
def api_barks():
    start = request.args.get("start", type=float)
    end   = request.args.get("end",   type=float)
    conn  = _conn()
    rows  = query_episodes(conn, start=start, end=end)
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/export.csv")
def api_export():
    start   = request.args.get("start", type=float)
    end     = request.args.get("end",   type=float)
    tz_name = request.args.get("tz", "UTC")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    conn = _conn()
    rows = query_episodes(conn, start=start, end=end)
    conn.close()

    def fmt(ts):
        return datetime.datetime.fromtimestamp(ts, tz=tz).isoformat()

    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["id","started_at_local","ended_at_local","duration_ms",
                "bark_count","peak_db","avg_db","confidence","wav_file"])
    for r in rows:
        w.writerow([r["id"], fmt(r["started_at"]), fmt(r["ended_at"]),
                    r["duration_ms"], r["bark_count"], r["peak_db"],
                    r["avg_db"], r["confidence"], r["wav_file"] or ""])

    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"]        = "text/csv"
    resp.headers["Content-Disposition"] = "attachment; filename=bark_export.csv"
    return resp


@bp.route("/recordings/<path:filename>")
def recordings(filename):
    try:
        return send_from_directory(current_app.config["RECORDINGS_DIR"], filename, conditional=True)
    except Exception:
        return "", 404


@bp.route("/api/stats")
def api_stats():
    conn  = _conn()
    stats = query_stats(conn)
    conn.close()
    return jsonify(stats)
```

- [ ] **Step 5: Create placeholder src/web/static/dashboard.html**

```html
<!DOCTYPE html>
<html><head><title>BARK COUNTER</title></head>
<body><h1>BARK COUNTER</h1></body></html>
```

- [ ] **Step 6: Run tests — expect all PASS**

```bash
python -m pytest tests/test_routes.py -v
```

- [ ] **Step 7: Create src/web/__main__.py**

```python
from src.config import load_config
from src.web.app import create_app

cfg = load_config()
app = create_app(db_path=cfg.storage.db_path, recordings_dir=cfg.storage.recordings_dir)

if __name__ == "__main__":
    app.run(host=cfg.web.host, port=cfg.web.port)
```

- [ ] **Step 8: Create systemd/bark-web.service**

```ini
[Unit]
Description=Bark Counter - Web Server
After=network.target bark-detector.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bark-counter
ExecStart=/home/pi/bark-counter/venv/bin/python -m src.web
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 9: Commit**

```bash
git add src/web/ systemd/bark-web.service tests/test_routes.py
git commit -m "feat: Flask HTTP server with JSON API and CSV export"
```

---

## Task 8: Web Dashboard

**Files:**
- Replace: `src/web/static/dashboard.html`
- Download: `src/web/static/chart.min.js`

No automated tests — verify visually in a browser.

- [ ] **Step 1: Download Chart.js**

```bash
curl -sL "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js" \
     -o src/web/static/chart.min.js
```

- [ ] **Step 2: Replace dashboard.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bark Counter</title>
<script src="/static/chart.min.js"></script>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#111;color:#eee;font-family:monospace;padding:16px}
  h1{font-size:1.3rem;letter-spacing:2px;color:#f90;margin-bottom:8px}
  .stats{display:flex;gap:20px;margin-bottom:12px;font-size:.85rem;color:#aaa}
  .stats strong{color:#fff;font-size:1rem}
  .zoom-strip{display:flex;gap:6px;margin-bottom:12px}
  .zoom-strip button{background:#222;color:#aaa;border:1px solid #444;
    padding:5px 12px;cursor:pointer;font-family:monospace;border-radius:3px}
  .zoom-strip button.active{background:#f90;color:#111;border-color:#f90}
  #chartBox{position:relative;height:280px;margin-bottom:20px}
  table{width:100%;border-collapse:collapse;font-size:.8rem}
  th{text-align:left;color:#777;border-bottom:1px solid #333;padding:5px 8px}
  td{padding:5px 8px;border-bottom:1px solid #1e1e1e}
  tr:hover{background:#1a1a1a}
  audio{height:22px;vertical-align:middle}
</style>
</head>
<body>
<h1>BARK COUNTER</h1>
<div class="stats">
  <span>Today: <strong id="sToday">—</strong></span>
  <span>Last Hour: <strong id="sHour">—</strong></span>
  <span>Peak: <strong id="sPeak">—</strong></span>
</div>
<div class="zoom-strip">
  <button onclick="zoom(1)"   id="z1">1h</button>
  <button onclick="zoom(6)"   id="z6">6h</button>
  <button onclick="zoom(24)"  id="z24" class="active">24h</button>
  <button onclick="zoom(168)" id="z168">7d</button>
  <button onclick="zoom(720)" id="z720">30d</button>
</div>
<div id="chartBox"><canvas id="chart"></canvas></div>
<table>
  <thead><tr><th>Time</th><th>Duration</th><th>Barks</th><th>Peak dB</th><th>Audio</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<script>
const ZOOM_IDS={1:'z1',6:'z6',24:'z24',168:'z168',720:'z720'};
let hours=24, chart=null;

function zoom(h){
  hours=h;
  Object.entries(ZOOM_IDS).forEach(([k,id])=>
    document.getElementById(id).classList.toggle('active',+k===h));
  load();
}

async function loadStats(){
  const s=await fetch('/api/stats').then(r=>r.json());
  document.getElementById('sToday').textContent=
    `${s.today.episodes}ep / ${s.today.barks}bark`;
  document.getElementById('sHour').textContent=
    `${s.last_hour.episodes}ep / ${s.last_hour.barks}bark`;
  document.getElementById('sPeak').textContent=
    s.today.peak_db!=null ? s.today.peak_db.toFixed(1)+' dBFS' : '—';
}

async function load(){
  const now=Date.now()/1000;
  const eps=await fetch(`/api/barks?start=${now-hours*3600}&end=${now}`).then(r=>r.json());
  renderChart(eps);
  renderTable(eps);
}

function renderChart(eps){
  const now=Date.now()/1000;
  const n=Math.min(hours,48);
  const bsz=hours*3600/n;
  const barks=new Array(n).fill(0), epcnt=new Array(n).fill(0);
  const base=now-hours*3600;
  eps.forEach(e=>{
    const i=Math.max(0,Math.min(n-1,Math.floor((e.started_at-base)/bsz)));
    barks[i]+=e.bark_count; epcnt[i]+=1;
  });
  const labels=Array.from({length:n},(_,i)=>{
    const d=new Date((base+i*bsz)*1000);
    return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  });
  if(chart)chart.destroy();
  chart=new Chart(document.getElementById('chart').getContext('2d'),{
    type:'bar',
    data:{labels,datasets:[
      {type:'bar',label:'Barks',data:barks,backgroundColor:'rgba(255,153,0,.5)',
       borderColor:'#f90',borderWidth:1,yAxisID:'y'},
      {type:'line',label:'Episodes',data:epcnt,borderColor:'#4af',
       backgroundColor:'transparent',pointRadius:2,tension:.3,yAxisID:'y1'},
    ]},
    options:{responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{legend:{labels:{color:'#aaa',font:{family:'monospace'}}}},
      scales:{
        x:{ticks:{color:'#555',maxTicksLimit:12},grid:{color:'#1e1e1e'}},
        y:{position:'left',ticks:{color:'#f90'},grid:{color:'#1e1e1e'},
           title:{display:true,text:'Barks',color:'#f90'}},
        y1:{position:'right',ticks:{color:'#4af'},grid:{drawOnChartArea:false},
            title:{display:true,text:'Episodes',color:'#4af'}},
      }},
  });
}

function renderTable(eps){
  document.getElementById('rows').innerHTML=[...eps].reverse().map(e=>`
    <tr>
      <td>${new Date(e.started_at*1000).toLocaleString()}</td>
      <td>${(e.duration_ms/1000).toFixed(1)}s</td>
      <td>${e.bark_count}</td>
      <td>${e.peak_db.toFixed(1)}</td>
      <td>${e.wav_file?`<audio controls src="/recordings/${e.wav_file}"></audio>`:'—'}</td>
    </tr>`).join('');
}

loadStats(); load();
setInterval(loadStats,30000); setInterval(load,30000);
</script>
</body>
</html>
```

- [ ] **Step 3: Smoke-test the dashboard**

```bash
# Run with a temp DB so you don't need the Pi
python -m src.web
```
Open `http://localhost:80` (or the configured port). Confirm the chart and zoom buttons render.

- [ ] **Step 4: Commit**

```bash
git add src/web/static/
git commit -m "feat: Chart.js dashboard with zoom strip and episode list"
```

---

## Task 9: Display Renderer

**Files:**
- Create: `src/display/layout.py`
- Create: `src/display/touch.py`
- Create: `src/display/renderer.py`
- Create: `src/display/__main__.py`
- Create: `systemd/bark-display.service`

No automated tests — pygame framebuffer only works on the Pi. Verify visually on-device.

- [ ] **Step 1: Create src/display/layout.py**

```python
WIDTH  = 480
HEIGHT = 320

HEADER_H = 28
ZOOM_H   = 30
CHART_Y  = HEADER_H
CHART_H  = HEIGHT - HEADER_H - ZOOM_H
CHART_X  = 36   # left margin for y-axis tick labels
CHART_W  = WIDTH - CHART_X - 4
ZOOM_Y   = HEIGHT - ZOOM_H

# Colors (RGB)
BG             = (17,  17,  17)
HEADER_BG      = (30,  30,  30)
BAR_COLOR      = (255, 153,  0)
TEXT_COLOR     = (238, 238, 238)
DIM_COLOR      = (100, 100, 100)
GRID_COLOR     = (34,  34,  34)
ZOOM_ON_BG     = (255, 153,  0)
ZOOM_ON_FG     = (17,  17,  17)
ZOOM_OFF_BG    = (34,  34,  34)
ZOOM_OFF_FG    = (150, 150, 150)

ZOOM_LEVELS = [("1h", 1), ("6h", 6), ("24h", 24), ("7d", 168)]
```

- [ ] **Step 2: Create src/display/touch.py**

```python
import threading
from typing import Callable, Optional

try:
    import evdev
    from evdev import ecodes
    _EVDEV = True
except ImportError:
    _EVDEV = False


class TouchInput:
    def __init__(
        self,
        device_path: str,
        calibration_file: str,
        on_tap: Callable[[int, int], None],
    ):
        self._path  = device_path
        self._cal   = self._read_cal(calibration_file)
        self._on_tap = on_tap
        self._t: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if not _EVDEV:
            return
        self._running = True
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        try:
            dev = evdev.InputDevice(self._path)
            rx = ry = 0
            for ev in dev.read_loop():
                if not self._running:
                    break
                if ev.type == ecodes.EV_ABS:
                    if ev.code == ecodes.ABS_X:
                        rx = ev.value
                    elif ev.code == ecodes.ABS_Y:
                        ry = ev.value
                elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH and ev.value == 1:
                    self._on_tap(*self._cal_pt(rx, ry))
        except Exception:
            pass

    def _cal_pt(self, rx: int, ry: int) -> tuple[int, int]:
        from src.display.layout import WIDTH, HEIGHT
        if self._cal is None:
            return rx, ry
        x0, x1, y0, y1 = self._cal
        x = int((rx - x0) / (x1 - x0) * WIDTH)
        y = int((ry - y0) / (y1 - y0) * HEIGHT)
        return max(0, min(WIDTH - 1, x)), max(0, min(HEIGHT - 1, y))

    def _read_cal(self, path: str) -> Optional[tuple]:
        try:
            vals = [int(v) for v in open(path).read().split()]
            return tuple(vals)  # x_min x_max y_min y_max
        except Exception:
            return None
```

- [ ] **Step 3: Create src/display/renderer.py**

```python
import datetime
import os
import time
from typing import Optional

os.environ.setdefault("SDL_VIDEODRIVER", "fbcon")
os.environ.setdefault("SDL_FBDEV",       "/dev/fb1")
os.environ.setdefault("SDL_MOUSEDRV",    "TSLIB")

import pygame

import src.display.layout as L
from src.storage.db import get_connection
from src.storage.models import query_episodes, query_stats


class DisplayRenderer:
    def __init__(self, db_path: str, refresh_seconds: int):
        self._db      = db_path
        self._refresh = refresh_seconds
        self._zoom_i  = 2   # default index → 24h
        self._screen: Optional[pygame.Surface] = None
        self._fsm: Optional[pygame.font.Font]  = None
        self._fmd: Optional[pygame.font.Font]  = None
        self._conn = None

    def init(self) -> None:
        pygame.init()
        self._screen = pygame.display.set_mode((L.WIDTH, L.HEIGHT), pygame.NOFRAME)
        self._fsm    = pygame.font.SysFont("monospace", 13)
        self._fmd    = pygame.font.SysFont("monospace", 15)
        self._conn   = get_connection(self._db)

    def handle_tap(self, x: int, y: int) -> None:
        if y < L.ZOOM_Y:
            return
        idx = x // (L.WIDTH // len(L.ZOOM_LEVELS))
        if 0 <= idx < len(L.ZOOM_LEVELS):
            self._zoom_i = idx
            self.render()

    def render(self) -> None:
        s = self._screen
        s.fill(L.BG)
        self._header()
        self._chart()
        self._zoom_strip()
        pygame.display.flip()

    def _header(self) -> None:
        pygame.draw.rect(self._screen, L.HEADER_BG, (0, 0, L.WIDTH, L.HEADER_H))
        st    = query_stats(self._conn)
        now   = datetime.datetime.now().strftime("%H:%M %a %d %b")
        today = st["today"]
        hr    = st["last_hour"]
        txt   = (f"BARK COUNTER  {now}  "
                 f"Today:{today['episodes']}/{today['barks']}  "
                 f"LastHr:{hr['episodes']}/{hr['barks']}")
        surf  = self._fsm.render(txt, True, L.TEXT_COLOR)
        self._screen.blit(surf, (5, (L.HEADER_H - surf.get_height()) // 2))

    def _chart(self) -> None:
        _, hours = L.ZOOM_LEVELS[self._zoom_i]
        now      = time.time()
        rows     = query_episodes(self._conn, start=now - hours * 3600, end=now)
        n        = min(hours, 48)
        bsz      = (hours * 3600) / n
        base     = now - hours * 3600
        buckets  = [0] * n
        for r in rows:
            i = max(0, min(n - 1, int((r["started_at"] - base) / bsz)))
            buckets[i] += r["bark_count"]

        peak = max(buckets) if any(buckets) else 1
        bw   = max(1, L.CHART_W // n - 1)

        for gi in range(1, 5):
            y = L.CHART_Y + L.CHART_H - int(L.CHART_H * gi / 4)
            pygame.draw.line(self._screen, L.GRID_COLOR, (L.CHART_X, y), (L.WIDTH - 4, y))
            lbl = self._fsm.render(str(int(peak * gi / 4)), True, L.DIM_COLOR)
            self._screen.blit(lbl, (0, y - lbl.get_height() // 2))

        for i, cnt in enumerate(buckets):
            if cnt == 0:
                continue
            bh = int(L.CHART_H * cnt / peak)
            x  = L.CHART_X + i * (L.CHART_W // n)
            pygame.draw.rect(self._screen, L.BAR_COLOR,
                             (x, L.CHART_Y + L.CHART_H - bh, bw, bh))

    def _zoom_strip(self) -> None:
        bw = L.WIDTH // len(L.ZOOM_LEVELS)
        for i, (label, _) in enumerate(L.ZOOM_LEVELS):
            active = i == self._zoom_i
            bg = L.ZOOM_ON_BG if active else L.ZOOM_OFF_BG
            fg = L.ZOOM_ON_FG if active else L.ZOOM_OFF_FG
            pygame.draw.rect(self._screen, bg,
                             (i * bw + 2, L.ZOOM_Y + 2, bw - 4, L.ZOOM_H - 4))
            surf = self._fmd.render(label, True, fg)
            self._screen.blit(surf, (
                i * bw + (bw - surf.get_width())  // 2,
                L.ZOOM_Y  + (L.ZOOM_H - surf.get_height()) // 2,
            ))
```

- [ ] **Step 4: Create src/display/__main__.py**

```python
import signal
import sys
import time

import pygame

from src.config import load_config
from src.display.renderer import DisplayRenderer
from src.display.touch import TouchInput


def main():
    cfg      = load_config()
    renderer = DisplayRenderer(cfg.storage.db_path, cfg.display.refresh_seconds)
    renderer.init()

    touch = TouchInput(
        device_path="/dev/input/event0",
        calibration_file=cfg.display.calibration_file,
        on_tap=renderer.handle_tap,
    )
    touch.start()

    def _quit(sig, frame):
        touch.stop()
        pygame.quit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _quit)
    signal.signal(signal.SIGINT,  _quit)

    last = 0.0
    while True:
        now = time.monotonic()
        if now - last >= cfg.display.refresh_seconds:
            renderer.render()
            last = now
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                _quit(None, None)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Create systemd/bark-display.service**

```ini
[Unit]
Description=Bark Counter - Display
After=bark-detector.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bark-counter
ExecStart=/home/pi/bark-counter/venv/bin/python -m src.display
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_FBDEV=/dev/fb1

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 6: Commit**

```bash
git add src/display/ systemd/bark-display.service
git commit -m "feat: pygame framebuffer display with touch zoom"
```

---

## Task 10: System Setup Script

**Files:**
- Create: `setup.sh`

- [ ] **Step 1: Create setup.sh**

```bash
#!/usr/bin/env bash
set -e

INSTALL_DIR=/home/pi/bark-counter
DATA_DIR=/var/lib/bark-counter

echo "=== Bark Counter Setup ==="

# System packages
sudo apt-get update -q
sudo apt-get install -y -q \
  python3 python3-venv python3-pip \
  libportaudio2 portaudio19-dev \
  libsdl2-dev libsdl2-ttf-dev \
  avahi-daemon \
  python3-evdev \
  curl

# Enable I2S for INMP441 mic
BOOT_CFG=/boot/firmware/config.txt
if ! grep -q "dtparam=i2s=on" "$BOOT_CFG"; then
  sudo tee -a "$BOOT_CFG" > /dev/null <<'EOF'

# I2S microphone (INMP441)
dtparam=i2s=on
dtoverlay=i2s-mmap
EOF
fi

# ALSA — route default capture to I2S mic (card 1)
sudo tee /etc/asound.conf > /dev/null <<'EOF'
pcm.i2smic { type hw; card 1; device 0; }
pcm.!default { type asym; capture.pcm "i2smic"; }
EOF

# Waveshare 4" LCD setup — must be done manually once
# Follow: https://www.waveshare.com/wiki/4inch_RPi_LCD_(A)
# The overlay exposes /dev/fb1 (display) and /dev/input/event0 (touch).
if [ ! -f /boot/firmware/overlays/waveshare35a.dtbo ]; then
  echo ""
  echo "WARNING: Waveshare display overlay not installed."
  echo "Run the Waveshare installer, then re-run this script."
  echo "See: https://www.waveshare.com/wiki/4inch_RPi_LCD_(A)"
  echo ""
fi

# Data directories
sudo mkdir -p "$DATA_DIR/recordings"
sudo chown -R pi:pi "$DATA_DIR"

# Python virtualenv + dependencies
cd "$INSTALL_DIR"
python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt

# Bundle Chart.js locally (no CDN at runtime)
curl -sL "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js" \
     -o src/web/static/chart.min.js

# Systemd services
sudo cp systemd/bark-detector.service /etc/systemd/system/
sudo cp systemd/bark-web.service      /etc/systemd/system/
sudo cp systemd/bark-display.service  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bark-detector bark-web bark-display

# mDNS hostname → bark-counter.local
sudo hostnamectl set-hostname bark-counter
sudo sed -i 's/^#*host-name=.*/host-name=bark-counter/' /etc/avahi/avahi-daemon.conf
sudo systemctl enable avahi-daemon
sudo systemctl restart avahi-daemon

echo ""
echo "=== Done ==="
echo "Reboot to load I2S + display drivers: sudo reboot"
echo "After reboot: sudo systemctl start bark-detector bark-web bark-display"
echo "Dashboard: http://bark-counter.local"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x setup.sh
git add setup.sh
git commit -m "feat: system setup script — I2S, display, systemd, avahi"
```

---

## Full Test Run

- [ ] **Run all tests before declaring done**

```bash
python -m pytest tests/ -v
```

Expected: all tests in `test_db.py`, `test_models.py`, `test_spectral.py`, `test_state_machine.py`, `test_recorder.py`, `test_routes.py` PASS. No tests exist for `capture.py`, `renderer.py`, `touch.py` — hardware-only.

- [ ] **Final commit**

```bash
git add -A
git commit -m "chore: final integration — all unit tests passing"
```
