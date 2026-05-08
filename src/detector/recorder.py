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
