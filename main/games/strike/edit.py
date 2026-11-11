"""Visually create or edit a pose by dragging joints.

    python -m main.games.strike.edit <pose-name>

Blank panel, T-pose seed for new names. Drag freely; bone lengths stay locked
via live IK. Press C to snap a pose from the webcam, then keep dragging.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from main import content
from main.settings import StrikeConfig as Config
from main.pose.library import (
    HEAD_JOINT,
    Pose,
    PoseError,
    load_pose,
    midpoint,
    pose_from_dict,
    save_pose,
)
from main.pose.tracker import Camera, CameraError, PoseDetector

from .capture import (
    CAPTURE_SECONDS,
    compose_live,
    is_valid_name,
    largest_person,
    pose_from_person,
)
from .edit_fk import (
    TORSO_JOINTS,
    BoneLengths,
    apply_drag,
    clip_translation,
    measure_lengths,
    mid_shoulder,
)
from .game import (
    ACCENT,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    MUTED,
    PANEL,
    WHITE,
    CvRenderer,
    MouseEvent,
    Rect,
    Transform,
    dim,
    draw_skeleton,
    draw_text,
    fill,
    fit,
    new_canvas,
)

EDIT_PANEL: Rect = (270, 90, 740, 540)
HIT_RADIUS = 0.045


class EditPhase(Enum):
    EDITING = auto()
    CAPTURING = auto()
    CONFIRM_OVERWRITE = auto()
    CONFIRM_DISCARD = auto()


@dataclass
class PoseEditor:
    """Pure editor state: joints, dirty tracking, confirm phases."""

    name: str
    path: Path
    joints: dict[str, tuple[float, float]]
    open_joints: dict[str, tuple[float, float]]
    saved_joints: dict[str, tuple[float, float]]
    lengths: BoneLengths
    open_lengths: BoneLengths
    existed_at_open: bool
    nose_offset: tuple[float, float]
    phase: EditPhase = EditPhase.EDITING
    status: str = ""
    _drag_joint: str | None = None
    _drag_origin: tuple[float, float] | None = None
    _drag_joints: dict[str, tuple[float, float]] | None = None

    @classmethod
    def open(
        cls, name: str, path: Path, seed_path: Path
    ) -> PoseEditor:
        seed = load_pose(seed_path)
        shoulders = midpoint(seed.joints, ("left_shoulder", "right_shoulder"))
        assert shoulders is not None and HEAD_JOINT in seed.joints
        nose_offset = (
            seed.joints[HEAD_JOINT][0] - shoulders[0],
            seed.joints[HEAD_JOINT][1] - shoulders[1],
        )

        if path.exists():
            pose = load_pose(path)
            if pose.name != name:
                raise PoseError(
                    f'{path}: name is "{pose.name}", expected "{name}"'
                )
            joints = dict(pose.joints)
            existed = True
        else:
            joints = dict(seed.joints)
            existed = False

        snapshot = {key: point for key, point in joints.items()}
        lengths = measure_lengths(snapshot)
        return cls(
            name=name,
            path=path,
            joints=joints,
            open_joints=dict(snapshot),
            saved_joints=dict(snapshot),
            lengths=lengths,
            open_lengths=lengths,
            existed_at_open=existed,
            nose_offset=nose_offset,
        )

    @property
    def dirty(self) -> bool:
        return self.joints != self.saved_joints

    def prompt(self) -> str:
        if self.status:
            return self.status
        if self.phase is EditPhase.CONFIRM_OVERWRITE:
            return "Overwrite existing file? SPACE: yes      Q: cancel"
        if self.phase is EditPhase.CONFIRM_DISCARD:
            return "Discard unsaved changes? Q: yes      SPACE: keep editing"
        if self.phase is EditPhase.CAPTURING:
            return (
                f"SPACE: capture in {CAPTURE_SECONDS:.0f} seconds      "
                "Q: back to editor"
            )
        dirty = "  (unsaved)" if self.dirty else ""
        return (
            f"drag joints / background      SPACE: save      C: camera      "
            f"R: reset      N: nose      Q: quit{dirty}"
        )

    def confirm(self) -> None:
        self.status = ""
        if self.phase is EditPhase.CAPTURING:
            return
        if self.phase is EditPhase.CONFIRM_DISCARD:
            self.phase = EditPhase.EDITING
            return
        if self.phase is EditPhase.CONFIRM_OVERWRITE:
            self._write()
            return
        if self.existed_at_open:
            self.phase = EditPhase.CONFIRM_OVERWRITE
            return
        self._write()

    def request_quit(self) -> bool:
        """True when the editor should close."""
        self.status = ""
        if self.phase is EditPhase.CAPTURING:
            self.phase = EditPhase.EDITING
            self._clear_drag()
            return False
        if self.phase is EditPhase.CONFIRM_OVERWRITE:
            self.phase = EditPhase.EDITING
            return False
        if self.phase is EditPhase.CONFIRM_DISCARD:
            return True
        if self.dirty:
            self.phase = EditPhase.CONFIRM_DISCARD
            return False
        return True

    def start_capture(self) -> None:
        if self.phase is not EditPhase.EDITING:
            return
        self.status = ""
        self._clear_drag()
        self.phase = EditPhase.CAPTURING

    def apply_capture(self, pose: Pose) -> None:
        """Replace joints with a webcam snap; leave unsaved for further editing."""
        self.joints = dict(pose.joints)
        self.lengths = measure_lengths(self.joints)
        self.phase = EditPhase.EDITING
        self.status = "Captured — drag to refine, SPACE to save"
        self._clear_drag()

    def fail_capture(self, message: str) -> None:
        self.phase = EditPhase.CAPTURING
        self.status = message

    def reset(self) -> None:
        if self.phase is not EditPhase.EDITING:
            return
        self.joints = dict(self.open_joints)
        self.lengths = self.open_lengths
        self.status = ""
        self._clear_drag()

    def toggle_nose(self) -> None:
        if self.phase is not EditPhase.EDITING:
            return
        self.status = ""
        if HEAD_JOINT in self.joints:
            del self.joints[HEAD_JOINT]
            return
        mid = mid_shoulder(self.joints)
        placed = (mid[0] + self.nose_offset[0], mid[1] + self.nose_offset[1])
        if not (0.0 <= placed[0] <= 1.0 and 0.0 <= placed[1] <= 1.0):
            self.status = "Cannot place nose: offset leaves the panel"
            return
        self.joints[HEAD_JOINT] = placed

    def pointer_down(self, cursor: tuple[float, float]) -> None:
        if self.phase is not EditPhase.EDITING:
            return
        self.status = ""
        hit = nearest_joint(self.joints, cursor, HIT_RADIUS)
        if hit is not None:
            self._drag_joint = hit
            self._drag_origin = None
            self._drag_joints = None
            return
        if 0.0 <= cursor[0] <= 1.0 and 0.0 <= cursor[1] <= 1.0:
            self._drag_joint = None
            self._drag_origin = cursor
            self._drag_joints = dict(self.joints)

    def pointer_move(self, cursor: tuple[float, float]) -> None:
        if self.phase is not EditPhase.EDITING:
            return
        if self._drag_joint is not None:
            proposed = apply_drag(
                self.joints, self._drag_joint, cursor, self.lengths
            )
            if proposed is not None:
                self.joints = proposed
            return
        if self._drag_origin is not None and self._drag_joints is not None:
            dx = cursor[0] - self._drag_origin[0]
            dy = cursor[1] - self._drag_origin[1]
            self.joints = clip_translation(self._drag_joints, dx, dy)

    def pointer_up(self) -> None:
        self._clear_drag()

    def _write(self) -> None:
        rounded = {
            name: (round(x, 3), round(y, 3)) for name, (x, y) in self.joints.items()
        }
        try:
            pose = pose_from_dict(
                {
                    "name": self.name,
                    "joints": {name: [x, y] for name, (x, y) in rounded.items()},
                }
            )
        except PoseError as error:
            self.phase = EditPhase.EDITING
            self.status = f"Not saved: {error}"
            return
        save_pose(pose, self.path)
        self.joints = dict(pose.joints)
        self.saved_joints = dict(pose.joints)
        self.phase = EditPhase.EDITING
        self.status = f"Saved {self.path.name}"

    def _clear_drag(self) -> None:
        self._drag_joint = None
        self._drag_origin = None
        self._drag_joints = None


def nearest_joint(
    joints: dict[str, tuple[float, float]],
    cursor: tuple[float, float],
    radius: float,
) -> str | None:
    best_name = None
    best_dist = radius
    for name, point in joints.items():
        dist = ((point[0] - cursor[0]) ** 2 + (point[1] - cursor[1]) ** 2) ** 0.5
        if dist <= best_dist:
            best_dist = dist
            best_name = name
    return best_name


def unit_transform(rect: Rect) -> Transform:
    """Map the unit square into `rect` (with margin), fixed while editing."""
    left, top, width, height = rect
    margin = round(min(width, height) * 0.08)
    inner: Rect = (left + margin, top + margin, width - 2 * margin, height - 2 * margin)
    return fit(1.0, 1.0, inner)


def canvas_to_unit(transform: Transform, x: int, y: int) -> tuple[float, float]:
    return ((x - transform.dx) / transform.scale, (y - transform.dy) / transform.scale)


def compose_editor(editor: PoseEditor, transform: Transform) -> np.ndarray:
    canvas = new_canvas()
    title = content.Strike.edit_title.format(name=editor.name)
    if editor.existed_at_open:
        title += " (existing)"
    else:
        title += " (new)"
    draw_text(canvas, title, CANVAS_WIDTH // 2, 58, 1.4, WHITE, "center")

    fill(canvas, EDIT_PANEL, PANEL)
    thickness = max(3, round(min(EDIT_PANEL[2], EDIT_PANEL[3]) / 55))
    body = {name: point for name, point in editor.joints.items() if name != HEAD_JOINT}
    draw_skeleton(canvas, body, transform, WHITE, thickness)

    head = editor.joints.get(HEAD_JOINT)
    if head is not None:
        shoulders = mid_shoulder(editor.joints)
        hips = midpoint(editor.joints, ("left_hip", "right_hip"))
        assert hips is not None
        torso_length = ((shoulders[0] - hips[0]) ** 2 + (shoulders[1] - hips[1]) ** 2) ** 0.5
        radius = max(round(0.2 * torso_length * transform.scale), 4)
        cv2.circle(canvas, transform.apply(head), radius, WHITE, thickness, cv2.LINE_AA)

    for name, point in editor.joints.items():
        color = ACCENT if name in TORSO_JOINTS or name == HEAD_JOINT else WHITE
        cv2.circle(canvas, transform.apply(point), 8, color, -1, cv2.LINE_AA)
        cv2.circle(canvas, transform.apply(point), 8, ACCENT, 1, cv2.LINE_AA)

    dim(canvas, (0, CANVAS_HEIGHT - 84, CANVAS_WIDTH, 84))
    draw_text(
        canvas, editor.prompt(), CANVAS_WIDTH // 2, CANVAS_HEIGHT - 32, 0.75, MUTED, "center"
    )
    return canvas


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m main.games.strike.edit",
        description="Create or edit a pose by dragging stick-figure joints.",
    )
    parser.add_argument("name", help="lowercase words joined by dashes, like arms-up")
    name = parser.parse_args(argv).name

    config = Config()
    path = config.poses_dir / f"{name}.json"
    seed_path = config.poses_dir / "t-pose.json"

    if not is_valid_name(name):
        print(
            f'Cannot use "{name}" as a pose name: use lowercase letters, digits '
            "and dashes, like arms-up.",
            file=sys.stderr,
        )
        return 1
    if not seed_path.exists():
        print(f"Missing seed pose: {seed_path}", file=sys.stderr)
        return 1

    try:
        editor = PoseEditor.open(name, path, seed_path)
    except PoseError as error:
        print(f"Cannot open: {error}", file=sys.stderr)
        return 1

    transform = unit_transform(EDIT_PANEL)
    renderer = CvRenderer()
    camera: Camera | None = None
    detector: PoseDetector | None = None
    deadline: float | None = None
    capture_idle = f"SPACE: capture in {CAPTURE_SECONDS:.0f} seconds      Q: back to editor"

    def ensure_camera() -> str | None:
        nonlocal camera, detector
        if camera is not None and detector is not None:
            return None
        try:
            detector = PoseDetector(config.model_path)
            camera = Camera(config.camera_index)
        except (CameraError, FileNotFoundError) as error:
            camera = None
            detector = None
            return str(error)
        return None

    try:
        while True:
            if editor.phase is EditPhase.CAPTURING:
                assert camera is not None and detector is not None
                frame = camera.read()
                now = time.monotonic()
                person = largest_person(detector.detect(frame))
                if deadline is not None and now >= deadline:
                    deadline = None
                    try:
                        if person is None:
                            raise PoseError("nobody is in frame")
                        snapped = pose_from_person(
                            editor.name, person, config.joint_confidence
                        )
                    except PoseError as error:
                        editor.fail_capture(
                            f"Not captured: {error}. SPACE: try again"
                        )
                    else:
                        editor.apply_capture(snapped)

                seconds_left = None
                if deadline is not None:
                    seconds_left = min(
                        math.ceil(deadline - now), math.ceil(CAPTURE_SECONDS)
                    )
                message = editor.status if editor.status else capture_idle
                if editor.phase is EditPhase.CAPTURING:
                    renderer.show_image(
                        compose_live(
                            frame,
                            person,
                            editor.name,
                            config.joint_confidence,
                            seconds_left,
                            message,
                            title=f"Capture to edit: {editor.name}",
                        )
                    )
                    action = renderer.poll_edit_action()
                    if action == "confirm" and deadline is None:
                        editor.status = ""
                        deadline = time.monotonic() + CAPTURE_SECONDS
                    elif action == "quit":
                        deadline = None
                        editor.request_quit()
                    continue

            renderer.show_image(compose_editor(editor, transform))
            for event in renderer.poll_mouse():
                cursor = canvas_to_unit(transform, event.x, event.y)
                if event.kind == "down":
                    editor.pointer_down(cursor)
                elif event.kind == "move":
                    editor.pointer_move(cursor)
                else:
                    editor.pointer_up()

            action = renderer.poll_edit_action()
            if action is None:
                continue
            if action == "confirm":
                editor.confirm()
            elif action == "capture":
                error = ensure_camera()
                if error is not None:
                    editor.status = f"Camera unavailable: {error}"
                else:
                    deadline = None
                    editor.start_capture()
            elif action == "reset":
                editor.reset()
            elif action == "nose":
                editor.toggle_nose()
            elif action == "quit":
                if editor.request_quit():
                    break
    except CameraError as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    finally:
        if camera is not None:
            camera.release()
        renderer.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
