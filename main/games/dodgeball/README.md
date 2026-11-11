# Dodgeball

Body-controlled dodgeball: dodge a bouncing ball with your real body, tracked by the webcam.

```sh
python -m main dodgeball
```

## How to play

- Stand in front of the camera.
- A ball appears and moves around the live feed.
- Each player starts with **5 lives**, shown as hearts in the top-right.
- Avoid getting hit. If the ball touches your body shape, you lose a life and the round pauses.
- Press **R** to resume (5-second countdown). A player with no lives left is out.
- Last player standing wins (solo: play until your lives run out). Press **R** to start a new match.

## Keys

Shared shell keys (`D` debug, `F` fullscreen, `Esc` menu, `Q` quit) plus:

| Key | Action |
|---|---|
| `R` | Reset (5-second countdown) |

## Files

- `dodgeball.py` — bouncing-ball dodgeball