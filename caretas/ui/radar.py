"""Mapa das emoções: valência (desagradável <-> agradável) x excitação (calmo <-> agitado).

O modelo devolve esses dois números a cada quadro, além das 8 classes. O ponto
anda pelo mapa conforme a careta, deixando um rastro, e os emojis marcam onde
cada careta do jogo costuma cair. É o "modelo circumplexo" usado em pesquisa
de emoções, em versão de feira.
"""

from __future__ import annotations

import math
from collections import deque

import pygame

from . import draw, theme
from .emoji import draw_emoji

# Onde cada careta costuma cair no mapa (valência, excitação), medido em fotos de teste.
ANCHORS = {"happiness": (0.70, 0.30), "surprise": (0.10, 0.85), "sadness": (-0.62, -0.40)}
LIMIT = 1.15   # o modelo passa um pouco de 1 (surpresa forte chega a ~1,1)


def _mix(c1, c2, k: float):
    k = max(0.0, min(1.0, k))
    return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))


class EmotionMap:
    def __init__(self, trail_seconds: float = 1.6):
        self.trail_seconds = trail_seconds
        self.trail: deque = deque()          # (t, x, y) já na escala -1..1 do mapa
        self._pos: tuple[float, float] | None = None
        self._goal: tuple[float, float] | None = None
        self._last_t = 0.0

    def reset(self) -> None:
        self.trail.clear()
        self._pos = self._goal = None

    def update(self, now: float, valence: float, arousal: float) -> None:
        """Chame a cada leitura nova do modelo."""
        x = max(-1.0, min(1.0, valence / LIMIT))
        y = max(-1.0, min(1.0, arousal / LIMIT))
        self._goal = (x, y)
        if self._pos is None:
            self._pos = self._goal

    def _step(self, now: float) -> None:
        # A câmera entrega ~10-30 leituras/s; a tela, 60 quadros/s. O ponto desliza até a
        # leitura mais nova, em vez de pular.
        dt = max(0.0, min(0.1, now - self._last_t))
        self._last_t = now
        if self._goal is None or self._pos is None:
            return
        k = 1.0 - math.exp(-dt / 0.09)
        self._pos = (self._pos[0] + (self._goal[0] - self._pos[0]) * k,
                     self._pos[1] + (self._goal[1] - self._pos[1]) * k)
        self.trail.append((now, *self._pos))
        while self.trail and now - self.trail[0][0] > self.trail_seconds:
            self.trail.popleft()

    def draw(self, dst: pygame.Surface, rect: pygame.Rect, now: float, u: float,
             target: str | None = None, dot_color=theme.MINT, labels: bool = True,
             emoji_scale: float = 1.0) -> None:
        self._step(now)
        cx, cy = rect.center
        half = min(rect.w, rect.h) / 2
        if labels:   # sobra uma margem para os rótulos não ficarem embaixo dos emojis
            half *= 0.86

        def P(x, y):
            return (cx + x * half, cy - y * half)

        # grade: anéis e cruz
        lw = max(1, int(2 * u))
        for rr in (1.0, 0.5):
            pygame.draw.circle(dst, theme.SLATE, (cx, cy), int(half * rr), lw)
        pygame.draw.line(dst, theme.SLATE, P(-1, 0), P(1, 0), lw)
        pygame.draw.line(dst, theme.SLATE, P(0, -1), P(0, 1), lw)

        if labels:
            # Acima/abaixo do eixo do lado oposto ao emoji daquele lado (feliz em cima à direita,
            # triste embaixo à esquerda), para nada ficar sobreposto.
            fs = max(10, int(half * 0.095))
            col = theme.GRAY
            draw.label(dst, "AGITADO", fs, col, (cx, rect.top), "midtop")
            draw.label(dst, "CALMO", fs, col, (cx, rect.bottom), "midbottom")
            draw.label(dst, "AGRADÁVEL", fs, col, (rect.right, cy + 6 * u), "topright")
            draw.label(dst, "DESAGRADÁVEL", fs, col, (rect.left, cy - 6 * u), "bottomleft")

        # emojis das caretas: o alvo pulsa, os outros ficam menores
        base_r = half * 0.13 * emoji_scale
        for key, (v, a) in ANCHORS.items():
            p = P(v / LIMIT, a / LIMIT)
            is_target = key == target
            r = base_r * (1.25 + 0.12 * math.sin(now * 6.0)) if is_target else base_r * (0.8 if target else 1.0)
            if is_target:
                meta = theme.EMOTIONS[key]
                draw.ring(dst, p, r + 9 * u, max(3, int(4 * u)), 1.0, meta["color"])
            draw_emoji(dst, key, p, max(6, int(r)), 1.0)

        # rastro que vai sumindo + ponto atual
        if len(self.trail) >= 2:
            pts = list(self.trail)
            n = len(pts)
            for i in range(1, n):
                k = i / n
                col = _mix(theme.CANVAS, dot_color, k)
                pygame.draw.line(dst, col, P(pts[i - 1][1], pts[i - 1][2]), P(pts[i][1], pts[i][2]),
                                 max(2, int((2 + 5 * k) * u)))
        if self._pos is not None:
            p = P(*self._pos)
            rad = max(5, int(half * 0.075))
            pygame.draw.circle(dst, theme.WHITE, p, rad + max(2, int(3 * u)))
            pygame.draw.circle(dst, dot_color, p, rad)
