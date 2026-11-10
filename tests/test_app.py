import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.app import draw_skeletons
from main.pose import PoseFrame

from test_gestures import person


def test_draw_skeletons_accepts_yolo_float32_keypoints():
    pygame.init()
    canvas = pygame.Surface((640, 480))
    frame = PoseFrame(np.zeros((480, 640, 3), np.uint8), 0.0, (person(), None), [])
    assert frame.players[0].xy.dtype == np.float32
    draw_skeletons(canvas, frame)  # used to raise "invalid start_pos argument"
