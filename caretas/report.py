"""Relatório da partida: o que a IA "anotou" enquanto a pessoa jogava.

É a mesma ideia de um relatório de uso real: o modelo resume o que viu e um
humano confere. Guarda só números em memória (probabilidades suavizadas,
valência, excitação e tempos), nunca imagens, e tudo é apagado no reset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .emotion import CLASS_INDEX, CLASS_NAMES, EmotionReading

MAX_SAMPLES = 6000          # ~3 min a 30 FPS: sobra para uma partida de 60 s
TARGET_KEYS = ("happiness", "surprise", "sadness")
BONUS_KEYS = ("anger", "contempt", "disgust", "fear")   # "a IA também viu..."


class MatchHistory:
    """Leituras suavizadas da partida (calibração + jogo), só em memória."""

    def __init__(self):
        self.clear()

    def clear(self) -> None:
        self.t: list[float] = []
        self.probs: list[np.ndarray] = []
        self.valence: list[float] = []
        self.arousal: list[float] = []
        self.playing: list[bool] = []

    def __len__(self) -> int:
        return len(self.t)

    def add(self, t: float, r: EmotionReading, playing: bool) -> None:
        if len(self.t) >= MAX_SAMPLES:
            return
        self.t.append(float(t))
        self.probs.append(np.asarray(r.probs, np.float32).copy())
        self.valence.append(float(r.valence))
        self.arousal.append(float(r.arousal))
        self.playing.append(bool(playing))


@dataclass
class TargetResult:
    key: str
    done: bool
    seconds: float | None = None   # quanto levou desde que a careta foi pedida
    at: float | None = None        # quando foi reconhecida (s desde o início da partida)
    peak: float = 0.0              # maior probabilidade dessa emoção durante o jogo


@dataclass
class MatchReport:
    number: int
    won: bool
    duration: float                          # segundos de jogo (sem a calibração)
    times: np.ndarray                        # (N,) s relativos ao início do jogo; calibração < 0
    probs: np.ndarray                        # (N, 8)
    valence: np.ndarray                      # (N,)
    arousal: np.ndarray                      # (N,)
    targets: list[TargetResult] = field(default_factory=list)
    strongest: str | None = None             # careta feita com a maior "força" (probabilidade)
    fastest: str | None = None               # careta feita mais rápido
    bonus: tuple[str, float] | None = None   # emoção fora do jogo que mais apareceu (e o pico)
    bonus_at: float | None = None            # quando foi esse pico (s desde o início do jogo)
    dominant: tuple[str, float] = ("neutral", 0.0)   # emoção no topo por mais tempo (fração)

    def target(self, key: str) -> TargetResult | None:
        return next((t for t in self.targets if t.key == key), None)

    def wipe(self) -> None:
        for arr in (self.times, self.probs, self.valence, self.arousal):
            arr.fill(0)


def build_report(number: int, won: bool, history: MatchHistory, match_t0: float, end_t: float,
                 order: list[str], completions: dict[str, tuple[float, float]]) -> MatchReport:
    """`completions`: emoção -> (segundos que levou, instante absoluto em que foi reconhecida)."""
    n = len(history)
    times = np.asarray(history.t, np.float64) - match_t0 if n else np.zeros(0)
    probs = np.stack(history.probs) if n else np.zeros((0, len(CLASS_NAMES)), np.float32)
    valence = np.asarray(history.valence, np.float32) if n else np.zeros(0, np.float32)
    arousal = np.asarray(history.arousal, np.float32) if n else np.zeros(0, np.float32)
    playing = np.asarray(history.playing, bool) if n else np.zeros(0, bool)
    play_probs = probs[playing] if n else probs

    def peak(key: str) -> float:
        return float(play_probs[:, CLASS_INDEX[key]].max()) if len(play_probs) else 0.0

    targets = []
    for key in order:
        if key in completions:
            secs, at = completions[key]
            targets.append(TargetResult(key, True, float(secs), float(at - match_t0), peak(key)))
        else:
            targets.append(TargetResult(key, False, None, None, peak(key)))

    done = [t for t in targets if t.done]
    strongest = max(done, key=lambda t: t.peak).key if done else None
    fastest = min(done, key=lambda t: t.seconds).key if done else None

    bonus, bonus_at = None, None
    if len(play_probs):
        key = max(BONUS_KEYS, key=peak)
        bonus = (key, peak(key))
        play_times = times[playing]
        bonus_at = float(play_times[int(play_probs[:, CLASS_INDEX[key]].argmax())])

    dominant = ("neutral", 0.0)
    if len(play_probs):
        counts = np.bincount(play_probs.argmax(axis=1), minlength=len(CLASS_NAMES))
        i = int(counts.argmax())
        dominant = (CLASS_NAMES[i], float(counts[i] / counts.sum()))

    return MatchReport(number, won, max(0.0, end_t - match_t0), times, probs, valence, arousal,
                       targets, strongest, fastest, bonus, bonus_at, dominant)
