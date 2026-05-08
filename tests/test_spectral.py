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
