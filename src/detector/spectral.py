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
) -> tuple:
    bark  = compute_band_energy(samples, sample_rate, bark_low, bark_high)
    total = compute_band_energy(samples, sample_rate, total_low, total_high)
    ratio = bark / total if total > 0.0 else 0.0
    dbfs  = samples_to_dbfs(samples)
    return ratio > ratio_threshold and dbfs > db_floor, ratio, dbfs
