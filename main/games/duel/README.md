# Wild West Duel

Two-player quick-draw. Stand side by side facing the camera. Left half of the screen is Player 1, right half is Player 2. You don't see yourselves — listen for the cues.

```sh
python -m main duel
```

## How to play

- A round starts once both players have been visible and not drawing for about 1 second.
- **READY**, then **STEADY**, then a random pause, then **BANG!** When you hear BANG, draw by pointing either arm out sideways at shoulder height.
- The fastest draw shoots the other player, who loses a heart. Both reaction times are shown after every round.
- Draw before BANG and you miss: you can't shoot that round, but your opponent still has to draw after BANG to hit you.
- If nobody draws within 3 seconds, no one is hit. Simultaneous draws and double early draws are replayed.
- Each player has 3 hearts. Lose them all and the other player wins.

## Keys

Shared shell keys (`D` debug, `F` fullscreen, `Esc` menu, `Q` quit) plus:

| Key | Action |
|---|---|
| `R` | Reset the match |

## Customising

- **Settings:** copy `.env.example` to `.env` and change lives, timings, pose thresholds, camera, animation speed. Anything left out keeps its default; command-line flags beat `.env`.
- **Messages:** edit the pools on `content.Duel` in `main/content.py` (`shot_messages`, `win_messages`, `early_messages`).
- **Win pictures:** any PNG in `assets/sprites/cowboys/` can appear on the win screen.
- **Sounds:** drop `ready.wav`, `steady.wav`, `bang.wav`, `early.wav`, `hit.wav`, or `match_over.wav` into `assets/sounds/` to replace the built-in synthesized sounds. See `assets/sounds/README.md`.
