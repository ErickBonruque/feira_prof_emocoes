import numpy as np
import pytest

from caretas.config import CalibrationConfig, RulesConfig
from caretas.scoring import Baseline, Calibrator, HoldTimer, Smoother, evaluate

from .helpers import HAPPY, NEUTRAL, SAD, SURPRISED, reading


def test_smoother_moves_gradually():
    s = Smoother(0.4)
    s.update(NEUTRAL)
    out = s.update(HAPPY)
    assert NEUTRAL.prob("happiness") < out.prob("happiness") < HAPPY.prob("happiness")
    assert out.probs.sum() == pytest.approx(1.0)


def test_calibrator_rejects_expressive_and_few_frames():
    cal = Calibrator(CalibrationConfig(min_frames=5, max_expression=0.45))
    for _ in range(3):
        cal.add(NEUTRAL)
    assert cal.finish().reason == "few_frames"
    cal.reset()
    for _ in range(10):
        cal.add(HAPPY)
    res = cal.finish()
    assert not res.ok and res.reason == "expressive"
    cal.reset()
    for _ in range(10):
        cal.add(NEUTRAL)
    assert cal.finish().ok


@pytest.mark.parametrize("target,good,bads", [
    ("happiness", HAPPY, [NEUTRAL, SURPRISED, SAD]),
    ("surprise", SURPRISED, [NEUTRAL, HAPPY, SAD]),
    ("sadness", SAD, [NEUTRAL, HAPPY, SURPRISED]),
])
def test_evaluate_targets(target, good, bads):
    rules = RulesConfig()
    base = Baseline(NEUTRAL.probs, NEUTRAL.valence, NEUTRAL.arousal)
    assert evaluate(target, rules.for_emotion(target), good, base).passed
    for bad in bads:
        ev = evaluate(target, rules.for_emotion(target), bad, base)
        assert not ev.passed
        assert ev.intensity < 1.0


def test_high_class_prob_without_valence_is_rejected():
    """Classe alta mas valência neutra (ex.: ruído do modelo) não passa."""
    rules = RulesConfig()
    base = Baseline(NEUTRAL.probs, 0.0, 0.0)
    fake = reading({"happiness": 0.9}, valence=0.05, arousal=0.0)
    assert not evaluate("happiness", rules.happiness, fake, base).passed


def test_hold_timer_needs_frames_and_time():
    h = HoldTimer(seconds=1.0, frames=12)
    t = 0.0
    for _ in range(12):     # 12 quadros em 0,36 s: frames ok, tempo não
        h.update(True, t)
        t += 0.03
    assert not h.completed(t - 0.03)
    while t < 1.05:
        h.update(True, t)
        t += 0.03
    assert h.completed(t - 0.03)
    h.update(False, t)
    assert h.progress(t) == 0.0 and not h.completed(t)


def test_default_baseline_is_valid_distribution():
    b = Baseline.default()
    assert b.is_default and np.isclose(b.probs.sum(), 1.0)
