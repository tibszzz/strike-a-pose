# Dodgeball

Body-controlled dodgeball: dodge a bouncing ball with your real body, tracked by the webcam.

```sh
python -m main dodgeball
```

## Getting started

1. **Rules screen**: the rules are shown over the live camera. Press **SPACE**.
2. **Who's playing?**: everyone in front of the camera holds up a hand:
   - 👍 **thumbs up** to play (up to 3 players). Your box gets a colour and a P1/P2/P3 label.
   - 👎 **thumbs down** to sit out. You're marked OUT and ignored during the game, even if you stay in frame.
   - Hold the gesture for about a third of a second; a ring fills up while it counts.
3. Press **SPACE** to start with everyone who gave a thumbs up.

Gestures are read by MediaPipe's gesture recognizer (`assets/models/gesture_recognizer.task`), only on the "Who's playing?" screen. Each hand counts for the person whose box it is in.

## How to play

- Stand in front of the camera.
- A ball appears and moves around the live feed.
- Each player starts with **5 lives**, shown as hearts in the top-right.
- Avoid getting hit. If the ball touches your body shape, you lose a life and the round pauses.
- Press **R** to resume (5-second countdown). A player with no lives left is out.
- Last player standing wins (solo: play until your lives run out). Press **R** to start a new match.
- If you move out of the screen for long (3 seconds), you lose a life

## Keys

Shared shell keys (`D` debug, `F` fullscreen, `Esc` menu, `Q` quit) plus:

| Key | Action |
|---|---|
| `SPACE` | Rules → who's playing; who's playing → start the match |
| `R` | Who's playing: clear everyone's choice. In game: resume / new match (5-second countdown) |
| `Backspace` | Who's playing → back to the rules |
| `1` / `2` / `3` | Skip gestures and start with that many people from the frame |

## Files

- `dodgeball.py` — bouncing-ball dodgeball
- `ball.py` — the ball: movement, bouncing, body collision
- `roster.py` — thumbs-up / thumbs-down confirmation (pure logic, tested in `tests/test_dodgeball_roster.py`)