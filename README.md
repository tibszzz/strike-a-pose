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
python -m main duel
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

### Customising duel

- **Settings:** copy `.env.example` to `.env` and change what you like: lives, timings, pose thresholds, camera, animation speed. Anything you leave out keeps its default, and command-line flags beat `.env`.
- **Messages:** edit `assets/messages/shot.txt` (shown to the player who got shot), `win.txt` (shown on the win screen) and `early.txt` (drifts up when someone draws too early). One message per line, picked at random.
- **Win pictures:** any PNG in `assets/sprites/cowboys/` can come up on the win screen.
- **Sounds:** drop `ready.wav`, `steady.wav`, `bang.wav`, `early.wav`, `hit.wav` or `match_over.wav` into `assets/sounds/` to replace the built-in synthesized sounds.

### Dodgeball (1-2 players)

```sh
python -m main dodgeball
```

- Stand in front of the camera. A ball bounces around the live feed.
- Avoid the ball: if it touches your body shape, you take a hit and the round pauses.
- Press **R** to restart (5-second countdown). Lowest hit count wins.
- Same camera / imgsz / device flags as duel. Keys: D debug, R reset, F fullscreen, Q / Esc quit.

Also in the same package: `python -m main cannonball` — a Z-axis ball thrown toward the screen.

### Strike a Pose (2 to 4 players)

```sh
python -m main strike
```

For solo testing while developing, pass `--debug` so the lobby accepts one person:

```sh
python -m main strike --debug
```

A party game for 2 to 4 players sharing one webcam. Each round shows a stick-figure pose, takes a snapshot at zero, and scores each player from 0 to 100 on how closely they match it. After 5 rounds the highest total wins.

- Stand far enough back that everyone's whole body is in frame. Players are numbered left to right as they appear on screen.
- The screen is a mirror: if the figure's raised arm is on the left of the screen, raise the arm you see on the left of your own image.
- SPACE starts the game and moves on from each results screen. Q quits.
- People in the background are ignored: the snapshot scores the tallest figures in frame, as many as started the game.
- If the snapshot finds fewer people than started the game, the round is replayed with the same pose.

Settings (rounds, countdown length, scoring strictness, camera, model) are in `main/config.py`.

#### Adding poses

Poses are JSON files in `assets/poses/`. Each game picks 5 of them at random.

To capture one from the webcam:

```sh
python -m main.games.strike.capture my-new-pose
```

Press SPACE, hold the pose with your whole body in frame for 3 seconds, and it is saved as `assets/poses/my-new-pose.json`.

To create or edit a pose by dragging joints on a stick figure:

```sh
python -m main.games.strike.edit my-new-pose
```

New names start from `t-pose`. Drag a joint freely — limb bone lengths stay locked (live IK); drag the background to move the whole figure. C snaps a pose from the webcam into the editor (then keep dragging). SPACE saves (existing files ask before overwrite), R resets, N toggles the nose, Q quits. Restart the game to play a pose you just saved.

A pose file can also be written or edited by hand. Coordinates run from 0 to 1, with x growing toward the right of the screen and y growing downward. `left_*` joints are the figure's own left, which is the right side of the screen. All 12 body joints are required; `nose` is optional and only places the head.

## Development

```sh
python -m pytest              # rules and gesture tests, no camera needed
python scripts/detect_yolo.py # raw YOLO pose debug view
```

Layout:

- `main/pose/`: live YOLO tracker, P1/P2 assignment, gesture helpers; pose-file types in `library.py`
- `main/app.py`: shared pygame loop and keys for duel. Games implement `update` / `draw` / `reset`.
- `main/games/duel/`: Wild West Duel (from `shooter-v1`)
- `main/games/dodgeball/`: Dodgeball and Cannonball (from `kaizer1v`)
- `main/games/strike/`: the party pose game. `logic.py` is the rules, `game.py` draws
- `main/config.py`: `.env` loading, message lists, and strike `Config`
- `assets/models/`: pose model weights
- `assets/poses/`: strike pose library
- `assets/fonts/`: Pixelify Sans (SIL Open Font License, see `OFL.txt`)
