# Dodgeball

Body-controlled dodgeball: dodge a bouncing ball with your real body, tracked by the webcam.

```sh
python -m main dodgeball
```

Also in this package: `cannonball.py` (Z-axis ball toward the screen). It is not
wired into the menu or CLI right now.

## How to play

- Stand in front of the camera.
- A ball appears and moves around the live feed.
- Avoid getting hit. If the ball touches your body shape, you take a hit and the round pauses.
- Press **R** to restart (5-second countdown). Lowest hit count wins.

## Keys

Shared shell keys (`D` debug, `F` fullscreen, `Esc` menu, `Q` quit) plus:

| Key | Action |
|---|---|
| `R` | Reset (5-second countdown) |

## Files

- `dodgeball.py` — bouncing-ball dodgeball
- `cannonball.py` — Z-axis ball thrown toward the screen
