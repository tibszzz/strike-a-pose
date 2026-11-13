# Dodgeball

Body-controlled dodgeball: dodge a bouncing ball with your real body, tracked by the webcam.

```sh
python -m main dodgeball
```

## Getting started

1. **Rules screen**: the rules are shown over the live camera. Press **SPACE**.
2. **Who's playing?**: everyone in front of the camera holds up a hand:
   - **Thumbs up** to play (up to `max_players`). Your P-marker fills with colour.
   - Leave the frame to cancel ready.
   - When enough players are ready, any ready player holds a **fist** to start; a paper badge + ring fills on that hand while it counts.
3. Debug **SPACE** can force-start when enough are ready.

Gestures are read by MediaPipe's gesture recognizer (`assets/models/gesture_recognizer.task`), only on the "Who's playing?" screen. Each hand counts for the person whose box it is in.

## How to play

- Stand in front of the camera.
- A ball appears and moves around the live feed.
- Lives scale with roster size (**2P: 3 Lives, 3P: 2 Lives, 4P: 1 Life**), shown as hearts in the top-right.
- Avoid getting hit. If the ball touches your body shape, you lose a life and the round restarts itself.
- A player with no lives left is out (their HUD P# tag goes gray).
- Last player standing wins. Press **R** on game over to rematch into ready-up.
- If you move out of the screen for long (3 seconds), you lose a life

## Keys

Shared shell keys (`D` debug, `F` fullscreen, `Esc` menu, `Q` quit) plus:

| Key | Action |
|---|---|
| `SPACE` | Rules → who's playing; who's playing → start the match. `--debug`: force-start ready-up when eligible |
| `R` | Ready-up: clear choices / reset. Mid-match: no-op (round restarts itself). Game over: rematch into ready-up. With `--debug` after play starts: skip to RESULTS |
| `Backspace` | Who's playing → back to the rules |
| `1` / `2` / `3` | Skip gestures and start with that many people from the frame |

## Files

- `dodgeball.py` — bouncing-ball dodgeball
- `ball.py` — the ball: movement, bouncing, body collision
- `roster.py` — thumbs-up / thumbs-down confirmation (pure logic, tested in `tests/test_dodgeball_roster.py`)