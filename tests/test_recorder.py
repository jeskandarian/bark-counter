import wave
import numpy as np
from collections import deque
from src.detector.recorder import save_wav_clip

SR = 16000
N  = 1024


def chunk(val=0.1):
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
