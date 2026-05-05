import pytest
from src.detector.state_machine import BarkStateMachine, StateMachineResult


def feed(sm, seq, dbfs=-20.0, conf=0.6):
    return [sm.process(f, dbfs, conf, 0.064) for f in seq]


def test_silence_produces_no_episode():
    sm = BarkStateMachine(3, 8, 2)
    assert not any(r.episode_complete for r in feed(sm, [False] * 20))


def test_two_flagged_chunks_do_not_trigger():
    sm = BarkStateMachine(3, 8, 2)
    assert not any(r.episode_complete for r in feed(sm, [True, True, False] * 6))


def test_episode_completes_after_offset_chunks():
    sm = BarkStateMachine(3, 8, 2)
    results = feed(sm, [True] * 5 + [False] * 8)
    assert sum(1 for r in results if r.episode_complete) == 1


def test_continuous_bark_is_one_bark():
    sm = BarkStateMachine(3, 8, 2)
    results = feed(sm, [True] * 10 + [False] * 8)
    ep = next(r for r in results if r.episode_complete)
    assert ep.bark_count == 1


def test_dip_then_bark_counts_two():
    sm = BarkStateMachine(3, 8, 2)
    # onset(5) + dip(2 = dip_chunks) + second bark(3) + offset(8)
    seq = [True] * 5 + [False] * 2 + [True] * 3 + [False] * 8
    results = feed(sm, seq)
    ep = next(r for r in results if r.episode_complete)
    assert ep.bark_count == 2


def test_peak_db_is_maximum():
    sm = BarkStateMachine(3, 8, 2)
    sm.process(True, -30.0, 0.5, 0.064)
    sm.process(True, -10.0, 0.5, 0.064)
    sm.process(True, -20.0, 0.5, 0.064)
    last = None
    for _ in range(8):
        last = sm.process(False, -40.0, 0.0, 0.064)
    assert last.peak_db == pytest.approx(-10.0)


def test_state_resets_for_second_episode():
    sm = BarkStateMachine(3, 8, 2)
    feed(sm, [True] * 5 + [False] * 8)
    results = feed(sm, [True] * 5 + [False] * 8)
    assert sum(1 for r in results if r.episode_complete) == 1
