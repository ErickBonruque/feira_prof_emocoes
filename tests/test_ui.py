"""Telas e sons sem câmera, sem janela e sem áudio (drivers "dummy" do SDL)."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from caretas.config import Config  # noqa: E402
from caretas.game import Game, Phase  # noqa: E402
from caretas.pipeline import FrameResult  # noqa: E402
from caretas.ui.lab import LabView  # noqa: E402
from caretas.ui.renderer import Renderer  # noqa: E402
from caretas.ui.smooth import OneEuro, SmoothBox  # noqa: E402
from caretas.ui.sound import SoundBoard, build_sounds  # noqa: E402

from .helpers import HAPPY, NEUTRAL, SAD, SURPRISED, face  # noqa: E402

FRAME = np.full((720, 1280, 3), 90, np.uint8)
CROP = np.full((224, 224, 3), 120, np.uint8)


class FakeCamera:
    fps = 30.0
    status = "ok"
    message = ""
    source_label = "câmera 0"
    resolution = (1280, 720)
    index = 0

    def healthy(self):
        return True

    def last_frame_age(self):
        return 0.0

    def peek(self):
        return FRAME, 1


class Sim:
    def __init__(self, game):
        self.game, self.t, self.fid, self.last = game, 100.0, 0, None

    def run(self, secs, r):
        f = face()
        for _ in range(int(round(secs * 30))):
            self.t += 1 / 30
            self.fid += 1
            self.last = FrameResult(self.fid, self.t, FRAME, [f], f, True, None, 1.0, 0.0, r,
                                    {"detect_ms": 5.0, "emotion_ms": 7.0}, CROP)
            self.game.update(self.last, self.t)


def play_match(sim):
    sim.run(0.1, NEUTRAL)
    sim.run(sim.game.cfg.calibration.seconds + 0.2, NEUTRAL)
    for expr in (HAPPY, SURPRISED, SAD):
        sim.run(0.8, NEUTRAL)
        sim.run(1.8, expr)
        sim.run(sim.game.cfg.game.between_seconds + 0.1, NEUTRAL)


@pytest.fixture(params=[(1920, 1080), (1024, 768)], ids=["16x9", "4x3"])
def screen(request):
    pygame.init()   # sem pygame.quit(): as fontes ficam em cache entre os testes
    return pygame.display.set_mode(request.param)


def draw_for(renderer, game, sim, seconds=1.5):
    cam = FakeCamera()
    for i in range(int(seconds * 30)):
        renderer.draw(sim.t + i / 30, game, sim.last, cam)


def test_every_screen_draws_without_errors(screen):
    cfg = Config()
    game = Game(cfg, 100.0)
    sim = Sim(game)
    r = Renderer(cfg, screen)
    draw_for(r, game, sim)                              # espera
    sim.run(0.1, NEUTRAL)
    draw_for(r, game, sim)                              # calibração
    play_match(sim)
    assert game.phase == Phase.VICTORY
    draw_for(r, game, sim)
    game.advance(sim.t)
    assert game.phase == Phase.REPORT
    draw_for(r, game, sim, 3.0)                         # relatório com animação de entrada
    assert set(r.report_view.buttons) == {"yes", "no", "next"}
    game.review(False, sim.t)
    draw_for(r, game, sim)                              # carimbo "corrigido"
    game.advance(sim.t)
    assert game.phase == Phase.IDLE and game.report is None
    draw_for(r, game, sim, 0.2)
    assert r.report_view.buttons == {}                  # reset esqueceu fotos e botões


def test_lab_view_draws_with_and_without_a_face(screen):
    cfg = Config()
    r = Renderer(cfg, screen)
    lab = LabView(cfg, r)
    game = Game(cfg, 100.0)
    sim = Sim(game)
    lab.draw(screen, 1.0, None, FakeCamera(), "CPU")   # ninguém na frente
    for _ in range(20):
        sim.run(1 / 30, HAPPY)
        lab.draw(screen, sim.t, sim.last, FakeCamera(), "GPU (CUDA)")


def test_report_buttons_are_on_screen(screen):
    cfg = Config()
    game = Game(cfg, 100.0)
    sim = Sim(game)
    r = Renderer(cfg, screen)
    play_match(sim)
    game.advance(sim.t)
    draw_for(r, game, sim, 2.0)
    area = screen.get_rect()
    for rect in r.report_view.buttons.values():
        assert area.contains(rect)
        assert rect.w > 40 and rect.h > 20


def test_sounds_are_synthesized_in_range():
    sounds = build_sounds()
    for name in ("lock", "tick", "go", "charge1", "charge2", "done", "victory", "timeout", "print",
                 "stamp_yes", "stamp_no", "next"):
        wave = sounds[name]
        assert wave.dtype == np.float32 and 0.02 < len(wave) / 44100 < 3.0
        assert 0.1 < np.abs(wave).max() <= 0.86


def test_soundboard_plays_on_game_events():
    cfg = Config()
    pygame.init()
    board = SoundBoard(cfg)
    played = []
    board.play = played.append
    game = Game(cfg, 100.0)
    sim = Sim(game)
    # como no laço do jogo: um update do SoundBoard a cada quadro
    for secs, r in [(0.1, NEUTRAL), (cfg.calibration.seconds + 0.2, NEUTRAL), (0.8, NEUTRAL), (1.8, HAPPY)]:
        for _ in range(int(round(secs * 30))):
            sim.run(1 / 30, r)
            board.update(game, sim.t)
    assert "lock" in played and "go" in played and "tick" in played
    assert "charge1" in played and "charge2" in played and "done" in played
    board.enabled = False
    assert board.toggle() is True


def test_one_euro_removes_jitter_but_follows_motion():
    f = OneEuro(1.0, 0.008)
    rng = np.random.default_rng(0)
    out = [f(500 + rng.normal(0, 4), 1 / 30) for _ in range(90)]
    assert np.std(out[30:]) < 1.5                        # parado: tremido some
    for _ in range(30):
        last = f(900, 1 / 30)
    assert last > 880                                    # mexeu: acompanha


def test_smooth_box_glides_and_forgets():
    box = SmoothBox()
    a = box.update(pygame.Rect(100, 100, 50, 50), 1, 0.0)
    assert a.center == (125, 125)
    b = box.update(pygame.Rect(300, 100, 50, 50), 2, 0.016)
    assert 125 < b.centerx < 325                         # desliza, não teleporta
    assert box.update(None, 2, 2.0) is None               # sumiu faz tempo: esquece
