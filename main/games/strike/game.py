"""Draws the game in one OpenCV window. The only renderer for now.

`compose` turns a screen description into an image without opening a window,
so it can be checked by writing the image to a file. `CvRenderer` owns the
window and the keyboard.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np

from main import content, styles
from main.nav.hand_geometry import (
    HAND_CONNECTIONS,
    hand_ring_radius,
    palm_center,
    primary_landmarks,
    show_hold_ring,
)
from main.pose.library import BONES, HEAD_JOINT, Box, Joints, Point, Pose, midpoint
from main.settings import CANVAS_HEIGHT, CANVAS_WIDTH

from .screens import (
    Action,
    CountdownScreen,
    FinalScreen,
    LobbyScreen,
    ResultsScreen,
    RetryScreen,
    Screen,
)

theme = styles.STRIKE
copy = content.Strike

WINDOW_NAME = copy.window_title

# OpenCV wants BGR; Theme stores RGB.
BACKGROUND = styles.bgr(theme.bg)
PANEL = styles.bgr(theme.panel)
WHITE = styles.bgr(theme.ink)
MUTED = styles.bgr(theme.muted)
ACCENT = styles.bgr(theme.accent)
PLAYER_COLORS = tuple(styles.bgr(c) for c in theme.player)
HOLD_FILL = styles.bgr((85, 221, 224))  # #55dde0 progress arc
HAND_TRACK = ACCENT  # #f6ae2d skeleton + ring track

# Results score stack: large score over P#, anchored above the head.
SCORE_SCALE = 1.6
PLAYER_LABEL_SCALE = 0.9
SCORE_GAP_ABOVE_LABEL = 28  # score baseline above P# baseline
LABEL_GAP_ABOVE_HEAD = 10  # P# baseline above head top
RESULTS_PROMPT_Y = CANVAS_HEIGHT - 48

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
    return copy.player_label.format(player=player)


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

    `color` is BGR (OpenCV); shared renderer wants RGB.
    Font pixels scale with canvas height (design sizes at CANVAS_HEIGHT).
    """
    styles.draw_text(
        canvas,
        text,
        x,
        y,
        scale,
        color=(color[2], color[1], color[0]),
        align=align,
        outline=outline,
        face=theme.font,
        h=canvas.shape[0],
    )


def fill(canvas: np.ndarray, rect: Rect, color: tuple[int, int, int]) -> None:
    left, top, width, height = rect
    canvas[top : top + height, left : left + width] = color


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
    canvas: np.ndarray,
    joints: Joints,
    rect: Rect,
    color: tuple[int, int, int] = WHITE,
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

# Countdown target HUD: final size ~18% of canvas height, parked top-right
# under the header. Intro holds 2x at center for 1.5s, then eases over 0.5s.
HEADER_BOTTOM = 70
COUNTDOWN_MARGIN = 40
COUNTDOWN_TARGET_HEIGHT = 130
COUNTDOWN_TARGET_WIDTH = 200
COUNTDOWN_HOLD_SECONDS = 1.5
COUNTDOWN_EASE_SECONDS = 0.5
TIMER_OPACITY = 0.65
TIMER_CENTER_SCALE = 16.0
TIMER_VISIBLE_AT_SECONDS = 3
TIMER_BLINK_SECONDS = 0.06
TIMER_FADE_SECONDS = 0.28


def _header(canvas: np.ndarray, text: str, *, show_esc: bool = True) -> None:
    draw_text(canvas, text, 40, 62, 1.3)
    if show_esc:
        draw_text(canvas, copy.esc_menu, CANVAS_WIDTH - 40, 58, 0.7, MUTED, "right")


def _ease_out(t: float) -> float:
    """Cubic ease-out for t in [0, 1]."""
    u = 1.0 - t
    return 1.0 - u * u * u


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _countdown_target_rect(elapsed: float) -> Rect:
    """Where the target stick figure sits for a given countdown elapsed time."""
    final_w, final_h = COUNTDOWN_TARGET_WIDTH, COUNTDOWN_TARGET_HEIGHT
    final_left = CANVAS_WIDTH - final_w - COUNTDOWN_MARGIN
    final_top = HEADER_BOTTOM
    final_cx = final_left + final_w / 2
    final_cy = final_top + final_h / 2

    start_w, start_h = final_w * 2, final_h * 2
    start_cx = CANVAS_WIDTH / 2
    start_cy = CANVAS_HEIGHT / 2

    if elapsed < COUNTDOWN_HOLD_SECONDS:
        t = 0.0
    elif elapsed < COUNTDOWN_HOLD_SECONDS + COUNTDOWN_EASE_SECONDS:
        t = _ease_out((elapsed - COUNTDOWN_HOLD_SECONDS) / COUNTDOWN_EASE_SECONDS)
    else:
        t = 1.0

    w = _lerp(start_w, final_w, t)
    h = _lerp(start_h, final_h, t)
    cx = _lerp(start_cx, final_cx, t)
    cy = _lerp(start_cy, final_cy, t)
    return (round(cx - w / 2), round(cy - h / 2), round(w), round(h))


def _baseline_for_vertical_center(text: str, center_y: int, scale: float) -> int:
    """Baseline that places the glyph's visual center at `center_y`."""
    (_, height), descent = styles.text_size(text, scale, theme.font, h=CANVAS_HEIGHT)
    return round(center_y + (height - descent) / 2)


def _countdown_timer_style(seconds_left: int) -> tuple[int, int, float]:
    """Centered large timer layout for a visible countdown digit."""
    text = str(seconds_left)
    return (
        CANVAS_WIDTH // 2,
        _baseline_for_vertical_center(text, CANVAS_HEIGHT // 2, TIMER_CENTER_SCALE),
        TIMER_CENTER_SCALE,
    )


def _countdown_timer_opacity(seconds_left: int, digit_age: float) -> float | None:
    """Hide until 3s; each new digit blinks off briefly then fades in."""
    if seconds_left > TIMER_VISIBLE_AT_SECONDS or seconds_left <= 0:
        return None
    if digit_age < TIMER_BLINK_SECONDS:
        return 0.0
    fade_t = (digit_age - TIMER_BLINK_SECONDS) / TIMER_FADE_SECONDS
    if fade_t >= 1.0:
        return TIMER_OPACITY
    return TIMER_OPACITY * _ease_out(max(0.0, min(1.0, fade_t)))


def _draw_translucent_text(
    canvas: np.ndarray,
    text: str,
    x: int,
    y: int,
    scale: float,
    color: tuple[int, int, int],
    opacity: float,
) -> None:
    """Draw outlined text blended onto the canvas at `opacity`."""
    overlay = canvas.copy()
    draw_text(overlay, text, x, y, scale, color, "center", outline=True)
    cv2.addWeighted(overlay, opacity, canvas, 1.0 - opacity, 0, canvas)


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

    draw_text(canvas, copy.banner, CANVAS_WIDTH // 2, 58, 1.6, WHITE, "center", outline=True)
    draw_text(canvas, copy.quit_key, CANVAS_WIDTH - 40, 54, 0.7, MUTED, "right", outline=True)

    count = len(screen.markers)
    if screen.can_start:
        label = "player" if count == 1 else "players"
        message = copy.lobby_ready.format(count=count, label=label)
        color = ACCENT
    else:
        message = (
            copy.lobby_need.format(min_players=screen.min_players, max_players=screen.max_players)
            + f"  -  found {count}"
        )
        color = WHITE
    draw_text(
        canvas, message, CANVAS_WIDTH // 2, CANVAS_HEIGHT - 32, 1.1, color, "center", outline=True
    )
    return canvas


def _compose_countdown(screen: CountdownScreen, frame: np.ndarray) -> np.ndarray:
    canvas = new_canvas()
    draw_frame(canvas, frame, FULL_CANVAS)
    _header(
        canvas,
        copy.round_of.format(round_number=screen.round_number, total_rounds=screen.total_rounds),
        show_esc=False,
    )
    draw_stick_figure(
        canvas, screen.target.joints, _countdown_target_rect(screen.elapsed), WHITE
    )
    opacity = _countdown_timer_opacity(screen.seconds_left, screen.digit_age)
    if opacity is not None and opacity > 0:
        timer_x, timer_y, timer_scale = _countdown_timer_style(screen.seconds_left)
        _draw_translucent_text(
            canvas,
            str(screen.seconds_left),
            timer_x,
            timer_y,
            timer_scale,
            WHITE,
            opacity,
        )
    return canvas


def _compose_retry(screen: RetryScreen) -> np.ndarray:
    canvas = new_canvas()
    _header(
        canvas,
        copy.round_of.format(round_number=screen.round_number, total_rounds=screen.total_rounds),
    )
    _large_target_panel(canvas, screen.target)

    draw_text(
        canvas,
        copy.found_players.format(found=screen.found, expected=screen.expected),
        SIDE_CENTER,
        300,
        1.1,
        ACCENT,
        "center",
    )
    for line_number, line in enumerate(copy.missing_retry):
        draw_text(canvas, line, SIDE_CENTER, 370 + line_number * 44, 0.9, WHITE, "center")
    return canvas


def _parked_target_rect() -> Rect:
    """Countdown HUD parked top-right (after intro animation)."""
    return _countdown_target_rect(COUNTDOWN_HOLD_SECONDS + COUNTDOWN_EASE_SECONDS)


def _head_anchor_xy(joints: Joints, box: Box, transform: Transform) -> tuple[int, int]:
    """Canvas pixel at the top of the head (nose if present, else box top center)."""
    if "nose" in joints:
        return transform.apply(joints["nose"])
    left, top = transform.apply((box[0], box[1]))
    right, _ = transform.apply((box[2], box[1]))
    return (left + right) // 2, top


def _results_score_stack_baselines(head_y: int) -> tuple[int, int]:
    """Score and P# baselines above the head, clamped below the header."""
    label_y = head_y - LABEL_GAP_ABOVE_HEAD
    score_y = label_y - SCORE_GAP_ABOVE_LABEL
    (_, ascent), _ = styles.text_size("88", SCORE_SCALE, theme.font, h=CANVAS_HEIGHT)
    score_top = score_y - ascent
    if score_top < HEADER_BOTTOM:
        shift = HEADER_BOTTOM - score_top
        score_y += shift
        label_y += shift
    return score_y, label_y


def _draw_results_player_stack(
    canvas: np.ndarray,
    player_number: int,
    round_score: int,
    joints: Joints,
    box: Box,
    transform: Transform,
    color: tuple[int, int, int],
) -> None:
    head_x, head_y = _head_anchor_xy(joints, box, transform)
    score_y, label_y = _results_score_stack_baselines(head_y)
    draw_text(
        canvas,
        str(round_score),
        head_x,
        score_y,
        SCORE_SCALE,
        color,
        "center",
        outline=True,
    )
    draw_text(
        canvas,
        player_name(player_number),
        head_x,
        label_y,
        PLAYER_LABEL_SCALE,
        color,
        "center",
        outline=True,
    )


def _compose_results(screen: ResultsScreen) -> np.ndarray:
    canvas = new_canvas()
    transform = draw_frame(canvas, screen.snapshot, FULL_CANVAS)
    _header(
        canvas,
        copy.round_results.format(
            round_number=screen.round_number, total_rounds=screen.total_rounds
        ),
        show_esc=False,
    )
    draw_stick_figure(canvas, screen.target.joints, _parked_target_rect(), WHITE)

    for player in screen.players:
        color = player_color(player.player)
        draw_skeleton(canvas, player.joints, transform, color)
        _draw_results_player_stack(
            canvas,
            player.player,
            player.round_score,
            player.joints,
            player.box,
            transform,
            color,
        )

    if screen.idle:
        _draw_results_prompt(
            canvas, final_round=screen.round_number == screen.total_rounds
        )

    return canvas


def _draw_results_prompt(canvas: np.ndarray, *, final_round: bool) -> None:
    prompt = copy.results_thumbs_final if final_round else copy.results_thumbs
    draw_text(
        canvas,
        prompt,
        CANVAS_WIDTH // 2,
        RESULTS_PROMPT_Y,
        0.9,
        ACCENT,
        "center",
        outline=True,
    )


def hand_owner_player(
    anchor: tuple[float, float],
    players: Sequence,
) -> int | None:
    """Player whose results box owns this hand; nearest box center as fallback."""
    if not players:
        return None
    ax, ay = anchor
    for player in players:
        x0, y0, x1, y1 = player.box
        if x0 <= ax <= x1 and y0 <= ay <= y1:
            return player.player
    return min(
        players,
        key=lambda p: abs(ax - (p.box[0] + p.box[2]) / 2.0),
    ).player


def draw_hand_skeleton(
    canvas: np.ndarray,
    landmarks: Sequence[tuple[float, float]],
    transform: Transform,
    color: tuple[int, int, int] = HAND_TRACK,
) -> None:
    """Draw MediaPipe hand bones and joints in canvas space."""
    if len(landmarks) < 2:
        return
    pts = [transform.apply(p) for p in landmarks]
    for a, b in HAND_CONNECTIONS:
        if a < len(pts) and b < len(pts):
            cv2.line(canvas, pts[a], pts[b], color, 2, cv2.LINE_AA)
    for pt in pts:
        cv2.circle(canvas, pt, 3, color, -1, cv2.LINE_AA)


def draw_hold_ring(
    canvas: np.ndarray,
    center: tuple[float, float],
    radius: float,
    progress: float,
    transform: Transform,
    *,
    track_color: tuple[int, int, int] = HAND_TRACK,
    fill_color: tuple[int, int, int] = HOLD_FILL,
) -> None:
    """Faint track circle + bright progress arc around the palm."""
    if radius <= 1:
        return
    cx, cy = transform.apply(center)
    r = max(4, round(radius * transform.scale))
    # Track at lower opacity via a darkened accent blend.
    track = tuple(int(c * 0.45) for c in track_color)
    cv2.circle(canvas, (cx, cy), r, track, 3, cv2.LINE_AA)
    if progress <= 0:
        return
    sweep = 360.0 * min(1.0, progress)
    cv2.ellipse(
        canvas,
        (cx, cy),
        (r, r),
        0,
        -90,
        -90 + sweep,
        fill_color,
        5,
        cv2.LINE_AA,
    )


def overlay_results_hold(
    canvas: np.ndarray,
    progress: float,
    *,
    final_round: bool,
    snap: object | None = None,
    frame_size: tuple[int, int] | None = None,
    players: Sequence = (),
) -> None:
    """Prompt, primary-hand skeleton, and palm hold ring after compose."""
    _draw_results_prompt(canvas, final_round=final_round)
    if snap is None or frame_size is None:
        return
    fw, fh = frame_size
    if fw <= 0 or fh <= 0:
        return
    transform = fit(fw, fh, FULL_CANVAS)

    # Single primary hand only (MediaPipe is configured for one hand on results).
    primary = primary_landmarks(snap)
    if primary:
        wrist = primary[0]
        owner = hand_owner_player(wrist, players)
        color = player_color(owner) if owner is not None else HAND_TRACK
        draw_hand_skeleton(canvas, primary, transform, color)

    box = getattr(snap, "hand_box", None)
    if primary and show_hold_ring(progress, getattr(snap, "label", None)):
        center = palm_center(primary)
        if center is not None:
            radius = hand_ring_radius(box) if box is not None else 40.0
            draw_hold_ring(canvas, center, radius, progress, transform)


def _winners_line(screen: FinalScreen) -> str:
    winners = [player_name(s.player) for s in screen.standings if s.place == 1]
    if len(winners) == 1:
        return copy.winner_one.format(name=winners[0])
    return f"{', '.join(winners[:-1])} and {winners[-1]} share the win!"


def _compose_final(screen: FinalScreen) -> np.ndarray:
    canvas = new_canvas()
    center = CANVAS_WIDTH // 2
    draw_text(canvas, copy.final_scores, center, 110, 2.0, WHITE, "center")
    draw_text(canvas, _winners_line(screen), center, 190, 1.4, ACCENT, "center")

    for row, standing in enumerate(screen.standings):
        y = 300 + row * 80
        fill(canvas, (center - 260, y - 54, 520, 68), PANEL)
        draw_text(canvas, f"{standing.place}.", center - 230, y, 1.5, MUTED)
        draw_text(
            canvas, player_name(standing.player), center - 120, y, 1.5, player_color(standing.player)
        )
        draw_text(canvas, str(standing.total), center + 230, y, 1.5, WHITE, "right")

    draw_text(canvas, copy.space_new_game, center, 680, 0.9, MUTED, "center")
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
