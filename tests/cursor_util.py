"""Test helpers for the smoothed hand cursor (main.nav.cursor)."""

from main.settings import GestureNavConfig

GAIN = GestureNavConfig().cursor_gain


def hand_for(x: float, y: float, size=(640, 480), gain: float = GAIN) -> tuple[float, float]:
    """Hand (palm) position that puts an absolute-mode cursor on screen point (x, y)."""
    cx, cy = size[0] / 2, size[1] / 2
    return (cx + (x - cx) / gain, cy + (y - cy) / gain)


def palm_at(x: float, y: float, count: int = 21, wrist=None) -> tuple[tuple[float, float], ...]:
    """21 landmarks all at (x, y) (so the palm centre is there), optional wrist override."""
    pts = [(x, y)] * count
    if wrist is not None:
        pts[0] = wrist
    return tuple(pts)


def landmarks_on(x: float, y: float, size=(640, 480), count: int = 21, wrist=None):
    """Landmarks whose palm puts an absolute-mode (menu / results) cursor on (x, y)."""
    return palm_at(*hand_for(x, y, size), count=count, wrist=wrist)
