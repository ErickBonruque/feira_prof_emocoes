"""Tela "Relatório da IA": fotos das caretas, linha do tempo das emoções, o que a
IA notou, revisão humana ("a IA acertou?") e o botão de próximo jogador.

É o paralelo com o uso real de modelos de emoção: a IA resume o que viu num
relatório e uma pessoa confere. As fotos e números só existem em memória e são
apagados quando o operador chama o próximo jogador.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pygame

from ..emotion import CLASS_INDEX, LABELS_PT
from ..game import Game
from ..report import MatchReport
from . import draw, theme
from .emoji import bob, draw_emoji

LINE_COLORS = theme.CLASS_COLORS


def _num(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def _pct(x: float) -> str:
    return f"{int(round(max(0.0, min(1.0, x)) * 100))}%"


class ReportView:
    def __init__(self, cfg, renderer):
        self.cfg = cfg
        self.r = renderer
        self.buttons: dict[str, pygame.Rect] = {}
        self._cache: dict = {}
        self._cache_id = None
        self._stamp_t = -10.0
        self._answer_seen = None

    def forget(self) -> None:
        """Solta fotos/gráfico em cache (chamado no reset)."""
        self._cache.clear()
        self._cache_id = None
        self.buttons = {}

    # ================================================================== layout
    def _layout(self):
        L, u = self.r.L, self.r.L.u
        m = L.m
        header = pygame.Rect(m, m, L.W - 2 * m, int(150 * u))
        fh = int(96 * u)
        footer = pygame.Rect(m, L.H - m - fh, L.W - 2 * m, fh)
        top = header.bottom + int(14 * u)
        content = pygame.Rect(m, top, L.W - 2 * m, footer.top - int(22 * u) - top)
        g = int(22 * u)
        if L.wide:
            left = pygame.Rect(content.left, content.top, int(content.w * 0.60), content.h)
            right = pygame.Rect(left.right + g, content.top, content.right - left.right - g, content.h)
            photos = pygame.Rect(left.left, left.top, left.w, int(left.h * 0.53))
            chart = pygame.Rect(left.left, photos.bottom + g, left.w, left.bottom - photos.bottom - g)
            review_h = int(right.h * 0.42)
            findings = pygame.Rect(right.left, right.top, right.w, right.h - review_h - g)
            review = pygame.Rect(right.left, findings.bottom + g, right.w, review_h)
        else:
            photos = pygame.Rect(content.left, content.top, content.w, int(content.h * 0.35))
            chart = pygame.Rect(content.left, photos.bottom + g, content.w, int(content.h * 0.22))
            bottom = pygame.Rect(content.left, chart.bottom + g, content.w, content.bottom - chart.bottom - g)
            findings = pygame.Rect(bottom.left, bottom.top, int(bottom.w * 0.52), bottom.h)
            review = pygame.Rect(findings.right + g, bottom.top, bottom.right - findings.right - g, bottom.h)
        return header, photos, chart, findings, review, footer

    # ================================================================== tela
    def draw(self, s: pygame.Surface, now: float, game: Game) -> None:
        rep = game.report
        if rep is None:
            return
        if self._cache_id != (rep.number, s.get_size()):
            self.forget()
            self._cache_id = (rep.number, s.get_size())
        el = game.phase_elapsed(now)
        if game.review_answer != self._answer_seen:
            self._answer_seen = game.review_answer
            if game.review_answer is not None:
                self._stamp_t = now
        header, photos, chart, findings, review, footer = self._layout()
        self._draw_header(s, header, now, game, rep)
        self._draw_photos(s, photos, now, el, game, rep)
        self._draw_chart(s, chart, now, el, game, rep)
        self._draw_findings(s, findings, el, rep)
        self._draw_review(s, review, now, el, game)
        self._draw_footer(s, footer, now, el, game)
        if game.review_answer is not None:
            self._draw_stamp(s, chart, now, game.review_answer)   # nunca em cima das fotos

    # ------------------------------------------------------------------ cabeçalho
    def _draw_header(self, s, h, now, game: Game, rep: MatchReport) -> None:
        u = self.r.L.u
        kick = f"RELATÓRIO Nº {rep.number:03d}  •  GERADO PELA IA"
        if self.r.L.wide:
            kick += f"  •  {self.cfg.ui.kicker}"
        kr = draw.label(s, kick, int(20 * u), theme.MINT, (h.left, h.top))
        title = "RELATÓRIO DA IA"
        size = draw.fit_size(title, "display", int(112 * u), int(h.width * 0.56))
        avail = h.bottom - kr.bottom - int(22 * u)
        while draw.tight_surface(title, "display", size, theme.WHITE).get_height() > avail and size > 12:
            size = int(size * 0.94)
        draw.blit_tight(s, title, "display", size, theme.WHITE, (h.left, kr.bottom + int(14 * u)))

        ans = game.review_answer
        if ans is None:
            text, bg, fg = "AGUARDANDO REVISÃO HUMANA", theme.ORANGE, theme.BLACK
        elif ans:
            text, bg, fg = "CONFERIDO POR UM HUMANO", theme.MINT, theme.BLACK
        else:
            text, bg, fg = "CORRIGIDO POR UM HUMANO", theme.YELLOW, theme.BLACK
        pr = draw.pill_label(s, "    " + text, int(20 * u), fg, bg, (h.right, h.top + int(4 * u)), "topright")
        dot = (pr.left + int(26 * u), pr.centery)
        if ans is not None or int(now * 2) % 2 == 0:
            pygame.draw.circle(s, fg, dot, int(7 * u))
        done = sum(t.done for t in rep.targets)
        info = f"Partida de {_num(rep.duration)} s  ·  {done} de {len(rep.targets)} caretas reconhecidas"
        draw.blit_text(s, info, "ui_medium", int(24 * u), theme.GRAY, (h.right, h.bottom - int(34 * u)), "bottomright")

    # ------------------------------------------------------------------ fotos
    def _photo(self, game: Game, key: str, side: int) -> pygame.Surface | None:
        ck = ("photo", key, side)
        if ck in self._cache:
            return self._cache[ck]
        img = game.snapshots.get(key)
        surf = None
        if img is not None:
            rgb = cv2.cvtColor(cv2.resize(img, (side, side), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
            surf = pygame.image.frombuffer(rgb.tobytes(), (side, side), "RGB").convert()
        self._cache[ck] = surf
        return surf

    def _card(self, game: Game, rep: MatchReport, key: str, w: int, h: int) -> pygame.Surface:
        ck = ("card", key, w, h)
        if ck in self._cache:
            return self._cache[ck]
        u = self.r.L.u
        meta = theme.EMOTIONS[key]
        res = rep.target(key)
        done = res is not None and res.done
        card = pygame.Surface((w, h), pygame.SRCALPHA)
        rect = card.get_rect()
        radius = int(26 * u)
        pad = int(16 * u)
        name_size = int(min(54 * u, h * 0.13))
        stat_size = max(12, int(min(19 * u, h * 0.05)))
        cap_h = name_size + stat_size + int(26 * u)
        side = int(min(w - 2 * pad, h - cap_h - 2 * pad))
        photo_r = pygame.Rect(0, 0, side, side)
        photo_r.midtop = (rect.centerx, pad)
        if done:
            draw.block(card, rect, meta["color"], radius)
            ink = meta["ink"]
            photo = self._photo(game, key, side)
            if photo is not None:
                card.blit(photo, photo_r)
            else:
                pygame.draw.rect(card, theme.CANVAS, photo_r)
                draw_emoji(card, key, photo_r.center, int(side * 0.3), 1.0)
            draw.corner_caps(card, photo_r, int(18 * u), meta["color"])
            draw_emoji(card, key, (photo_r.right - side * 0.13, photo_r.bottom - side * 0.13), int(side * 0.13), 1.0)
            cr = int(20 * u)
            cc = (photo_r.right - cr - int(8 * u), photo_r.top + cr + int(8 * u))
            pygame.draw.circle(card, theme.WHITE, cc, cr + max(2, int(3 * u)))
            pygame.draw.circle(card, theme.BLACK, cc, cr)
            w3 = max(3, cr // 4)
            pygame.draw.lines(card, theme.WHITE, False, [(cc[0] - cr * 0.45, cc[1]), (cc[0] - cr * 0.1, cc[1] + cr * 0.38),
                                                         (cc[0] + cr * 0.5, cc[1] - cr * 0.4)], w3)
            stat = f"FORÇA {_pct(res.peak)}  •  {_num(res.seconds)} s"
        else:
            draw.block(card, rect, theme.CANVAS, radius, meta["color"], max(2, int(3 * u)))
            ink = theme.WHITE
            pygame.draw.rect(card, theme.SLATE, photo_r, border_radius=int(18 * u))
            draw_emoji(card, key, photo_r.center, int(side * 0.26), 0.35)
            draw.pill_label(card, "A IA NÃO VIU", max(12, int(18 * u)), theme.BLACK, meta["color"],
                            (photo_r.centerx, photo_r.bottom - int(14 * u)), "midbottom")
            stat = f"CHEGOU A {_pct(res.peak if res else 0.0)}"
        ny = photo_r.bottom + int(10 * u)
        nr = draw.blit_tight(card, meta["name"], "display", draw.fit_size(meta["name"], "display", name_size, w - 2 * pad),
                             ink, (rect.centerx, ny), "midtop")
        draw.label(card, stat, stat_size, ink, (rect.centerx, nr.bottom + int(10 * u)), "midtop")
        self._cache[ck] = card
        return card

    def _draw_photos(self, s, area, now, el, game: Game, rep: MatchReport) -> None:
        u = self.r.L.u
        n = len(rep.targets)
        gap = int(20 * u)
        w = (area.w - gap * (n - 1)) // n
        for i, t in enumerate(rep.targets):
            card = self._card(game, rep, t.key, w, area.h)
            cx = area.left + i * (w + gap) + w // 2
            k = draw.ease_out_back((el - 0.1 - i * 0.12) / 0.45)
            if k <= 0:
                continue
            y = area.centery + bob(now, i * 1.4, 3 * u)
            img = card if k >= 0.999 else pygame.transform.rotozoom(card, (1 - k) * 12, max(0.05, k))
            s.blit(img, img.get_rect(center=(cx, int(y))))

    # ------------------------------------------------------------------ gráfico
    def _plot_rect(self, area: pygame.Rect) -> pygame.Rect:
        u = self.r.L.u
        return pygame.Rect(area.left + int(78 * u), area.top + int(62 * u),
                           area.w - int(78 * u) - int(28 * u), area.h - int(62 * u) - int(46 * u))

    def _xmap(self, rep: MatchReport, plot: pygame.Rect):
        t0 = min(0.0, float(rep.times.min())) if len(rep.times) else 0.0
        t1 = max(rep.duration, 1.0) * 1.03 + 0.4   # folga: o último marcador não fica na borda
        return t0, t1, (lambda t: plot.left + (t - t0) / (t1 - t0) * plot.w)

    def _chart_lines(self, rep: MatchReport, plot: pygame.Rect) -> pygame.Surface:
        ck = ("chart", plot.size)
        if ck in self._cache:
            return self._cache[ck]
        u = self.r.L.u
        ss = 2   # supersampling: linhas grossas com borda suave
        big = pygame.Surface((plot.w * ss, plot.h * ss), pygame.SRCALPHA)
        t0, t1, _ = self._xmap(rep, plot)
        if len(rep.times) >= 2:
            xs = (rep.times - t0) / (t1 - t0) * plot.w * ss

            def points(key):
                ys = (1.0 - rep.probs[:, CLASS_INDEX[key]]) * (plot.h * ss - 1)
                pts = list(zip(xs.tolist(), ys.tolist()))
                step = max(1, len(pts) // (plot.w // 2 or 1))
                return pts[::step] + [pts[-1]]

            # a emoção "extra" que a IA também viu: tracejada e por baixo das 3 do jogo
            if rep.bonus is not None:
                draw.dashed_lines(big, LINE_COLORS[rep.bonus[0]], points(rep.bonus[0]),
                                  max(2, int(4 * u * ss)), 14 * u * ss, 9 * u * ss)
            for key in rep_keys(rep):
                pts = points(key)
                wid = max(3, int(5 * u * ss))
                col = LINE_COLORS.get(key, theme.WHITE)
                pygame.draw.lines(big, col, False, pts, wid)
                for p in pts[:: max(1, len(pts) // 60)] + [pts[-1]]:
                    pygame.draw.circle(big, col, p, wid // 2)
        surf = pygame.transform.smoothscale(big, plot.size)
        self._cache[ck] = surf
        return surf

    def _draw_chart(self, s, area, now, el, game: Game, rep: MatchReport) -> None:
        u = self.r.L.u
        draw.block(s, area, theme.CANVAS, int(26 * u), theme.SLATE, max(2, int(3 * u)))
        draw.label(s, "LINHA DO TEMPO DA IA", int(19 * u), theme.MINT, (area.left + int(24 * u), area.top + int(20 * u)))
        # legenda (a emoção extra vem por último, com traço tracejado)
        x = area.right - int(24 * u)
        if rep.bonus is not None:
            bk = rep.bonus[0]
            lr = draw.label(s, f"{LABELS_PT[bk]} (EXTRA)", int(16 * u), theme.WHITE, (x, area.top + int(22 * u)), "topright")
            y = lr.centery
            for i in range(2):
                x0 = lr.left - int(40 * u) + i * int(16 * u)
                pygame.draw.line(s, LINE_COLORS[bk], (x0, y), (x0 + int(10 * u), y), max(3, int(4 * u)))
            x = lr.left - int(54 * u)
        for key in reversed(rep_keys(rep)):
            lr = draw.label(s, theme.EMOTIONS[key]["name"], int(16 * u), theme.WHITE, (x, area.top + int(22 * u)), "topright")
            pygame.draw.circle(s, LINE_COLORS[key], (lr.left - int(14 * u), lr.centery), int(8 * u))
            x = lr.left - int(34 * u)

        plot = self._plot_rect(area)
        t0, t1, X = self._xmap(rep, plot)
        # zona da calibração ("medindo o neutro")
        if t0 < 0:
            zone = pygame.Rect(plot.left, plot.top, int(X(0) - plot.left), plot.h)
            pygame.draw.rect(s, theme.FRAME, zone)
            if zone.w > 60 * u:
                draw.label(s, "NEUTRO", int(14 * u), theme.GRAY, (zone.centerx, plot.top + int(8 * u)), "midtop")
        for frac, txt in ((1.0, "100%"), (0.5, "50%"), (0.0, "0%")):
            y = plot.bottom - frac * plot.h
            pygame.draw.line(s, theme.SLATE, (plot.left, y), (plot.right, y), max(1, int(2 * u)))
            draw.label(s, txt, int(14 * u), theme.GRAY, (plot.left - int(10 * u), y), "midright")
        step = 5 if t1 <= 40 else 10
        for tk in range(0, int(t1) + 1, step):
            draw.blit_text(s, f"{tk}s", "mono", int(15 * u), theme.GRAY, (X(tk), plot.bottom + int(8 * u)), "midtop")

        # linhas com revelação da esquerda para a direita (efeito "impressora")
        reveal = draw.ease_out_cubic((el - 0.35) / 1.4)
        if reveal > 0:
            lines = self._chart_lines(rep, plot)
            w = int(plot.w * reveal)
            s.blit(lines, plot.topleft, pygame.Rect(0, 0, w, plot.h))
            if reveal < 1.0:
                pygame.draw.line(s, theme.WHITE, (plot.left + w, plot.top), (plot.left + w, plot.bottom), max(2, int(3 * u)))

        # marcadores: a foto da careta no momento em que a IA reconheceu
        d = int(min(64 * u, plot.h * 0.42))
        taken: list[pygame.Rect] = []
        for t in rep.targets:
            if not t.done or t.at is None:
                continue
            x = X(t.at)
            if x > plot.left + plot.w * reveal:
                continue
            idx = int(np.argmin(np.abs(rep.times - t.at))) if len(rep.times) else 0
            p = float(rep.probs[idx, CLASS_INDEX[t.key]]) if len(rep.times) else 1.0
            y = plot.bottom - p * plot.h
            k = 1.0 if reveal >= 0.999 else draw.ease_out_back(min(1.0, (plot.left + plot.w * reveal - x) / (plot.w * 0.08)))
            col = theme.EMOTIONS[t.key]["color"]
            for yy in range(int(plot.top), int(plot.bottom), max(4, int(12 * u))):
                pygame.draw.line(s, theme.GRAY, (x, yy), (x, yy + max(2, int(5 * u))), max(1, int(2 * u)))
            cy = max(plot.top + d / 2, min(plot.bottom - d / 2, y))
            rad = max(4, int(d / 2 * k))
            thumb = self.r.thumb(game, t.key, rad * 2)
            taken.append(pygame.Rect(int(x - d / 2 - 6 * u), int(cy - d / 2 - 6 * u), int(d + 12 * u), int(d + 12 * u)))
            pygame.draw.circle(s, col, (int(x), int(cy)), rad + max(3, int(5 * u)))
            if thumb is not None:
                s.blit(thumb, thumb.get_rect(center=(int(x), int(cy))))
            else:
                draw_emoji(s, t.key, (x, cy), rad, 1.0)

        # pico da emoção extra que a IA também viu: ponto + etiqueta, sem cobrir as fotos
        if rep.bonus is not None and rep.bonus_at is not None:
            bk, bp = rep.bonus
            x = X(rep.bonus_at)
            if x <= plot.left + plot.w * reveal:
                k = 1.0 if reveal >= 0.999 else draw.ease_out_back(min(1.0, (plot.left + plot.w * reveal - x) / (plot.w * 0.08)))
                y = plot.bottom - bp * plot.h
                col = LINE_COLORS[bk]
                pygame.draw.circle(s, theme.WHITE, (int(x), int(y)), max(3, int(9 * u * k)))
                pygame.draw.circle(s, col, (int(x), int(y)), max(2, int(6 * u * k)))
                if k > 0.6:
                    text = f"{LABELS_PT[bk]} {_pct(bp)}"
                    size = max(11, int(15 * u))
                    gap = int(14 * u)
                    options = []
                    for anchor, pos in (("midbottom", (x, y - gap)), ("midtop", (x, y + gap)),
                                        ("midleft", (x + gap, y)), ("midright", (x - gap, y))):
                        r = draw.pill_rect(text, size, pos, anchor)
                        r.clamp_ip(plot)
                        options.append(r)
                    best = next((r for r in options if not any(r.colliderect(t) for t in taken)), options[0])
                    draw.pill_label(s, text, size, theme.BLACK, col, best.topleft, "topleft", border_color=theme.WHITE)

    # ------------------------------------------------------------------ o que a IA notou
    def _rows(self, rep: MatchReport):
        """(ícone, rótulo, valor, cor do ícone "8" ou None)."""
        rows = []
        if rep.strongest:
            t = rep.target(rep.strongest)
            rows.append((rep.strongest, "CARETA MAIS FORTE", f"{theme.EMOTIONS[t.key]['name']}  {_pct(t.peak)}", None))
        else:
            best = max(rep.targets, key=lambda t: t.peak)
            rows.append((best.key, "CHEGOU MAIS PERTO", f"{theme.EMOTIONS[best.key]['name']}  {_pct(best.peak)}", None))
        if rep.fastest:
            t = rep.target(rep.fastest)
            rows.append((rep.fastest, "MAIS RÁPIDA", f"{theme.EMOTIONS[t.key]['name']}  {_num(t.seconds)} s", None))
        else:
            rows.append(("clock", "TEMPO DE JOGO", f"{_num(rep.duration)} s", None))
        if rep.bonus is not None:
            bk, bp = rep.bonus
            rows.append(("eight", "A IA TAMBÉM VIU UM POUCO DE", f"{LABELS_PT[bk]}  {_pct(bp)}", LINE_COLORS[bk]))
        dk, frac = rep.dominant
        icon = dk if dk in theme.EMOTIONS or dk == "neutral" else "eight"
        rows.append((icon, "NA MAIOR PARTE DO TEMPO", f"{LABELS_PT[dk]}  {_pct(frac)} DO TEMPO", LINE_COLORS.get(dk)))
        return rows

    def _icon(self, s, kind: str, center, r: int, color=None) -> None:
        u = self.r.L.u
        if kind in theme.EMOTIONS or kind == "neutral":
            draw_emoji(s, kind, center, r, 1.0)
            return
        if kind == "clock":
            lw = max(2, int(4 * u))
            pygame.draw.circle(s, theme.WHITE, center, r)
            pygame.draw.circle(s, theme.BLACK, center, r, lw)
            pygame.draw.line(s, theme.BLACK, center, (center[0], center[1] - r * 0.6), lw)
            pygame.draw.line(s, theme.BLACK, center, (center[0] + r * 0.45, center[1]), lw)
            return
        # "8": a IA conhece 8 emoções, não só as 3 do jogo (na cor da linha extra do gráfico)
        pygame.draw.circle(s, color or theme.MINT, center, r)
        draw.blit_tight(s, "8", "display", int(r * 1.2), theme.BLACK, center, "center")

    def _draw_findings(self, s, area, el, rep: MatchReport) -> None:
        u = self.r.L.u
        draw.block(s, area, theme.CANVAS, int(26 * u), theme.SLATE, max(2, int(3 * u)))
        tr = draw.label(s, "O QUE A IA NOTOU", int(19 * u), theme.MINT, (area.left + int(24 * u), area.top + int(20 * u)))
        rows = self._rows(rep)
        top = tr.bottom + int(12 * u)
        avail_h = area.bottom - int(14 * u) - top
        if avail_h / len(rows) < 64 * u:   # tela pequena: fica com as 3 mais importantes
            rows = rows[:3]
        rh = avail_h / len(rows)
        prev = s.get_clip()
        s.set_clip(area)
        for i, (icon, lab, val, icon_color) in enumerate(rows):
            k = draw.ease_out_cubic((el - 0.5 - i * 0.15) / 0.4)
            if k <= 0:
                continue
            y0 = top + i * rh
            dx = int((1 - k) * area.w * 0.4)
            if i:
                pygame.draw.line(s, theme.SLATE, (area.left + int(24 * u), y0), (area.right - int(24 * u), y0), max(1, int(2 * u)))
            ir = int(min(rh * 0.32, 34 * u))
            ic = (area.left + int(24 * u) + ir + dx, int(y0 + rh / 2))
            self._icon(s, icon, ic, ir, icon_color)
            tx = ic[0] + ir + int(20 * u)
            avail = area.right - int(24 * u) - tx
            ls = max(10, int(min(17 * u, rh * 0.17)))
            lab_s = draw.text_surface(lab.upper(), "mono", ls, theme.GRAY, ls * 0.12)
            vs = draw.fit_size(val, "display", int(min(50 * u, rh * 0.44)), avail)
            val_s = draw.tight_surface(val, "display", vs, theme.WHITE)
            gap = int(6 * u)
            y = y0 + (rh - lab_s.get_height() - gap - val_s.get_height()) / 2
            s.blit(lab_s, (tx, int(y)))
            s.blit(val_s, (tx, int(y + lab_s.get_height() + gap)))
        s.set_clip(prev)

    # ------------------------------------------------------------------ revisão humana
    def _keycap(self, s, text: str, pos, size: int, fg, bg, anchor="center") -> pygame.Rect:
        surf = draw.text_surface(text, "mono", size, fg, size * 0.08)
        r = pygame.Rect(0, 0, max(surf.get_width() + int(size * 0.9), int(size * 1.7)), int(size * 1.6))
        setattr(r, anchor, (int(pos[0]), int(pos[1])))
        draw.block(s, r, bg, int(size * 0.35), fg, max(2, size // 9))
        s.blit(surf, surf.get_rect(center=r.center))
        return r

    def _draw_review(self, s, area, now, el, game: Game) -> None:
        u = self.r.L.u
        ans = game.review_answer
        k = draw.ease_out_back((el - 1.0) / 0.45)
        border = theme.ORANGE if ans is None else (theme.MINT if ans else theme.YELLOW)
        pulse = ans is None and int(now * 2) % 2 == 0 and el > 1.5
        draw.block(s, area, theme.CANVAS, int(26 * u), theme.WHITE if pulse else border, max(3, int(4 * u)))
        if k <= 0:
            return
        pad = int(24 * u)
        tr = draw.label(s, "REVISÃO HUMANA", int(19 * u), border, (area.left + pad, area.top + int(20 * u)))
        q = "A IA ACERTOU?"
        qs = draw.fit_size(q, "display", int(min(76 * u, area.h * 0.22)), area.w - 2 * pad)
        qr = draw.blit_tight(s, q, "display", qs, theme.WHITE, (area.left + pad, tr.bottom + int(12 * u)))
        sub = "Um humano sempre confere o relatório da IA." if ans is None else (
            "Relatório confirmado por uma pessoa." if ans else "Uma pessoa corrigiu a IA: é para isso que a revisão existe!")
        ss = draw.fit_size(sub, "ui_medium", int(24 * u), area.w - 2 * pad)
        sr = draw.blit_text(s, sub, "ui_medium", ss, theme.GRAY, (area.left + pad, qr.bottom + int(10 * u)))

        by = sr.bottom + int(16 * u)
        bh = min(int(area.bottom - pad - by), int(120 * u))
        if bh < 30 * u:
            by = area.bottom - pad - int(30 * u)
            bh = int(30 * u)
        gap = int(18 * u)
        bw = (area.w - 2 * pad - gap) // 2
        for i, (key, word, cap, col) in enumerate((("yes", "SIM", "S", theme.MINT), ("no", "NÃO", "N", theme.ORANGE))):
            b = pygame.Rect(area.left + pad + i * (bw + gap), by, bw, bh)
            chosen = ans is not None and ans == (key == "yes")
            faded = ans is not None and not chosen
            bg = theme.SLATE if faded else col
            ink = theme.GRAY if faded else theme.BLACK
            if k < 0.999:
                b = b.inflate(-int(b.w * (1 - k)), -int(b.h * (1 - k)))
            draw.block(s, b, bg, int(22 * u), theme.WHITE if chosen else None, max(3, int(5 * u)))
            fs = draw.fit_size(word, "display", int(bh * 0.55), int(b.w * 0.5))
            wr = draw.blit_tight(s, word, "display", fs, ink, (b.centerx - int(b.w * 0.08), b.centery), "center")
            self._keycap(s, cap, (wr.right + int(22 * u), b.centery), max(12, int(bh * 0.2)), ink, bg, "midleft")
            if chosen:
                cc = (b.right - int(26 * u), b.top + int(26 * u))
                cr = int(15 * u)
                pygame.draw.circle(s, theme.BLACK, cc, cr)
                pygame.draw.lines(s, theme.WHITE, False, [(cc[0] - cr * 0.45, cc[1]), (cc[0] - cr * 0.1, cc[1] + cr * 0.38),
                                                          (cc[0] + cr * 0.5, cc[1] - cr * 0.4)], max(2, cr // 4))
            self.buttons[key] = b

    # ------------------------------------------------------------------ rodapé + botão
    def _draw_footer(self, s, f, now, el, game: Game) -> None:
        u = self.r.L.u
        msg = "A IA faz o relatório. Quem decide é sempre uma pessoa."
        bw = int(min(f.w * 0.44, 640 * u))
        btn = pygame.Rect(f.right - bw, f.top, bw, f.h)
        ms = draw.fit_size(msg, "ui", int(32 * u), f.w - bw - int(40 * u))
        draw.blit_text(s, msg, "ui", ms, theme.WHITE, (f.left, f.centery), "midleft")

        ready = game.review_answer is not None
        col = theme.MINT if ready else theme.WHITE
        grow = 1.0 + (0.025 * math.sin(now * 5.0) if ready else 0.0)
        b = btn.inflate(int(btn.w * (grow - 1)), int(btn.h * (grow - 1)))
        draw.block(s, b, col, b.h // 2)
        cap = self._keycap(s, "ENTER", (b.left + int(26 * u), b.centery), max(12, int(20 * u)), theme.BLACK, col, "midleft")
        # seta ▶
        ax = b.right - int(44 * u)
        ah = int(b.h * 0.22)
        pygame.draw.polygon(s, theme.BLACK, [(ax - ah, b.centery - ah), (ax + ah * 0.6, b.centery), (ax - ah, b.centery + ah)])
        txt = "PRÓXIMO JOGADOR"
        avail = (ax - ah - int(20 * u)) - (cap.right + int(20 * u))
        ts = draw.fit_size(txt, "display", int(b.h * 0.5), avail)
        draw.blit_tight(s, txt, "display", ts, theme.BLACK, ((cap.right + ax - ah) // 2, b.centery), "center")
        self.buttons["next"] = b
        to = self.cfg.game.report_timeout
        if to > 0:
            left = max(0, int(math.ceil(to - el)))
            draw.label(s, f"OU AUTOMÁTICO EM {left}s", int(14 * u), theme.GRAY, (b.centerx, b.bottom + int(6 * u)), "midtop")

    # ------------------------------------------------------------------ carimbo
    def _stamp(self, ok: bool) -> pygame.Surface:
        ck = ("stamp", ok)
        if ck in self._cache:
            return self._cache[ck]
        u = self.r.L.u
        col = theme.MINT if ok else theme.YELLOW
        word = "CONFERIDO" if ok else "CORRIGIDO"
        big = draw.text_surface(word, "display", int(96 * u), col)
        small = draw.text_surface("POR UM HUMANO", "mono", int(24 * u), col, 24 * u * 0.2)
        pad = int(28 * u)
        w = max(big.get_width(), small.get_width()) + 2 * pad
        h = big.get_height() + small.get_height() + pad
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        bg = pygame.Rect(0, 0, w, h)
        pygame.draw.rect(surf, (*theme.CANVAS, 235), bg, border_radius=int(24 * u))
        pygame.draw.rect(surf, col, bg, width=max(4, int(8 * u)), border_radius=int(24 * u))
        surf.blit(big, big.get_rect(midtop=(w // 2, int(pad * 0.4))))
        surf.blit(small, small.get_rect(midbottom=(w // 2, h - int(pad * 0.6))))
        self._cache[ck] = surf
        return surf

    def _draw_stamp(self, s, area, now, ok: bool) -> None:
        age = now - self._stamp_t
        k = draw.ease_out_cubic(age / 0.22)
        stamp = self._stamp(ok)
        final = min(0.9, area.h * 1.05 / stamp.get_height(), area.w * 0.5 / stamp.get_width())
        scale = final * (2.2 - 1.2 * k)
        img = pygame.transform.rotozoom(stamp, -9, scale)
        center = (area.right - area.w * 0.27, area.centery + area.h * 0.04)
        if k >= 1.0 and age < 0.35:   # "tremidinha" do carimbo batendo
            center = (center[0] + math.sin(age * 90) * 4, center[1])
        s.blit(img, img.get_rect(center=(int(center[0]), int(center[1]))))


def rep_keys(rep: MatchReport) -> list[str]:
    return [t.key for t in rep.targets]
