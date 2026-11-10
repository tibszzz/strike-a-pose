# Dodgeball

Body-controlled dodgeball: dodge a bouncing ball with your real body, tracked by the webcam.

```sh
python -m main dodgeball
```

Also:

```sh
python -m main cannonball
```

## How to play

- Stand in front of the camera.
- A ball appears and bounces around the screen.
- Avoid getting hit. If the ball touches your body shape, you get a hit.
- Lowest hit count wins.

| Key | Action |
|-----|--------|
| R | Reset (5-second countdown) |
| D | Toggle debug overlay |
| F | Toggle fullscreen |
| Q / Esc | Quit |

## Files

- `dodgeball.py` — bouncing-ball dodgeball
- `cannonball.py` — Z-axis ball thrown toward the screen
