# Bark Counter — Claude Context

## What this is

A Raspberry Pi 4 device that listens for a neighbor's dog barking, counts episodes and individual barks via FFT spectral analysis, saves WAV clips, and exposes data through an HTTP dashboard. A 4" TFT shows a live summary on-device.

## Running tests

```bash
python3 -m pytest tests/ -v
```

34 tests across 6 files. All should pass. No tests exist for `capture.py`, `renderer.py`, or `touch.py` — hardware-only, verify on-device.

## Architecture

Three independent systemd services sharing a single SQLite database in WAL mode:

```
bark-detector   Nice=-5   src/detector/__main__.py   writes episodes + WAV clips
bark-web                  src/web/__main__.py         Flask on port 80, read-only
bark-display              src/display/__main__.py     pygame → /dev/fb1, read-only
```

SQLite at `/var/lib/bark-counter/barks.db`. WAL mode allows concurrent reads from web and display while the detector writes.

WAV clips at `/var/lib/bark-counter/recordings/`. Served via `/recordings/<filename>` on the web server.

## Key files

| File | Role |
|---|---|
| `config.toml` | All tunable parameters — edit this, not source code |
| `src/config.py` | Loads config.toml into typed dataclasses |
| `src/storage/db.py` | SQLite connection factory, WAL setup, schema |
| `src/storage/models.py` | `insert_episode()`, `query_episodes()`, `query_stats()` |
| `src/detector/spectral.py` | FFT bark detection — Hann window, band energy ratio, dBFS |
| `src/detector/state_machine.py` | Episode FSM (IDLE↔BARKING) + individual bark counter |
| `src/detector/recorder.py` | 16-bit PCM WAV writer with pre/post roll |
| `src/detector/capture.py` | sounddevice I2S capture + pre-roll deque |
| `src/web/app.py` | Flask app factory `create_app(db_path, recordings_dir)` |
| `src/web/routes.py` | HTTP endpoints (see API section below) |
| `src/web/static/dashboard.html` | Chart.js dashboard — zoom strip, bar+line chart, episode table |
| `src/display/layout.py` | Screen constants (480×320), colors, zoom levels |
| `src/display/renderer.py` | pygame framebuffer renderer — header, chart, zoom strip |
| `src/display/touch.py` | evdev XPT2046 touch with 4-point calibration |
| `setup.sh` | Full Pi deployment — I2S, ALSA, systemd, avahi |

## HTTP API

```
GET /                          dashboard HTML
GET /api/barks?start=&end=     JSON array of episodes
GET /api/stats                 {last_hour, today, this_week, all_time}
GET /api/export.csv?tz=        CSV download with local-timezone timestamps
GET /recordings/<filename>     WAV stream with Accept-Ranges
```

## Detection pipeline

```
sounddevice callback (1024 samples = 64ms chunks at 16kHz)
  → Hann window + rfft → PSD
  → bark_band_energy(500–2000Hz) / total_band_energy(80–8000Hz) > 0.45
  → AND total_dBFS > -30
  → BarkStateMachine: 3 consecutive flagged = BARKING, 8 consecutive unflagged = episode end
  → dip of ≥2 unflagged chunks within episode = new individual bark
  → on episode end: save WAV (2s pre-roll + episode + 1s post-roll), insert SQLite row
```

## Dev machine vs Pi

| | Dev (macOS) | Pi target |
|---|---|---|
| Python | 3.9.6 | 3.11+ (Bookworm) |
| `tomllib` | not in stdlib — `tomli` backport via requirements.txt | stdlib |
| `sounddevice` | imports fine, no audio hardware | INMP441 via ALSA |
| `pygame` | imports fine, no framebuffer | `/dev/fb1` via `SDL_VIDEODRIVER=fbcon` |
| `evdev` | not available on macOS — `touch.py` degrades gracefully | `/dev/input/event0` |

Never try to call `renderer.init()` or start `AudioCapture` in tests — hardware only.

## Hardware

- **SBC**: Raspberry Pi 4 Model B 1GB
- **Mic**: INMP441 I2S MEMS — GPIO 18 (CLK), 19 (WS), 20 (DIN); L/R pin → GND for left channel
- **Display**: Waveshare 4inch RPi LCD (A), ILI9486, 480×320 SPI — exposes `/dev/fb1` and `/dev/input/event0` (XPT2046 resistive touch) via device tree overlay
- **I2S and display pins do not conflict** — display uses SPI0 (GPIO 8,10,11) + control pins (7,17,24,25,27)

## First-time Pi setup

```bash
git clone https://github.com/jeskandarian/bark-counter /home/pi/bark-counter
cd /home/pi/bark-counter
bash setup.sh
sudo reboot
# after reboot:
sudo systemctl start bark-detector bark-web bark-display
```

Dashboard reachable at `http://bark-counter.local` via mDNS (avahi).

**Waveshare display overlay must be installed manually before running setup.sh** — the script detects and warns if missing. See https://www.waveshare.com/wiki/4inch_RPi_LCD_(A)
