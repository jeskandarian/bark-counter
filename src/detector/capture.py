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
