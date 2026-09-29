"""Máquina de estados do jogo: espera -> calibração -> 3 emoções -> vitória -> relatório."""

from __future__ import annotations

import logging
from enum import Enum

import cv2
import numpy as np

from .config import Config
from .emotion import EmotionReading
from .pipeline import FrameResult
from .report import MatchHistory, MatchReport, build_report
from .scoring import Baseline, Calibrator, Evaluation, HoldTimer, Smoother, evaluate

log = logging.getLogger(__name__)


class Phase(str, Enum):
    IDLE = "idle"                # esperando alguém chegar perto
    CALIBRATING = "calibrating"  # medindo o rosto neutro da pessoa
    PLAYING = "playing"          # fazendo a careta atual
    BETWEEN = "between"          # comemoração curta entre uma careta e outra
    VICTORY = "victory"
    TIMEOUT = "timeout"
    REPORT = "report"            # relatório da IA + revisão humana; espera o botão "próximo"


ACTIVE = (Phase.CALIBRATING, Phase.PLAYING, Phase.BETWEEN)
FINISHED = (Phase.VICTORY, Phase.TIMEOUT, Phase.REPORT)


class Game:
    def __init__(self, cfg: Config, now: float = 0.0):
        self.cfg = cfg
        self.order = list(cfg.game.order)
        self.smoother = Smoother(cfg.emotion.smoothing)
        self.calibrator = Calibrator(cfg.calibration)
        self.hold = HoldTimer(cfg.rules.hold_seconds, cfg.rules.hold_frames)
        self.victories = 0            # só em memória, para a tela inicial
        self.matches = 0              # partidas que chegaram ao fim (número do relatório)
        self.reviews_ok = 0           # relatórios que um humano confirmou
        self.reviews_fixed = 0        # relatórios que um humano corrigiu
        self.history = MatchHistory()
        self.report: MatchReport | None = None
        self.release_request: float | None = None
        self.events: dict[str, tuple[float, dict]] = {}
        self.last_result: FrameResult | None = None
        self.snapshots: dict[str, np.ndarray] = {}
        self._clear_match()
        self.phase = Phase.IDLE
        self.phase_t0 = now
        self.cooldown_until = now

    # ------------------------------------------------------------------ estado
    def _clear_match(self) -> None:
        self.target_index = 0
        self.completed: list[str] = []
        for img in self.snapshots.values():
            img.fill(0)  # sobrescreve os pixels antes de soltar a referência
        self.snapshots = {}
        self.history.clear()
        if self.report is not None:
            self.report.wipe()
        self.report = None
        self.review_answer: bool | None = None
        self.completions: dict[str, tuple[float, float]] = {}
        self.target_t0 = 0.0
        self.smoother.reset()
        self.calibrator.reset()
        self.hold.reset()
        self.baseline: Baseline | None = None
        self.smoothed: EmotionReading | None = None
        self.evaluation: Evaluation | None = None
        self.hold_progress = 0.0
        self.calib_attempt = 0
        self.calib_retry_reason = ""
        self.match_t0: float | None = None

    @property
    def target(self) -> str | None:
        if self.phase in (Phase.PLAYING, Phase.BETWEEN) and self.target_index < len(self.order):
            return self.order[self.target_index]
        return None

    def phase_elapsed(self, now: float) -> float:
        return now - self.phase_t0

    def time_left(self, now: float) -> float | None:
        if self.match_t0 is None or self.cfg.game.match_timeout <= 0:
            return None
        return max(0.0, self.cfg.game.match_timeout - (now - self.match_t0))

    def calibration_progress(self, now: float) -> float:
        if self.phase != Phase.CALIBRATING:
            return 0.0
        return min(1.0, self.phase_elapsed(now) / max(self.cfg.calibration.seconds, 1e-6))

    def event_age(self, name: str, now: float) -> float | None:
        ev = self.events.get(name)
        return None if ev is None else now - ev[0]

    def _emit(self, name: str, now: float, **data) -> None:
        self.events[name] = (now, data)
        log.info("evento: %s %s", name, data if data else "")

    def _enter(self, phase: Phase, now: float) -> None:
        self.phase = phase
        self.phase_t0 = now

    # ------------------------------------------------------------------ comandos
    def reset(self, now: float, reason: str = "manual", cooldown: float | None = None) -> None:
        pause = 0.3 if cooldown is None else cooldown
        self._clear_match()
        self._enter(Phase.IDLE, now)
        self.cooldown_until = now + pause
        self.release_request = now + pause
        self._emit("reset", now, reason=reason)

    def advance(self, now: float) -> None:
        """Botão "próximo" do operador: pula a comemoração, ou chama o próximo jogador."""
        if self.phase in (Phase.VICTORY, Phase.TIMEOUT) and self.cfg.ui.report:
            self._enter_report(now)
        elif self.phase in FINISHED:
            self.reset(now, "next_player", cooldown=self.cfg.game.cooldown_seconds)
        else:
            self.reset(now, "manual")

    def review(self, ok: bool, now: float) -> bool:
        """Revisão humana do relatório: a IA acertou? Pode trocar a resposta."""
        if self.phase != Phase.REPORT:
            return False
        if self.review_answer is not None:
            if self.review_answer:
                self.reviews_ok -= 1
            else:
                self.reviews_fixed -= 1
        self.review_answer = ok
        if ok:
            self.reviews_ok += 1
        else:
            self.reviews_fixed += 1
        self._emit("review", now, ok=ok)
        return True

    def take_release_request(self) -> float | None:
        req, self.release_request = self.release_request, None
        return req

    # ------------------------------------------------------------------ laço
    def update(self, result: FrameResult | None, now: float) -> None:
        if result is not None and result is not self.last_result:
            self.last_result = result
            self._on_result(result, now)
        self._tick(now)

    def _on_result(self, r: FrameResult, now: float) -> None:
        if self.phase in ACTIVE and not r.locked:
            # O jogador sumiu por mais de detector.lost_seconds: partida reseta sozinha.
            self._emit("lost", now)
            self.reset(now, "lost", cooldown=0.0)
            return

        if self.phase == Phase.IDLE:
            if r.locked and r.player is not None and now >= self.cooldown_until:
                self._clear_match()
                self._start_calibration(now)
                self._emit("locked", now)
            return

        if r.reading is not None:
            self.smoothed = self.smoother.update(r.reading)
            if self.phase in ACTIVE:
                self.history.add(r.timestamp, self.smoothed, playing=self.phase != Phase.CALIBRATING)

        if self.phase == Phase.CALIBRATING:
            if r.reading is not None:
                self.calibrator.add(r.reading)
        elif self.phase == Phase.PLAYING:
            target = self.order[self.target_index]
            if r.reading is None:
                # Rosto não apareceu neste quadro: a contagem "seguida" recomeça.
                self.hold.reset()
                self.hold_progress = 0.0
                return
            rule = self.cfg.rules.for_emotion(target)
            self.evaluation = evaluate(target, rule, self.smoothed, self.baseline)
            self.hold_progress = self.hold.update(self.evaluation.passed, r.timestamp)
            if self.hold.completed(r.timestamp):
                self._complete_target(r, now)

    def _tick(self, now: float) -> None:
        g = self.cfg.game
        el = self.phase_elapsed(now)
        if self.phase == Phase.CALIBRATING:
            c = self.cfg.calibration
            if el >= c.seconds and self.calibrator.frames >= c.min_frames:
                self._finish_calibration(now)
            elif el >= c.seconds * 3:
                self._retry_calibration(now, "few_frames")
        elif self.phase == Phase.PLAYING:
            left = self.time_left(now)
            if left is not None and left <= 0:
                self._finish_match(now, won=False)
                self._enter(Phase.TIMEOUT, now)
                self._emit("timeout", now)
        elif self.phase == Phase.BETWEEN:
            if el >= g.between_seconds:
                self.target_index += 1
                self.hold.reset()
                self.hold_progress = 0.0
                self.evaluation = None
                self.target_t0 = now
                self._enter(Phase.PLAYING, now)
        elif self.phase in (Phase.VICTORY, Phase.TIMEOUT):
            if el >= (g.victory_seconds if self.phase == Phase.VICTORY else g.timeout_seconds):
                if self.cfg.ui.report:
                    self._enter_report(now)
                else:
                    self.reset(now, f"{self.phase.value}_done", cooldown=g.cooldown_seconds)
        elif self.phase == Phase.REPORT:
            # Rede de segurança: se ninguém apertar o botão, volta sozinho (0 = só pelo botão).
            if g.report_timeout > 0 and el >= g.report_timeout:
                self.reset(now, "report_timeout", cooldown=g.cooldown_seconds)

    # ------------------------------------------------------------------ etapas
    def _start_calibration(self, now: float) -> None:
        self.calibrator.reset()
        self.smoother.reset()
        self.history.clear()
        self._enter(Phase.CALIBRATING, now)

    def _retry_calibration(self, now: float, reason: str) -> None:
        self.calib_attempt += 1
        if self.calib_attempt >= self.cfg.calibration.max_attempts:
            log.info("calibração: usando neutro padrão após %d tentativas", self.calib_attempt)
            self._start_playing(Baseline.default(), now)
            return
        self.calib_retry_reason = reason
        self._emit("calib_retry", now, reason=reason)
        self._start_calibration(now)

    def _finish_calibration(self, now: float) -> None:
        res = self.calibrator.finish()
        if res.ok:
            self._start_playing(res.baseline, now)
        else:
            self._retry_calibration(now, res.reason)

    def _start_playing(self, baseline: Baseline, now: float) -> None:
        self.baseline = baseline
        self.calib_retry_reason = ""
        self.target_index = 0
        self.hold.reset()
        self.hold_progress = 0.0
        self.match_t0 = now
        self.target_t0 = now
        self._enter(Phase.PLAYING, now)
        self._emit("calib_done", now, default=baseline.is_default)

    def _complete_target(self, r: FrameResult, now: float) -> None:
        target = self.order[self.target_index]
        self.completed.append(target)
        self.completions[target] = (now - self.target_t0, now)
        self.hold_progress = 1.0
        if self.cfg.ui.victory_snapshots and r.player is not None:
            self.snapshots[target] = portrait_crop(r.frame, r.player)
        self._emit("target_done", now, target=target)
        if len(self.completed) >= len(self.order):
            self.victories += 1
            self._finish_match(now, won=True)
            self._enter(Phase.VICTORY, now)
            self._emit("victory", now)
        else:
            self._enter(Phase.BETWEEN, now)

    def _finish_match(self, now: float, won: bool) -> None:
        self.matches += 1
        start = self.match_t0 if self.match_t0 is not None else now
        self.report = build_report(self.matches, won, self.history, start, now, self.order, self.completions)

    def _enter_report(self, now: float) -> None:
        self.review_answer = None
        self._enter(Phase.REPORT, now)
        self._emit("report", now)


def portrait_crop(frame: np.ndarray, face, size: int = 360) -> np.ndarray:
    """Recorte quadrado "de retrato" em volta do rosto, só em memória (cópia pequena)."""
    h, w = frame.shape[:2]
    side = int(min(max(face.w, face.h) * 2.0, h, w))
    cx, cy = face.cx, face.cy + face.h * 0.08
    x0 = int(np.clip(cx - side / 2, 0, w - side))
    y0 = int(np.clip(cy - side / 2, 0, h - side))
    crop = frame[y0:y0 + side, x0:x0 + side]
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
