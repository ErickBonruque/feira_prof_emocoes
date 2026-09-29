"""Thread de processamento: pega o quadro mais novo da câmera, detecta rostos,
trava o jogador e roda o modelo de emoção só no rosto dele."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from .capture import Camera
from .config import Config
from .detection import Face, FaceDetector, PlayerTracker
from .emotion import EmotionModel, EmotionReading, crop_face

log = logging.getLogger(__name__)


@dataclass
class FrameResult:
    frame_id: int
    timestamp: float                 # time.monotonic() da captura
    frame: np.ndarray                # BGR, já espelhado se configurado
    faces: list[Face]
    player: Face | None
    locked: bool
    candidate: Face | None
    lock_progress: float
    lost_for: float
    reading: EmotionReading | None   # leitura crua (sem suavização) do jogador
    timings: dict[str, float] = field(default_factory=dict)
    crop: np.ndarray | None = None   # recorte RGB 224x224 que a rede recebeu (modo explicação)


class Processor(threading.Thread):
    def __init__(self, cfg: Config, camera: Camera, detector: FaceDetector, emotion: EmotionModel):
        super().__init__(name="processor", daemon=True)
        self.cfg = cfg
        self.camera = camera
        self.detector = detector
        self.emotion = emotion
        self.tracker = PlayerTracker(cfg.detector)
        self._lock = threading.Lock()
        self._latest: FrameResult | None = None
        self._release_until: float | None = None
        self._running = True
        self.fps = 0.0

    def request_release(self, pause_until: float) -> None:
        """Pede para soltar o jogador atual (reset/fim de partida). Seguro entre threads."""
        with self._lock:
            self._release_until = pause_until

    def latest(self) -> FrameResult | None:
        with self._lock:
            return self._latest

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        last_id = -1
        last_t = time.monotonic()
        while self._running:
            got = self.camera.wait_frame(last_id, timeout=0.2)
            if got is None:
                continue
            frame, frame_id, ts = got
            last_id = frame_id
            try:
                result = self._process(frame, frame_id, ts)
            except Exception:  # noqa: BLE001 - nunca derrubar o jogo por um quadro ruim
                log.exception("erro processando quadro")
                continue
            now = time.monotonic()
            dt = now - last_t
            last_t = now
            if dt > 0:
                self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt) if self.fps else 1.0 / dt
            with self._lock:
                self._latest = result

    def _process(self, frame: np.ndarray, frame_id: int, ts: float) -> FrameResult:
        with self._lock:
            release, self._release_until = self._release_until, None
        if release is not None:
            self.tracker.release(release)

        t0 = time.perf_counter()
        faces = self.detector.detect(frame)
        t1 = time.perf_counter()
        h, w = frame.shape[:2]
        st = self.tracker.update(faces, w, h, time.monotonic())

        reading = None
        crop = None
        t2 = t1
        if st.player is not None:
            crop = crop_face(frame, st.player, self.cfg.emotion.crop_margin, self.cfg.emotion.align)
            reading = self.emotion.predict(crop)
            t2 = time.perf_counter()
        return FrameResult(
            frame_id=frame_id, timestamp=ts, frame=frame, faces=faces,
            player=st.player, locked=st.locked, candidate=st.candidate,
            lock_progress=st.lock_progress, lost_for=st.lost_for, reading=reading,
            timings={"detect_ms": (t1 - t0) * 1000, "emotion_ms": (t2 - t1) * 1000},
            crop=crop if st.player is not None else None,
        )
