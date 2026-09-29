"""Modo explicação (tecla E): "Por dentro da IA".

Mostra, passo a passo, o que acontece a cada quadro: 1) o detector acha o rosto
e 5 pontos; 2) o rosto é recortado e endireitado em 224x224 pixels; 3) a rede
neural lê o recorte; 4) saem 8 emoções; 5) e também valência x excitação (mapa).
O jogo fica pausado; nada é gravado.
"""

from __future__ import annotations

import pygame

from ..emotion import CLASS_NAMES, LABELS_PT
from ..pipeline import FrameResult
from ..scoring import Smoother
from . import draw, theme
from .emoji import draw_emoji
from .radar import EmotionMap
from .smooth import SmoothBox

LAB_MARQUEE = ("MODO EXPLICAÇÃO  •  A IA LÊ A EXPRESSÃO DO ROSTO, NÃO O QUE VOCÊ SENTE POR DENTRO  •  "
               "ELA FAZ O RELATÓRIO; QUEM DECIDE É SEMPRE UMA PESSOA  •  NENHUMA IMAGEM É GRAVADA  •  ")

CLASS_COLORS = theme.CLASS_COLORS


class LabView:
    def __init__(self, cfg, renderer):
        self.cfg = cfg
        self.r = renderer
        self.smoother = Smoother(cfg.emotion.smoothing)
        self.map = EmotionMap(trail_seconds=2.5)
        self.box = SmoothBox()
        self._fid = -1
        self._crop_surf: pygame.Surface | None = None
        self._crop_fid = -1
        self._shown = [0.0] * len(CLASS_NAMES)
        self._last_now = 0.0

    def reset(self) -> None:
        self.smoother.reset()
        self.map.reset()
        self.box.reset()
        self._crop_surf = None
        self._shown = [0.0] * len(CLASS_NAMES)

    # ------------------------------------------------------------------ layout
    def _layout(self):
        L, u = self.r.L, self.r.L.u
        top = L.header.bottom + int(8 * u)
        bottom = L.footer.top - int(20 * u)
        g = int(20 * u)
        if L.wide:
            feed = pygame.Rect(L.m, top, int((L.W - 2 * L.m) * 0.44), bottom - top)
            grid = pygame.Rect(feed.right + g, top, L.W - L.m - feed.right - g, bottom - top)
            cw, ch = (grid.w - g) // 2, (grid.h - g) // 2
            cells = [pygame.Rect(grid.left + (i % 2) * (cw + g), grid.top + (i // 2) * (ch + g), cw, ch) for i in range(4)]
            return feed, cells
        # 4:3: sem a caixa "rede neural" (o tempo vai para a câmera); câmera + recorte à
        # esquerda, 8 emoções + mapa à direita.
        colw = (L.W - 2 * L.m - g) // 2
        fh = int((bottom - top) * 0.58)
        feed = pygame.Rect(L.m, top, colw, fh)
        crop = pygame.Rect(L.m, feed.bottom + g, colw, bottom - feed.bottom - g)
        rx = L.m + colw + g
        half = (bottom - top - g) // 2
        bars = pygame.Rect(rx, top, colw, half)
        mp = pygame.Rect(rx, top + half + g, colw, bottom - top - half - g)
        return feed, [crop, None, bars, mp]

    # ------------------------------------------------------------------ tela
    def draw(self, s: pygame.Surface, now: float, r: FrameResult | None, camera, device_label: str) -> None:
        L, u = self.r.L, self.r.L.u
        dt = max(0.0, min(0.1, now - self._last_now))
        self._last_now = now
        if r is not None and r.frame_id != self._fid:
            self._fid = r.frame_id
            if r.reading is not None:
                sm = self.smoother.update(r.reading)
                self.map.update(now, sm.valence, sm.arousal)
            elif not r.locked:
                self.smoother.reset()
        sm = self.smoother.state if (r is not None and r.locked) else None

        s.fill(theme.CANVAS)
        self.r.draw_header_block(s, now, "MODO EXPLICAÇÃO  •  TECLA E VOLTA AO JOGO", "POR DENTRO DA IA",
                                 "Como a rede neural lê uma expressão, passo a passo")
        feed, cells = self._layout()
        self._draw_feed(s, feed, now, r, camera, device_label)
        self._cell_crop(s, cells[0], r)
        if cells[1] is not None:
            self._cell_network(s, cells[1], r, device_label)
        n = 4 if cells[1] is not None else 3
        self._cell_bars(s, cells[2], sm, dt, n)
        self._cell_map(s, cells[3], now, sm, n + 1)
        self.r.draw_marquee(s, now, LAB_MARQUEE)

    def _step(self, s, rect: pygame.Rect, n: int, title: str, sub: str = "") -> int:
        """Título numerado da etapa. Devolve o y onde o conteúdo pode começar."""
        u = self.r.L.u
        rad = int(22 * u)
        c = (rect.left + int(20 * u) + rad, rect.top + int(20 * u) + rad)
        pygame.draw.circle(s, theme.MINT, c, rad)
        draw.blit_tight(s, str(n), "display", int(rad * 1.3), theme.BLACK, c, "center")
        tr = draw.label(s, title, int(19 * u), theme.WHITE, (c[0] + rad + int(14 * u), c[1] - int(2 * u)), "bottomleft")
        y = tr.bottom
        if sub:
            sr = draw.blit_text(s, sub, "ui_medium", draw.fit_size(sub, "ui_medium", int(20 * u), rect.right - tr.left - int(16 * u)),
                                theme.GRAY, (tr.left, tr.bottom + int(2 * u)))
            y = sr.bottom
        return max(y, c[1] + rad) + int(12 * u)

    def _cell(self, s, rect) -> None:
        u = self.r.L.u
        draw.block(s, rect, theme.CANVAS, int(26 * u), theme.SLATE, max(2, int(3 * u)))

    # ------------------------------------------------------------------ 1. câmera
    def _draw_feed(self, s, f: pygame.Rect, now, r: FrameResult | None, camera, device_label: str) -> None:
        L, u = self.r.L, self.r.L.u
        fv = self.r.feed
        frame, fid = self.r.display_frame(r, camera)
        if frame is not None:
            fv.update(frame, fid, f)
            s.blit(fv.surface, f.topleft)
        else:
            draw.block(s, f, theme.SLATE, L.radius)
        if r is not None:
            prev = s.get_clip()
            s.set_clip(f)
            for face in r.faces:
                if face is r.player:
                    continue
                rect = fv.map_rect(face)
                pygame.draw.rect(s, theme.GRAY, rect, max(1, int(2 * u)))
                draw.label(s, "IGNORADO", int(14 * u), theme.GRAY, (rect.left, rect.bottom + int(4 * u)))
            if r.player is not None:
                box = self.box.update(fv.map_rect(r.player), r.frame_id, now)
                draw.brackets(s, box.inflate(int(20 * u), int(20 * u)), theme.MINT, int(box.w * 0.2), max(4, int(6 * u)))
                pts = []
                for (lx, ly) in r.player.landmarks:
                    pts.append((float(fv.rect.x + (lx - fv.x0) * fv.scale), float(fv.rect.y + (ly - fv.y0) * fv.scale)))
                eye_l, eye_r, nose, mouth_l, mouth_r = pts
                lw = max(2, int(2 * u))
                for a, b in ((eye_l, eye_r), (eye_l, nose), (eye_r, nose), (nose, mouth_l), (nose, mouth_r), (mouth_l, mouth_r)):
                    pygame.draw.line(s, theme.MINT, a, b, lw)
                for p in pts:
                    pygame.draw.circle(s, theme.BLACK, p, int(7 * u))
                    pygame.draw.circle(s, theme.MINT, p, int(5 * u))
                draw.pill_label(s, f"ROSTO {int(r.player.score * 100)}%", int(18 * u), theme.BLACK, theme.MINT,
                                (box.centerx, box.top - int(16 * u)), "midbottom")
            else:
                self.box.update(None, r.frame_id, now)
                if r.candidate is not None:
                    rect = fv.map_rect(r.candidate).inflate(int(20 * u), int(20 * u))
                    draw.brackets(s, rect, theme.WHITE, int(rect.w * 0.2), max(3, int(5 * u)))
            s.set_clip(prev)
        draw.corner_caps(s, f, L.radius, theme.CANVAS)
        pygame.draw.rect(s, theme.MINT, f, width=max(3, int(4 * u)), border_radius=L.radius)
        pad = int(18 * u)
        draw.pill_label(s, "1 · ACHAR O ROSTO E 5 PONTOS", int(18 * u), theme.BLACK, theme.MINT, (f.left + pad, f.top + pad))
        if r is None or r.player is None:
            draw.pill_label(s, "CHEGUE PERTO DA CÂMERA", int(24 * u), theme.BLACK, theme.WHITE,
                            (f.centerx, f.bottom - pad), "midbottom")
        elif r.timings:
            text = f"DETECTOR: {r.timings.get('detect_ms', 0):.0f} ms"
            if not L.wide:   # 4:3 não tem a caixa da rede neural
                text += f"  •  REDE: {r.timings.get('emotion_ms', 0):.0f} ms ({device_label.split()[0]})"
            draw.pill_label(s, text, int(16 * u), theme.WHITE, theme.CANVAS,
                            (f.left + pad, f.bottom - pad), "bottomleft", border_color=theme.MINT)

    # ------------------------------------------------------------------ 2. recorte
    def _cell_crop(self, s, rect, r: FrameResult | None) -> None:
        u = self.r.L.u
        self._cell(s, rect)
        y = self._step(s, rect, 2, "RECORTAR E ENDIREITAR", "A rede só recebe isto:")
        side = int(min(rect.w - 2 * int(24 * u), rect.bottom - y - int(56 * u)))
        box = pygame.Rect(0, 0, side, side)
        box.midtop = (rect.centerx, y)
        crop = r.crop if (r is not None and r.player is not None) else None
        if crop is not None:
            if r.frame_id != self._crop_fid or self._crop_surf is None or self._crop_surf.get_width() != side:
                h, w = crop.shape[:2]
                raw = pygame.image.frombuffer(crop.tobytes(), (w, h), "RGB")
                self._crop_surf = pygame.transform.smoothscale(raw, (side, side))
                self._crop_fid = r.frame_id
            s.blit(self._crop_surf, box)
        else:
            pygame.draw.rect(s, theme.SLATE, box)
            draw_emoji(s, "neutral", box.center, int(side * 0.25), 1.0, face=theme.GRAY)
        draw.corner_caps(s, box, int(14 * u), theme.CANVAS)
        pygame.draw.rect(s, theme.MINT, box, max(2, int(3 * u)), border_radius=int(14 * u))
        draw.label(s, "224 × 224 PIXELS", int(17 * u), theme.MINT, (rect.centerx, box.bottom + int(12 * u)), "midtop")

    # ------------------------------------------------------------------ 3. rede
    def _cell_network(self, s, rect, r: FrameResult | None, device_label: str) -> None:
        u = self.r.L.u
        self._cell(s, rect)
        y = self._step(s, rect, 3, "REDE NEURAL", "Uma conta gigante, feita num piscar de olhos")
        pad = int(26 * u)
        ms = r.timings.get("emotion_ms", 0.0) if (r is not None and r.player is not None) else 0.0
        big = f"{ms:.0f} ms" if ms > 0 else "-- ms"
        avail_h = rect.bottom - y - pad
        bs = draw.fit_size(big, "display", int(min(130 * u, avail_h * 0.42)), rect.w - 2 * pad)
        br = draw.blit_tight(s, big, "display", bs, theme.YELLOW, (rect.left + pad, y + int(4 * u)))
        draw.label(s, f"POR ROSTO · {device_label.split()[0]}", int(16 * u), theme.GRAY, (br.right + int(14 * u), br.bottom), "bottomleft")
        facts = (("APRENDEU COM", "~290 MIL FOTOS DE ROSTOS"), ("TAMANHO", "4 MILHÕES DE PARÂMETROS"))
        fy = br.bottom + int(18 * u)
        row = (rect.bottom - pad - fy) / len(facts)
        for i, (lab, val) in enumerate(facts):
            yy = fy + i * row
            lr = draw.label(s, lab, int(15 * u), theme.GRAY, (rect.left + pad, yy))
            vs = draw.fit_size(val, "ui", int(min(32 * u, row * 0.45)), rect.w - 2 * pad)
            draw.blit_text(s, val, "ui", vs, theme.WHITE, (rect.left + pad, lr.bottom + int(2 * u)))

    # ------------------------------------------------------------------ 4. 8 emoções
    def _cell_bars(self, s, rect, sm, dt: float, n_step: int) -> None:
        u = self.r.L.u
        self._cell(s, rect)
        y = self._step(s, rect, n_step, "8 EMOÇÕES", "Quanto a rede acha de cada uma" if self.r.L.wide else "")
        pad = int(24 * u)
        n = len(CLASS_NAMES)
        rh = (rect.bottom - pad - y) / n
        fs = max(10, int(min(18 * u, rh * 0.62)))
        top_i = int(sm.probs.argmax()) if sm is not None else -1
        lab_w = int(170 * u)
        for i, name in enumerate(CLASS_NAMES):
            target = float(sm.probs[i]) if sm is not None else 0.0
            self._shown[i] += (target - self._shown[i]) * min(1.0, dt * 10)
            yy = int(y + i * rh + rh / 2)
            col = CLASS_COLORS[name]
            draw.label(s, LABELS_PT[name], fs, theme.WHITE if i == top_i else theme.GRAY, (rect.left + pad, yy), "midleft")
            bar = pygame.Rect(rect.left + pad + lab_w, yy - int(rh * 0.2), rect.w - 2 * pad - lab_w - int(64 * u), max(6, int(rh * 0.4)))
            draw.progress_bar(s, bar, self._shown[i], col, theme.SLATE)
            draw.label(s, f"{int(round(self._shown[i] * 100))}%", fs, theme.WHITE if i == top_i else theme.GRAY,
                       (rect.right - pad, yy), "midright")

    # ------------------------------------------------------------------ 5. mapa
    def _cell_map(self, s, rect, now, sm, n_step: int) -> None:
        u = self.r.L.u
        self._cell(s, rect)
        y = self._step(s, rect, n_step, "MAPA DAS EMOÇÕES", "Agradável x agitado: o ponto é você" if self.r.L.wide else "")
        pad = int(22 * u)
        side = int(min(rect.w - 2 * pad, rect.bottom - pad - y))
        box = pygame.Rect(0, 0, side, side)
        box.midtop = (rect.centerx, y)
        color = CLASS_COLORS[CLASS_NAMES[int(sm.probs.argmax())]] if sm is not None else theme.GRAY
        if sm is None:
            self.map.reset()
        self.map.draw(s, box, now, u, None, color, labels=box.w >= 200)
