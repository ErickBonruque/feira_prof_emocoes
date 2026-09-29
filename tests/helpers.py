"""Leituras e quadros sintéticos para testar a lógica sem câmera."""

from __future__ import annotations

import numpy as np

from caretas.detection import Face
from caretas.emotion import CLASS_INDEX, EmotionReading
from caretas.pipeline import FrameResult


def reading(probs: dict[str, float] | None = None, valence: float = 0.0, arousal: float = 0.0) -> EmotionReading:
    """Leitura com as probabilidades dadas; o resto vai para 'neutral'."""
    p = np.zeros(8)
    for k, v in (probs or {}).items():
        p[CLASS_INDEX[k]] = v
    p[CLASS_INDEX["neutral"]] += max(0.0, 1.0 - p.sum())
    return EmotionReading(p / p.sum(), valence, arousal)


NEUTRAL = reading({"neutral": 0.85, "happiness": 0.05, "sadness": 0.05}, 0.0, -0.1)
HAPPY = reading({"happiness": 0.95}, 0.8, 0.2)
SURPRISED = reading({"surprise": 0.85, "fear": 0.1}, 0.1, 0.9)
SAD = reading({"sadness": 0.85}, -0.7, -0.4)
MILD_SMILE = reading({"happiness": 0.55}, 0.25, 0.0)  # sorrisinho: não pode contar


def face(x=500, y=250, w=260, h=300, score=0.9) -> Face:
    lm = np.array([[x + w * 0.3, y + h * 0.4], [x + w * 0.7, y + h * 0.4], [x + w * 0.5, y + h * 0.6],
                   [x + w * 0.35, y + h * 0.8], [x + w * 0.65, y + h * 0.8]], np.float32)
    return Face(x, y, w, h, score, lm)


_FRAME = np.zeros((720, 1280, 3), np.uint8)


def result(t: float, fid: int, r: EmotionReading | None, locked: bool = True, player=True,
           lost_for: float = 0.0) -> FrameResult:
    f = face() if player else None
    return FrameResult(frame_id=fid, timestamp=t, frame=_FRAME, faces=[f] if f else [], player=f,
                       locked=locked, candidate=None, lock_progress=1.0 if locked else 0.0,
                       lost_for=lost_for, reading=r if player else None)


class Sim:
    """Roda o jogo quadro a quadro a 30 FPS com um relógio falso."""

    def __init__(self, game, fps: float = 30.0, t0: float = 100.0):
        self.game = game
        self.dt = 1.0 / fps
        self.t = t0
        self.fid = 0

    def run(self, seconds: float, r: EmotionReading | None, **kw) -> None:
        n = int(round(seconds / self.dt))
        for _ in range(n):
            self.t += self.dt
            self.fid += 1
            self.game.update(result(self.t, self.fid, r, **kw), self.t)
