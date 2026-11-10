"""Add a pose to the library by striking it at the webcam.

    python -m strike_a_pose.capture <pose-name>

Shows the mirrored feed with a skeleton on the largest person in frame. SPACE
starts a 3 second countdown; at zero that person's pose is saved to the pose
folder. The whole body must be in frame.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import time
from typing import Sequence

import numpy as np

from ...camera import Camera, CameraError
from ...config import Config
from .detector import Person, PoseDetector
from .pose import (
    BODY_JOINTS,
    POSE_FILE_JOINTS,
    Pose,
    PoseError,
    normalize_joints,
    pose_from_dict,
    save_pose,
)
from ...render_cv import (
    ACCENT,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FULL_CANVAS,
    PANEL,
    WHITE,
    CvRenderer,
    dim,
    draw_frame,
    draw_skeleton,
    draw_stick_figure,
    draw_text,
    fill,
    new_canvas,
)
from .screens import Action

CAPTURE_SECONDS = 3.0
NAME_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def is_valid_name(name: str) -> bool:
    """Lowercase words joined by dashes, like `arms-up`."""
    return NAME_PATTERN.fullmatch(name) is not None


def largest_person(people: Sequence[Person]) -> Person | None:
    return max(people, key=lambda person: person.height, default=None)


def pose_from_person(name: str, person: Person, min_confidence: float) -> Pose:
    """Turn a detected person into a pose the game can use as a target."""
    visible = person.visible_joints(min_confidence)
    hidden = [joint for joint in BODY_JOINTS if joint not in visible]
    if hidden:
        raise PoseError(f"the camera cannot see: {', '.join(hidden)}")
    joints = normalize_joints(
        {joint: visible[joint] for joint in POSE_FILE_JOINTS if joint in visible}
    )
    # Rounded here so the pose in memory is exactly what the file will hold.
    return pose_from_dict(
        {
            "name": name,
            "joints": {joint: [round(x, 3), round(y, 3)] for joint, (x, y) in joints.items()},
        }
    )


def compose_live(
    frame: np.ndarray,
    person: Person | None,
    name: str,
    min_confidence: float,
    seconds_left: int | None,
    message: str,
) -> np.ndarray:
    canvas = new_canvas()
    transform = draw_frame(canvas, frame, FULL_CANVAS)
    if person is not None:
        draw_skeleton(canvas, person.visible_joints(min_confidence), transform, ACCENT)

    dim(canvas, (0, 0, CANVAS_WIDTH, 84))
    draw_text(canvas, f"New pose: {name}", CANVAS_WIDTH // 2, 58, 1.4, WHITE, "center")
    if seconds_left is not None:
        # Off to the side, so the number does not cover the person posing.
        draw_text(
            canvas, str(seconds_left), CANVAS_WIDTH - 130, 300, 6.0, ACCENT, "center", outline=True
        )
    dim(canvas, (0, CANVAS_HEIGHT - 84, CANVAS_WIDTH, 84))
    draw_text(canvas, message, CANVAS_WIDTH // 2, CANVAS_HEIGHT - 32, 0.9, WHITE, "center")
    return canvas


def compose_saved(pose: Pose) -> np.ndarray:
    canvas = new_canvas()
    draw_text(canvas, f"Saved: {pose.name}", CANVAS_WIDTH // 2, 62, 1.4, WHITE, "center")
    panel = (270, 90, 740, 540)
    fill(canvas, panel, PANEL)
    draw_stick_figure(canvas, pose.joints, panel)
    draw_text(canvas, "SPACE or Q: close", CANVAS_WIDTH // 2, 680, 0.9, ACCENT, "center")
    return canvas


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m strike_a_pose.capture",
        description="Save a pose from the webcam into the pose library.",
    )
    parser.add_argument("name", help="lowercase words joined by dashes, like arms-up")
    name = parser.parse_args(argv).name

    config = Config()
    path = config.poses_dir / f"{name}.json"
    if not is_valid_name(name):
        print(
            f'Cannot use "{name}" as a pose name: use lowercase letters, digits '
            "and dashes, like arms-up.",
            file=sys.stderr,
        )
        return 1
    if path.exists():
        print(
            f"{path} already exists. Pick another name, or delete that file first.",
            file=sys.stderr,
        )
        return 1

    try:
        detector = PoseDetector(config.model_path)
        camera = Camera(config.camera_index)
    except (CameraError, FileNotFoundError) as error:
        print(f"Cannot start: {error}", file=sys.stderr)
        return 1

    idle_message = f"SPACE: capture in {CAPTURE_SECONDS:.0f} seconds      Q: quit"
    renderer = CvRenderer()
    saved: Pose | None = None
    try:
        deadline: float | None = None
        message = idle_message
        action = None
        while action is not Action.QUIT and saved is None:
            frame = camera.read()
            now = time.monotonic()
            person = largest_person(detector.detect(frame))

            if deadline is None and action is Action.CONFIRM:
                deadline = now + CAPTURE_SECONDS
                message = "Hold the pose..."
            if deadline is not None and now >= deadline:
                deadline = None
                try:
                    if person is None:
                        raise PoseError("nobody is in frame")
                    saved = pose_from_person(name, person, config.joint_confidence)
                except PoseError as error:
                    print(f"Not saved: {error}", file=sys.stderr)
                    message = "Not saved: your whole body must be in frame. SPACE: try again"
                else:
                    save_pose(saved, path)
                    print(f"Saved {path}")

            seconds_left = None
            if deadline is not None:
                # Capped for the same float-error reason as the game's countdown.
                seconds_left = min(math.ceil(deadline - now), math.ceil(CAPTURE_SECONDS))
            renderer.show_image(
                compose_live(frame, person, name, config.joint_confidence, seconds_left, message)
            )
            action = renderer.poll_action()

        while saved is not None and action is None:
            renderer.show_image(compose_saved(saved))
            action = renderer.poll_action()
    except CameraError as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    finally:
        camera.release()
        renderer.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
