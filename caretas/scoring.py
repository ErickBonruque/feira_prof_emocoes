"""Regras anti "vitória fácil": suavização, neutro da pessoa, limiares e tempo mínimo."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import CalibrationConfig, EmotionRule
from .emotion import CLASS_INDEX, EmotionReading

TARGETS = ("happiness", "surprise", "sadness")


class Smoother:
    """Média móvel exponencial das probabilidades e de valência/excitação."""

    def __init__(self, alpha: float):
        self.alpha = alpha
        self.state: EmotionReading | None = None

    def reset(self) -> None:
        self.state = None

    def update(self, r: EmotionReading) -> EmotionReading:
        if self.state is None:
            self.state = EmotionReading(r.probs.copy(), r.valence, r.arousal)
        else:
            a = self.alpha
            s = self.state
            self.state = EmotionReading(
                (1 - a) * s.probs + a * r.probs,
                (1 - a) * s.valence + a * r.valence,
                (1 - a) * s.arousal + a * r.arousal,
            )
        return self.state


@dataclass
class Baseline:
    probs: np.ndarray
    valence: float
    arousal: float
    is_default: bool = False

    @staticmethod
    def default() -> "Baseline":
        # Neutro "genérico" usado se a calibração falhar: os limiares absolutos continuam valendo.
        probs = np.full(8, 0.05)
        probs[CLASS_INDEX["neutral"]] = 0.65
        return Baseline(probs / probs.sum(), 0.0, 0.0, is_default=True)


@dataclass
class CalibrationResult:
    ok: bool
    baseline: Baseline | None
    reason: str = ""   # "", "expressive" (não estava neutro), "few_frames"


class Calibrator:
    """Junta leituras cruas durante alguns segundos e calcula o neutro da pessoa."""

    def __init__(self, cfg: CalibrationConfig):
        self.cfg = cfg
        self._readings: list[EmotionReading] = []

    def reset(self) -> None:
        self._readings.clear()

    @property
    def frames(self) -> int:
        return len(self._readings)

    def add(self, r: EmotionReading) -> None:
        self._readings.append(r)

    def finish(self) -> CalibrationResult:
        if len(self._readings) < self.cfg.min_frames:
            return CalibrationResult(False, None, "few_frames")
        probs = np.mean([r.probs for r in self._readings], axis=0)
        baseline = Baseline(
            probs,
            float(np.mean([r.valence for r in self._readings])),
            float(np.mean([r.arousal for r in self._readings])),
        )
        # Se a pessoa já estava fazendo careta, o "neutro" fica distorcido: pede de novo.
        if max(probs[CLASS_INDEX[k]] for k in TARGETS) > self.cfg.max_expression:
            return CalibrationResult(False, baseline, "expressive")
        return CalibrationResult(True, baseline)


@dataclass
class Check:
    value: float
    threshold: float

    @property
    def ok(self) -> bool:
        return self.value >= self.threshold

    def ratio(self) -> float:
        """0..1: quão perto de cumprir (para barras de feedback)."""
        if self.threshold > 1e-6:
            return float(np.clip(self.value / self.threshold, 0.0, 1.0))
        return float(np.clip(1.0 + (self.value - self.threshold) / 0.5, 0.0, 1.0))


@dataclass
class Evaluation:
    target: str
    checks: dict[str, Check] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks.values())

    @property
    def intensity(self) -> float:
        """Condição mais distante de ser cumprida manda (gargalo)."""
        return min(c.ratio() for c in self.checks.values()) if self.checks else 0.0


def evaluate(target: str, rule: EmotionRule, s: EmotionReading, base: Baseline) -> Evaluation:
    idx = CLASS_INDEX[target]
    p = float(s.probs[idx])
    sign = 1.0 if rule.direction == "up" else -1.0
    axis_now = s.valence if rule.axis == "valence" else s.arousal
    axis_base = base.valence if rule.axis == "valence" else base.arousal
    return Evaluation(target, {
        "prob": Check(p, rule.min_prob),
        "gain": Check(p - float(base.probs[idx]), rule.min_gain),
        "axis": Check(sign * axis_now, rule.axis_min),
        "axis_gain": Check(sign * (axis_now - axis_base), rule.axis_gain),
    })


class HoldTimer:
    """A expressão precisa ficar certa por N quadros SEGUIDOS e por T segundos."""

    def __init__(self, seconds: float, frames: int):
        self.seconds = seconds
        self.frames = frames
        self.reset()

    def reset(self) -> None:
        self.count = 0
        self.start: float | None = None

    def update(self, passed: bool, t: float) -> float:
        if not passed:
            self.reset()
            return 0.0
        if self.start is None:
            self.start = t
        self.count += 1
        return self.progress(t)

    def progress(self, t: float) -> float:
        if self.start is None:
            return 0.0
        by_frames = self.count / self.frames
        by_time = 1.0 if self.seconds <= 0 else (t - self.start) / self.seconds
        return float(min(1.0, by_frames, by_time))

    def completed(self, t: float) -> bool:
        return self.start is not None and self.count >= self.frames and (t - self.start) >= self.seconds
