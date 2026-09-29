"""Confete e partículas (leve o bastante para rodar junto com a câmera)."""

from __future__ import annotations

import math
import random

import pygame

from . import theme

PALETTE = (theme.MINT, theme.UV, theme.YELLOW, theme.PINK, theme.ORANGE, theme.WHITE)


class Confetti:
    MAX = 700

    def __init__(self):
        self.parts: list[list[float]] = []   # x, y, vx, vy, ang, vang, w, h, life, color_idx
        self._rng = random.Random()

    def clear(self) -> None:
        self.parts.clear()

    def burst(self, x: float, y: float, n: int, speed: float, size: float) -> None:
        r = self._rng
        for _ in range(n):
            a = r.uniform(-math.pi, 0)  # para cima
            v = r.uniform(0.35, 1.0) * speed
            self._add(x, y, math.cos(a) * v, math.sin(a) * v, size)

    def rain(self, width: float, n: int, speed: float, size: float) -> None:
        r = self._rng
        for _ in range(n):
            self._add(r.uniform(0, width), r.uniform(-size * 8, -size), r.uniform(-0.15, 0.15) * speed,
                      r.uniform(0.2, 0.6) * speed, size)

    def _add(self, x, y, vx, vy, size) -> None:
        if len(self.parts) >= self.MAX:
            return
        r = self._rng
        w = size * r.uniform(0.6, 1.2)
        self.parts.append([x, y, vx, vy, r.uniform(0, 6.28), r.uniform(-9, 9), w, w * r.uniform(0.35, 0.7),
                           r.uniform(2.5, 4.5), r.randrange(len(PALETTE))])

    def update(self, dt: float, gravity: float, height: float) -> None:
        dt = min(dt, 0.05)
        keep = []
        for p in self.parts:
            p[3] += gravity * dt
            p[2] *= 0.995
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] += p[5] * dt
            p[8] -= dt
            if p[8] > 0 and p[1] < height + 50:
                keep.append(p)
        self.parts = keep

    def draw(self, dst: pygame.Surface) -> None:
        for x, y, _, _, ang, _, w, h, _, ci in self.parts:
            # "papel girando": a largura aparente oscila com o ângulo
            ca, sa = math.cos(ang), math.sin(ang)
            hw, hh = w / 2 * abs(math.cos(ang * 1.7)) + 1, h / 2
            pts = [(x + ca * dx - sa * dy, y + sa * dx + ca * dy)
                   for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            pygame.draw.polygon(dst, PALETTE[ci], pts)
