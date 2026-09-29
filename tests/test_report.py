import pytest

from caretas.report import MAX_SAMPLES, MatchHistory, build_report

from .helpers import HAPPY, NEUTRAL, SAD, SURPRISED, reading


def history(samples):
    h = MatchHistory()
    for t, r, playing in samples:
        h.add(t, r, playing)
    return h


def test_report_summarizes_the_match():
    fear = reading({"fear": 0.6}, -0.3, 0.6)
    h = history([(9.0, NEUTRAL, False), (10.5, HAPPY, True), (11.0, fear, True),
                 (12.0, SURPRISED, True), (13.0, NEUTRAL, True), (14.0, NEUTRAL, True)])
    rep = build_report(7, False, h, match_t0=10.0, end_t=15.0, order=["happiness", "surprise", "sadness"],
                       completions={"happiness": (1.2, 11.2), "surprise": (0.9, 12.1)})
    assert rep.number == 7 and not rep.won and rep.duration == pytest.approx(5.0)
    assert rep.times[0] == pytest.approx(-1.0)            # calibração fica antes do zero
    happy, surprise, sad = rep.targets
    assert happy.done and happy.seconds == pytest.approx(1.2) and happy.at == pytest.approx(1.2)
    assert happy.peak == pytest.approx(HAPPY.prob("happiness"), abs=1e-6)
    assert not sad.done and sad.seconds is None
    assert rep.strongest == "happiness"                   # 0,95 > 0,85
    assert rep.fastest == "surprise"
    assert rep.bonus[0] == "fear" and rep.bonus[1] == pytest.approx(0.6, abs=1e-6)
    assert rep.bonus_at == pytest.approx(1.0)             # o medo apareceu em t = 11 s (1 s de jogo)
    assert rep.dominant[0] == "neutral" and rep.dominant[1] == pytest.approx(2 / 5)


def test_calibration_samples_do_not_count_as_peaks():
    h = history([(0.0, HAPPY, False), (1.0, NEUTRAL, True)])
    rep = build_report(1, False, h, 0.5, 2.0, ["happiness"], {})
    assert rep.targets[0].peak < 0.2
    assert rep.strongest is None and rep.fastest is None


def test_empty_history_does_not_crash():
    rep = build_report(1, False, MatchHistory(), 0.0, 1.0, ["happiness", "surprise", "sadness"], {})
    assert len(rep.times) == 0 and rep.bonus is None and rep.dominant[0] == "neutral"


def test_history_is_capped_and_wipe_zeroes_the_numbers():
    h = MatchHistory()
    for i in range(MAX_SAMPLES + 50):
        h.add(i, SAD, True)
    assert len(h) == MAX_SAMPLES
    rep = build_report(1, True, h, 0.0, 1.0, ["sadness"], {"sadness": (1.0, 1.0)})
    rep.wipe()
    assert not rep.probs.any() and not rep.valence.any()
    h.clear()
    assert len(h) == 0
