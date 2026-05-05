# Bark Counter — Design Spec
*2026-05-04*

## Overview

A Raspberry Pi 4-based device that continuously listens for a neighbor's dog barking, counts both episodes and individual barks using spectral audio analysis, saves WAV clips of each event, and exposes the data via an HTTP server (dashboard + CSV export + audio streaming). A 4" TFT display shows a live glanceable summary on the device itself.

---

## Hardware Bill of Materials

| Component | Part | ~Cost |
|---|---|---|
| SBC | Raspberry Pi 4 Model B 1GB | $35 |
| Display | Waveshare 4inch RPi LCD (A) — 480×320 SPI, ILI9486 | $28 |
| Microphone | INMP441 I2S MEMS breakout | $6 |
| Storage | 32GB microSD (Class 10) | $8 |
| Power | 5V/3A USB-C supply | $10 |
| **Total** | | **~$87** |

---

## Wiring — INMP441 to Pi 4 GPIO

The Waveshare HAT occupies the full 40-pin header but exposes a passthrough header. I2S pins (GPIO 18–20) are not used by the display and are available on the passthrough.

The display uses SPI0 (GPIO 8, 10, 11) and GPIO 7, 17, 24, 25, 27 for CS/DC/RST/BL/touch-IRQ — no conflict with I2S.

```
INMP441   →   Pi 4 (BCM)            Physical Pin
────────────────────────────────────────────────────
VDD       →   3.3V                  Pin 1
GND       →   GND                   Pin 6
SCK       →   GPIO 18 (I2S CLK)    Pin 12
WS        →   GPIO 19 (I2S WS)     Pin 35
SD        →   GPIO 20 (I2S DIN)    Pin 38
L/R       →   GND                  (selects left channel)
```

---

## Software Architecture

Three `systemd` services, each an independent Python process. SQLite with WAL mode is the shared data store — allows concurrent reads from web and display while the detector writes.

```
┌─────────────────────────────────────────────────────────┐
│  bark-detector.service          (Nice=-5)               │
│                                                          │
│  sounddevice → I2S capture (16kHz mono)                 │
│  → circular pre-roll buffer (2s)                        │
│  → FFT spectral analysis per 64ms chunk                 │
│  → bark state machine (onset / sustain / offset)        │
│  → peak detector (individual bark count within episode) │
│  → on episode end: write SQLite row + save WAV clip     │
└─────────────────────┬───────────────────────────────────┘
                      │ SQLite WAL (/var/lib/bark-counter/barks.db)
          ┌───────────┴───────────┐
          ▼                       ▼
┌──────────────────┐   ┌──────────────────────────────────┐
│ bark-display     │   │ bark-web.service                  │
│ .service         │   │                                   │
│                  │   │ Flask on port 80                  │
│ pygame →         │   │ GET /  → dashboard + Chart.js    │
│ /dev/fb1         │   │ GET /api/barks → JSON            │
│                  │   │ GET /api/export.csv → download   │
│ reads SQLite     │   │ GET /recordings/<f> → WAV stream │
│ every 5s         │   │ GET /api/stats → summary JSON    │
│ touch via evdev  │   │                                   │
└──────────────────┘   └──────────────────────────────────┘
```

**systemd configuration:**
- `bark-detector`: `Nice=-5`, `Restart=always`, starts after network
- `bark-web`: `Restart=always`, depends on bark-detector (DB must exist)
- `bark-display`: `Restart=always`, depends on bark-detector
- mDNS via `avahi-daemon` — device reachable at `bark-counter.local`

---

## Audio Capture and Bark Detection Pipeline

**Capture parameters:**
- 16kHz sample rate, mono, 32-bit float via `sounddevice` callback mode
- Chunk size: 1024 samples = 64ms per chunk
- Circular pre-roll buffer: 2s (~31 chunks) via `collections.deque`

**Spectral analysis per chunk:**
1. Apply Hann window to chunk
2. `numpy.fft.rfft` → frequency bins
3. Compute power spectral density
4. Extract band energies:
   - **Bark band:** 500Hz – 2000Hz
   - **Total band:** 80Hz – 8000Hz
5. Chunk flagged as "bark-like" if both:
   - `bark_band_energy / total_band_energy > SPECTRAL_RATIO_THRESHOLD` (default 0.45)
   - `total_dBFS > DB_FLOOR` (default -30dBFS)

**Episode state machine:**
```
IDLE → (ONSET_CHUNKS consecutive flagged chunks) → BARKING
BARKING → (OFFSET_CHUNKS consecutive unflagged chunks) → write SQLite + save WAV → IDLE
```
- Default `ONSET_CHUNKS = 3` (192ms to enter — prevents transient false triggers)
- Default `OFFSET_CHUNKS = 8` (512ms to exit — handles brief mid-bark silences)

**Individual bark counter (within BARKING state):**
- Envelope follower tracks running RMS across chunks
- Each upward crossing of threshold after a minimum dip of ~150ms increments `bark_count`
- Stored on the episode row, not as separate DB rows

**WAV clip per episode:**
- 2s pre-roll (from circular buffer) + episode duration + 1s post-roll
- 16kHz mono 16-bit PCM WAV saved to `/var/lib/bark-counter/recordings/`
- Filename: `bark_<ISO8601_timestamp>.wav` (colons replaced with hyphens for filesystem safety)

**Tunable parameters (config.toml):**
```toml
BARK_BAND_LOW = 500       # Hz
BARK_BAND_HIGH = 2000     # Hz
SPECTRAL_RATIO_THRESHOLD = 0.45
DB_FLOOR = -30            # dBFS
ONSET_CHUNKS = 3
OFFSET_CHUNKS = 8
TIMEZONE = "America/Los_Angeles"
```

---

## Data Storage Schema

SQLite at `/var/lib/bark-counter/barks.db`, WAL mode.

```sql
CREATE TABLE episodes (
    id          INTEGER PRIMARY KEY,
    started_at  REAL NOT NULL,       -- Unix timestamp (UTC)
    ended_at    REAL NOT NULL,
    duration_ms INTEGER NOT NULL,
    bark_count  INTEGER NOT NULL,    -- individual barks within episode
    peak_db     REAL NOT NULL,
    avg_db      REAL NOT NULL,
    confidence  REAL NOT NULL,       -- avg spectral ratio across episode
    wav_file    TEXT                 -- basename only, e.g. bark_2026-05-04T15-42-00.wav
);

CREATE INDEX idx_episodes_started ON episodes(started_at);
```

Full path is `/var/lib/bark-counter/recordings/<wav_file>`. The HTTP endpoint serves it at `/recordings/<wav_file>`.

Config lives in `config.toml`, not the database.

---

## HTTP API

Flask server on port 80. All endpoints read SQLite in read-only mode.

```
GET /
    Full dashboard HTML — Chart.js served as static file (no CDN)
    Bar chart: barks per hour | Line overlay: episodes per hour
    Summary cards: Today and LastHr counts
    Zoom strip: 1h | 6h | 24h | 7d | 30d
    Episode list below chart, filtered by clicking a bar
    Each row: timestamp, duration, bark_count, peak_db, play button

GET /api/barks?start=<unix>&end=<unix>
    JSON array of episodes in time range

GET /api/export.csv?start=<unix>&end=<unix>&tz=<IANA>
    CSV download with local-timezone timestamps
    Columns: id, started_at_local, ended_at_local, duration_ms,
             bark_count, peak_db, avg_db, confidence, wav_file
    Defaults to full history if no range given

GET /recordings/<filename>
    WAV file stream with Accept-Ranges (seekable in browser)

GET /api/stats
    JSON summary: last_hour, today, this_week, all_time
    Each: { episodes, barks, peak_db }
    Polled every 30s by dashboard
```

---

## Display Rendering

**Driver:** Waveshare 4" (A) ILI9486 device tree overlay exposes `/dev/fb1` (display) and `/dev/input/event0` (XPT2046 resistive touch). pygame runs with `SDL_VIDEODRIVER=fbcon`, `SDL_FBDEV=/dev/fb1` — no X11 required.

**Touch calibration:** 4-point calibration on first boot, stored to a file, loaded at display service startup.

**Layout (480×320):**
```
┌─────────────────────────────────────────────────────────────────┐
│ BARK COUNTER  15:42 Mon 04 May   Today: 31/147   LastHr: 6/23  │  28px
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                      bar chart                                   │  262px
│              (barks per hour, active zoom window)               │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│         [ 1h ]      [ 6h ]      [ 24h ]      [ 7d ]            │  30px
└─────────────────────────────────────────────────────────────────┘
```

Header format: `episodes/barks` — `Today: 31/147` = 31 episodes, 147 individual barks.

**Rendering loop:**
- Full redraw every 5 seconds (SQLite read → pygame blit)
- Touch on zoom button: updates active time window, triggers immediate redraw
- Bundled monospace bitmap font (no system font dependency)
