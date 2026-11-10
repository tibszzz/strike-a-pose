"""The webcam, read as a mirror image."""

from __future__ import annotations

import cv2


class CameraError(RuntimeError):
    pass


class Camera:
    def __init__(self, index: int) -> None:
        self._capture = cv2.VideoCapture(index)
        if not self._capture.isOpened():
            raise CameraError(
                f"could not open camera {index}. Check that it is connected and "
                "that this terminal is allowed to use the camera."
            )

    def read(self):
        """One frame, flipped left to right.

        This is the only place the image is flipped. Everything after it
        (detection, scoring, drawing, saved poses) works in what the players
        see on screen, which is what makes the game a mirror.
        """
        ok, frame = self._capture.read()
        if not ok:
            raise CameraError("the camera stopped sending frames")
        return cv2.flip(frame, 1)

    def release(self) -> None:
        self._capture.release()
