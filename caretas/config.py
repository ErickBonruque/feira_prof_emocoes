"""Carrega o config.yaml em dataclasses tipadas.

Chaves ausentes no YAML usam os valores padrão daqui; chaves desconhecidas
geram erro com a lista de chaves válidas (evita erro de digitação silencioso).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMOTION_KEYS = ("happiness", "surprise", "sadness")


class ConfigError(ValueError):
    pass


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    fourcc: str = "MJPG"
    mirror: bool = True
    reconnect_interval: float = 2.0
    frame_timeout: float = 2.0
    usb_hardware_id: str = ""
    exposure: str = "auto"


@dataclass
class DetectorConfig:
    model: str = "models/face_detection_yunet_2023mar.onnx"
    input_width: int = 640
    score_threshold: float = 0.75
    min_face_width: float = 0.12
    center_weight: float = 0.5
    lock_seconds: float = 0.6
    lost_seconds: float = 3.0
    max_jump: float = 0.8


@dataclass
class EmotionConfig:
    model: str = "models/enet_b0_8_va_mtl.onnx"
    device: str = "auto"
    crop_margin: float = 0.10
    align: bool = True
    smoothing: float = 0.40


@dataclass
class CalibrationConfig:
    seconds: float = 2.5
    min_frames: int = 15
    max_attempts: int = 3
    max_expression: float = 0.45


@dataclass
class EmotionRule:
    min_prob: float = 0.6
    min_gain: float = 0.3
    axis: str = "valence"
    direction: str = "up"
    axis_min: float = 0.2
    axis_gain: float = 0.2


@dataclass
class RulesConfig:
    hold_seconds: float = 1.0
    hold_frames: int = 12
    happiness: EmotionRule = field(default_factory=lambda: EmotionRule(0.70, 0.35, "valence", "up", 0.30, 0.25))
    surprise: EmotionRule = field(default_factory=lambda: EmotionRule(0.60, 0.35, "arousal", "up", 0.35, 0.20))
    sadness: EmotionRule = field(default_factory=lambda: EmotionRule(0.50, 0.30, "valence", "down", 0.10, 0.15))

    def for_emotion(self, key: str) -> EmotionRule:
        return getattr(self, key)


@dataclass
class GameConfig:
    order: list[str] = field(default_factory=lambda: list(EMOTION_KEYS))
    match_timeout: float = 60.0
    victory_seconds: float = 5.0
    timeout_seconds: float = 4.0
    report_timeout: float = 90.0     # relatório volta sozinho após N s (0 = só pelo botão)
    cooldown_seconds: float = 2.5
    between_seconds: float = 1.2


@dataclass
class UIConfig:
    fullscreen: bool = True
    window_size: list[int] = field(default_factory=lambda: [1280, 720])
    fps_limit: int = 60
    title: str = "JOGO DAS CARETAS"
    kicker: str = "FEIRA DE PROFISSÕES · UTFPR"
    subtitle: str = "Reconhecimento de emoções com visão computacional"
    victory_snapshots: bool = True
    show_ai_reading: bool = True
    emotion_map: bool = True         # mapa valência x excitação no canto da câmera
    report: bool = True              # relatório da IA + revisão humana no fim da partida


@dataclass
class AudioConfig:
    enabled: bool = True
    volume: float = 0.6


@dataclass
class PrivacyConfig:
    block_network: bool = True


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    emotion: EmotionConfig = field(default_factory=EmotionConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    rules: RulesConfig = field(default_factory=RulesConfig)
    game: GameConfig = field(default_factory=GameConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)

    def resolve_path(self, relative: str) -> Path:
        p = Path(relative)
        return p if p.is_absolute() else PROJECT_ROOT / p


def _build(cls, data: Any, where: str):
    """Instancia a dataclass `cls` a partir de um dict, recursivamente, sobre os padrões."""
    instance = cls()
    if data is None:
        return instance
    if not isinstance(data, dict):
        raise ConfigError(f"'{where}' deveria ser um bloco de chaves, mas é {data!r}")
    fields = {f.name: f for f in dataclasses.fields(cls)}
    for key, value in data.items():
        if key not in fields:
            raise ConfigError(f"chave desconhecida '{where}.{key}'. Válidas: {', '.join(fields)}")
        current = getattr(instance, key)
        if dataclasses.is_dataclass(current):
            value = _build(type(current), value, f"{where}.{key}")
        elif isinstance(current, bool):
            if not isinstance(value, bool):
                raise ConfigError(f"'{where}.{key}' deve ser true/false")
        elif isinstance(current, (int, float)) and not isinstance(current, bool):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ConfigError(f"'{where}.{key}' deve ser um número")
            value = type(current)(value) if isinstance(current, float) else value
        setattr(instance, key, value)
    return instance


def _validate(cfg: Config) -> None:
    for key in cfg.game.order:
        if key not in EMOTION_KEYS:
            raise ConfigError(f"game.order: '{key}' inválido. Use: {', '.join(EMOTION_KEYS)}")
    if not cfg.game.order:
        raise ConfigError("game.order não pode ser vazio")
    if len(set(cfg.game.order)) != len(cfg.game.order):
        raise ConfigError("game.order não pode repetir emoções")
    for key in EMOTION_KEYS:
        rule = cfg.rules.for_emotion(key)
        if rule.axis not in ("valence", "arousal"):
            raise ConfigError(f"rules.{key}.axis deve ser 'valence' ou 'arousal'")
        if rule.direction not in ("up", "down"):
            raise ConfigError(f"rules.{key}.direction deve ser 'up' ou 'down'")
        if not 0.0 < rule.min_prob <= 1.0:
            raise ConfigError(f"rules.{key}.min_prob deve estar entre 0 e 1")
    if not 0.0 < cfg.emotion.smoothing <= 1.0:
        raise ConfigError("emotion.smoothing deve estar entre 0 (exclusivo) e 1")
    if cfg.emotion.device not in ("auto", "cuda", "cpu"):
        raise ConfigError("emotion.device deve ser auto, cuda ou cpu")
    if cfg.rules.hold_frames < 1 or cfg.rules.hold_seconds < 0:
        raise ConfigError("rules.hold_frames >= 1 e rules.hold_seconds >= 0")
    if not 0.0 <= cfg.audio.volume <= 1.0:
        raise ConfigError("audio.volume deve estar entre 0 e 1")
    exposure = cfg.camera.exposure
    if isinstance(exposure, bool) or not (isinstance(exposure, (int, float)) or str(exposure).strip().lower() == "auto"):
        raise ConfigError("camera.exposure deve ser auto ou um número (ex.: -6)")
    if cfg.game.report_timeout < 0:
        raise ConfigError("game.report_timeout deve ser >= 0 (0 = só pelo botão)")


def load_config(path: str | Path | None = None) -> Config:
    path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    data: dict = {}
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    cfg = _build(Config, data, "config")
    _validate(cfg)
    return cfg
