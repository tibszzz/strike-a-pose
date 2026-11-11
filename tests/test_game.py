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
    SnapshotTaken,
    Standing,
)

FRAME = object()  # stands in for a camera frame; the game only passes it along
COUNTDOWN = 5.0
ROUND_GAP = 10.0  # seconds between the starts of two rounds in these tests
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


def play_full_game(game, strike, players=2):
    """Play all five rounds. Returns each round's results and the final screen."""
    start_game(game, players)
    results = []
    screen = None
    for round_index in range(5):
        started_at = round_index * ROUND_GAP
        results.append(play_round(game, started_at, strike))
        screen = game.step(started_at + ROUND_GAP, confirm=True)
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
    game, _ = new_game(min_players=1)

    lobby = game.step(0.0, people=standing_people(1))
    assert lobby.can_start
    assert lobby.min_players == 1

    screen = game.step(0.0, confirm=True, people=standing_people(1))
    assert isinstance(screen, CountdownScreen)

    results = play_round(game, 0.0, everyone_perfect(1))
    assert isinstance(results, ResultsScreen)
    assert [player.round_score for player in results.players] == [100]


# --- countdown and snapshot --------------------------------------------------


def test_countdown_shows_5_down_to_1_and_ticks_once_per_number():
    game, events = new_game()
    start_game(game)

    shown = [game.step(now).seconds_left for now in (0.0, 0.5, 0.99, 1.0, 2.0, 3.0, 4.0, 4.99)]

    assert shown == [5, 5, 5, 4, 3, 2, 1, 1]
    assert [tick.seconds_left for tick in of_type(events, CountdownTick)] == [5, 4, 3, 2, 1]


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
    assert game.step(6.0) is results
    assert game.step(7.0) is results
    assert len(of_type(events, SnapshotTaken)) == 1
    assert len(of_type(events, RoundScored)) == 1


def test_results_keep_the_snapshot_frame():
    game, _ = new_game()
    start_game(game)
    assert play_round(game, 0.0, everyone_perfect(2)).snapshot is FRAME


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


def test_bystanders_are_ignored_by_keeping_the_tallest():
    game, _ = new_game()
    start_game(game, players=2)

    def strike(target):
        return [
            person_striking(target.joints, center_x=900.0, height=420.0),
            person_striking(target.joints, center_x=500.0, height=150.0),  # bystander
            person_striking(target.joints, center_x=100.0, height=400.0),
        ]

    results = play_round(game, 0.0, strike)

    assert isinstance(results, ResultsScreen)
    assert [player.player for player in results.players] == [1, 2]
    centers = [(player.box[0] + player.box[2]) / 2 for player in results.players]
    assert centers == [100.0, 900.0]


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
