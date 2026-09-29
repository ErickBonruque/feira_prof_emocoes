"""Emojis desenhados por código (nítidos em qualquer resolução de projetor).

`intensity` (0..1) faz a expressão sair do neutro e ir até o máximo, então o
mesmo desenho serve de "espelho" da careta do jogador.
"""

from __future__ import annotations

import math

import pygame

from . import theme

_SS = 3  # supersampling para bordas suaves
_cache: dict = {}


def emoji_surface(kind: str, radius: int, intensity: float = 1.0, face=theme.YELLOW,
                  outline=theme.BLACK) -> pygame.Surface:
    q = round(max(0.0, min(1.0, intensity)) * 20) / 20
    key = (kind, int(radius), q, tuple(face), tuple(outline))
    surf = _cache.get(key)
    if surf is None:
        surf = _render(kind, int(radius), q, face, outline)
        if len(_cache) > 400:
            _cache.clear()
        _cache[key] = surf
    return surf


def draw_emoji(dst, kind: str, center, radius: int, intensity: float = 1.0, face=theme.YELLOW,
               outline=theme.BLACK, angle: float = 0.0) -> None:
    surf = emoji_surface(kind, radius, intensity, face, outline)
    if angle:
        surf = pygame.transform.rotozoom(surf, angle, 1.0)
    dst.blit(surf, surf.get_rect(center=(int(center[0]), int(center[1]))))


def _render(kind: str, radius: int, k: float, face, outline) -> pygame.Surface:
    R = radius * _SS
    pad = int(R * 0.12)
    size = 2 * R + 2 * pad
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    lw = max(2, int(R * 0.085))

    def P(x, y):
        return (c + x * R, c + y * R)

    def thick_line(pts, width=lw, color=outline):
        pts = [P(*p) for p in pts]
        pygame.draw.lines(s, color, False, pts, width)
        for p in (pts[0], pts[-1]):
            pygame.draw.circle(s, color, p, width / 2)

    def ellipse(cx, cy, rx, ry, color, width=0):
        r = pygame.Rect(0, 0, 2 * rx * R, 2 * ry * R)
        r.center = P(cx, cy)
        pygame.draw.ellipse(s, color, r, width)

    # rosto
    pygame.draw.circle(s, outline, (c, c), R)
    pygame.draw.circle(s, face, (c, c), R - lw)

    if kind == "happiness":
        # bochechas
        ellipse(-0.58, 0.22, 0.16, 0.1, theme.PINK)
        ellipse(0.58, 0.22, 0.16, 0.1, theme.PINK)
        if k > 0.55:  # olhos de "^ ^"
            for ex in (-0.34, 0.34):
                thick_line([(ex - 0.16, -0.14), (ex, -0.3), (ex + 0.16, -0.14)])
        else:
            for ex in (-0.34, 0.34):
                ellipse(ex, -0.2, 0.08, 0.12, outline)
        depth = 0.12 + 0.36 * k
        top = 0.2
        pts = []
        for i in range(25):
            u = -1 + 2 * i / 24
            pts.append((0.5 * u, top + depth * (1 - u * u) ** 0.8))
        poly = [P(-0.5, top)] + [P(*p) for p in pts] + [P(0.5, top)]
        pygame.draw.polygon(s, outline, poly)
        if depth > 0.2:  # dentes e língua
            teeth = pygame.Rect(0, 0, 0.78 * R, 0.1 * R)
            teeth.midtop = P(0, top + 0.03)
            pygame.draw.rect(s, theme.WHITE, teeth, border_radius=int(0.04 * R))
            ellipse(0, top + depth * 0.72, 0.2, depth * 0.22, theme.PINK)
        pygame.draw.lines(s, outline, False, poly, lw)

    elif kind == "surprise":
        by = -0.52 - 0.12 * k
        for ex in (-0.34, 0.34):
            thick_line([(ex - 0.16, by + 0.05), (ex, by - 0.03), (ex + 0.16, by + 0.05)])
            er = 0.12 + 0.07 * k
            ellipse(ex, -0.17, er, er * 1.1, theme.WHITE)
            ellipse(ex, -0.17, er, er * 1.1, outline, lw)
            ellipse(ex, -0.15, er * 0.45, er * 0.5, outline)
        ellipse(0, 0.47, 0.13 + 0.09 * k, 0.12 + 0.2 * k, outline)

    elif kind == "sadness":
        lift = 0.1 * k
        thick_line([(-0.52, -0.36), (-0.18, -0.46 - lift)])
        thick_line([(0.52, -0.36), (0.18, -0.46 - lift)])
        for ex in (-0.34, 0.34):
            ellipse(ex, -0.17, 0.08, 0.11, outline)
        drop = 0.05 + 0.2 * k
        pts = []
        for i in range(21):
            u = -1 + 2 * i / 20
            pts.append((0.34 * u, 0.58 - drop * (1 - u * u)))
        thick_line(pts)
        if k > 0.35:  # lágrima
            ty = 0.02 + 0.16 * k
            tr = 0.085
            ellipse(0.36, ty, tr, tr, theme.TEAR)
            pygame.draw.polygon(s, theme.TEAR, [P(0.36 - tr * 0.95, ty - 0.02), P(0.36, ty - 0.2), P(0.36 + tr * 0.95, ty - 0.02)])

    else:  # neutral
        for ex in (-0.34, 0.34):
            ellipse(ex, -0.17, 0.08, 0.12, outline)
        thick_line([(-0.3, 0.42), (0.3, 0.42)])

    return pygame.transform.smoothscale(s, (size // _SS, size // _SS))


def bob(t: float, phase: float = 0.0, amp: float = 1.0) -> float:
    """Oscilação suave para animar emojis parados."""
    return math.sin(t * 2.4 + phase) * amp
