import math
import socket

import cv2
import numpy as np
import pytest

from caretas import offline
from caretas.config import PROJECT_ROOT, ConfigError, load_config
from caretas.detection import Face
from caretas.emotion import crop_face


def test_project_config_loads():
    cfg = load_config()
    assert cfg.game.order == ["happiness", "surprise", "sadness"]
    assert cfg.privacy.block_network


def test_unknown_key_is_an_error(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("rules:\n  happines:\n    min_prob: 0.5\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="happines"):
        load_config(p)


def test_bad_value_is_an_error(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("rules:\n  sadness:\n    direction: sideways\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)


def test_crop_alignment_levels_the_eyes():
    img = np.zeros((480, 640, 3), np.uint8)
    # "olhos" como pontos brancos inclinados 20 graus
    cx, cy, d = 320, 240, 80
    a = math.radians(20)
    e1 = (cx - d * math.cos(a), cy - d * math.sin(a))
    e2 = (cx + d * math.cos(a), cy + d * math.sin(a))
    for e in (e1, e2):
        cv2.circle(img, (int(e[0]), int(e[1])), 8, (255, 255, 255), -1)
    lm = np.array([e1, e2, (cx, cy), (cx - 40, cy + 60), (cx + 40, cy + 60)], np.float32)
    f = Face(cx - 120, cy - 120, 240, 240, 0.9, lm)
    crop = cv2.cvtColor(crop_face(img, f, 0.0, True), cv2.COLOR_RGB2GRAY)
    ys, xs = np.nonzero(crop > 128)
    left = ys[xs < 112].mean()
    right = ys[xs >= 112].mean()
    assert abs(left - right) < 3


def test_offline_guard_blocks_external_but_allows_loopback():
    offline.install()
    with pytest.raises(offline.NetworkBlockedError):
        socket.create_connection(("example.com", 80), timeout=1)
    with pytest.raises(offline.NetworkBlockedError):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(("1.1.1.1", 443))
        finally:
            s.close()
    # loopback continua permitido: não levanta NetworkBlockedError (não precisa ter servidor ouvindo)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    s.connect_ex(("127.0.0.1", 9))
    s.close()
    assert offline.blocked_attempts[-2:] == ["DNS example.com", "1.1.1.1:443"]


@pytest.mark.skipif(not (PROJECT_ROOT / "models" / "enet_b0_8_va_mtl.onnx").exists(), reason="modelos não baixados")
def test_models_load_and_run():
    from caretas.detection import FaceDetector
    from caretas.emotion import EmotionModel

    cfg = load_config()
    det = FaceDetector(cfg.resolve_path(cfg.detector.model))
    assert det.detect(np.zeros((720, 1280, 3), np.uint8)) == []
    emo = EmotionModel(cfg.resolve_path(cfg.emotion.model), "cpu")
    r = emo.predict(np.full((224, 224, 3), 128, np.uint8))
    assert r.probs.shape == (8,) and abs(r.probs.sum() - 1) < 1e-5
    assert -3 < r.valence < 3 and -3 < r.arousal < 3
