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

    episode_buf = []
    post_remaining = [0]

    def on_chunk(chunk, pre_roll):
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
