"""Captura da câmera em uma thread própria, com reconexão automática.

Mantém só o quadro mais recente em memória (nada é gravado em disco).
Se a câmera cair (cabo, usbipd, driver), fecha e tenta abrir de novo a cada
`reconnect_interval` segundos, sem travar o resto do jogo.

No Windows (DirectShow), a câmera é escolhida pelo VID:PID de `camera.usb_hardware_id`
a cada (re)conexão, porque os índices mudam quando uma câmera é tirada e recolocada.
"""

from __future__ import annotations

import logging
import platform
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from .config import CameraConfig
from .win_camera import allowed_devices, list_devices, parse_hardware_ids

log = logging.getLogger(__name__)


class Camera:
    def __init__(self, cfg: CameraConfig, video_path: str | None = None):
        self.cfg = cfg
        self.index = cfg.index
        self.video_path = video_path
        # Windows: só câmeras da lista, pelo VID:PID (vazia = usa o índice fixo)
        on_windows = platform.system() == "Windows" and not video_path
        self._hwids = parse_hardware_ids(cfg.usb_hardware_id) if on_windows else []
        self._choice = 0             # qual câmera da lista (tecla C avança)
        self.device_name = ""
        self._open_error = ""
        self._cond = threading.Condition()
        self._frame: np.ndarray | None = None
        self._frame_id = 0
        self._frame_ts = 0.0
        self._running = False
        self._thread: threading.Thread | None = None
        self._switch_to: int | None = None
        self.status = "connecting"   # connecting | ok | error
        self.message = ""
        self.resolution = (0, 0)
        self.fps = 0.0

    @property
    def source_label(self) -> str:
        if self.video_path:
            return Path(self.video_path).name
        return self.device_name or f"câmera {self.index}"

    # ------------------------------------------------------------------ API
    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="camera", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        with self._cond:
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout=3)

    def switch(self, index: int) -> None:
        self._switch_to = index

    def next_camera(self) -> None:
        """Tecla C: próxima câmera (no Windows, só entre as da lista usb_hardware_id)."""
        self.switch(self._choice + 1 if self._hwids else (self.index + 1) % 4)

    def healthy(self) -> bool:
        """True se chegou quadro recentemente (independe da thread estar travada em read())."""
        return self._frame_id > 0 and self.last_frame_age() < self.cfg.frame_timeout

    def last_frame_age(self) -> float:
        return time.monotonic() - self._frame_ts if self._frame_id > 0 else float("inf")

    def peek(self) -> tuple[np.ndarray, int] | None:
        """Quadro mais novo, sem esperar (a tela mostra este, sem aguardar a IA)."""
        with self._cond:
            if self._frame is None:
                return None
            return self._frame, self._frame_id

    def wait_frame(self, last_id: int, timeout: float) -> tuple[np.ndarray, int, float] | None:
        with self._cond:
            if self._frame_id == last_id:
                self._cond.wait(timeout)
            if self._frame is None or self._frame_id == last_id:
                return None
            return self._frame, self._frame_id, self._frame_ts

    # ------------------------------------------------------------------ thread
    def _open(self) -> cv2.VideoCapture | None:
        if self.video_path:
            cap = cv2.VideoCapture(self.video_path)
            return cap if cap.isOpened() else None
        system = platform.system()
        if system == "Windows":
            return self._open_dshow()
        backend = cv2.CAP_V4L2 if system == "Linux" else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.index, backend)
        if not cap.isOpened():
            cap.release()
            return None
        if self.cfg.fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.cfg.fourcc[:4]))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        cap.set(cv2.CAP_PROP_FPS, self.cfg.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # menos atraso: não acumula quadros velhos
        return cap

    def _open_dshow(self) -> cv2.VideoCapture | None:
        self._open_error = ""
        if self._hwids:
            devices = allowed_devices(list_devices(), self._hwids)
            if not devices:
                self.device_name = ""
                self._open_error = f"nenhuma câmera da lista conectada ({', '.join(self._hwids)})"
                return None
            dev = devices[self._choice % len(devices)]
            self.index, self.device_name = dev.index, dev.name
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            return None
        # Ordem importa no DirectShow: o MJPG só vale se for pedido DEPOIS de largura/altura, e um
        # set(CAP_PROP_FPS) depois disso renegocia para YUY2 (C920 a 1280x720: YUY2 = 10 FPS,
        # MJPG = 30 FPS). Por isso o FPS não é pedido: o MJPG já vem no máximo da câmera.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        if self.cfg.fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.cfg.fourcc[:4]))
        if str(self.cfg.exposure).strip().lower() == "auto":
            # Religa sempre: a exposição manual fica gravada na câmera depois que o jogo fecha.
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        else:
            # Exposição manual (DSHOW: log2 dos segundos, -6 = 1/64 s): com pouca luz a automática
            # alonga a exposição e derruba o FPS.
            cap.set(cv2.CAP_PROP_EXPOSURE, float(self.cfg.exposure))
        return cap

    def _loop(self) -> None:
        cap = None
        last_ok = time.monotonic()
        video_period = 0.0
        next_video_t = 0.0
        fps_t, fps_n = time.monotonic(), 0
        while self._running:
            if self._switch_to is not None:
                if self._hwids:
                    self._choice = self._switch_to
                else:
                    self.index = self._switch_to
                self._switch_to = None
                if cap is not None:
                    cap.release()
                    cap = None
                log.info("trocando de câmera")

            if cap is None:
                self.status = "connecting"
                cap = self._open()
                if cap is None:
                    self.status = "error"
                    self.message = self._open_error or f"não abriu {self.source_label}"
                    log.warning("%s; nova tentativa em %.0fs", self.message, self.cfg.reconnect_interval)
                    self._sleep(self.cfg.reconnect_interval)
                    continue
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.resolution = (w, h)
                if self.video_path:
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    video_period = 1.0 / max(1.0, fps)
                fcc = int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode("ascii", "replace").strip("\x00")
                log.info("%s aberta em %dx%d%s", self.source_label, w, h, f" ({fcc})" if fcc.isprintable() and fcc else "")
                last_ok = time.monotonic()

            ok, frame = cap.read()
            now = time.monotonic()
            if not ok or frame is None:
                if self.video_path:  # vídeo de teste: volta ao início
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                if not ok or frame is None:
                    if now - last_ok > self.cfg.frame_timeout:
                        self.status = "error"
                        self.message = f"{self.source_label} parou de enviar imagem"
                        log.warning("%s; reconectando", self.message)
                        cap.release()
                        cap = None
                        self._sleep(self.cfg.reconnect_interval)
                    else:
                        time.sleep(0.01)
                    continue

            if self.video_path:
                # respeita o FPS do arquivo
                if next_video_t > now:
                    time.sleep(next_video_t - now)
                next_video_t = max(now, next_video_t) + video_period

            last_ok = time.monotonic()
            if self.cfg.mirror:
                frame = cv2.flip(frame, 1)
            with self._cond:
                self._frame = frame
                self._frame_id += 1
                self._frame_ts = last_ok
                self._cond.notify_all()
            self.status = "ok"
            self.message = ""
            fps_n += 1
            if last_ok - fps_t >= 1.0:
                self.fps = fps_n / (last_ok - fps_t)
                fps_t, fps_n = last_ok, 0

        if cap is not None:
            cap.release()

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end and self._switch_to is None:
            time.sleep(0.05)
