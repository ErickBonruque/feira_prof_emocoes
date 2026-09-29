from caretas.config import DetectorConfig
from caretas.detection import PlayerTracker

from .helpers import face

W, H = 1280, 720


def step(tr, faces, t0, seconds, fps=30):
    st = None
    n = int(seconds * fps)
    for i in range(n):
        st = tr.update(faces, W, H, t0 + i / fps)
    return st, t0 + n / fps


def test_locks_on_big_centered_face_and_ignores_background():
    tr = PlayerTracker(DetectorConfig())
    player = face(x=520, y=200, w=240, h=280)
    small_bg = face(x=60, y=80, w=80, h=95)            # gente passando ao fundo
    st, t = step(tr, [small_bg, player], 0.0, 1.0)
    assert st.locked and st.player.x == player.x


def test_prefers_centered_face_when_sizes_are_similar():
    tr = PlayerTracker(DetectorConfig(center_weight=0.8))
    center = face(x=530, y=220, w=220, h=260)
    corner = face(x=1000, y=40, w=230, h=270)
    st, _ = step(tr, [corner, center], 0.0, 1.0)
    assert st.player.x == center.x


def test_needs_to_be_stable_before_locking():
    tr = PlayerTracker(DetectorConfig(lock_seconds=0.6))
    st, t = step(tr, [face()], 0.0, 0.3)
    assert not st.locked and 0 < st.lock_progress < 1


def test_stays_on_player_when_bigger_face_appears():
    tr = PlayerTracker(DetectorConfig())
    player = face(x=500, y=250, w=220, h=260)
    st, t = step(tr, [player], 0.0, 1.0)
    assert st.locked
    intruder = face(x=100, y=100, w=400, h=460)         # alguém se debruça do lado
    st, t = step(tr, [intruder, player], t, 1.0)
    assert st.player.x == player.x


def test_follows_player_moving_slowly():
    tr = PlayerTracker(DetectorConfig())
    st, t = step(tr, [face(x=500)], 0.0, 1.0)
    for dx in range(0, 300, 10):
        st = tr.update([face(x=500 + dx)], W, H, t)
        t += 1 / 30
    assert st.locked and st.player.x == 790


def test_releases_after_lost_seconds():
    tr = PlayerTracker(DetectorConfig(lost_seconds=3.0))
    st, t = step(tr, [face()], 0.0, 1.0)
    st, t = step(tr, [], t, 2.0)
    assert st.locked and st.player is None and st.lost_for > 1.5
    st, t = step(tr, [], t, 1.5)
    assert not st.locked


def test_release_pauses_locking():
    tr = PlayerTracker(DetectorConfig())
    st, t = step(tr, [face()], 0.0, 1.0)
    tr.release(pause_until=t + 2.0)
    st, t2 = step(tr, [face()], t, 1.5)
    assert not st.locked
    st, _ = step(tr, [face()], t2, 1.5)
    assert st.locked
