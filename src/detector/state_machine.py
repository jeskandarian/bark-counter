import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class _State(Enum):
    IDLE    = "idle"
    BARKING = "barking"


@dataclass
class StateMachineResult:
    episode_complete: bool = False
    started_at: float  = 0.0
    ended_at:   float  = 0.0
    duration_ms: int   = 0
    bark_count:  int   = 0
    peak_db:     float = 0.0
    avg_db:      float = 0.0
    confidence:  float = 0.0


@dataclass
class _Acc:
    started_at:     float
    peak_db:        float = -120.0
    total_db:       float = 0.0
    chunk_count:    int   = 0
    confidence_sum: float = 0.0
    bark_count:     int   = 1
    in_dip:         bool  = False
    dip_count:      int   = 0


class BarkStateMachine:
    def __init__(self, onset_chunks: int, offset_chunks: int, dip_chunks: int):
        self._onset   = onset_chunks
        self._offset  = offset_chunks
        self._dip     = dip_chunks
        self._state   = _State.IDLE
        self._on_run  = 0
        self._off_run = 0
        self._acc: Optional[_Acc] = None
        self._pending_chunks = []

    def process(self, flagged: bool, dbfs: float, confidence: float, chunk_duration_s: float) -> StateMachineResult:
        if self._state == _State.IDLE:
            return self._idle(flagged, dbfs, confidence)
        return self._barking(flagged, dbfs, confidence)

    def _idle(self, flagged: bool, dbfs: float, conf: float) -> StateMachineResult:
        if flagged:
            self._pending_chunks.append((dbfs, conf))
            self._on_run += 1
            if self._on_run >= self._onset:
                self._state   = _State.BARKING
                self._off_run = 0
                self._acc     = _Acc(started_at=time.time())
                for pdb, pconf in self._pending_chunks:
                    self._tick(pdb, pconf)
                self._pending_chunks = []
        else:
            self._on_run = 0
            self._pending_chunks = []
        return StateMachineResult()

    def _barking(self, flagged: bool, dbfs: float, conf: float) -> StateMachineResult:
        if flagged:
            if self._acc.in_dip and self._acc.dip_count >= self._dip:
                self._acc.bark_count += 1
            self._acc.in_dip  = False
            self._acc.dip_count = 0
            self._off_run = 0
            self._tick(dbfs, conf)
            return StateMachineResult()

        self._off_run += 1
        self._acc.in_dip = True
        self._acc.dip_count += 1

        if self._off_run >= self._offset:
            return self._finish()
        return StateMachineResult()

    def _finish(self) -> StateMachineResult:
        acc = self._acc
        ended_at = time.time()
        result = StateMachineResult(
            episode_complete=True,
            started_at=acc.started_at,
            ended_at=ended_at,
            duration_ms=int((ended_at - acc.started_at) * 1000),
            bark_count=acc.bark_count,
            peak_db=acc.peak_db,
            avg_db=acc.total_db / acc.chunk_count if acc.chunk_count else 0.0,
            confidence=acc.confidence_sum / acc.chunk_count if acc.chunk_count else 0.0,
        )
        self._state   = _State.IDLE
        self._on_run  = 0
        self._off_run = 0
        self._acc     = None
        return result

    def _tick(self, dbfs: float, conf: float) -> None:
        self._acc.peak_db        = max(self._acc.peak_db, dbfs)
        self._acc.total_db      += dbfs
        self._acc.chunk_count   += 1
        self._acc.confidence_sum += conf
