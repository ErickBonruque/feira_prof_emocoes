"""Overlay de debug (tecla D): caixas, probabilidades, valência/excitação e as
condições de cada emoção, com os picos recentes para ajudar a calibrar limiares."""

from __future__ import annotations

from collections import deque

import numpy as np
import pygame

from ..emotion import CLASS_NAMES, LABELS_PT
from ..game import Game
from ..pipeline import FrameResult
from ..scoring import TARGETS, Baseline, evaluate
from . import draw, theme

CHECK_NAMES = {"prob": "prob", "gain": "ganho", "axis": "eixo", "axis_gain": "g.eixo"}


class DebugOverlay:
    def __init__(self, cfg):
        self.cfg = cfg
        self._hist: deque = deque()   # (t, probs, valence, arousal) dos últimos segundos
        self._last_fid = -1

    def draw(self, s: pygame.Surface, renderer, now: float, game: Game, r: FrameResult | None,
             camera, processor, emotion_device: str, render_fps: float) -> None:
        u = renderer.L.u
        if r is not None and renderer.feed.surface is not None:
            self._draw_boxes(s, renderer, r, u)
        if r is not None and r.frame_id != self._last_fid and game.smoothed is not None:
            self._last_fid = r.frame_id
            sm = game.smoothed
            self._hist.append((now, sm.probs.copy(), sm.valence, sm.arousal))
        while self._hist and now - self._hist[0][0] > 5.0:
            self._hist.popleft()

        W, H = s.get_size()
        pw = int(min(760 * u, W * 0.46))
        panel = pygame.Rect(W - pw - int(12 * u), int(12 * u), pw, H - int(24 * u))
        bg = pygame.Surface(panel.size, pygame.SRCALPHA)
        bg.fill((0, 0, 0, 225))
        s.blit(bg, panel.topleft)
        pygame.draw.rect(s, theme.MINT, panel, 2, border_radius=8)

        fs = max(12, int(18 * u))
        lh = int(fs * 1.35)
        x = panel.left + int(14 * u)
        y = panel.top + int(10 * u)

        def line(text, color=theme.WHITE, dy=lh):
            nonlocal y
            draw.blit_text(s, text, "mono", fs, color, (x, y))
            y += dy

        line("DEBUG  (D esconde)", theme.MINT)
        line(f"tela {render_fps:4.0f} fps | câmera {camera.fps:4.0f} fps | proc {processor.fps:4.0f} fps")
        if r is not None:
            line(f"detecção {r.timings.get('detect_ms', 0):5.1f} ms | emoção {r.timings.get('emotion_ms', 0):5.1f} ms ({emotion_device})")
        cam_state = "OK" if camera.healthy() else camera.status.upper()
        line(f"{camera.source_label} {camera.resolution[0]}x{camera.resolution[1]} [{cam_state}] {camera.message}")
        tl = game.time_left(now)
        line(f"fase {game.phase.value} | alvo {game.target or '-'} | tempo {'' if tl is None else f'{tl:4.1f}s'}")
        line(f"segura: {game.hold.count}/{self.cfg.rules.hold_frames} quadros, "
             f"{game.hold_progress * 100:3.0f}%  (mín {self.cfg.rules.hold_seconds:.1f}s)")
        if r is not None:
            pinfo = "-"
            if r.player is not None and r.frame is not None:
                pinfo = f"{r.player.w / r.frame.shape[1] * 100:4.1f}% larg, score {r.player.score:.2f}"
            line(f"rostos {len(r.faces)} | travado {'sim' if r.locked else 'não'} | jogador {pinfo}")
        base = game.baseline
        if base is not None:
            line(f"neutro: V {base.valence:+.2f} A {base.arousal:+.2f}{' (PADRÃO)' if base.is_default else ''}", theme.GRAY)
        y += int(6 * u)

        sm = game.smoothed
        if sm is None:
            line("sem leitura de emoção (ninguém travado)", theme.GRAY)
            return

        # barras das 8 classes (suavizado) + cru como traço
        raw = r.reading if r is not None else None
        peaks = np.max([h[1] for h in self._hist], axis=0) if self._hist else sm.probs
        bw = panel.width - int(270 * u)
        for i, name in enumerate(CLASS_NAMES):
            col = theme.EMOTIONS[name]["color"] if name in theme.EMOTIONS else theme.GRAY
            draw.blit_text(s, LABELS_PT[name], "mono", fs, col, (x, y))
            bar = pygame.Rect(x + int(170 * u), y + fs // 4, bw, fs // 2 + 2)
            draw.progress_bar(s, bar, float(sm.probs[i]), col, theme.SLATE)
            if raw is not None:
                rx = bar.left + int(bar.width * float(raw.probs[i]))
                pygame.draw.line(s, theme.WHITE, (rx, bar.top - 3), (rx, bar.bottom + 3), 2)
            px = bar.left + int(bar.width * float(peaks[i]))
            pygame.draw.line(s, theme.PINK, (px, bar.top - 5), (px, bar.bottom + 5), 2)
            draw.blit_text(s, f"{sm.probs[i]:.2f}", "mono", fs, theme.WHITE, (bar.right + int(8 * u), y))
            y += lh
        line("branco = cru | rosa = pico 5s", theme.GRAY)
        vpk = (min(h[2] for h in self._hist), max(h[2] for h in self._hist)) if self._hist else (sm.valence, sm.valence)
        apk = (min(h[3] for h in self._hist), max(h[3] for h in self._hist)) if self._hist else (sm.arousal, sm.arousal)
        line(f"valência {sm.valence:+.2f} (5s: {vpk[0]:+.2f}..{vpk[1]:+.2f})")
        line(f"excitação {sm.arousal:+.2f} (5s: {apk[0]:+.2f}..{apk[1]:+.2f})")
        y += int(6 * u)

        # condições das 3 emoções (em relação ao neutro medido, ou ao padrão)
        ref = base or Baseline.default()
        for key in TARGETS:
            ev = evaluate(key, self.cfg.rules.for_emotion(key), sm, ref)
            meta = theme.EMOTIONS[key]
            head = f"{meta['name']:8s} {'PASSA' if ev.passed else '-----'}  força {ev.intensity * 100:3.0f}%"
            line(head, meta["color"])
            parts = []
            for cname, c in ev.checks.items():
                parts.append((f"{CHECK_NAMES[cname]} {c.value:+.2f}/{c.threshold:.2f}", theme.MINT if c.ok else theme.RED))
            for row in (parts[:2], parts[2:]):
                cx = x + int(18 * u)
                for text, col in row:
                    rr = draw.blit_text(s, text, "mono", int(fs * 0.9), col, (cx, y))
                    cx = rr.right + int(18 * u)
                y += int(lh * 0.9)

    def _draw_boxes(self, s, renderer, r: FrameResult, u: float) -> None:
        prev = s.get_clip()
        s.set_clip(renderer.L.feed)
        for f in r.faces:
            rect = renderer.feed.map_rect(f)
            is_player = r.player is not None and f is r.player
            col = theme.MINT if is_player else (theme.YELLOW if f is r.candidate else theme.GRAY)
            pygame.draw.rect(s, col, rect, 2)
            draw.blit_text(s, f"{f.score:.2f} {f.w / r.frame.shape[1] * 100:.0f}%", "mono", int(16 * u), col,
                           (rect.left, rect.bottom + 4))
            for (lx, ly) in f.landmarks:
                px = renderer.feed.rect.x + (lx - renderer.feed.x0) * renderer.feed.scale
                py = renderer.feed.rect.y + (ly - renderer.feed.y0) * renderer.feed.scale
                pygame.draw.circle(s, col, (int(px), int(py)), 3)
        s.set_clip(prev)
