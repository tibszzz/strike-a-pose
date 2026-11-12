import random

import pytest
from builders import ONE_ARM_UP, T_POSE, mirrored, person_striking

from main.config import Config
from main.games.strike.logic import Game, rank
from main.pose.library import JOINT_NAMES, Pose, load_library
from main.games.strike.screens import (
    CountdownScreen,
    CountdownTick,
    FinalScreen,
    GameOver,
    LobbyScreen,
    ResultsScreen,
    RetryScreen,
    RoundScored,
    ScoreRevealLocked,
    ScoreRevealTick,
    SnapshotTaken,
    Standing,
)

FRAME = object()  # stands in for a camera frame; the game only passes it along
COUNTDOWN = 5.0
SPOTS = (200.0, 500.0, 800.0, 1100.0, 1400.0)  # where people stand, left to right


def new_game(poses=None, **settings):
    """A game plus the list its events are recorded into."""
    settings.setdefault("countdown_seconds", COUNTDOWN)
    config = Config(**settings)
    game = Game(config, poses or load_library(config.poses_dir), random.Random(7))
    events = []
    game.subscribe(events.append)
    return game, events


def standing_people(count):
    return [person_striking(T_POSE, center_x=SPOTS[index]) for index in range(count)]


def start_game(game, players=2, now=0.0):
    people = standing_people(players)
    return game.step(now, confirm=True, people=people)


def play_round(game, started_at, strike):
    """Run one countdown to its snapshot.

    `strike(target)` returns the people in frame when the snapshot is taken.
    """
    countdown = game.step(started_at + 1.0)
    assert isinstance(countdown, CountdownScreen)
    snapshot_time = started_at + COUNTDOWN
    assert game.wants_people(snapshot_time)
    return game.step(snapshot_time, frame=FRAME, people=strike(countdown.target))


def advance_results(game, snapshot_at, player_count=None, confirm=True):
    """Wait out the results score reveal, then optionally confirm.

    Returns `(screen, next_started_at)` where `next_started_at` is when the
    following countdown began (or idle time if not confirming).
    """
    screen = game.step(snapshot_at)
    assert isinstance(screen, ResultsScreen)
    assert not screen.idle
    idle_at = snapshot_at + game._config.results_reveal_s
    screen = game.step(idle_at)
    assert isinstance(screen, ResultsScreen)
    assert screen.idle
    if not confirm:
        return screen, idle_at
    confirm_at = idle_at + 0.01
    screen = game.step(confirm_at, confirm=True)
    return screen, confirm_at


def play_full_game(game, strike, players=2):
    """Play all five rounds. Returns each round's results and the final screen."""
    start_game(game, players)
    results = []
    screen = None
    started_at = 0.0
    for _ in range(5):
        results.append(play_round(game, started_at, strike))
        snapshot_at = started_at + COUNTDOWN
        screen, started_at = advance_results(game, snapshot_at, players)
    return results, screen


def everyone_perfect(count):
    def strike(target):
        return [
            person_striking(target.joints, center_x=SPOTS[index]) for index in range(count)
        ]

    return strike


def of_type(events, event_type):
    return [event for event in events if isinstance(event, event_type)]


# --- lobby -------------------------------------------------------------------


def test_lobby_asks_for_people_every_step():
    game, _ = new_game()
    assert game.wants_people(0.0)


def test_lobby_numbers_people_left_to_right():
    game, _ = new_game()
    people = [person_striking(T_POSE, center_x=x) for x in (900.0, 100.0, 500.0)]

    screen = game.step(0.0, people=people)

    assert isinstance(screen, LobbyScreen)
    assert [marker.player for marker in screen.markers] == [1, 2, 3]
    centers = [(marker.box[0] + marker.box[2]) / 2 for marker in screen.markers]
    assert centers == [100.0, 500.0, 900.0]


@pytest.mark.parametrize("count", [0, 1, 5])
def test_lobby_refuses_to_start_outside_2_to_4_people(count):
    game, _ = new_game()

    screen = game.step(0.0, confirm=True, people=standing_people(count))

    assert isinstance(screen, LobbyScreen)
    assert not screen.can_start
    assert len(screen.markers) == count


@pytest.mark.parametrize("count", [2, 3, 4])
def test_confirm_with_2_to_4_people_starts_round_1(count):
    game, _ = new_game()
    assert game.step(0.0, people=standing_people(count)).can_start

    screen = game.step(0.0, confirm=True, people=standing_people(count))

    assert isinstance(screen, CountdownScreen)
    assert (screen.round_number, screen.total_rounds, screen.seconds_left) == (1, 5, 5)


def test_debug_lobby_allows_a_solo_player():
    game, _ = new_game(min_players=1, debug=True)

    lobby = game.step(0.0, people=standing_people(1))
    assert lobby.can_start
    assert lobby.min_players == 1

    screen = game.step(0.0, confirm=True, people=standing_people(1))
    assert isinstance(screen, CountdownScreen)

    results = play_round(game, 0.0, everyone_perfect(1))
    assert isinstance(results, ResultsScreen)
    assert len(results.players) == game._config.max_players
    assert results.players[0].round_score == 100
    assert [player.player for player in results.players] == [1, 2, 3, 4]
    assert not results.idle


# --- countdown and snapshot --------------------------------------------------


def test_countdown_shows_5_down_to_1_and_ticks_once_per_number():
    game, events = new_game()
    start_game(game)

    shown = [game.step(now).seconds_left for now in (0.0, 0.5, 0.99, 1.0, 2.0, 3.0, 4.0, 4.99)]

    assert shown == [5, 5, 5, 4, 3, 2, 1, 1]
    assert [tick.seconds_left for tick in of_type(events, CountdownTick)] == [5, 4, 3, 2, 1]


def test_countdown_reports_elapsed_seconds():
    game, _ = new_game()
    start_game(game)

    assert game.step(0.0).elapsed == pytest.approx(0.0)
    assert game.step(1.25).elapsed == pytest.approx(1.25)
    assert game.step(4.5).elapsed == pytest.approx(4.5)


def test_countdown_reports_digit_age():
    game, _ = new_game()
    start_game(game)

    # At elapsed 2.0, remaining is 3.0 → digit "3" just started.
    assert game.step(2.0).seconds_left == 3
    assert game.step(2.0).digit_age == pytest.approx(0.0)
    assert game.step(2.25).digit_age == pytest.approx(0.25)
    assert game.step(3.1).seconds_left == 2
    assert game.step(3.1).digit_age == pytest.approx(0.1)


def test_results_score_stack_clamps_below_header():
    from main.games.strike.game import (
        HEADER_BOTTOM,
        LABEL_GAP_ABOVE_HEAD,
        SCORE_GAP_ABOVE_LABEL,
        _results_score_stack_baselines,
    )

    # Comfortable head position: fixed gaps, no clamp.
    score_y, label_y = _results_score_stack_baselines(400)
    assert label_y == 400 - LABEL_GAP_ABOVE_HEAD
    assert score_y == label_y - SCORE_GAP_ABOVE_LABEL

    # Near the top: whole stack shifts down so the score clears the header.
    score_y, label_y = _results_score_stack_baselines(80)
    assert label_y - score_y == SCORE_GAP_ABOVE_LABEL
    assert score_y >= HEADER_BOTTOM


def test_hand_owner_player_matches_box_then_nearest():
    from main.games.strike.game import hand_owner_player
    from main.games.strike.screens import PlayerResult

    p1 = PlayerResult(1, {}, (0.0, 0.0, 100.0, 200.0), 0, 0)
    p2 = PlayerResult(2, {}, (200.0, 0.0, 300.0, 200.0), 0, 0)
    players = (p1, p2)

    assert hand_owner_player((50.0, 80.0), players) == 1
    assert hand_owner_player((250.0, 80.0), players) == 2
    # Outside both boxes: nearest horizontal center (50 vs 250).
    assert hand_owner_player((160.0, 10.0), players) == 2
    assert hand_owner_player((50.0, 80.0), ()) is None


def test_countdown_target_rect_holds_then_eases_to_top_right():
    from main.games.strike.game import (
        CANVAS_HEIGHT,
        CANVAS_WIDTH,
        COUNTDOWN_MARGIN,
        COUNTDOWN_TARGET_HEIGHT,
        COUNTDOWN_TARGET_WIDTH,
        HEADER_BOTTOM,
        _countdown_target_rect,
    )

    hold = _countdown_target_rect(0.5)
    assert hold[2:] == (COUNTDOWN_TARGET_WIDTH * 2, COUNTDOWN_TARGET_HEIGHT * 2)
    assert hold[0] + hold[2] // 2 == CANVAS_WIDTH // 2
    assert hold[1] + hold[3] // 2 == CANVAS_HEIGHT // 2

    # Still holding at 1.4s; final park is after 1.5s hold + 0.5s ease.
    assert _countdown_target_rect(1.4)[2:] == (COUNTDOWN_TARGET_WIDTH * 2, COUNTDOWN_TARGET_HEIGHT * 2)

    final = _countdown_target_rect(2.0)
    assert final == (
        CANVAS_WIDTH - COUNTDOWN_TARGET_WIDTH - COUNTDOWN_MARGIN,
        HEADER_BOTTOM,
        COUNTDOWN_TARGET_WIDTH,
        COUNTDOWN_TARGET_HEIGHT,
    )

    mid = _countdown_target_rect(1.75)
    assert hold[3] > mid[3] > final[3]
    assert mid[1] < hold[1]
    assert mid[0] > hold[0]


def test_countdown_timer_centered_when_visible():
    from main.games.strike.game import (
        CANVAS_HEIGHT,
        CANVAS_WIDTH,
        TIMER_CENTER_SCALE,
        _baseline_for_vertical_center,
        _countdown_timer_style,
    )

    expected_y = _baseline_for_vertical_center("3", CANVAS_HEIGHT // 2, TIMER_CENTER_SCALE)
    x, y, scale = _countdown_timer_style(3)
    assert (x, y, scale) == (CANVAS_WIDTH // 2, expected_y, TIMER_CENTER_SCALE)
    assert y != CANVAS_HEIGHT // 2  # baseline sits below visual center

    x, y, scale = _countdown_timer_style(1)
    assert (x, scale) == (CANVAS_WIDTH // 2, TIMER_CENTER_SCALE)
    assert y == _baseline_for_vertical_center("1", CANVAS_HEIGHT // 2, TIMER_CENTER_SCALE)


def test_countdown_timer_hidden_until_three_then_blinks_and_fades():
    from main.games.strike.game import (
        TIMER_BLINK_SECONDS,
        TIMER_FADE_SECONDS,
        TIMER_OPACITY,
        _countdown_timer_opacity,
    )

    assert _countdown_timer_opacity(5, 0.5) is None
    assert _countdown_timer_opacity(4, 0.5) is None
    assert _countdown_timer_opacity(0, 0.5) is None

    assert _countdown_timer_opacity(3, 0.0) == 0.0
    assert _countdown_timer_opacity(3, TIMER_BLINK_SECONDS / 2) == 0.0

    mid_fade = _countdown_timer_opacity(3, TIMER_BLINK_SECONDS + TIMER_FADE_SECONDS / 2)
    assert 0.0 < mid_fade < TIMER_OPACITY

    assert _countdown_timer_opacity(2, TIMER_BLINK_SECONDS + TIMER_FADE_SECONDS) == TIMER_OPACITY
    assert _countdown_timer_opacity(1, 1.0) == TIMER_OPACITY


def test_countdown_never_starts_above_5():
    # Float error makes (3.3 + 5.0) - 3.3 come out a hair above 5.
    started_at = 3.3
    assert (started_at + COUNTDOWN) - started_at > COUNTDOWN

    game, _ = new_game()
    assert start_game(game, now=started_at).seconds_left == 5


def test_no_people_are_asked_for_during_the_countdown():
    game, _ = new_game()
    start_game(game)
    assert not game.wants_people(0.0)
    assert not game.wants_people(4.99)
    assert game.wants_people(5.0)


def test_snapshot_fires_once_at_5_seconds():
    game, events = new_game()
    start_game(game)

    assert isinstance(game.step(4.99), CountdownScreen)
    assert of_type(events, SnapshotTaken) == []

    results = game.step(5.0, frame=FRAME, people=standing_people(2))
    assert isinstance(results, ResultsScreen)
    assert of_type(events, SnapshotTaken) == [SnapshotTaken(round_number=1)]

    assert not game.wants_people(6.0)
    later = game.step(6.0)
    assert isinstance(later, ResultsScreen)
    assert later.snapshot is results.snapshot
    assert not later.idle
    idle = game.step(5.0 + game._config.results_reveal_s)
    assert isinstance(idle, ResultsScreen)
    assert idle.idle
    assert game.step(7.0).snapshot is results.snapshot
    assert len(of_type(events, SnapshotTaken)) == 1
    assert len(of_type(events, RoundScored)) == 1


def test_results_keep_the_snapshot_frame():
    game, _ = new_game()
    start_game(game)
    assert play_round(game, 0.0, everyone_perfect(2)).snapshot is FRAME


def test_results_stay_busy_until_reveal_locks_then_accept_confirm():
    game, _ = one_round_game()
    start_game(game)
    results = play_round(
        game,
        0.0,
        lambda target: [
            person_striking(target.joints, center_x=200.0),
            person_striking(mirrored(target.joints), center_x=800.0),
        ],
    )
    assert not results.idle
    assert len(results.players) == 2
    reveal_s = game._config.results_reveal_s

    still_busy = game.step(COUNTDOWN + reveal_s - 0.01, confirm=True)
    assert isinstance(still_busy, ResultsScreen)
    assert not still_busy.idle
    assert still_busy.snapshot is results.snapshot

    # Lock frame ignores confirm (no skip / no same-frame advance).
    idle = game.step(COUNTDOWN + reveal_s, confirm=True)
    assert isinstance(idle, ResultsScreen)
    assert idle.idle
    assert idle.display_scores == tuple(p.round_score for p in idle.players)

    final = game.step(COUNTDOWN + reveal_s + 0.01, confirm=True)
    assert isinstance(final, FinalScreen)


def test_snapshot_without_people_is_a_caller_error():
    game, _ = new_game()
    start_game(game)
    with pytest.raises(ValueError, match="wants_people"):
        game.step(5.0)


def test_confirm_during_the_countdown_does_nothing():
    game, _ = new_game()
    start_game(game)
    screen = game.step(2.0, confirm=True)
    assert isinstance(screen, CountdownScreen)
    assert screen.seconds_left == 3


# --- who gets scored ---------------------------------------------------------


def test_too_few_people_replays_the_round_with_the_same_pose():
    game, events = new_game()
    first = start_game(game, players=3)

    retry = play_round(game, 0.0, lambda target: standing_people(2))

    assert isinstance(retry, RetryScreen)
    assert (retry.found, retry.expected, retry.round_number) == (2, 3, 1)
    assert retry.target == first.target
    assert of_type(events, RoundScored) == []
    assert game.step(8.0) == retry  # waits for a key press

    again = game.step(20.0, confirm=True)
    assert isinstance(again, CountdownScreen)
    assert (again.round_number, again.seconds_left) == (1, 5)
    assert again.target == first.target

    results = play_round(game, 20.0, everyone_perfect(3))
    assert isinstance(results, ResultsScreen)
    assert results.round_number == 1
    assert [player.total for player in results.players] == [100, 100, 100]


def test_bystanders_are_ignored_by_roster_seeds():
    """Snapshot keeps the people nearest the ready-up L→R seeds, not the tallest."""
    game, _ = new_game()
    start_game(game, players=2)  # seeds at SPOTS[0]=200 and SPOTS[1]=500

    def strike(target):
        return [
            person_striking(target.joints, center_x=900.0, height=420.0),  # far bystander
            person_striking(target.joints, center_x=510.0, height=150.0),
            person_striking(target.joints, center_x=190.0, height=400.0),
        ]

    results = play_round(game, 0.0, strike)

    assert isinstance(results, ResultsScreen)
    assert [player.player for player in results.players] == [1, 2]
    centers = [(player.box[0] + player.box[2]) / 2 for player in results.players]
    assert centers == [190.0, 510.0]


# --- scoring inside the game -------------------------------------------------


def one_round_game():
    return new_game(poses=[Pose(name="one-arm-up", joints=dict(ONE_ARM_UP))], rounds=1)


def test_exact_copy_scores_100_and_wrong_way_round_scores_less():
    game, _ = one_round_game()
    start_game(game)

    results = play_round(
        game,
        0.0,
        lambda target: [
            person_striking(target.joints, center_x=200.0),
            person_striking(mirrored(target.joints), center_x=800.0),
        ],
    )

    exact, wrong_way_round = results.players
    assert exact.round_score == 100
    assert wrong_way_round.round_score < 100


def test_low_confidence_joint_counts_as_hidden():
    game, _ = one_round_game()
    start_game(game)

    results = play_round(
        game,
        0.0,
        lambda target: [
            person_striking(target.joints, center_x=200.0, hidden=("left_wrist",)),
            person_striking(target.joints, center_x=800.0),
        ],
    )

    hidden_wrist, fully_visible = results.players
    assert hidden_wrist.round_score == 89  # 8 of 9 segments: 88.9 rounded
    assert "left_wrist" not in hidden_wrist.joints
    assert fully_visible.round_score == 100


def test_round_scored_event_lists_scores_in_player_order():
    game, events = one_round_game()
    start_game(game)

    play_round(
        game,
        0.0,
        lambda target: [
            person_striking(target.joints, center_x=800.0, hidden=tuple(JOINT_NAMES)),
            person_striking(target.joints, center_x=200.0),
        ],
    )

    assert of_type(events, RoundScored) == [
        RoundScored(round_number=1, scores=(100, 0), totals=(100, 0))
    ]


# --- a whole game ------------------------------------------------------------


def test_game_is_five_rounds_of_five_different_poses():
    game, events = new_game()

    results, final = play_full_game(game, everyone_perfect(2))

    assert [result.round_number for result in results] == [1, 2, 3, 4, 5]
    assert len({result.target.name for result in results}) == 5
    assert isinstance(final, FinalScreen)
    assert len(of_type(events, GameOver)) == 1


def test_totals_are_the_sum_of_the_whole_number_round_scores():
    game, _ = new_game()

    def strike(target):
        return [
            person_striking(target.joints, center_x=200.0),
            person_striking(T_POSE, center_x=800.0),  # P2 never moves
        ]

    results, final = play_full_game(game, strike)

    for player_index in (0, 1):
        running_total = 0
        for result in results:
            player = result.players[player_index]
            assert isinstance(player.round_score, int)
            running_total += player.round_score
            assert player.total == running_total

    p2_total = results[-1].players[1].total
    assert 0 < p2_total < 500
    assert final.standings == (
        Standing(place=1, player=1, total=500),
        Standing(place=2, player=2, total=p2_total),
    )


def test_final_screen_carries_every_rounds_score_for_the_points_table():
    game, _ = new_game()

    def strike(target):
        return [
            person_striking(target.joints, center_x=200.0),
            person_striking(T_POSE, center_x=800.0),
        ]

    results, final = play_full_game(game, strike)

    assert final.total_rounds == 5
    assert final.round_scores == tuple(
        tuple(result.players[index].round_score for result in results) for index in (0, 1)
    )
    assert final.round_scores[0] == (100, 100, 100, 100, 100)
    assert sum(final.round_scores[1]) == results[-1].players[1].total


def test_equal_totals_share_first_place():
    game, events = new_game()

    def strike(target):
        return [
            person_striking(target.joints, center_x=200.0),
            person_striking(target.joints, center_x=500.0, hidden=tuple(JOINT_NAMES)),
            person_striking(target.joints, center_x=800.0),
        ]

    _, final = play_full_game(game, strike, players=3)

    assert final.standings == (
        Standing(place=1, player=1, total=500),
        Standing(place=1, player=3, total=500),
        Standing(place=3, player=2, total=0),
    )
    assert of_type(events, GameOver) == [GameOver(standings=final.standings)]


def test_rank_orders_best_first_and_skips_places_after_a_tie():
    assert rank([300, 450, 450, 120]) == (
        Standing(place=1, player=2, total=450),
        Standing(place=1, player=3, total=450),
        Standing(place=3, player=1, total=300),
        Standing(place=4, player=4, total=120),
    )


def test_final_screen_waits_then_returns_to_a_fresh_lobby():
    game, _ = new_game()
    _, final = play_full_game(game, everyone_perfect(2))
    assert game.step(60.0) == final

    lobby = game.step(61.0, confirm=True)
    assert isinstance(lobby, LobbyScreen)
    assert lobby.markers == ()
    assert game.wants_people(61.0)

    start_game(game, players=2, now=70.0)
    results = play_round(game, 70.0, everyone_perfect(2))
    assert (results.round_number, [p.total for p in results.players]) == (1, [100, 100])


def test_too_few_poses_for_the_rounds_is_refused():
    poses = load_library(Config().poses_dir)[:4]
    with pytest.raises(ValueError, match="5 different poses"):
        Game(Config(), poses)


def test_dodgeball_countdown_reuses_strike_timer_look():
    import main.countdown as shared
    from main.games.strike import game as strike_view

    assert strike_view._countdown_timer_opacity is shared.timer_opacity
    assert strike_view.TIMER_CENTER_SCALE == shared.TIMER_CENTER_SCALE == 16.0
# --- results score reveal ----------------------------------------------------


def test_results_scramble_excludes_finals_until_lock():
    game, events = new_game(results_reveal_s=2.0, results_reveal_hz=10.0)
    start_game(game)
    results = play_round(game, 0.0, everyone_perfect(2))
    assert isinstance(results, ResultsScreen)
    finals = tuple(player.round_score for player in results.players)
    assert results.display_scores != finals
    for shown, final in zip(results.display_scores, finals, strict=True):
        assert shown != final
        assert 0 <= shown <= 100

    ticks = of_type(events, ScoreRevealTick)
    assert len(ticks) >= 1
    assert ticks[0].scores == results.display_scores

    # Mid-reveal flash stays scrambled and never equals finals.
    mid = game.step(COUNTDOWN + 1.0)
    assert isinstance(mid, ResultsScreen)
    assert not mid.idle
    for shown, final in zip(mid.display_scores, finals, strict=True):
        assert shown != final

    locked = game.step(COUNTDOWN + game._config.results_reveal_s)
    assert isinstance(locked, ResultsScreen)
    assert locked.idle
    assert locked.display_scores == finals
    assert of_type(events, ScoreRevealLocked) == [ScoreRevealLocked(scores=finals)]


def test_results_reveal_emits_ticks_at_flash_rate():
    game, events = new_game(results_reveal_s=0.5, results_reveal_hz=10.0)
    start_game(game)
    play_round(game, 0.0, everyone_perfect(2))
    # Snapshot already emitted flash 0; step each new 0.1s flash boundary.
    for index in range(1, 5):
        game.step(COUNTDOWN + index * 0.1)
    assert len(of_type(events, ScoreRevealTick)) == 5
    game.step(COUNTDOWN + 0.5)
    assert len(of_type(events, ScoreRevealLocked)) == 1
    assert len(of_type(events, ScoreRevealTick)) == 5


def test_shared_countdown_timer_matches_strike_layout_pixel_for_pixel():
    import numpy as np

    from main.settings import CANVAS_HEIGHT, CANVAS_WIDTH
    from main.games.strike.game import (
        WHITE,
        _countdown_timer_opacity,
        _countdown_timer_style,
        _draw_translucent_text,
        draw_countdown_timer,
    )

    base = np.random.default_rng(0).integers(0, 255, (CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8)
    shared, manual = base.copy(), base.copy()
    draw_countdown_timer(shared, 2, 0.6)
    x, y, scale = _countdown_timer_style(2)
    _draw_translucent_text(manual, "2", x, y, scale, WHITE, _countdown_timer_opacity(2, 0.6))
    assert np.array_equal(shared, manual)
