"""Gesture → MenuCommand mapper (no MediaPipe / camera)."""

from main.nav import LABEL_TO_COMMAND, GestureCommandMapper, GestureSnapshot, MenuCommand


def snap(label: str | None, score: float = 1.0) -> GestureSnapshot:
    return GestureSnapshot(label=label, score=score)


def test_label_map():
    assert LABEL_TO_COMMAND["Thumb_Up"] is MenuCommand.MOVE_UP
    assert LABEL_TO_COMMAND["Thumb_Down"] is MenuCommand.MOVE_DOWN
    assert LABEL_TO_COMMAND["Victory"] is MenuCommand.SELECT
    assert "Open_Palm" not in LABEL_TO_COMMAND


def test_rising_edge_fires_once():
    mapper = GestureCommandMapper(min_score=0.5, refractory_ms=350)
    assert mapper.feed(snap("Thumb_Up"), 0) is MenuCommand.MOVE_UP
    assert mapper.feed(snap("Thumb_Up"), 50) is None
    assert mapper.feed(snap("Thumb_Up"), 100) is None


def test_hold_does_not_repeat_after_label_switch_without_gap():
    mapper = GestureCommandMapper(min_score=0.5, refractory_ms=350)
    assert mapper.feed(snap("Thumb_Up"), 0) is MenuCommand.MOVE_UP
    # Still in a mapped-gesture streak — no second command until leave + refractory.
    assert mapper.feed(snap("Thumb_Down"), 20) is None
    assert mapper.feed(snap("Victory"), 40) is None


def test_fires_again_after_clear_and_refractory():
    mapper = GestureCommandMapper(min_score=0.5, refractory_ms=350)
    assert mapper.feed(snap("Victory"), 0) is MenuCommand.SELECT
    assert mapper.feed(snap(None), 10) is None  # leave → start refractory
    assert mapper.feed(snap("Victory"), 100) is None  # still in refractory
    assert mapper.feed(snap("Victory"), 360) is MenuCommand.SELECT


def test_below_min_score_ignored():
    mapper = GestureCommandMapper(min_score=0.5, refractory_ms=350)
    assert mapper.feed(snap("Thumb_Up", score=0.49), 0) is None
    assert mapper.feed(snap("Thumb_Up", score=0.5), 10) is MenuCommand.MOVE_UP


def test_unmapped_labels_emit_nothing():
    mapper = GestureCommandMapper(min_score=0.5, refractory_ms=350)
    assert mapper.feed(snap("Open_Palm"), 0) is None
    assert mapper.feed(snap("Closed_Fist"), 20) is None
    assert mapper.feed(snap("ILoveYou"), 40) is None


def test_reset_clears_holding_state():
    mapper = GestureCommandMapper(min_score=0.5, refractory_ms=350)
    assert mapper.feed(snap("Thumb_Up"), 0) is MenuCommand.MOVE_UP
    mapper.reset()
    assert mapper.feed(snap("Thumb_Up"), 10) is MenuCommand.MOVE_UP
