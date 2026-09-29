"""Efeitos sonoros sintetizados por código (nada para baixar, nenhuma licença).

Cada som é gerado com numpy na abertura do jogo (~0,1 s). Se não houver saída de
áudio, o jogo segue mudo sem reclamar. Tecla M liga/desliga.
"""

from __future__ import annotations

import logging

import numpy as np
import pygame

from ..game import Game, Phase

log = logging.getLogger(__name__)

RATE = 44100


def _note(name: str) -> float:
    """'C5' -> Hz (lá 440)."""
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave - 4)) / 12)


def _t(dur: float) -> np.ndarray:
    return np.arange(int(RATE * dur)) / RATE


def _env(n: int, attack: float = 0.005, decay: float = 8.0) -> np.ndarray:
    t = np.arange(n) / RATE
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t * decay)


def tone(freq: float, dur: float, kind: str = "sine", decay: float = 6.0, attack: float = 0.005,
         slide: float | None = None, vibrato: float = 0.0) -> np.ndarray:
    """Nota com envelope. `slide`: frequência final (glissando). Formas: sine, tri, square, brass, bell."""
    t = _t(dur)
    f = np.full_like(t, freq) if slide is None else freq * (slide / freq) ** (t / dur)
    if vibrato:
        f = f * (1 + vibrato * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.15, 0, 1))
    ph = 2 * np.pi * np.cumsum(f) / RATE
    if kind == "sine":
        w = np.sin(ph)
    elif kind == "tri":
        w = 2 / np.pi * np.arcsin(np.sin(ph))
    elif kind == "square":   # quadrada "macia": só harmônicos ímpares baixos
        w = sum(np.sin(k * ph) / k for k in (1, 3, 5, 7)) * 0.8
    elif kind == "brass":    # dente de serra com poucos harmônicos (trombone de desenho animado)
        w = sum(np.sin(k * ph) / k for k in range(1, 7)) * 0.6
    elif kind == "bell":
        w = np.sin(ph) + 0.4 * np.sin(2.76 * ph) + 0.2 * np.sin(5.4 * ph)
    else:
        raise ValueError(kind)
    return (w * _env(len(t), attack, decay)).astype(np.float32)


def noise(dur: float, decay: float = 20.0, smooth: int = 1, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    w = rng.uniform(-1, 1, int(RATE * dur))
    if smooth > 1:   # passa-baixa simples (média móvel): chiado mais grave
        w = np.convolve(w, np.ones(smooth) / smooth, mode="same")
    return (w * _env(len(w), 0.002, decay)).astype(np.float32)


def seq(*parts: tuple[float, np.ndarray]) -> np.ndarray:
    """Mistura sons começando em instantes diferentes: seq((0.0, a), (0.1, b))."""
    end = max(int(t * RATE) + len(x) for t, x in parts)
    out = np.zeros(end, np.float32)
    for t, x in parts:
        i = int(t * RATE)
        out[i:i + len(x)] += x
    return out


def _norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = float(np.abs(x).max()) or 1.0
    return x * (peak / m)


def build_sounds() -> dict[str, np.ndarray]:
    """Todos os efeitos, como float32 mono em -1..1."""
    N = _note
    s: dict[str, np.ndarray] = {}
    s["lock"] = seq((0, tone(N("E5"), 0.09, "tri", 18)), (0.08, tone(N("B5"), 0.14, "tri", 14)))
    s["tick"] = seq((0, tone(1200, 0.05, "sine", 60)), (0, noise(0.02, 120, 3) * 0.3))
    s["go"] = seq(*[(i * 0.07, tone(N(n), 0.16, "square", 14) * 0.7) for i, n in enumerate(("C5", "E5", "G5", "C6"))])
    for i, n in enumerate(("E5", "G5")):
        s[f"charge{i + 1}"] = tone(N(n), 0.12, "tri", 16)
    shutter = seq((0, noise(0.03, 90, 1)), (0.05, noise(0.04, 70, 1) * 0.7))
    s["done"] = seq((0, shutter * 0.6), *[(0.05 + i * 0.06, tone(N(n), 0.5, "bell", 7) * 0.5)
                                          for i, n in enumerate(("G5", "B5", "D6", "G6"))])
    fan = [(0.0, "C5", 0.11), (0.12, "C5", 0.11), (0.24, "C5", 0.11), (0.36, "E5", 0.3), (0.62, "G5", 0.12), (0.76, "C6", 0.9)]
    parts = [(t, tone(N(n), d, "square", 2.5 if d > 0.5 else 9, vibrato=0.006 if d > 0.5 else 0.0) * 0.6) for t, n, d in fan]
    parts += [(0.76, tone(N("E5"), 0.9, "square", 2.5) * 0.35), (0.76, tone(N("G5"), 0.9, "square", 2.5) * 0.35)]
    s["victory"] = seq(*parts)
    s["timeout"] = seq(*[(i * 0.36, tone(N(n), 0.34 if i < 3 else 1.0, "brass", 3 if i < 3 else 1.8,
                                         attack=0.03, vibrato=0.0 if i < 3 else 0.02) * 0.7)
                         for i, n in enumerate(("G4", "F#4", "F4", "E4"))])
    # "impressora": rajadas curtas de ruído, como uma matricial imprimindo o relatório
    bursts = [(0.045 * i, noise(0.03, 60, 2, seed=i) * (0.35 + 0.1 * (i % 3))) for i in range(16)]
    s["print"] = seq(*bursts, (0.74, tone(N("C6"), 0.18, "tri", 18) * 0.5))
    thump = seq((0, tone(95, 0.18, "sine", 22)), (0, noise(0.05, 60, 6) * 0.5))
    s["stamp_yes"] = seq((0, thump), (0.1, tone(N("E6"), 0.6, "bell", 6) * 0.45), (0.2, tone(N("B6"), 0.6, "bell", 6) * 0.3))
    s["stamp_no"] = seq((0, thump), (0.1, tone(N("A4"), 0.35, "tri", 8, slide=N("E4")) * 0.6))
    s["next"] = seq((0, noise(0.35, 7, 8, seed=3) * 0.6), (0.05, tone(N("C5"), 0.3, "sine", 10, slide=N("C6")) * 0.35))
    s["click"] = tone(1800, 0.03, "sine", 90)
    # volume relativo: bips curtos mais baixos, comemorações mais altas
    gain = {"tick": 0.45, "charge1": 0.5, "charge2": 0.6, "click": 0.35, "lock": 0.6, "print": 0.6, "next": 0.6}
    return {k: (_norm(v, 0.85) * gain.get(k, 1.0)).astype(np.float32) for k, v in s.items()}


class SoundBoard:
    """Toca os efeitos a partir dos eventos do jogo."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.enabled = bool(cfg.audio.enabled)
        self.available = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._seen: dict[str, float] = {}
        self._last_hold = 0.0
        self._last_count = None
        if not self.enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 512)
            freq, _fmt, channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(16)
            for name, wave in build_sounds().items():
                if freq != RATE:
                    idx = np.linspace(0, len(wave) - 1, int(len(wave) * freq / RATE))
                    wave = np.interp(idx, np.arange(len(wave)), wave).astype(np.float32)
                pcm = (np.clip(wave, -1, 1) * 32767).astype(np.int16)
                if channels > 1:
                    pcm = np.repeat(pcm[:, None], channels, axis=1)
                snd = pygame.sndarray.make_sound(np.ascontiguousarray(pcm))
                snd.set_volume(float(cfg.audio.volume))
                self._sounds[name] = snd
            self.available = True
            log.info("som: %d efeitos prontos (tecla M liga/desliga)", len(self._sounds))
        except Exception as exc:  # noqa: BLE001 - sem áudio o jogo continua, só fica mudo
            log.warning("som indisponível (%s); o jogo segue mudo", exc)

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled and self.available:
            pygame.mixer.stop()
        return self.enabled

    def play(self, name: str) -> None:
        if self.enabled and self.available and name in self._sounds:
            self._sounds[name].play()

    def update(self, game: Game, now: float) -> None:
        """Chame uma vez por quadro, depois de game.update()."""
        for name, (t, data) in game.events.items():
            if self._seen.get(name) == t:
                continue
            first = name not in self._seen
            self._seen[name] = t
            if first and now - t > 1.0:
                continue   # evento antigo (ex.: voltando do modo explicação)
            if name == "locked":
                self.play("lock")
            elif name == "calib_done":
                self.play("go")
            elif name == "target_done":
                self.play("done")
            elif name == "victory":
                self.play("victory")
            elif name == "timeout":
                self.play("timeout")
            elif name == "report":
                self.play("print")
            elif name == "review":
                self.play("stamp_yes" if data.get("ok") else "stamp_no")
            elif name == "reset" and data.get("reason") == "next_player":
                self.play("next")

        # contagem da calibração: um "tic" por segundo
        if game.phase == Phase.CALIBRATING:
            left = max(0.0, game.cfg.calibration.seconds - game.phase_elapsed(now))
            count = int(np.ceil(left))
            if self._last_count is not None and count < self._last_count and count > 0:
                self.play("tick")
            self._last_count = count
        else:
            self._last_count = None

        # careta sendo segurada: notas subindo em 1/3, 2/3 (a 3/3 é o "plim" de concluído)
        hp = game.hold_progress if game.phase == Phase.PLAYING else 0.0
        for i, th in enumerate((0.34, 0.67)):
            if self._last_hold < th <= hp:
                self.play(f"charge{i + 1}")
        self._last_hold = hp
