"""Draws the game in one OpenCV window. The only renderer for now.

`compose` turns a screen description into an image without opening a window,
so it can be checked by writing the image to a file. `CvRenderer` owns the
window and the keyboard.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from .detector import Box
from .pose import BONES, HEAD_JOINT, Joints, Point, Pose, midpoint
from .screens import (
    Action,
    CountdownScreen,
    FinalScreen,
    LobbyScreen,
    ResultsScreen,
    RetryScreen,
    Screen,
)

WINDOW_NAME = "Strike a Pose"
CANVAS_WIDTH, CANVAS_HEIGHT = 1280, 720
FONT = cv2.FONT_HERSHEY_DUPLEX

# Colours are (blue, green, red), as OpenCV expects.
BACKGROUND = (30, 26, 24)
PANEL = (52, 46, 42)
WHITE = (255, 255, 255)
MUTED = (175, 175, 175)
ACCENT = (70, 215, 255)
PLAYER_COLORS = (
    (95, 95, 255),  # P1 red
    (255, 175, 70),  # P2 blue
    (110, 230, 110),  # P3 green
    (70, 215, 255),  # P4 yellow
)

# Left, top, width, height, in canvas pixels.
Rect = tuple[int, int, int, int]
FULL_CANVAS: Rect = (0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)


@dataclass(frozen=True)
class Transform:
    """Maps a point from a picture or pose onto the canvas."""

    scale: float
    dx: float
    dy: float

    def apply(self, point: Point) -> tuple[int, int]:
        return (
            round(point[0] * self.scale + self.dx),
            round(point[1] * self.scale + self.dy),
        )


def fit(width: float, height: float, rect: Rect) -> Transform:
    """The transform that fits a width x height area, centred, inside `rect`."""
    left, top, rect_width, rect_height = rect
    scale = min(rect_width / width, rect_height / height)
    return Transform(
        scale=scale,
        dx=left + (rect_width - width * scale) / 2,
        dy=top + (rect_height - height * scale) / 2,
    )


def player_name(player: int) -> str:
    return f"P{player}"


def player_color(player: int) -> tuple[int, int, int]:
    return PLAYER_COLORS[(player - 1) % len(PLAYER_COLORS)]


# --- drawing helpers ---------------------------------------------------------


def new_canvas() -> np.ndarray:
    return np.full((CANVAS_HEIGHT, CANVAS_WIDTH, 3), BACKGROUND, np.uint8)


def draw_text(
    canvas: np.ndarray,
    text: str,
    x: int,
    y: int,
    scale: float = 1.0,
    color: tuple[int, int, int] = WHITE,
    align: str = "left",
    outline: bool = False,
) -> None:
    """Draw text with its baseline at `y`. `align` places `x` at the text's
    left edge, centre or right edge. `outline` keeps text readable over video.
    """
    thickness = max(1, round(scale * 1.6))
    (width, _), _ = cv2.getTextSize(text, FONT, scale, thickness)
    if align == "center":
        x -= width // 2
    elif align == "right":
        x -= width
    if outline:
        cv2.putText(canvas, text, (x, y), FONT, scale, (0, 0, 0), thickness + 4, cv2.LINE_AA)
    cv2.putText(canvas, text, (x, y), FONT, scale, color, thickness, cv2.LINE_AA)


def fill(canvas: np.ndarray, rect: Rect, color: tuple[int, int, int]) -> None:
    left, top, width, height = rect
    canvas[top : top + height, left : left + width] = color


def dim(canvas: np.ndarray, rect: Rect, amount: float = 0.35) -> None:
    """Darken part of the canvas so text on top of video is readable."""
    left, top, width, height = rect
    region = canvas[top : top + height, left : left + width]
    canvas[top : top + height, left : left + width] = (region * amount).astype(np.uint8)


def draw_frame(canvas: np.ndarray, frame: np.ndarray, rect: Rect) -> Transform:
    """Draw a camera frame as large as fits in `rect`, keeping its shape.

    Returns the transform from frame pixels to canvas pixels, for drawing
    things on top of the people in it.
    """
    frame_height, frame_width = frame.shape[:2]
    transform = fit(frame_width, frame_height, rect)
    width = max(1, round(frame_width * transform.scale))
    height = max(1, round(frame_height * transform.scale))
    left, top = round(transform.dx), round(transform.dy)
    method = cv2.INTER_AREA if transform.scale < 1 else cv2.INTER_LINEAR
    canvas[top : top + height, left : left + width] = cv2.resize(
        frame, (width, height), interpolation=method
    )
    return transform


def draw_skeleton(
    canvas: np.ndarray,
    joints: Joints,
    transform: Transform,
    color: tuple[int, int, int],
    thickness: int = 3,
) -> None:
    """Draw the bones whose two joints are both present."""
    for start, end in BONES:
        if start in joints and end in joints:
            cv2.line(
                canvas,
                transform.apply(joints[start]),
                transform.apply(joints[end]),
                color,
                thickness,
                cv2.LINE_AA,
            )
    for name, point in joints.items():
        if any(name in bone for bone in BONES):
            cv2.circle(canvas, transform.apply(point), thickness + 1, color, -1, cv2.LINE_AA)


def draw_box_label(
    canvas: np.ndarray, text: str, box: Box, transform: Transform, color: tuple[int, int, int]
) -> None:
    """Write `text` centred just above a person's box."""
    left, top = transform.apply((box[0], box[1]))
    right, _ = transform.apply((box[2], box[1]))
    draw_text(
        canvas, text, (left + right) // 2, max(top - 12, 40), 1.3, color, "center", outline=True
    )


def _head(joints: Joints) -> tuple[Point, float]:
    """Centre and radius of a stick figure's head, in the pose's own units."""
    shoulders = midpoint(joints, ("left_shoulder", "right_shoulder"))
    hips = midpoint(joints, ("left_hip", "right_hip"))
    assert shoulders is not None and hips is not None
    shoulder_width = math.dist(joints["left_shoulder"], joints["right_shoulder"])
    torso_length = math.dist(shoulders, hips)
    radius = 0.2 * torso_length
    if HEAD_JOINT in joints:
        return joints[HEAD_JOINT], radius
    # No nose in the file: put the head above the shoulders, along the spine.
    up = ((shoulders[0] - hips[0]) / torso_length, (shoulders[1] - hips[1]) / torso_length)
    lift = max(0.7 * shoulder_width, 1.6 * radius)
    return (shoulders[0] + up[0] * lift, shoulders[1] + up[1] * lift), radius


def draw_stick_figure(
    canvas: np.ndarray, joints: Joints, rect: Rect, color: tuple[int, int, int] = WHITE
) -> None:
    """Draw a pose as a stick figure, as large as fits inside `rect`."""
    head_center, head_radius = _head(joints)
    xs = [x for x, _ in joints.values()] + [head_center[0] - head_radius, head_center[0] + head_radius]
    ys = [y for _, y in joints.values()] + [head_center[1] - head_radius, head_center[1] + head_radius]

    left, top, width, height = rect
    margin = round(min(width, height) * 0.08)
    inner: Rect = (left + margin, top + margin, width - 2 * margin, height - 2 * margin)
    placed = fit(max(xs) - min(xs), max(ys) - min(ys), inner)
    transform = Transform(
        scale=placed.scale,
        dx=placed.dx - min(xs) * placed.scale,
        dy=placed.dy - min(ys) * placed.scale,
    )

    thickness = max(3, round(min(width, height) / 55))
    body = {name: point for name, point in joints.items() if name != HEAD_JOINT}
    draw_skeleton(canvas, body, transform, color, thickness)
    cv2.circle(
        canvas,
        transform.apply(head_center),
        round(head_radius * transform.scale),
        color,
        thickness,
        cv2.LINE_AA,
    )


# --- screens -----------------------------------------------------------------


def compose(screen: Screen, frame: np.ndarray) -> np.ndarray:
    """The image for one screen. `frame` is the current mirrored camera frame."""
    if isinstance(screen, LobbyScreen):
        return _compose_lobby(screen, frame)
    if isinstance(screen, CountdownScreen):
        return _compose_countdown(screen, frame)
    if isinstance(screen, RetryScreen):
        return _compose_retry(screen)
    if isinstance(screen, ResultsScreen):
        return _compose_results(screen)
    return _compose_final(screen)


TARGET_PANEL: Rect = (40, 90, 740, 590)
SIDE_LEFT, SIDE_WIDTH = 820, 420
SIDE_CENTER = SIDE_LEFT + SIDE_WIDTH // 2


def _header(canvas: np.ndarray, text: str) -> None:
    draw_text(canvas, text, 40, 62, 1.3)
    draw_text(canvas, "Q: quit", CANVAS_WIDTH - 40, 58, 0.7, MUTED, "right")


def _target_panel(
    canvas: np.ndarray, target: Pose, rect: Rect, caption_height: int, caption_scale: float
) -> None:
    """A panel with the pose's name along the top and its stick figure below."""
    left, top, width, height = rect
    fill(canvas, rect, PANEL)
    draw_text(
        canvas, target.name, left + 16, top + round(caption_height * 0.75), caption_scale, ACCENT
    )
    draw_stick_figure(
        canvas, target.joints, (left, top + caption_height, width, height - caption_height)
    )


def _large_target_panel(canvas: np.ndarray, target: Pose) -> None:
    _target_panel(canvas, target, TARGET_PANEL, caption_height=56, caption_scale=1.0)


def _compose_lobby(screen: LobbyScreen, frame: np.ndarray) -> np.ndarray:
    canvas = new_canvas()
    transform = draw_frame(canvas, frame, FULL_CANVAS)

    for marker in screen.markers:
        color = player_color(marker.player)
        cv2.rectangle(
            canvas,
            transform.apply((marker.box[0], marker.box[1])),
            transform.apply((marker.box[2], marker.box[3])),
            color,
            2,
            cv2.LINE_AA,
        )
        draw_box_label(canvas, player_name(marker.player), marker.box, transform, color)

    dim(canvas, (0, 0, CANVAS_WIDTH, 84))
    draw_text(canvas, "STRIKE A POSE", CANVAS_WIDTH // 2, 58, 1.6, WHITE, "center")
    draw_text(canvas, "Q: quit", CANVAS_WIDTH - 40, 54, 0.7, MUTED, "right")

    count = len(screen.markers)
    dim(canvas, (0, CANVAS_HEIGHT - 84, CANVAS_WIDTH, 84))
    if screen.can_start:
        label = "player" if count == 1 else "players"
        message, color = f"{count} {label} in frame  -  press SPACE to start", ACCENT
    else:
        message = (
            f"Need {screen.min_players} to {screen.max_players} players in frame"
            f"  -  found {count}"
        )
        color = WHITE
    draw_text(canvas, message, CANVAS_WIDTH // 2, CANVAS_HEIGHT - 32, 1.1, color, "center")
    return canvas


def _compose_countdown(screen: CountdownScreen, frame: np.ndarray) -> np.ndarray:
    canvas = new_canvas()
    _header(canvas, f"Round {screen.round_number} of {screen.total_rounds}")
    _large_target_panel(canvas, screen.target)

    draw_text(canvas, str(screen.seconds_left), SIDE_CENTER, 340, 9.0, ACCENT, "center")

    feed: Rect = (SIDE_LEFT, 400, SIDE_WIDTH, 280)
    fill(canvas, feed, PANEL)
    draw_frame(canvas, frame, feed)
    return canvas


def _compose_retry(screen: RetryScreen) -> np.ndarray:
    canvas = new_canvas()
    _header(canvas, f"Round {screen.round_number} of {screen.total_rounds}")
    _large_target_panel(canvas, screen.target)

    draw_text(
        canvas,
        f"Found {screen.found} of {screen.expected} players",
        SIDE_CENTER,
        300,
        1.1,
        ACCENT,
        "center",
    )
    for line_number, line in enumerate(
        ("Everyone back in frame,", "then press SPACE", "to try this pose again.")
    ):
        draw_text(canvas, line, SIDE_CENTER, 370 + line_number * 44, 0.9, WHITE, "center")
    return canvas


def _compose_results(screen: ResultsScreen) -> np.ndarray:
    canvas = new_canvas()
    _header(canvas, f"Round {screen.round_number} of {screen.total_rounds}  -  results")

    photo: Rect = (40, 90, 800, 590)
    fill(canvas, photo, PANEL)
    transform = draw_frame(canvas, screen.snapshot, photo)
    for player in screen.players:
        color = player_color(player.player)
        draw_skeleton(canvas, player.joints, transform, color)
        draw_box_label(canvas, player_name(player.player), player.box, transform, color)

    side_left, side_width = 880, 360
    side_right = side_left + side_width
    _target_panel(
        canvas, screen.target, (side_left, 90, side_width, 240), caption_height=40, caption_scale=0.8
    )

    draw_text(canvas, "PLAYER", side_left + 10, 378, 0.6, MUTED)
    draw_text(canvas, "ROUND", side_left + 215, 378, 0.6, MUTED, "right")
    draw_text(canvas, "TOTAL", side_right - 10, 378, 0.6, MUTED, "right")
    for row, player in enumerate(screen.players):
        y = 432 + row * 58
        color = player_color(player.player)
        draw_text(canvas, player_name(player.player), side_left + 10, y, 1.3, color)
        draw_text(canvas, str(player.round_score), side_left + 215, y, 1.3, WHITE, "right")
        draw_text(canvas, str(player.total), side_right - 10, y, 1.3, WHITE, "right")

    last_round = screen.round_number == screen.total_rounds
    prompt = "SPACE: final scores" if last_round else "SPACE: next round"
    draw_text(canvas, prompt, side_left + side_width // 2, 668, 0.8, ACCENT, "center")
    return canvas


def _winners_line(screen: FinalScreen) -> str:
    winners = [player_name(s.player) for s in screen.standings if s.place == 1]
    if len(winners) == 1:
        return f"{winners[0]} wins!"
    return f"{', '.join(winners[:-1])} and {winners[-1]} share the win!"


def _compose_final(screen: FinalScreen) -> np.ndarray:
    canvas = new_canvas()
    center = CANVAS_WIDTH // 2
    draw_text(canvas, "FINAL SCORES", center, 110, 2.0, WHITE, "center")
    draw_text(canvas, _winners_line(screen), center, 190, 1.4, ACCENT, "center")

    for row, standing in enumerate(screen.standings):
        y = 300 + row * 80
        fill(canvas, (center - 260, y - 54, 520, 68), PANEL)
        draw_text(canvas, f"{standing.place}.", center - 230, y, 1.5, MUTED)
        draw_text(
            canvas, player_name(standing.player), center - 120, y, 1.5, player_color(standing.player)
        )
        draw_text(canvas, str(standing.total), center + 230, y, 1.5, WHITE, "right")

    draw_text(canvas, "SPACE: new game      Q: quit", center, 680, 0.9, MUTED, "center")
    return canvas


# --- the window --------------------------------------------------------------


@dataclass(frozen=True)
class MouseEvent:
    """A pointer event in canvas pixel coordinates."""

    kind: str  # "down", "up", or "move"
    x: int
    y: int


class CvRenderer:
    def __init__(self) -> None:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        cv2.resizeWindow(WINDOW_NAME, CANVAS_WIDTH, CANVAS_HEIGHT)
        self._mouse_events: list[MouseEvent] = []
        cv2.setMouseCallback(WINDOW_NAME, self._on_mouse)

    def _on_mouse(self, event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self._mouse_events.append(MouseEvent("down", x, y))
        elif event == cv2.EVENT_LBUTTONUP:
            self._mouse_events.append(MouseEvent("up", x, y))
        elif event == cv2.EVENT_MOUSEMOVE and (_flags & cv2.EVENT_FLAG_LBUTTON):
            self._mouse_events.append(MouseEvent("move", x, y))

    def show(self, screen: Screen, frame: np.ndarray) -> None:
        self.show_image(compose(screen, frame))

    def show_image(self, image: np.ndarray) -> None:
        cv2.imshow(WINDOW_NAME, image)

    def poll_mouse(self) -> list[MouseEvent]:
        events = self._mouse_events
        self._mouse_events = []
        return events

    def poll_action(self) -> Action | None:
        """Let the window update, and report a key press if there was one."""
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            return Action.QUIT
        if key == ord(" "):
            return Action.CONFIRM
        return None

    def poll_edit_action(self) -> str | None:
        """Keys for the pose editor: confirm, quit, reset, nose, capture."""
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            return "quit"
        if key == ord(" "):
            return "confirm"
        if key in (ord("r"), ord("R")):
            return "reset"
        if key in (ord("n"), ord("N")):
            return "nose"
        if key in (ord("c"), ord("C")):
            return "capture"
        return None

    def close(self) -> None:
        cv2.destroyAllWindows()
