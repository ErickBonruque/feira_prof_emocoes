"""Desenha todas as telas do jogo com Pygame.

Layout responsivo: "wide" (16:9, 16:10) põe a câmera à esquerda e as 3 caretas
à direita; "stacked" (4:3, projetores antigos) põe a câmera em cima e as caretas
embaixo. Tudo é medido em `u` (1 u = 1 px numa tela 1920x1080).
"""

from __future__ import annotations

import math
import time

import cv2
import numpy as np
import pygame

from ..emotion import LABELS_PT
from ..game import ACTIVE, Game, Phase
from ..pipeline import FrameResult
from . import draw, theme
from .effects import Confetti
from .emoji import bob, draw_emoji
from .radar import EmotionMap
from .report_view import ReportView
from .smooth import SmoothBox

MARQUEE = ("FAÇA 3 CARETAS  •  FELIZ  •  SURPRESA  •  TRISTE  •  "
           "UMA REDE NEURAL RECONHECE SUAS EMOÇÕES EM TEMPO REAL  •  "
           "A IA LÊ A EXPRESSÃO DO ROSTO, NÃO O QUE VOCÊ SENTE POR DENTRO  •  "
           "A IA FAZ O RELATÓRIO; QUEM DECIDE É SEMPRE UMA PESSOA  •  "
           "NENHUMA IMAGEM É GRAVADA  •  ")


class Layout:
    def __init__(self, W: int, H: int):
        self.W, self.H = W, H
        self.wide = W / H >= 1.45
        u = min(W / 1920, H / 1080) if self.wide else min(W / 1300, H / 1080)
        self.u = u
        m = int((36 if self.wide else 28) * u)
        self.m = m
        header_h = int((150 if self.wide else 128) * u)
        footer_h = int((54 if self.wide else 46) * u)
        self.header = pygame.Rect(m, m, W - 2 * m, header_h)
        self.footer = pygame.Rect(m, H - int(m * 0.8) - footer_h, W - 2 * m, footer_h)
        top = self.header.bottom + int(8 * u)
        bottom = self.footer.top - int(20 * u)
        gap = int(20 * u)
        if self.wide:
            fw = int((W - 2 * m) * 0.64)
            self.feed = pygame.Rect(m, top, fw, bottom - top)
            side = pygame.Rect(self.feed.right + int(26 * u), top, W - m - self.feed.right - int(26 * u), bottom - top)
            th = (side.height - 2 * gap) // 3
            self.tiles = [pygame.Rect(side.left, side.top + i * (th + gap), side.width, th) for i in range(3)]
        else:
            fh = int((bottom - top) * 0.66)
            self.feed = pygame.Rect(m, top, W - 2 * m, fh)
            ty = self.feed.bottom + gap
            tw = (W - 2 * m - 2 * gap) // 3
            self.tiles = [pygame.Rect(m + i * (tw + gap), ty, tw, bottom - ty) for i in range(3)]
        self.radius = int(34 * u)


class FeedView:
    """Converte o quadro da câmera para a área da tela (preenche e corta, sem distorcer)."""

    def __init__(self):
        self.frame_id = -1
        self.surface: pygame.Surface | None = None
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.scale = 1.0
        self.x0 = 0.0
        self.y0 = 0.0

    def update(self, frame: np.ndarray, frame_id: int, rect: pygame.Rect) -> None:
        if frame_id == self.frame_id and rect == self.rect and self.surface is not None:
            return
        h, w = frame.shape[:2]
        scale = max(rect.w / w, rect.h / h)
        cw, ch = rect.w / scale, rect.h / scale
        x0, y0 = (w - cw) / 2, (h - ch) / 2
        crop = frame[int(y0):int(y0 + ch), int(x0):int(x0 + cw)]
        img = cv2.resize(crop, (rect.w, rect.h), interpolation=cv2.INTER_LINEAR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.surface = pygame.image.frombuffer(img.tobytes(), (rect.w, rect.h), "RGB")
        self.frame_id, self.rect, self.scale, self.x0, self.y0 = frame_id, rect.copy(), scale, x0, y0

    def map_rect(self, face) -> pygame.Rect:
        return pygame.Rect(int(self.rect.x + (face.x - self.x0) * self.scale),
                           int(self.rect.y + (face.y - self.y0) * self.scale),
                           int(face.w * self.scale), int(face.h * self.scale))

    def forget(self) -> None:
        self.surface = None
        self.frame_id = -1


class Renderer:
    def __init__(self, cfg, screen: pygame.Surface):
        self.cfg = cfg
        self.confetti = Confetti()
        self.feed = FeedView()
        self._seen: dict[str, float] = {}
        self._flash_t = -10.0
        self._last_now = time.monotonic()
        self._disp_intensity = 0.0
        self._victory_cards: tuple[float, list] | None = None
        self._thumbs: dict[tuple[str, int], tuple[int, pygame.Surface]] = {}
        self._toast: tuple[str, float] | None = None
        self.map = EmotionMap()
        self.box = SmoothBox()
        self._map_fid = -1
        self.report_view = ReportView(cfg, self)
        self.set_screen(screen)

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.L = Layout(*screen.get_size())
        self._victory_cards = None
        self._thumbs.clear()
        self.feed.forget()
        self.report_view.forget()
        self.box.reset()

    # ================================================================== frame
    def draw(self, now: float, game: Game, result: FrameResult | None, camera) -> None:
        s, L = self.screen, self.L
        dt = max(0.0, min(0.1, now - self._last_now))
        self._last_now = now
        self._handle_events(game, now)
        s.fill(theme.CANVAS)

        if game.phase == Phase.VICTORY:
            self._draw_victory(now, game)
            self._skip_hint(now, game)
        elif game.phase == Phase.TIMEOUT:
            self._draw_timeout(now, game)
            self._skip_hint(now, game)
        elif game.phase == Phase.REPORT:
            self.report_view.draw(s, now, game)
        else:
            self._draw_header(now, game)
            self._draw_feed(now, game, result, camera, dt)
            for i, key in enumerate(game.order[:3]):
                self._draw_tile(now, game, i, key, L.tiles[i])
            self.draw_marquee(s, now, MARQUEE)

        self.confetti.update(dt, gravity=900 * L.u, height=L.H)
        self.confetti.draw(s)
        self.draw_overlays(now)

    def draw_overlays(self, now: float) -> None:
        """Avisos para o operador, por cima de qualquer tela."""
        L = self.L
        if self._toast and now < self._toast[1]:
            draw.pill_label(self.screen, self._toast[0], int(24 * L.u), theme.BLACK, theme.ORANGE,
                            (L.W // 2, int(L.H * 0.45)), "center", border_color=theme.WHITE)

    def toast(self, message: str, now: float, seconds: float) -> None:
        """Aviso rápido para o operador (ex.: confirmar saída)."""
        self._toast = (message, now + seconds)

    def _handle_events(self, game: Game, now: float) -> None:
        L = self.L
        for name, (t, data) in game.events.items():
            if self._seen.get(name) == t:
                continue
            self._seen[name] = t
            if name == "target_done":
                self._flash_t = t
                f = L.feed
                self.confetti.burst(f.centerx, f.centery, 90, 1300 * L.u, 26 * L.u)
                idx = game.order.index(data["target"]) if data.get("target") in game.order else 0
                tile = L.tiles[min(idx, 2)]
                self.confetti.burst(tile.centerx, tile.centery, 40, 900 * L.u, 20 * L.u)
            elif name == "victory":
                self._victory_cards = None
                self.confetti.rain(L.W, 260, 700 * L.u, 28 * L.u)
            elif name == "review" and data.get("ok"):
                b = self.report_view.buttons.get("yes")
                if b is not None:
                    self.confetti.burst(b.centerx, b.top, 70, 1100 * L.u, 22 * L.u)
            elif name == "locked":
                self.map.reset()
                self.box.reset()
            elif name == "reset":
                self.confetti.clear()
                self._thumbs.clear()
                self._victory_cards = None
                self.report_view.forget()
                self.map.reset()
                self.box.reset()

    # ================================================================== header/footer
    def _draw_header(self, now: float, game: Game) -> None:
        pills = [(f"CAMPEÕES HOJE: {game.victories}", theme.BLACK, theme.MINT)]
        reviewed = game.reviews_ok + game.reviews_fixed
        if reviewed:
            pills.append((f"IA ACERTOU {game.reviews_ok}/{reviewed}", theme.BLACK, theme.YELLOW))
        self.draw_header_block(self.screen, now, self.cfg.ui.kicker, self.cfg.ui.title, self.cfg.ui.subtitle, pills)

    def draw_header_block(self, s: pygame.Surface, now: float, kicker: str, title: str, subtitle: str,
                          pills: list | tuple = ()) -> None:
        L, u = self.L, self.L.u
        h = L.header
        kr = draw.label(s, kicker, int(20 * u), theme.MINT, (h.left, h.top))
        size = draw.fit_size(title, "display", int(120 * u), int(h.width * 0.55))
        avail = h.bottom - kr.bottom - int(22 * u)
        while draw.tight_surface(title, "display", size, theme.WHITE).get_height() > avail and size > 12:
            size = int(size * 0.94)
        draw.blit_tight(s, title, "display", size, theme.WHITE, (h.left, kr.bottom + int(14 * u)))

        # canto direito: ao vivo + placares + subtítulo
        x = h.right
        r = draw.pill_label(s, "   AO VIVO", int(18 * u), theme.WHITE, theme.SLATE, (x, h.top + int(4 * u)), "topright")
        dot = (r.left + int(28 * u), r.centery)
        if int(now * 2) % 2 == 0:
            pygame.draw.circle(s, theme.RED, dot, int(7 * u))
        for text, fg, bg in pills:
            r = draw.pill_label(s, text, int(18 * u), fg, bg, (r.left - int(12 * u), r.top), "topright")
        sub_size = draw.fit_size(subtitle, "ui_medium", int(24 * u), int(h.width * 0.42))
        draw.blit_text(s, subtitle, "ui_medium", sub_size, theme.GRAY,
                       (h.right, h.bottom - int(34 * u)), "bottomright")

    def draw_marquee(self, s: pygame.Surface, now: float, text: str) -> None:
        L, u = self.L, self.L.u
        f = L.footer
        draw.hazard_tape(s, f, theme.MINT, theme.CANVAS, now, int(26 * u), speed=40 * u)
        inner = f.inflate(-int(f.width * 0.18), -int(10 * u))
        draw.block(s, inner, theme.CANVAS, inner.height // 2, theme.MINT, max(2, int(2 * u)))
        txt = draw.text_surface(text, "mono", int(19 * u), theme.WHITE, 19 * u * 0.12)
        prev = s.get_clip()
        clip = inner.inflate(-inner.height, 0)
        s.set_clip(clip)
        w = txt.get_width()
        off = (now * 90 * u) % w
        y = inner.centery - txt.get_height() // 2
        x = clip.left - off
        while x < clip.right:
            s.blit(txt, (x, y))
            x += w
        s.set_clip(prev)

    # ================================================================== câmera
    def _draw_feed(self, now: float, game: Game, r: FrameResult | None, camera, dt: float) -> None:
        s, L, u = self.screen, self.L, self.L.u
        f = L.feed
        target = game.target
        frame_color = theme.EMOTIONS[target]["color"] if target else theme.MINT

        healthy = camera.healthy()
        frame, fid = self.display_frame(r, camera)
        if frame is not None:
            self.feed.update(frame, fid, f)
        if r is not None and r.frame_id != self._map_fid and game.smoothed is not None:
            self._map_fid = r.frame_id
            self.map.update(now, game.smoothed.valence, game.smoothed.arousal)
        if self.feed.surface is not None:
            s.blit(self.feed.surface, f.topleft)
        else:
            draw.block(s, f, theme.SLATE, L.radius)

        # flash de "foto" ao completar uma careta
        fa = now - self._flash_t
        if 0 <= fa < 0.35 and self.feed.surface is not None:
            flash = pygame.Surface(f.size)
            flash.fill(theme.WHITE)
            flash.set_alpha(int(255 * (1 - fa / 0.35)))
            s.blit(flash, f.topleft)

        if r is not None and healthy:
            self._draw_face_marks(now, game, r)

        draw.corner_caps(s, f, L.radius, theme.CANVAS)
        pygame.draw.rect(s, frame_color, f, width=max(3, int(4 * u)), border_radius=L.radius)

        if not healthy:
            self._draw_camera_problem(now, camera)
            return

        pad = int(22 * u)
        if game.phase in (Phase.CALIBRATING, Phase.PLAYING, Phase.BETWEEN):
            if self.cfg.ui.emotion_map:
                self._draw_ai_card(now, game, (f.left + pad, f.top + pad))
            elif self.cfg.ui.show_ai_reading:
                self._draw_ai_reading(game, (f.left + pad, f.top + pad))
        left = game.time_left(now)
        if left is not None and game.phase in (Phase.PLAYING, Phase.BETWEEN):
            col = theme.ORANGE if left < 10 else theme.WHITE
            ink = theme.BLACK
            draw.pill_label(s, f"TEMPO {int(math.ceil(left)):02d}s", int(22 * u), ink, col,
                            (f.right - pad, f.top + pad), "topright")

        if game.phase == Phase.IDLE:
            self._banner_idle(now, game, r)
        elif game.phase == Phase.CALIBRATING:
            self._banner_calibration(now, game)
        elif game.phase == Phase.PLAYING:
            self._banner_playing(now, game, dt)
        elif game.phase == Phase.BETWEEN:
            self._draw_stamp(now, game)

        if game.phase in ACTIVE and r is not None and r.locked and r.player is None and r.lost_for > 0.4:
            self._draw_lost(r)

    def display_frame(self, r: FrameResult | None, camera):
        """Quadro mais novo para a tela: direto da câmera (sem esperar a IA), senão o processado."""
        peek = getattr(camera, "peek", None)
        got = peek() if peek is not None else None
        if got is not None:
            return got
        if r is not None:
            return r.frame, r.frame_id
        return None, -1

    def _draw_face_marks(self, now: float, game: Game, r: FrameResult) -> None:
        s, u = self.screen, self.L.u
        prev = s.get_clip()
        s.set_clip(self.L.feed)
        box = self.box.update(self.feed.map_rect(r.player) if r.player is not None else None, r.frame_id, now)
        if r.player is not None and box is not None:
            rect = box.inflate(int(24 * u), int(24 * u))
            col = theme.EMOTIONS[game.target]["color"] if game.target else theme.MINT
            draw.brackets(s, rect, col, int(rect.w * 0.2), max(4, int(7 * u)))
            draw.pill_label(s, "VOCÊ", int(18 * u), theme.BLACK, col, (rect.centerx, rect.top - int(10 * u)), "midbottom")
        elif r.candidate is not None and game.phase == Phase.IDLE:
            rect = self.feed.map_rect(r.candidate).inflate(int(24 * u), int(24 * u))
            draw.brackets(s, rect, theme.WHITE, int(rect.w * 0.2), max(3, int(5 * u)))
            rad = max(rect.w, rect.h) * 0.62
            draw.ring(s, rect.center, rad, max(6, int(10 * u)), r.lock_progress, theme.MINT)
        s.set_clip(prev)

    def _draw_ai_reading(self, game: Game, pos) -> None:
        if game.smoothed is None:
            return
        key, p = game.smoothed.top()
        color = theme.EMOTIONS[key]["color"] if key in theme.EMOTIONS else theme.WHITE
        u = self.L.u
        r = draw.pill_label(self.screen, f"A IA VÊ: {LABELS_PT[key]} {int(round(p * 100))}%", int(20 * u),
                            theme.WHITE, theme.CANVAS, pos, border_color=color)
        pygame.draw.circle(self.screen, color, (r.right - int(4 * u), r.top + int(4 * u)), int(8 * u))

    def _draw_ai_card(self, now: float, game: Game, pos) -> None:
        """Canto da câmera: "A IA VÊ" + mapa agradável x agitado com o ponto do jogador."""
        s, L, u = self.screen, self.L, self.L.u
        f = L.feed
        w = int(min(300 * u, f.w * 0.3, (f.h - self._banner_rect().h) * 0.62))
        head_h = int(52 * u)
        card = pygame.Rect(pos[0], pos[1], w, w + head_h)
        color = theme.GRAY
        text = "A IA ESTÁ OLHANDO..."
        if game.smoothed is not None:
            key, p = game.smoothed.top()
            color = theme.EMOTIONS[key]["color"] if key in theme.EMOTIONS else theme.WHITE
            text = f"A IA VÊ: {LABELS_PT[key]} {int(round(p * 100))}%"
        draw.block(s, card, theme.CANVAS, int(22 * u), color, max(3, int(4 * u)))
        ts = draw.fit_size(text, "mono", int(19 * u), card.w - int(28 * u), 19 * u * 0.12)
        draw.label(s, text, ts, theme.WHITE, (card.centerx, card.top + head_h // 2 + int(2 * u)), "center")
        pygame.draw.line(s, theme.SLATE, (card.left + int(12 * u), card.top + head_h),
                         (card.right - int(12 * u), card.top + head_h), max(1, int(2 * u)))
        mp = pygame.Rect(0, 0, w - int(30 * u), w - int(30 * u))
        mp.center = (card.centerx, card.top + head_h + w // 2)
        target = game.target if game.phase == Phase.PLAYING else None
        if game.smoothed is None:
            self.map.reset()
        self.map.draw(s, mp, now, u, target, color, labels=mp.w >= 200)

    def _skip_hint(self, now: float, game: Game) -> None:
        if not self.cfg.ui.report:
            return
        L, u = self.L, self.L.u
        draw.pill_label(self.screen, "ENTER: VER O RELATÓRIO", int(16 * u), theme.WHITE, theme.CANVAS,
                        (L.W - L.m, L.H - int(66 * u)), "bottomright", border_color=theme.GRAY)

    def _banner_rect(self) -> pygame.Rect:
        f, u = self.L.feed, self.L.u
        pad = int(22 * u)
        bh = int(min(210 * u, f.height * 0.32))
        return pygame.Rect(f.left + pad, f.bottom - pad - bh, f.width - 2 * pad, bh)

    def _banner(self, rect, color, ink, title: str, hint: str, emoji_kind: str | None,
                emoji_intensity: float = 1.0, now: float = 0.0, extra: int = 0,
                bottom_reserve: int = 0) -> pygame.Rect:
        """Bloco colorido com emoji + título + dica. Devolve a área de texto (para barras)."""
        s, u = self.screen, self.L.u
        draw.block(s, rect, color, int(28 * u))
        x = rect.left + int(26 * u)
        if emoji_kind:
            er = int(rect.height * 0.36)
            ec = (x + er, rect.centery + bob(now, 0, 4 * u))
            draw_emoji(s, emoji_kind, ec, er, emoji_intensity)
            x += 2 * er + int(26 * u)
        tw = rect.right - x - int(26 * u) - extra
        pad_v = int(24 * u)
        top, bottom = rect.top + pad_v, rect.bottom - pad_v - bottom_reserve
        gap = int(12 * u)
        hsize = draw.fit_size(hint, "ui_medium", int(28 * u), tw)
        hint_s = draw.tight_surface(hint, "ui_medium", hsize, ink)
        tsize = draw.fit_size(title, "display", int(84 * u), tw)
        title_s = draw.tight_surface(title, "display", tsize, ink)
        while title_s.get_height() + gap + hint_s.get_height() > bottom - top and tsize > 12:
            tsize = int(tsize * 0.92)
            title_s = draw.tight_surface(title, "display", tsize, ink)
        y = top + (bottom - top - (title_s.get_height() + gap + hint_s.get_height())) // 2
        s.blit(title_s, (x, y))
        s.blit(hint_s, (x, y + title_s.get_height() + gap))
        return pygame.Rect(x, rect.top, tw, rect.height)

    def _banner_idle(self, now: float, game: Game, r: FrameResult | None) -> None:
        rect = self._banner_rect()
        if now < game.cooldown_until:
            self._banner(rect, theme.WHITE, theme.BLACK, "PRÓXIMO JOGADOR!", "Chegue perto e olhe para a câmera",
                         "happiness", 1.0, now)
        elif r is not None and r.candidate is not None:
            self._banner(rect, theme.MINT, theme.BLACK, "ACHEI VOCÊ! FIQUE PARADINHO(A)...",
                         "Estou travando a câmera no seu rosto", "surprise", r.lock_progress, now)
        else:
            self._banner(rect, theme.MINT, theme.BLACK, "CHEGUE MAIS PERTO!",
                         "Fique sozinho(a) de frente para a câmera para jogar", "happiness",
                         0.5 + 0.5 * math.sin(now * 2.0) ** 2, now)

    def _banner_calibration(self, now: float, game: Game) -> None:
        s, u = self.screen, self.L.u
        rect = self._banner_rect()
        left = max(0.0, self.cfg.calibration.seconds - game.phase_elapsed(now))
        count_w = int(rect.height * 0.9)
        if game.calib_retry_reason == "expressive":
            color, title, hint = theme.YELLOW, "QUASE! AGORA SEM CARETA...", "Cara séria, boca fechada, olhando para a câmera"
        elif game.calib_retry_reason:
            color, title, hint = theme.YELLOW, "OLHE PARA A CÂMERA", "Fique de frente, sem cobrir o rosto"
        else:
            color, title, hint = theme.WHITE, "FIQUE SÉRIO(A)...", "Estou medindo o seu rosto neutro"
        bar_h = int(14 * u)
        area = self._banner(rect, color, theme.BLACK, title, hint, "neutral", 1.0, now, extra=count_w,
                            bottom_reserve=bar_h + int(14 * u))
        cx = rect.right - count_w // 2 - int(10 * u)
        cy = rect.centery
        rad = rect.height * 0.38
        pygame.draw.circle(s, theme.CANVAS, (cx, cy), rad)
        draw.ring(s, (cx, cy), rad, max(6, int(10 * u)), game.calibration_progress(now), theme.MINT)
        draw.blit_tight(s, str(int(math.ceil(left)) or 1), "display", int(rad * 1.2), theme.WHITE, (cx, cy), "center")
        bar = pygame.Rect(area.left, rect.bottom - int(24 * u) - bar_h, area.width, bar_h)
        draw.progress_bar(s, bar, game.calibration_progress(now), theme.BLACK, theme.MUTED)

    def _banner_playing(self, now: float, game: Game, dt: float) -> None:
        s, u = self.screen, self.L.u
        key = game.target
        meta = theme.EMOTIONS[key]
        ev = game.evaluation
        target_i = ev.intensity if ev is not None else 0.0
        self._disp_intensity += (target_i - self._disp_intensity) * min(1.0, dt * 12)
        passed = ev is not None and ev.passed
        rect = self._banner_rect()
        bar_h = int(18 * u)
        area = self._banner(rect, meta["color"], meta["ink"], meta["prompt"], meta["hint"], key,
                            self._disp_intensity, now, bottom_reserve=bar_h + int(14 * u))
        # anel de "segura!" em volta do emoji
        er = int(rect.height * 0.36)
        ec = (rect.left + int(26 * u) + er, rect.centery + bob(now, 0, 4 * u))
        if game.hold_progress > 0:
            draw.ring(s, ec, er + int(16 * u), max(6, int(10 * u)), game.hold_progress, theme.CANVAS)
        # medidor de força
        bar = pygame.Rect(area.left, rect.bottom - int(24 * u) - bar_h, int(area.width * 0.70), bar_h)
        bg = theme.UV_DARK if meta["ink"] == theme.WHITE else theme.WHITE
        draw.progress_bar(s, bar, self._disp_intensity, meta["ink"], bg)
        lab = "SEGURA AÍ!" if passed else "FORÇA DA CARETA"
        draw.label(s, lab, int(18 * u), meta["ink"], (bar.right + int(16 * u), bar.centery), "midleft")

    def _draw_stamp(self, now: float, game: Game) -> None:
        s, L, u = self.screen, self.L, self.L.u
        key = game.order[game.target_index]
        meta = theme.EMOTIONS[key]
        el = game.phase_elapsed(now)
        sc = draw.ease_out_back(el / 0.35)
        size = int(120 * u)
        txt = draw.text_surface(meta["stamp"], "display", size, meta["ink"])
        pad = int(34 * u)
        card = pygame.Surface((txt.get_width() + 2 * pad, txt.get_height() + pad), pygame.SRCALPHA)
        pygame.draw.rect(card, meta["color"], card.get_rect(), border_radius=int(30 * u))
        pygame.draw.rect(card, theme.WHITE, card.get_rect(), width=max(3, int(5 * u)), border_radius=int(30 * u))
        card.blit(txt, txt.get_rect(center=card.get_rect().center))
        img = pygame.transform.rotozoom(card, 6, max(0.05, sc))
        s.blit(img, img.get_rect(center=(L.feed.centerx, L.feed.centery - int(30 * u))))
        nxt = game.target_index + 1
        if nxt < len(game.order) and el > 0.3:
            nm = theme.EMOTIONS[game.order[nxt]]
            draw.pill_label(s, f"PRÓXIMA: {nm['name']}", int(26 * u), nm["ink"], nm["color"],
                            (L.feed.centerx, L.feed.bottom - int(60 * u)), "midbottom", border_color=theme.WHITE)

    def _draw_lost(self, r: FrameResult) -> None:
        s, L, u = self.screen, self.L, self.L.u
        f = L.feed
        rect = pygame.Rect(0, 0, int(f.width * 0.7), int(210 * u))
        rect.center = f.center
        draw.block(s, rect, theme.ORANGE, int(30 * u))
        draw.blit_text(s, "CADÊ VOCÊ?", "display", int(96 * u), theme.BLACK, (rect.centerx, rect.top + int(18 * u)), "midtop")
        left = max(0.0, self.cfg.detector.lost_seconds - r.lost_for)
        draw.blit_text(s, f"Volte para a câmera! Reiniciando em {int(math.ceil(left))}s", "ui_medium", int(28 * u),
                       theme.BLACK, (rect.centerx, rect.bottom - int(24 * u)), "midbottom")

    def _draw_camera_problem(self, now: float, camera) -> None:
        s, L, u = self.screen, self.L, self.L.u
        f = L.feed
        dim = pygame.Surface(f.size)
        dim.fill(theme.CANVAS)
        dim.set_alpha(200)
        s.blit(dim, f.topleft)
        first = camera.status == "connecting" and camera.message == ""
        title = "LIGANDO A CÂMERA..." if first else "CÂMERA DESCONECTADA"
        sub = "Um instante" if first else f"Tentando reconectar sozinho ({camera.source_label})"
        cx, cy = f.centerx, f.centery - int(60 * u)
        rad = 60 * u
        a = (now * 1.3) % 1.0
        draw.ring(s, (cx, cy), rad, 12 * u, 0.3, theme.MINT, start_deg=a * 360)
        draw.blit_text(s, title, "display", draw.fit_size(title, "display", int(90 * u), int(f.width * 0.9)),
                       theme.WHITE, (cx, cy + rad + int(24 * u)), "midtop")
        draw.label(s, sub, int(20 * u), theme.GRAY, (cx, cy + rad + int(150 * u)), "midtop")

    # ================================================================== caretas (tiles)
    def thumb(self, game: Game, key: str, diameter: int) -> pygame.Surface | None:
        """Foto redonda da careta (só em memória)."""
        img = game.snapshots.get(key)
        if img is None or diameter < 2:
            return None
        cached = self._thumbs.get((key, diameter))
        if cached and cached[0] == id(img):
            return cached[1]
        rgb = cv2.cvtColor(cv2.resize(img, (diameter, diameter), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        surf = pygame.image.frombuffer(rgb.tobytes(), (diameter, diameter), "RGB").convert_alpha()
        mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (diameter // 2, diameter // 2), diameter // 2)
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        if len(self._thumbs) > 40:
            self._thumbs.clear()
        self._thumbs[(key, diameter)] = (id(img), surf)
        return surf

    def _draw_tile(self, now: float, game: Game, i: int, key: str, rect: pygame.Rect) -> None:
        s, u = self.screen, self.L.u
        meta = theme.EMOTIONS[key]
        done = key in game.completed
        current = game.target == key and not done
        idle = game.phase in (Phase.IDLE, Phase.CALIBRATING)
        radius = int(28 * u)
        if done or current:
            draw.block(s, rect, meta["color"], radius, theme.WHITE if current else None, max(3, int(5 * u)))
            ink = meta["ink"]
        else:
            draw.block(s, rect, theme.CANVAS, radius, meta["color"], max(2, int(3 * u)))
            ink = theme.WHITE

        horizontal = rect.width / max(1, rect.height) > 1.6
        pad = int(24 * u)
        if horizontal:
            er = int(min(rect.height * 0.34, rect.width * 0.16))
            ec = (rect.left + pad + er, rect.centery)
            tx = ec[0] + er + int(26 * u)
        else:
            er = int(min(rect.height * 0.2, rect.width * 0.2))
            ec = (rect.centerx, rect.top + pad + er)
            tx = rect.left + pad

        wobble = bob(now, i * 1.3, 5 * u) if (idle or current) else 0.0
        thumb = self.thumb(game, key, 2 * er) if done else None
        if thumb is not None:
            s.blit(thumb, thumb.get_rect(center=ec))
            pygame.draw.circle(s, theme.WHITE, ec, er, max(3, int(5 * u)))
            draw_emoji(s, key, (ec[0] + er * 0.72, ec[1] + er * 0.72), int(er * 0.42), 1.0)
        else:
            inten = 1.0 if (done or idle or not current) else max(0.25, self._disp_intensity)
            draw_emoji(s, key, (ec[0], ec[1] + wobble), er, inten)

        if horizontal:
            status = "FEITO!" if done else ("AGORA!" if current else f"CARETA {i + 1}")
            draw.label(s, status, int(18 * u), ink, (tx, rect.top + pad))
            nsize = draw.fit_size(meta["name"], "display", int(min(96 * u, rect.height * 0.4)), rect.right - tx - pad)
            nr = draw.blit_text(s, meta["name"], "display", nsize, ink, (tx, rect.top + pad + int(22 * u)))
            bar = pygame.Rect(tx, min(rect.bottom - pad - int(18 * u), nr.bottom + int(10 * u)),
                              rect.right - tx - pad, int(18 * u))
        else:
            nsize = draw.fit_size(meta["name"], "display", int(min(70 * u, rect.height * 0.25)), rect.width - 2 * pad)
            nr = draw.blit_text(s, meta["name"], "display", nsize, ink, (rect.centerx, ec[1] + er + int(8 * u)), "midtop")
            bar = pygame.Rect(rect.left + pad, rect.bottom - pad - int(16 * u), rect.width - 2 * pad, int(16 * u))

        frac = 1.0 if done else (game.hold_progress if current else 0.0)
        bg = theme.SLATE if not (done or current) else (theme.UV_DARK if ink == theme.WHITE else theme.WHITE)
        draw.progress_bar(s, bar, frac, ink if (done or current) else meta["color"], bg)
        if done:
            self._check(s, (rect.right - pad - int(26 * u), rect.top + pad + int(24 * u)), int(26 * u), ink)

    @staticmethod
    def _check(s, center, r: int, color) -> None:
        cx, cy = center
        pygame.draw.circle(s, color, center, r)
        inner = theme.BLACK if color == theme.WHITE else theme.WHITE
        w = max(3, r // 4)
        pygame.draw.lines(s, inner, False, [(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.4)], w)

    # ================================================================== vitória
    def _build_cards(self, game: Game) -> list:
        L, u = self.L, self.L.u
        n = len(game.order)
        photo = int(min(330 * u, (L.W - 2 * L.m) / n * 0.62, L.H * 0.34))
        pad = int(16 * u)
        cap_h = int(photo * 0.26)
        angles = (-6, 4, -3)
        cards = []
        for i, key in enumerate(game.order):
            meta = theme.EMOTIONS[key]
            card = pygame.Surface((photo + 2 * pad, photo + pad + cap_h), pygame.SRCALPHA)
            pygame.draw.rect(card, theme.WHITE, card.get_rect(), border_radius=int(10 * u))
            prect = pygame.Rect(pad, pad, photo, photo)
            img = game.snapshots.get(key)
            if img is not None:
                rgb = cv2.cvtColor(cv2.resize(img, (photo, photo), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
                card.blit(pygame.image.frombuffer(rgb.tobytes(), (photo, photo), "RGB"), prect)
            else:
                pygame.draw.rect(card, meta["color"], prect)
                draw_emoji(card, key, prect.center, int(photo * 0.34), 1.0)
            draw.blit_text(card, meta["name"], "display", int(cap_h * 0.72), theme.BLACK,
                           (card.get_width() // 2, photo + pad + cap_h // 2), "center")
            # fita adesiva colorida no topo
            tape = pygame.Rect(0, 0, int(photo * 0.42), int(34 * u))
            tape.center = (card.get_width() // 2, int(6 * u))
            pygame.draw.rect(card, meta["color"], tape)
            if img is not None:
                draw_emoji(card, key, (prect.right - int(photo * 0.1), prect.bottom - int(photo * 0.1)),
                           int(photo * 0.15), 1.0)
            cards.append(pygame.transform.rotozoom(card, angles[i % 3], 1.0))
        return cards

    def _draw_victory(self, now: float, game: Game) -> None:
        s, L, u = self.screen, self.L, self.L.u
        el = game.phase_elapsed(now)
        band = int(30 * u)
        draw.hazard_tape(s, pygame.Rect(0, 0, L.W, band), theme.MINT, theme.UV, now, int(30 * u), 50 * u)
        draw.hazard_tape(s, pygame.Rect(0, L.H - band, L.W, band), theme.MINT, theme.UV, now, int(30 * u), -50 * u)

        if int(el * 10) % 7 == 0 and el < self.cfg.game.victory_seconds - 1.5:
            self.confetti.rain(L.W, 6, 700 * u, 26 * u)

        draw.label(s, f"3 DE 3 CARETAS  •  {self.cfg.ui.kicker}", int(22 * u), theme.MINT,
                   (L.W // 2, band + int(40 * u)), "midtop")
        title = "VOCÊ VENCEU!"
        sc = draw.ease_out_back(el / 0.5)
        tsize = draw.fit_size(title, "display", int(200 * u), int(L.W * 0.86))
        tsurf = draw.text_surface(title, "display", tsize, theme.WHITE)
        if sc < 0.999:
            tsurf = pygame.transform.rotozoom(tsurf, 0, max(0.05, sc))
        trect = tsurf.get_rect(midtop=(L.W // 2, band + int(76 * u)))
        s.blit(tsurf, trect)

        if self._victory_cards is None or self._victory_cards[0] != game.phase_t0:
            self._victory_cards = (game.phase_t0, self._build_cards(game))
        cards = self._victory_cards[1]
        n = len(cards)
        slot = (L.W - 2 * L.m) / n
        cy = trect.bottom + (L.H - band - int(150 * u) - trect.bottom) / 2
        for i, card in enumerate(cards):
            k = draw.ease_out_back((el - 0.35 - i * 0.18) / 0.45)
            if k <= 0:
                continue
            x = L.m + slot * (i + 0.5)
            y = cy + (1 - k) * L.H * 0.6
            s.blit(card, card.get_rect(center=(int(x), int(y))))

        msg = "Uma rede neural reconheceu as suas 3 emoções. Isso é visão computacional!"
        msize = draw.fit_size(msg, "ui", int(34 * u), int(L.W * 0.9))
        draw.blit_text(s, msg, "ui", msize, theme.WHITE, (L.W // 2, L.H - band - int(96 * u)), "midbottom")
        left = max(0.0, self.cfg.game.victory_seconds - el)
        bar = pygame.Rect(0, 0, int(L.W * 0.36), int(14 * u))
        bar.midbottom = (L.W // 2, L.H - band - int(40 * u))
        draw.progress_bar(s, bar, left / max(self.cfg.game.victory_seconds, 1e-6), theme.MINT, theme.SLATE)

    # ================================================================== tempo esgotado
    def _draw_timeout(self, now: float, game: Game) -> None:
        s, L, u = self.screen, self.L, self.L.u
        el = game.phase_elapsed(now)
        rect = pygame.Rect(0, 0, L.W, L.H).inflate(-2 * L.m, -2 * L.m)
        draw.block(s, rect, theme.YELLOW, int(40 * u))
        draw.label(s, "O TEMPO ACABOU", int(26 * u), theme.BLACK, (rect.centerx, rect.top + int(50 * u)), "midtop")
        sc = draw.ease_out_back(el / 0.4)
        t = draw.text_surface("QUASE!", "display", int(260 * u), theme.BLACK)
        if sc < 0.999:
            t = pygame.transform.rotozoom(t, 0, max(0.05, sc))
        tr = t.get_rect(midtop=(rect.centerx, rect.top + int(96 * u)))
        s.blit(t, tr)
        n = len(game.order)
        er = int(min(90 * u, rect.width / n * 0.25))
        for i, key in enumerate(game.order):
            x = rect.centerx + (i - (n - 1) / 2) * er * 3.2
            y = tr.bottom + er + int(30 * u)
            done = key in game.completed
            draw_emoji(s, key, (x, y + bob(now, i, 5 * u)), er, 1.0 if done else 0.4)
            if done:
                self._check(s, (int(x + er * 0.8), int(y - er * 0.8)), int(er * 0.35), theme.BLACK)
        msg = "Foi por pouco! Tente de novo ou chame o próximo."
        draw.blit_text(s, msg, "ui", draw.fit_size(msg, "ui", int(40 * u), int(rect.width * 0.9)), theme.BLACK,
                       (rect.centerx, rect.bottom - int(90 * u)), "midbottom")
        left = max(0.0, self.cfg.game.timeout_seconds - el)
        bar = pygame.Rect(0, 0, int(rect.width * 0.4), int(14 * u))
        bar.midbottom = (rect.centerx, rect.bottom - int(44 * u))
        draw.progress_bar(s, bar, left / max(self.cfg.game.timeout_seconds, 1e-6), theme.BLACK, theme.WHITE)

    # ================================================================== splash
    def draw_splash(self, message: str, now: float) -> None:
        s, L, u = self.screen, self.L, self.L.u
        s.fill(theme.CANVAS)
        cx, cy = L.W // 2, L.H // 2
        draw.label(s, self.cfg.ui.kicker, int(22 * u), theme.MINT, (cx, cy - int(190 * u)), "midtop")
        draw.blit_text(s, self.cfg.ui.title, "display", int(140 * u), theme.WHITE, (cx, cy - int(150 * u)), "midtop")
        draw.ring(s, (cx, cy + int(130 * u)), 50 * u, 10 * u, 0.3, theme.MINT, start_deg=(now * 400) % 360)
        draw.label(s, message, int(20 * u), theme.GRAY, (cx, cy + int(210 * u)), "midtop")
