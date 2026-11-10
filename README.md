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

### Body Trace (1-2 players)

```sh
python -m strike_a_pose body_trace
```

- Stand in front of the camera. Your body pose and movements are drawn live on the feed.
- Movement trails show your recent motion (last 15 frames).
- Filled silhouettes and skeleton lines visualize your body shape.

### Wild West Duel (2 players)

```sh
python -m strike_a_pose duel
```

- Stand side by side, facing the camera. The left half of the screen is Player 1 and the right half is Player 2.
- A round starts once both players have been visible and not drawing for about 1 second.
- **READY**, then **STEADY**, then a random pause, then **BANG!**. When you hear BANG, draw by pointing either arm out sideways at shoulder height.
- The fastest draw scores a point. Your reaction time is shown after every round.
- If you draw before BANG, you miss: you can't score that round, but your opponent still has to draw after BANG to get the point.
- If nobody draws within 3 seconds, no one scores. Simultaneous draws and double early draws are replayed.
- The first player to 3 points wins.

Options:

| Option | What it does |
|---|---|
| `--camera N` | Pick a different camera (default 0) |
| `--imgsz 480` | Smaller model input, for more speed |
| `--device cpu` | Force CPU (the default is `mps` when it's available) |

Keys:

| Key | Action |
|---|---|
| `D` | Debug overlay: skeletons, pose state per player, FPS |
| `R` | Reset the match |
| `F` | Toggle fullscreen |
| `Q` / `Esc` | Quit |

Tuning: timings are in `DuelConfig` in [strike_a_pose/games/duel/logic.py](strike_a_pose/games/duel/logic.py). Pose thresholds are in `GestureConfig` in [strike_a_pose/pose/gestures.py](strike_a_pose/pose/gestures.py).

## Development

```sh
python -m pytest              # rules and gesture tests, no camera needed
python scripts/detect_yolo.py # raw YOLO pose debug view
```

Layout:

- `strike_a_pose/pose/`: camera and YOLO tracker, P1/P2 assignment, gesture helpers
- `strike_a_pose/app.py`: shared pygame loop and keys. Games implement `update` / `draw` / `reset`.
- `strike_a_pose/games/<game>/`: one folder per game. Register new games in `strike_a_pose/__main__.py`.
- `assets/models/`: pose model weights
