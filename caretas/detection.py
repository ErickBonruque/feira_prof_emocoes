"""Detecção de rostos (YuNet via OpenCV) e escolha/travamento de UM jogador."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .config import DetectorConfig


@dataclass
class Face:
    x: float
    y: float
    w: float
    h: float
    score: float
    # 5 pontos (olho, olho, nariz, canto da boca, canto da boca) em pixels do quadro
    landmarks: np.ndarray = field(default_factory=lambda: np.zeros((5, 2), np.float32))

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def box(self) -> tuple[int, int, int, int]:
        return int(self.x), int(self.y), int(self.w), int(self.h)


def iou(a: Face, b: Face) -> float:
    x1, y1 = max(a.x, b.x), max(a.y, b.y)
    x2, y2 = min(a.x + a.w, b.x + b.w), min(a.y + a.h, b.y + b.h)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


class FaceDetector:
    """YuNet (OpenCV Zoo, 2023mar): ~230 KB, rápido na CPU, devolve caixa + 5 pontos."""

    def __init__(self, model_path: str | Path, input_width: int = 640,
                 score_threshold: float = 0.75, nms_threshold: float = 0.3):
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"modelo de rosto não encontrado: {model_path} (rode o setup)")
        self.input_width = input_width
        self._net = cv2.FaceDetectorYN.create(
            str(model_path), "", (320, 320), score_threshold, nms_threshold, 50)
        self._size = (320, 320)

    def detect(self, frame_bgr: np.ndarray) -> list[Face]:
        h, w = frame_bgr.shape[:2]
        scale = min(1.0, self.input_width / w)
        small = frame_bgr if scale == 1.0 else cv2.resize(
            frame_bgr, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
        size = (small.shape[1], small.shape[0])
        if size != self._size:
            self._net.setInputSize(size)
            self._size = size
        _, raw = self._net.detect(small)
        if raw is None:
            return []
        faces = []
        inv = 1.0 / scale
        for row in raw:
            x, y, bw, bh = (float(v) * inv for v in row[:4])
            lms = row[4:14].reshape(5, 2).astype(np.float32) * inv
            faces.append(Face(x, y, bw, bh, float(row[14]), lms))
        return faces


@dataclass
class TrackState:
    player: Face | None          # rosto do jogador neste quadro (None se sumiu momentaneamente)
    locked: bool                 # existe um jogador travado
    candidate: Face | None       # candidato a jogador (antes de travar)
    lock_progress: float         # 0..1 estabilidade do candidato
    lost_for: float              # segundos desde a última vez que o jogador foi visto
    just_locked: bool = False
    just_lost: bool = False


class PlayerTracker:
    """Trava no rosto maior/mais central e ignora os outros até ele sumir."""

    def __init__(self, cfg: DetectorConfig):
        self.cfg = cfg
        self._player: Face | None = None
        self._last_seen = 0.0
        self._candidate: Face | None = None
        self._candidate_since = 0.0
        self._paused_until = 0.0

    @property
    def locked(self) -> bool:
        return self._player is not None

    def release(self, pause_until: float = 0.0) -> None:
        self._player = None
        self._candidate = None
        self._paused_until = pause_until

    def _eligible(self, faces: list[Face], frame_w: int, factor: float = 1.0) -> list[Face]:
        min_w = self.cfg.min_face_width * frame_w * factor
        return [f for f in faces if f.w >= min_w]

    def _rank(self, face: Face, frame_w: int, frame_h: int) -> float:
        size = face.w / frame_w
        dx = (face.cx - frame_w / 2) / (frame_w / 2)
        dy = (face.cy - frame_h / 2) / (frame_h / 2)
        center_dist = min(1.0, float(np.hypot(dx, dy)) / np.sqrt(2))
        return size * (1.0 - self.cfg.center_weight * center_dist)

    def _same_person(self, prev: Face, face: Face) -> bool:
        if iou(prev, face) > 0.3:
            return True
        dist = np.hypot(face.cx - prev.cx, face.cy - prev.cy) / max(prev.w, 1.0)
        ratio = face.w / max(prev.w, 1.0)
        return dist <= self.cfg.max_jump and 0.5 <= ratio <= 2.0

    def update(self, faces: list[Face], frame_w: int, frame_h: int, now: float) -> TrackState:
        if self._player is not None:
            # Segue o mesmo jogador: o rosto mais próximo da posição anterior.
            # Tolera o jogador se afastar um pouco (fator 0.6 no tamanho mínimo).
            options = [f for f in self._eligible(faces, frame_w, 0.6) if self._same_person(self._player, f)]
            if options:
                best = min(options, key=lambda f: np.hypot(f.cx - self._player.cx, f.cy - self._player.cy))
                self._player = best
                self._last_seen = now
                return TrackState(best, True, None, 1.0, 0.0)
            lost_for = now - self._last_seen
            if lost_for > self.cfg.lost_seconds:
                self.release()
                return TrackState(None, False, None, 0.0, lost_for, just_lost=True)
            return TrackState(None, True, None, 1.0, lost_for)

        if now < self._paused_until:
            return TrackState(None, False, None, 0.0, 0.0)

        eligible = self._eligible(faces, frame_w)
        if not eligible:
            self._candidate = None
            return TrackState(None, False, None, 0.0, 0.0)
        best = max(eligible, key=lambda f: self._rank(f, frame_w, frame_h))
        if self._candidate is None or not self._same_person(self._candidate, best):
            self._candidate = best
            self._candidate_since = now
        else:
            self._candidate = best
        held = now - self._candidate_since
        progress = 1.0 if self.cfg.lock_seconds <= 0 else min(1.0, held / self.cfg.lock_seconds)
        if progress >= 1.0:
            self._player = best
            self._last_seen = now
            self._candidate = None
            return TrackState(best, True, None, 1.0, 0.0, just_locked=True)
        return TrackState(None, False, best, progress, 0.0)
