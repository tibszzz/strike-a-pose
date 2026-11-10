# strike-a-pose

A library of mini games where your body is the controller. Each game uses one webcam and
YOLO pose detection.

## Setup

1. Create and activate a virtualenv:
    ```sh
    python -m venv .venv
    source .venv/bin/activate
    ```
2. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

On macOS, give your terminal or editor camera access in System Settings > Privacy & Security > Camera.

## Games

### Wild West Duel (2 players)

```sh
python -m strike_a_pose duel
```

- Stand side by side, facing the camera. The left half of the screen is Player 1 and the right half is Player 2. You don't see yourselves; listen for the cues.
- A round starts once both players have been visible and not drawing for about 1 second.
- **READY**, then **STEADY**, then a random pause, then **BANG!**. When you hear BANG, draw by pointing either arm out sideways at shoulder height.
- The fastest draw shoots the other player, who loses a heart. Both reaction times are shown after every round.
- If you draw before BANG, you miss: you can't shoot that round, but your opponent still has to draw after BANG to hit you.
- If nobody draws within 3 seconds, no one is hit. Simultaneous draws and double early draws are replayed.
- Each player has 3 hearts. Lose them all and the other player wins.

Options:

| Option | What it does |
|---|---|
| `--camera N` | Pick a different camera (default 0) |
| `--imgsz 480` | Smaller model input, for more speed |
| `--device cpu` | Force CPU (the default is `mps` when it's available) |

Keys:

| Key | Action |
|---|---|
| `D` | Debug view: live camera behind the UI, skeletons, pose state per player, FPS |
| `R` | Reset the match |
| `F` | Toggle fullscreen |
| `Q` / `Esc` | Quit |

### Customising

- **Settings:** copy `.env.example` to `.env` and change what you like: lives, timings, pose thresholds, camera, animation speed. Anything you leave out keeps its default, and command-line flags beat `.env`.
- **Messages:** edit `assets/messages/shot.txt` (shown to the player who got shot), `win.txt` (shown on the win screen) and `early.txt` (drifts up when someone draws too early). One message per line, picked at random.
- **Win pictures:** any PNG in `assets/sprites/cowboys/` can come up on the win screen.
- **Sounds:** drop `ready.wav`, `steady.wav`, `bang.wav`, `early.wav`, `hit.wav` or `match_over.wav` into `assets/sounds/` to replace the built-in synthesized sounds.

## Development

```sh
python -m pytest              # rules and gesture tests, no camera needed
python scripts/detect_yolo.py # raw YOLO pose debug view
```

Layout:

- `strike_a_pose/pose/`: camera and YOLO tracker, P1/P2 assignment, gesture helpers
- `strike_a_pose/app.py`: shared pygame loop and keys. Games implement `update` / `draw` / `reset`.
- `strike_a_pose/games/<game>/`: one folder per game. Register new games in `strike_a_pose/__main__.py`.
- `strike_a_pose/config.py`: `.env` loading and message lists
- `assets/models/`: pose model weights
- `assets/fonts/`: Pixelify Sans (SIL Open Font License, see `OFL.txt`)
