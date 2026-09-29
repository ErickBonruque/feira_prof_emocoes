"""Suavização das marcações na tela (só visual; as regras do jogo usam os dados crus).

A detecção chega a ~10-30 quadros/s e treme alguns pixels; a tela roda a 60.
Um filtro One Euro tira o tremido quando o rosto está parado sem atrasar quando
ele se mexe, e um deslize exponencial preenche os quadros entre uma detecção e outra.
"""

from __future__ import annotations

import math

import pygame


class OneEuro:
    """Filtro One Euro (Casiez et al., 2012): corte baixo parado, corte alto em movimento."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.01, d_cutoff: float = 1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x: float | None = None
        self.dx = 0.0

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x: float, dt: float) -> float:
        if self.x is None or dt <= 0:
            self.x, self.dx = x, 0.0
            return x
        dx = (x - self.x) / dt
        self.dx += self._alpha(self.d_cutoff, dt) * (dx - self.dx)
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        self.x += self._alpha(cutoff, dt) * (x - self.x)
        return self.x


class SmoothBox:
    """Retângulo (em pixels da tela) que segue o rosto sem tremer."""

    def __init__(self, glide: float = 0.06, forget_after: float = 0.6):
        self.glide = glide
        self.forget_after = forget_after
        self.reset()

    def reset(self) -> None:
        self._filters = [OneEuro(1.0, 0.008) for _ in range(4)]
        self._goal: list[float] | None = None
        self._pos: list[float] | None = None
        self._last_id = -1
        self._last_det_t = 0.0
        self._last_draw_t = 0.0

    def update(self, rect: pygame.Rect | None, frame_id: int, now: float) -> pygame.Rect | None:
        if rect is None:
            if self._pos is not None and now - self._last_det_t > self.forget_after:
                self.reset()
            return self._as_rect()
        if frame_id != self._last_id:
            dt = now - self._last_det_t if self._last_id >= 0 else 0.0
            raw = (rect.centerx, rect.centery, rect.w, rect.h)
            self._goal = [f(v, dt) for f, v in zip(self._filters, raw)]
            self._last_id, self._last_det_t = frame_id, now
        if self._pos is None:
            self._pos = list(self._goal)
        else:
            dt = max(0.0, min(0.1, now - self._last_draw_t))
            k = 1.0 - math.exp(-dt / self.glide)
            self._pos = [p + (g - p) * k for p, g in zip(self._pos, self._goal)]
        self._last_draw_t = now
        return self._as_rect()

    def _as_rect(self) -> pygame.Rect | None:
        if self._pos is None:
            return None
        cx, cy, w, h = self._pos
        r = pygame.Rect(0, 0, int(w), int(h))
        r.center = (int(cx), int(cy))
        return r
