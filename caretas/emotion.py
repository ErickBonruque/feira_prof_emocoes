"""Classificação de emoção com HSEmotion (enet_b0_8_va_mtl, ONNX, pré-treinado na AffectNet).

Uma única inferência devolve 8 probabilidades + valência + excitação (arousal).
Pré-processamento idêntico ao pacote oficial hsemotion-onnx: RGB 224x224,
normalização ImageNet. Nada aqui baixa arquivos: o modelo já está em models/.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .detection import Face

log = logging.getLogger(__name__)

# Ordem das saídas do modelo (idx_to_class do hsemotion para modelos de 8 classes)
CLASS_NAMES = ("anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise")
CLASS_INDEX = {name: i for i, name in enumerate(CLASS_NAMES)}
LABELS_PT = {
    "anger": "RAIVA", "contempt": "DESPREZO", "disgust": "NOJO", "fear": "MEDO",
    "happiness": "FELICIDADE", "neutral": "NEUTRO", "sadness": "TRISTEZA", "surprise": "SURPRESA",
}

INPUT_SIZE = 224
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


@dataclass
class EmotionReading:
    probs: np.ndarray   # (8,) somam 1
    valence: float      # ~[-1, 1] negativo = desagradável, positivo = agradável
    arousal: float      # ~[-1, 1] calmo -> agitado

    def prob(self, key: str) -> float:
        return float(self.probs[CLASS_INDEX[key]])

    def top(self) -> tuple[str, float]:
        i = int(np.argmax(self.probs))
        return CLASS_NAMES[i], float(self.probs[i])


def crop_face(frame_bgr: np.ndarray, face: Face, margin: float = 0.1,
              align: bool = True, size: int = INPUT_SIZE) -> np.ndarray:
    """Recorte quadrado do rosto, opcionalmente endireitado pelos olhos. Devolve RGB uint8."""
    side = max(face.w, face.h) * (1.0 + margin)
    angle = 0.0
    if align:
        e1, e2 = face.landmarks[0], face.landmarks[1]
        left, right = (e1, e2) if e1[0] <= e2[0] else (e2, e1)
        dx, dy = float(right[0] - left[0]), float(right[1] - left[1])
        if dx > 1e-3:
            angle = math.degrees(math.atan2(dy, dx))
            angle = max(-30.0, min(30.0, angle))  # evita giros absurdos por ponto errado
    m = cv2.getRotationMatrix2D((face.cx, face.cy), angle, size / side)
    m[0, 2] += size / 2 - face.cx
    m[1, 2] += size / 2 - face.cy
    crop = cv2.warpAffine(frame_bgr, m, (size, size), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)
    return cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)


def preprocess(face_rgb: np.ndarray) -> np.ndarray:
    if face_rgb.shape[:2] != (INPUT_SIZE, INPUT_SIZE):
        face_rgb = cv2.resize(face_rgb, (INPUT_SIZE, INPUT_SIZE))
    x = (face_rgb.astype(np.float32) / 255.0 - _MEAN) / _STD
    return np.ascontiguousarray(x.transpose(2, 0, 1)[np.newaxis])


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


class EmotionModel:
    def __init__(self, model_path: str | Path, device: str = "auto"):
        import onnxruntime as ort

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"modelo de emoção não encontrado: {model_path} (rode o setup)")
        try:
            ort.disable_telemetry_events()
        except Exception:  # noqa: BLE001 - só existe/importa no Windows
            pass
        ort.set_default_logger_severity(3)

        self._ort = ort
        self._path = str(model_path)
        self.last_ms = 0.0
        want_gpu = device in ("auto", "cuda") and "CUDAExecutionProvider" in ort.get_available_providers()
        if want_gpu:
            try:
                # Carrega CUDA/cuDNN dos pacotes nvidia-* instalados no .venv
                ort.preload_dlls()
            except Exception as exc:  # noqa: BLE001
                log.warning("não consegui pré-carregar as bibliotecas CUDA: %s", exc)
            # HEURISTIC: medido 3,6 ms/rosto na RTX 3050. ("DEFAULT" cai num modo lento do cuDNN 9: ~490 ms)
            self._create([("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC"}), "CPUExecutionProvider"])
            ms = self._warmup()
            if self.provider == "CUDAExecutionProvider" and ms > 40:
                log.warning("GPU lenta (%.0f ms/rosto): usando CPU", ms)
                want_gpu = False
        if not want_gpu:
            self._create(["CPUExecutionProvider"])
            self._warmup()
        if device == "cuda" and self.provider != "CUDAExecutionProvider":
            log.warning("emotion.device=cuda mas a GPU não está disponível; usando CPU")

    def _create(self, providers: list) -> None:
        opts = self._ort.SessionOptions()
        opts.log_severity_level = 3
        self.session = self._ort.InferenceSession(self._path, sess_options=opts, providers=providers)
        self.provider = self.session.get_providers()[0]
        self._input = self.session.get_inputs()[0].name

    @property
    def device_label(self) -> str:
        return "GPU (CUDA)" if self.provider == "CUDAExecutionProvider" else "CPU"

    def _warmup(self) -> float:
        """Roda algumas vezes (a 1ª inferência na GPU é lenta) e devolve o tempo típico em ms."""
        dummy = np.zeros((INPUT_SIZE, INPUT_SIZE, 3), np.uint8)
        for _ in range(3):
            self.predict(dummy)
        times = []
        for _ in range(5):
            self.predict(dummy)
            times.append(self.last_ms)
        return float(np.median(times))

    def predict(self, face_rgb: np.ndarray) -> EmotionReading:
        t0 = time.perf_counter()
        out = self.session.run(None, {self._input: preprocess(face_rgb)})[0][0]
        self.last_ms = (time.perf_counter() - t0) * 1000
        return EmotionReading(_softmax(out[:8].astype(np.float64)), float(out[8]), float(out[9]))
