import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

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
