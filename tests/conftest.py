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
