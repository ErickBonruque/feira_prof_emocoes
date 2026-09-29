"""O que não pode acontecer na frente do público: ganhar com cara neutra."""

from caretas.config import Config
from caretas.game import Game, Phase

from .helpers import HAPPY, MILD_SMILE, NEUTRAL, SAD, SURPRISED, Sim


def new_sim(**game_overrides) -> Sim:
    cfg = Config()
    for k, v in game_overrides.items():
        setattr(cfg.game, k, v)
    return Sim(Game(cfg, now=100.0))


def calibrate(sim: Sim) -> None:
    sim.run(0.1, NEUTRAL)                       # trava o jogador
    assert sim.game.phase == Phase.CALIBRATING
    sim.run(sim.game.cfg.calibration.seconds + 0.2, NEUTRAL)
    assert sim.game.phase == Phase.PLAYING
    assert not sim.game.baseline.is_default


def test_neutral_face_never_wins():
    sim = new_sim(match_timeout=0)
    calibrate(sim)
    sim.run(60, NEUTRAL)
    assert sim.game.completed == []
    assert sim.game.phase == Phase.PLAYING


def test_mild_smile_is_not_enough():
    sim = new_sim(match_timeout=0)
    calibrate(sim)
    sim.run(10, MILD_SMILE)
    assert sim.game.completed == []


def test_short_expression_does_not_count():
    sim = new_sim()
    calibrate(sim)
    for _ in range(10):          # 0,5 s feliz / 0,5 s neutro, várias vezes
        sim.run(0.5, HAPPY)
        sim.run(0.5, NEUTRAL)
    assert sim.game.completed == []


def test_full_match_wins_and_returns_to_idle():
    sim = new_sim()
    calibrate(sim)
    for expr in (HAPPY, SURPRISED, SAD):
        sim.run(0.8, NEUTRAL)
        sim.run(1.8, expr)
        sim.run(sim.game.cfg.game.between_seconds + 0.1, NEUTRAL)
    assert sim.game.completed == ["happiness", "surprise", "sadness"]
    assert sim.game.phase == Phase.VICTORY
    assert sim.game.victories == 1
    sim.run(sim.game.cfg.game.victory_seconds + 0.1, NEUTRAL)
    assert sim.game.phase == Phase.REPORT
    assert sim.game.report.won and sim.game.report.number == 1
    sim.run(30, NEUTRAL)                      # o relatório espera o botão do operador
    assert sim.game.phase == Phase.REPORT
    sim.game.advance(sim.t)                   # "próximo jogador"
    assert sim.game.phase == Phase.IDLE
    assert sim.game.completed == [] and sim.game.snapshots == {} and sim.game.report is None
    assert len(sim.game.history) == 0


def test_wrong_expression_does_not_count_for_target():
    sim = new_sim(match_timeout=0)
    calibrate(sim)
    sim.run(5, SURPRISED)   # alvo atual é felicidade
    sim.run(5, SAD)
    assert sim.game.completed == []


def test_expressive_calibration_is_retried():
    sim = new_sim()
    sim.run(0.1, HAPPY)
    assert sim.game.phase == Phase.CALIBRATING
    sim.run(sim.game.cfg.calibration.seconds + 0.2, HAPPY)
    assert sim.game.phase == Phase.CALIBRATING
    assert sim.game.calib_retry_reason == "expressive"
    sim.run(sim.game.cfg.calibration.seconds + 0.2, NEUTRAL)
    assert sim.game.phase == Phase.PLAYING


def test_calibration_gives_up_after_max_attempts_with_default_baseline():
    sim = new_sim()
    sim.run(0.1, HAPPY)
    for _ in range(sim.game.cfg.calibration.max_attempts):
        sim.run(sim.game.cfg.calibration.seconds + 0.2, HAPPY)
    assert sim.game.phase == Phase.PLAYING
    assert sim.game.baseline.is_default


def test_timeout_then_idle():
    sim = new_sim(match_timeout=5)
    calibrate(sim)
    sim.run(5.2, NEUTRAL)
    assert sim.game.phase == Phase.TIMEOUT
    sim.run(sim.game.cfg.game.timeout_seconds + 0.1, NEUTRAL)
    assert sim.game.phase == Phase.REPORT
    assert not sim.game.report.won
    assert [t.done for t in sim.game.report.targets] == [False, False, False]
    sim.game.advance(sim.t)
    assert sim.game.phase == Phase.IDLE


def test_player_lost_resets_match():
    sim = new_sim()
    calibrate(sim)
    sim.run(1.8, HAPPY)
    sim.run(1.0, NEUTRAL)
    assert sim.game.completed == ["happiness"] or sim.game.phase == Phase.BETWEEN
    sim.run(0.5, None, locked=True, player=False, lost_for=1.0)   # sumiu, ainda travado
    assert sim.game.phase in (Phase.PLAYING, Phase.BETWEEN)
    sim.run(0.1, None, locked=False, player=False, lost_for=3.5)  # rastreador soltou
    assert sim.game.phase == Phase.IDLE
    assert sim.game.completed == []


def test_face_missing_breaks_the_streak():
    sim = new_sim(match_timeout=0)
    calibrate(sim)
    for _ in range(8):
        sim.run(0.6, HAPPY)
        sim.run(0.05, None, locked=True, player=False, lost_for=0.05)
    assert sim.game.completed == []


def test_manual_reset_goes_idle_and_requests_release():
    sim = new_sim()
    calibrate(sim)
    sim.game.reset(sim.t)
    assert sim.game.phase == Phase.IDLE
    assert sim.game.take_release_request() is not None
    assert sim.game.take_release_request() is None


def test_resting_sad_face_needs_real_change():
    """Pessoa cujo neutro já parece um pouco triste: precisa superar o PRÓPRIO neutro."""
    from .helpers import reading
    resting = reading({"sadness": 0.40}, -0.25, -0.1)
    slightly_sadder = reading({"sadness": 0.60}, -0.35, -0.1)
    cfg = Config()
    cfg.game.order = ["sadness", "happiness", "surprise"]
    cfg.game.match_timeout = 0
    sim = Sim(Game(cfg, now=100.0))
    sim.run(0.1, resting)
    sim.run(cfg.calibration.seconds + 0.2, resting)
    assert sim.game.phase == Phase.PLAYING
    sim.run(10, slightly_sadder)
    assert sim.game.completed == []
    sim.run(2, SAD)
    assert sim.game.completed == ["sadness"]


def win(sim: Sim) -> None:
    calibrate(sim)
    for expr in (HAPPY, SURPRISED, SAD):
        sim.run(0.8, NEUTRAL)
        sim.run(1.8, expr)
        sim.run(sim.game.cfg.game.between_seconds + 0.1, NEUTRAL)
    assert sim.game.phase == Phase.VICTORY


def test_report_timeout_returns_to_idle_when_nobody_presses():
    sim = new_sim(report_timeout=20)
    win(sim)
    sim.run(sim.game.cfg.game.victory_seconds + 0.1, NEUTRAL)
    assert sim.game.phase == Phase.REPORT
    sim.run(20.1, NEUTRAL)
    assert sim.game.phase == Phase.IDLE


def test_report_ignores_player_leaving():
    """O jogador pode sair enquanto o operador explica: o relatório continua na tela."""
    sim = new_sim(report_timeout=0)
    win(sim)
    sim.game.advance(sim.t)                   # pula a comemoração
    assert sim.game.phase == Phase.REPORT
    sim.run(10, None, locked=False, player=False, lost_for=10)
    assert sim.game.phase == Phase.REPORT


def test_human_review_tally_and_changed_answer():
    sim = new_sim(report_timeout=0)
    assert not sim.game.review(True, sim.t)   # fora do relatório não conta
    win(sim)
    sim.game.advance(sim.t)
    assert sim.game.review(False, sim.t)
    assert (sim.game.reviews_ok, sim.game.reviews_fixed) == (0, 1)
    assert sim.game.review(True, sim.t)       # mudou de ideia: não conta duas vezes
    assert (sim.game.reviews_ok, sim.game.reviews_fixed) == (1, 0)
    sim.game.advance(sim.t)
    assert sim.game.phase == Phase.IDLE
    assert (sim.game.reviews_ok, sim.game.reviews_fixed) == (1, 0)


def test_report_contents_after_win():
    sim = new_sim()
    win(sim)
    rep = sim.game.report
    assert [t.key for t in rep.targets] == ["happiness", "surprise", "sadness"]
    assert all(t.done for t in rep.targets)
    assert all(1.0 <= t.seconds <= 3.5 for t in rep.targets)
    assert rep.targets[0].at < rep.targets[1].at < rep.targets[2].at <= rep.duration
    assert rep.strongest in ("happiness", "surprise", "sadness")
    assert rep.times.min() < 0 <= rep.times.max()     # calibração aparece antes do zero
    assert rep.probs.shape == (len(rep.times), 8)


def test_report_disabled_keeps_old_flow():
    sim = new_sim()
    sim.game.cfg.ui.report = False
    win(sim)
    sim.run(sim.game.cfg.game.victory_seconds + 0.1, NEUTRAL)
    assert sim.game.phase == Phase.IDLE


def test_advance_skips_celebration_and_resets_during_play():
    sim = new_sim()
    calibrate(sim)
    sim.game.advance(sim.t)                   # no meio do jogo = reiniciar
    assert sim.game.phase == Phase.IDLE
    assert sim.game.report is None
