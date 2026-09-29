"""Primitivas de desenho: texto com cache, blocos arredondados, fita de perigo, anéis."""

from __future__ import annotations

import math
from collections import OrderedDict

import pygame

from . import theme

_text_cache: OrderedDict = OrderedDict()
_TEXT_CACHE_MAX = 600


def text_surface(text: str, kind: str, size: int, color, tracking: float = 0.0) -> pygame.Surface:
    key = (text, kind, int(size), tuple(color), round(tracking, 2))
    surf = _text_cache.get(key)
    if surf is not None:
        _text_cache.move_to_end(key)
        return surf
    f = theme.font(kind, size)
    if tracking <= 0:
        surf = f.render(text, True, color)
    else:
        glyphs = [f.render(ch, True, color) for ch in text]
        width = sum(g.get_width() for g in glyphs) + tracking * max(0, len(glyphs) - 1)
        surf = pygame.Surface((max(1, int(width)), f.get_height()), pygame.SRCALPHA)
        x = 0.0
        for g in glyphs:
            surf.blit(g, (int(x), 0))
            x += g.get_width() + tracking
    _text_cache[key] = surf
    if len(_text_cache) > _TEXT_CACHE_MAX:
        _text_cache.popitem(last=False)
    return surf


def blit_text(dst: pygame.Surface, text: str, kind: str, size: int, color, pos,
              anchor: str = "topleft", tracking: float = 0.0) -> pygame.Rect:
    surf = text_surface(text, kind, size, color, tracking)
    rect = surf.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    dst.blit(surf, rect)
    return rect


def tight_surface(text: str, kind: str, size: int, color, tracking: float = 0.0) -> pygame.Surface:
    """Texto recortado no contorno real das letras (a Anton tem muito espaço vertical sobrando)."""
    key = ("tight", text, kind, int(size), tuple(color), round(tracking, 2))
    surf = _text_cache.get(key)
    if surf is None:
        full = text_surface(text, kind, size, color, tracking)
        r = full.get_bounding_rect()
        surf = full.subsurface(r).copy() if r.w and r.h else full
        _text_cache[key] = surf
    return surf


def blit_tight(dst, text: str, kind: str, size: int, color, pos, anchor: str = "topleft",
               tracking: float = 0.0) -> pygame.Rect:
    surf = tight_surface(text, kind, size, color, tracking)
    rect = surf.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    dst.blit(surf, rect)
    return rect


def fit_size(text: str, kind: str, size: int, max_width: int, tracking: float = 0.0, min_size: int = 10) -> int:
    """Maior tamanho <= size em que o texto cabe em max_width."""
    s = int(size)
    while s > min_size:
        w = theme.font(kind, s).size(text)[0] + tracking * max(0, len(text) - 1)
        if w <= max_width:
            return s
        s = int(s * 0.92)
    return min_size


def label(dst, text: str, size: int, color, pos, anchor: str = "topleft") -> pygame.Rect:
    """Rótulo mono em CAIXA ALTA com espaçamento largo (assinatura do sistema)."""
    return blit_text(dst, text.upper(), "mono", size, color, pos, anchor, tracking=size * 0.12)


def block(dst, rect, color, radius: int, border_color=None, border: int = 0) -> None:
    pygame.draw.rect(dst, color, rect, border_radius=radius)
    if border_color is not None and border > 0:
        pygame.draw.rect(dst, border_color, rect, width=border, border_radius=radius)


def pill_rect(text: str, size: int, pos, anchor: str = "topleft", pad: float = 0.55) -> pygame.Rect:
    """Onde uma pill_label com esses parâmetros ficaria (para testar sobreposição antes)."""
    surf = text_surface(text.upper(), "mono", size, (0, 0, 0), size * 0.12)
    px, py = int(size * pad * 1.6), int(size * pad * 0.7)
    rect = pygame.Rect(0, 0, surf.get_width() + 2 * px, surf.get_height() + 2 * py)
    setattr(rect, anchor, (int(pos[0]), int(pos[1])))
    return rect


def pill_label(dst, text: str, size: int, fg, bg, pos, anchor: str = "topleft",
               pad: float = 0.55, border_color=None) -> pygame.Rect:
    surf = text_surface(text.upper(), "mono", size, fg, size * 0.12)
    rect = pill_rect(text, size, pos, anchor, pad)
    block(dst, rect, bg, rect.height // 2, border_color, max(1, size // 10) if border_color else 0)
    dst.blit(surf, surf.get_rect(center=rect.center))
    return rect


def corner_caps(dst, rect: pygame.Rect, radius: int, color) -> None:
    """Pinta os cantos fora do retângulo arredondado (para arredondar a imagem da câmera)."""
    if radius <= 0:
        return
    cap = _corner_cap(radius, tuple(color))
    dst.blit(cap, rect.topleft)
    dst.blit(pygame.transform.flip(cap, True, False), (rect.right - radius, rect.top))
    dst.blit(pygame.transform.flip(cap, False, True), (rect.left, rect.bottom - radius))
    dst.blit(pygame.transform.flip(cap, True, True), (rect.right - radius, rect.bottom - radius))


_cap_cache: dict = {}


def _corner_cap(radius: int, color) -> pygame.Surface:
    key = (radius, color)
    cap = _cap_cache.get(key)
    if cap is None:
        ss = 4
        big = pygame.Surface((radius * ss, radius * ss), pygame.SRCALPHA)
        big.fill((*color, 255))
        pygame.draw.circle(big, (0, 0, 0, 0), (radius * ss, radius * ss), radius * ss)
        cap = pygame.transform.smoothscale(big, (radius, radius))
        _cap_cache[key] = cap
    return cap


def hazard_tape(dst, rect: pygame.Rect, c1, c2, t: float, stripe: int, speed: float = 60.0) -> None:
    """Fita listrada diagonal animada."""
    prev = dst.get_clip()
    dst.set_clip(rect.clip(prev) if prev else rect)
    pygame.draw.rect(dst, c1, rect)
    h = rect.height
    period = stripe * 2
    offset = (t * speed) % period
    x = rect.left - h - period + offset
    while x < rect.right + h:
        pts = [(x, rect.bottom), (x + stripe, rect.bottom), (x + stripe + h, rect.top), (x + h, rect.top)]
        pygame.draw.polygon(dst, c2, pts)
        x += period
    dst.set_clip(prev)


def ring(dst, center, radius: float, width: float, frac: float, color, start_deg: float = -90.0) -> None:
    """Anel de progresso preenchido (polígono, sem os buracos do draw.arc)."""
    frac = max(0.0, min(1.0, frac))
    if frac <= 0:
        return
    cx, cy = center
    steps = max(8, int(90 * frac))
    a0 = math.radians(start_deg)
    a1 = a0 + frac * 2 * math.pi
    outer, inner = [], []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        ca, sa = math.cos(a), math.sin(a)
        outer.append((cx + ca * radius, cy + sa * radius))
        inner.append((cx + ca * (radius - width), cy + sa * (radius - width)))
    pygame.draw.polygon(dst, color, outer + inner[::-1])


def brackets(dst, rect: pygame.Rect, color, length: int, width: int) -> None:
    """Cantoneiras de visor de câmera em volta de um rosto."""
    x0, y0, x1, y1 = rect.left, rect.top, rect.right, rect.bottom
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        pygame.draw.line(dst, color, (cx, cy), (cx + dx * length, cy), width)
        pygame.draw.line(dst, color, (cx, cy), (cx, cy + dy * length), width)
        pygame.draw.circle(dst, color, (cx, cy), width // 2)


def dashed_lines(dst, color, pts, width: int, dash: float, gap: float) -> None:
    """Polilinha tracejada; o tracejado continua de um segmento para o outro."""
    on, left = True, dash
    r = width / 2
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while seg - pos > 1e-6:
            step = min(left, seg - pos)
            if on:
                a, b = pos / seg, (pos + step) / seg
                p = (x0 + (x1 - x0) * a, y0 + (y1 - y0) * a)
                q = (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)
                pygame.draw.line(dst, color, p, q, width)
                pygame.draw.circle(dst, color, p, r)
                pygame.draw.circle(dst, color, q, r)
            pos += step
            left -= step
            if left <= 1e-6:
                on = not on
                left = dash if on else gap


def progress_bar(dst, rect: pygame.Rect, frac: float, fg, bg, border_color=None, border: int = 0) -> None:
    frac = max(0.0, min(1.0, frac))
    r = rect.height // 2
    block(dst, rect, bg, r)
    if frac > 0:
        w = max(rect.height, int(rect.width * frac))
        pygame.draw.rect(dst, fg, pygame.Rect(rect.left, rect.top, w, rect.height), border_radius=r)
    if border_color is not None and border > 0:
        pygame.draw.rect(dst, border_color, rect, width=border, border_radius=r)


def ease_out_back(x: float) -> float:
    x = max(0.0, min(1.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3
