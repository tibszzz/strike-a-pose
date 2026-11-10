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

<<<<<<< HEAD
3. Run the script:
    a. cd scripts/
    b. python3 -m detect_yolo.py

## Strike a Pose game

A party game for 2 to 4 players sharing one webcam. Each round shows a stick-figure pose for 5 seconds, takes a snapshot at zero, and scores each player from 0 to 100 on how closely they match it. After 5 rounds the highest total wins.

Run it from the repo root, with the virtualenv active:

```
python -m strike_a_pose
```

For solo testing while developing, pass `--debug` so the lobby accepts one person:

```
python -m strike_a_pose --debug
```

- Stand far enough back that everyone's whole body is in frame. Players are numbered left to right as they appear on screen.
- The screen is a mirror: if the figure's raised arm is on the left of the screen, raise the arm you see on the left of your own image.
- SPACE starts the game and moves on from each results screen. Q quits.
- People in the background are ignored: the snapshot scores the tallest figures in frame, as many as started the game.
- If the snapshot finds fewer people than started the game, the round is replayed with the same pose.

Settings (rounds, countdown length, scoring strictness, camera, model) are in `strike_a_pose/config.py`.

### Adding poses

Poses are JSON files in `strike_a_pose/poses/`. Each game picks 5 of them at random.

To capture one from the webcam:

```
python -m strike_a_pose.capture my-new-pose
```

Press SPACE, hold the pose with your whole body in frame for 3 seconds, and it is saved as `strike_a_pose/poses/my-new-pose.json`.

A pose file can also be written or edited by hand. Coordinates run from 0 to 1, with x growing toward the right of the screen and y growing downward. `left_*` joints are the figure's own left, which is the right side of the screen. All 12 body joints are required; `nose` is optional and only places the head.

### Tests

```
python -m pytest
```
=======
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
>>>>>>> kaizer1v-yolo-test
