import pytest

from strike_a_pose.games.duel.float_path import P1_POINTS, FloatPath, ease_out, fade


def test_path_starts_at_text_and_ends_top_left():
    p = FloatPath((1000, 500), 0)
    assert p.at(0) == pytest.approx((P1_POINTS[0][0] * 1000, P1_POINTS[0][1] * 500))
    assert p.at(1) == pytest.approx((P1_POINTS[-1][0] * 1000, P1_POINTS[-1][1] * 500))


def test_player_two_is_mirrored():
    a, b = FloatPath((1000, 500), 0), FloatPath((1000, 500), 1)
    for u in (0, 0.3, 0.7, 1):
        (ax, ay), (bx, by) = a.at(u), b.at(u)
        assert bx == pytest.approx(1000 - ax) and by == pytest.approx(ay)


def test_ease_and_fade():
    assert ease_out(0) == 0 and ease_out(1) == 1 and ease_out(0.5) > 0.5
    assert fade(0.3) == 1 and fade(1) == 0 and fade(0.75) == pytest.approx(0.5)
