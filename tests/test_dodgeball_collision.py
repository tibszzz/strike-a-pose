"""Dodgeball collision geometry: primitives, body model, swept ball hits."""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from main.games.dodgeball.ball import Ball
from main.games.dodgeball.collision import (
    Body,
    Capsule,
    build_body,
    point_in_polygon,
    point_segment_distance,
    segment_distance,
    segments_intersect,
    swept_circle_hits,
)
from main.pose import KP, Person

approx = pytest.approx


# --- point_segment_distance ---------------------------------------------------


@pytest.mark.parametrize(
    "p, a, b, expected",
    [
        ((5, 3), (0, 0), (10, 0), 3.0),  # perpendicular foot inside the segment
        ((5, -3), (0, 0), (10, 0), 3.0),  # other side
        ((-3, 4), (0, 0), (10, 0), 5.0),  # beyond a: distance to a
        ((13, 4), (0, 0), (10, 0), 5.0),  # beyond b: distance to b
        ((0, 0), (0, 0), (10, 0), 0.0),  # on endpoint
        ((4, 0), (0, 0), (10, 0), 0.0),  # on the segment
        ((20, 0), (0, 0), (10, 0), 10.0),  # collinear, past the end
        ((3, 7), (0, 0), (0, 10), 3.0),  # vertical segment
        ((1, 1), (0, 0), (2, 2), 0.0),  # diagonal, on it
        ((0, 2), (0, 0), (2, 2), math.sqrt(2)),  # diagonal, off it
        ((3, 4), (0, 0), (0, 0), 5.0),  # degenerate segment (used to divide by zero)
        ((0, 0), (0, 0), (0, 0), 0.0),
    ],
)
def test_point_segment_distance_cases(p, a, b, expected):
    assert point_segment_distance(p, a, b) == approx(expected)


def test_point_segment_distance_is_symmetric_in_endpoints():
    rng = random.Random(1)
    for _ in range(500):
        p, a, b = [(rng.uniform(-50, 50), rng.uniform(-50, 50)) for _ in range(3)]
        assert point_segment_distance(p, a, b) == approx(point_segment_distance(p, b, a))


def test_point_segment_distance_matches_brute_force():
    rng = random.Random(2)
    for _ in range(300):
        p, a, b = [(rng.uniform(-50, 50), rng.uniform(-50, 50)) for _ in range(3)]
        samples = (
            math.dist(p, (a[0] + (b[0] - a[0]) * t / 400, a[1] + (b[1] - a[1]) * t / 400))
            for t in range(401)
        )
        brute = min(samples)
        exact = point_segment_distance(p, a, b)
        assert exact <= brute + 1e-9  # never further than any sampled point
        assert brute - exact < math.dist(a, b) / 400 + 1e-6  # and within sampling error


def test_ball_wrapper_keeps_old_name_and_handles_degenerate_segment():
    ball = Ball(x=0, y=0, radius=10)
    assert ball._point_to_line_distance((3, 4), (1, 1), (1, 1)) == approx(math.dist((3, 4), (1, 1)))


# --- segments_intersect / segment_distance ------------------------------------


@pytest.mark.parametrize(
    "a0, a1, b0, b1, crosses",
    [
        ((0, 0), (10, 10), (0, 10), (10, 0), True),  # X
        ((0, 0), (10, 0), (5, 0), (5, 5), True),  # T: endpoint on the other segment
        ((0, 0), (10, 0), (10, 0), (20, 5), True),  # shared endpoint
        ((0, 0), (10, 0), (5, 0), (15, 0), True),  # collinear overlap
        ((0, 0), (10, 0), (11, 0), (20, 0), False),  # collinear, gap
        ((0, 0), (10, 0), (0, 1), (10, 1), False),  # parallel
        ((0, 0), (10, 0), (5, 1), (5, 5), False),  # near miss
        ((3, 3), (3, 3), (0, 0), (6, 6), True),  # degenerate point on segment
        ((3, 4), (3, 4), (0, 0), (6, 6), False),  # degenerate point off segment
    ],
)
def test_segments_intersect_cases(a0, a1, b0, b1, crosses):
    assert segments_intersect(a0, a1, b0, b1) is crosses
    assert segments_intersect(b0, b1, a0, a1) is crosses


@pytest.mark.parametrize(
    "a0, a1, b0, b1, expected",
    [
        ((0, 0), (10, 10), (0, 10), (10, 0), 0.0),
        ((0, 0), (10, 0), (0, 3), (10, 3), 3.0),  # parallel
        ((0, 0), (10, 0), (13, 4), (20, 4), 5.0),  # endpoint to endpoint
        ((0, 0), (10, 0), (5, 2), (5, 9), 2.0),  # endpoint to interior
        ((0, 0), (0, 0), (3, 4), (3, 4), 5.0),  # two points
    ],
)
def test_segment_distance_cases(a0, a1, b0, b1, expected):
    assert segment_distance(a0, a1, b0, b1) == approx(expected)


def test_segment_distance_matches_brute_force():
    rng = random.Random(3)
    for _ in range(200):
        a0, a1, b0, b1 = [(rng.uniform(-40, 40), rng.uniform(-40, 40)) for _ in range(4)]
        brute = min(
            point_segment_distance(
                (a0[0] + (a1[0] - a0[0]) * t / 300, a0[1] + (a1[1] - a0[1]) * t / 300), b0, b1
            )
            for t in range(301)
        )
        exact = segment_distance(a0, a1, b0, b1)
        assert exact <= brute + 1e-9
        assert brute - exact < math.dist(a0, a1) / 300 + 1e-6


# --- point_in_polygon ---------------------------------------------------------

SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]
# A "U" shape: the notch (4..6, 5..10) is outside.
U_SHAPE = [(0, 0), (10, 0), (10, 10), (6, 10), (6, 5), (4, 5), (4, 10), (0, 10)]


@pytest.mark.parametrize(
    "point, inside",
    [((5, 5), True), ((0.1, 0.1), True), ((-1, 5), False), ((11, 5), False), ((5, 11), False)],
)
def test_point_in_square(point, inside):
    assert point_in_polygon(point, SQUARE) is inside


@pytest.mark.parametrize(
    "point, inside",
    [((2, 8), True), ((8, 8), True), ((5, 2), True), ((5, 8), False), ((5, 5.5), False)],
)
def test_point_in_concave_polygon(point, inside):
    assert point_in_polygon(point, U_SHAPE) is inside


def test_ray_through_a_vertex_counts_once():
    diamond = [(5, 0), (10, 5), (5, 10), (0, 5)]
    # y == 5 passes exactly through the vertices (10, 5) and (0, 5).
    assert point_in_polygon((5, 5), diamond)
    assert not point_in_polygon((-1, 5), diamond)
    assert not point_in_polygon((11, 5), diamond)


def test_horizontal_edges_do_not_divide_by_zero_or_flip():
    assert point_in_polygon((5, 5), SQUARE)  # top / bottom edges are horizontal
    assert not point_in_polygon((5, 0 - 1e-6), SQUARE)


def test_point_in_polygon_matches_triangle_area_test():
    rng = random.Random(4)
    tri = [(0, 0), (40, 5), (10, 30)]

    def area(a, b, c):
        return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2

    whole = area(*tri)
    for _ in range(1000):
        p = (rng.uniform(-5, 45), rng.uniform(-5, 35))
        parts = area(p, tri[1], tri[2]) + area(tri[0], p, tri[2]) + area(tri[0], tri[1], p)
        if abs(parts - whole) < 1e-6 * whole:
            inside = True
        elif parts > whole * (1 + 1e-6):
            inside = False
        else:
            continue  # on the boundary: either answer is fine
        assert point_in_polygon(p, tri) is inside


def test_degenerate_polygons_contain_nothing():
    assert not point_in_polygon((0, 0), [])
    assert not point_in_polygon((0, 0), [(0, 0), (1, 1)])


# --- body model + ball hits ---------------------------------------------------


def standing_person(cx: float = 500.0, top: float = 100.0, s: float = 100.0, conf: float = 0.9) -> Person:
    """Front-facing person with arms straight out (a T), shoulder width `s`."""
    xy = np.zeros((17, 2))
    xy[KP.NOSE] = (cx, top + 0.5 * s)
    xy[KP.L_EYE] = (cx + 0.1 * s, top + 0.4 * s)
    xy[KP.R_EYE] = (cx - 0.1 * s, top + 0.4 * s)
    xy[KP.L_EAR] = (cx + 0.2 * s, top + 0.45 * s)
    xy[KP.R_EAR] = (cx - 0.2 * s, top + 0.45 * s)
    sh_y, hip_y = top + 1.2 * s, top + 2.8 * s
    xy[KP.L_SHOULDER] = (cx + 0.5 * s, sh_y)
    xy[KP.R_SHOULDER] = (cx - 0.5 * s, sh_y)
    xy[KP.L_ELBOW] = (cx + 1.2 * s, sh_y)
    xy[KP.R_ELBOW] = (cx - 1.2 * s, sh_y)
    xy[KP.L_WRIST] = (cx + 1.9 * s, sh_y)
    xy[KP.R_WRIST] = (cx - 1.9 * s, sh_y)
    xy[KP.L_HIP] = (cx + 0.35 * s, hip_y)
    xy[KP.R_HIP] = (cx - 0.35 * s, hip_y)
    xy[KP.L_KNEE] = (cx + 0.35 * s, hip_y + 1.2 * s)
    xy[KP.R_KNEE] = (cx - 0.35 * s, hip_y + 1.2 * s)
    xy[KP.L_ANKLE] = (cx + 0.35 * s, hip_y + 2.4 * s)
    xy[KP.R_ANKLE] = (cx - 0.35 * s, hip_y + 2.4 * s)
    box = (cx - 2.0 * s, top, cx + 2.0 * s, hip_y + 2.5 * s)
    return Person(xy=xy, conf=np.full(17, conf), box=box)


def ball_at(x: float, y: float, radius: float = 20.0, prev: tuple[float, float] | None = None) -> Ball:
    ball = Ball(x=x, y=y, radius=radius)
    if prev is not None:
        ball.prev_x, ball.prev_y = prev
    return ball


@pytest.mark.parametrize(
    "where, xy",
    [
        ("head", (500, 150)),
        ("chest", (500, 300)),
        ("left hand, past the wrist", (500 + 1.9 * 100 + 25, 220)),
        ("right forearm", (500 - 1.5 * 100, 220 + 25)),  # just below the arm line
        ("left shin", (535, 100 + 2.8 * 100 + 180)),
    ],
)
def test_ball_touching_body_parts_hits(where, xy):
    assert ball_at(*xy).check_collision(standing_person())[0], where


@pytest.mark.parametrize(
    "where, xy",
    [
        ("well above the head", (500, 20)),
        ("under the arm, beside the waist", (500 + 1.4 * 100, 380)),
        ("far left of the hand", (500 - 1.9 * 100 - 80, 220)),
        ("top-left corner of the frame", (25, 25)),
    ],
)
def test_ball_clear_of_body_misses(where, xy):
    assert not ball_at(*xy).check_collision(standing_person())[0], where


def test_small_ball_passes_between_the_legs_but_a_big_one_does_not():
    shin_y = 100 + 2.8 * 100 + 180  # shins at x = 465 / 535, ~17 px thick
    assert not ball_at(500, shin_y, radius=8).check_collision(standing_person())[0]
    assert ball_at(500, shin_y, radius=20).check_collision(standing_person())[0]


def test_undetected_joints_at_origin_are_ignored():
    """Regression: low-confidence keypoints sit at (0, 0) and used to stretch the
    old polygon to the top-left corner, so a ball there counted as a hit."""
    person = standing_person()
    conf = person.conf.copy()
    xy = person.xy.copy()
    for k in (KP.L_WRIST, KP.R_WRIST, KP.L_ANKLE, KP.R_ANKLE):
        xy[k] = (0.0, 0.0)
        conf[k] = 0.05
    ghosted = Person(xy=xy, conf=conf, box=person.box)
    assert not ball_at(30, 30).check_collision(ghosted)[0]
    assert not ball_at(250, 150).check_collision(ghosted)[0]  # on the old bogus edge to (0,0)
    assert ball_at(500, 300).check_collision(ghosted)[0]  # body still solid


def test_fast_ball_cannot_tunnel_through_a_forearm():
    person = standing_person()
    arm_y = 220
    # Moves 60 px in one frame, straight across the forearm, ending clear of it.
    ball = ball_at(500 + 1.5 * 100, arm_y + 70, radius=10, prev=(500 + 1.5 * 100, arm_y - 70))
    assert not ball_at(ball.x, ball.y, radius=10).check_collision(person)[0]  # end alone misses
    assert ball.check_collision(person)[0]  # the swept path hits


def test_ball_move_records_previous_position():
    ball = Ball(x=100, y=100, radius=10)
    ball.vx, ball.vy = 7.0, -3.0
    ball.move()
    assert (ball.prev_x, ball.prev_y) == (100, 100)
    assert (ball.x, ball.y) == (107.0, 97.0)


def test_limbs_scale_with_player_size():
    near = build_body(standing_person(s=200).xy, np.full(17, 0.9), standing_person(s=200).box)
    far = build_body(standing_person(s=50).xy, np.full(17, 0.9), standing_person(s=50).box)
    assert max(c.radius for c in near.capsules) == approx(4 * max(c.radius for c in far.capsules))


def test_side_on_player_still_has_a_solid_torso():
    person = standing_person()
    xy = person.xy.copy()
    for k in (KP.L_SHOULDER, KP.R_SHOULDER):
        xy[k] = (500.0, xy[k][1])  # shoulders overlap: zero width
    for k in (KP.L_HIP, KP.R_HIP):
        xy[k] = (500.0, xy[k][1])
    side = Person(xy=xy, conf=person.conf, box=person.box)
    assert ball_at(500 + 30, 300).check_collision(side)[0]


def test_person_without_confident_joints_falls_back_to_box_middle():
    person = standing_person(conf=0.05)
    assert ball_at(500, 300).check_collision(person)[0]
    assert not ball_at(500 - 1.9 * 100, 300).check_collision(person)[0]  # box edge, not body


def test_no_person_means_no_hit():
    assert Ball(x=10, y=10).check_collision(None) == (False, None)


def test_returned_points_are_only_confident_joints():
    person = standing_person()
    conf = person.conf.copy()
    conf[KP.NOSE] = 0.0
    hit, points = ball_at(500, 300).check_collision(Person(xy=person.xy, conf=conf, box=person.box))
    assert hit and len(points) == 16


def test_swept_circle_against_a_bare_capsule_and_polygon():
    body = Body(capsules=(Capsule((0, 0), (100, 0), 5),), polygons=(((200, 0), (300, 0), (300, 100), (200, 100)),), points=())
    assert swept_circle_hits((50, 20), (50, 20), 15, body)  # 20 <= 15 + 5
    assert not swept_circle_hits((50, 21), (50, 21), 15, body)
    assert swept_circle_hits((150, 50), (250, 50), 1, body)  # enters the polygon
    assert swept_circle_hits((180, 50), (195, 50), 6, body)  # grazes its edge
    assert not swept_circle_hits((180, 50), (190, 50), 6, body)
