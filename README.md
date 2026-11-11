# strike-a-pose

Mini games where your body is the controller. One webcam, YOLO pose detection.

## Setup

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On macOS, grant camera access in System Settings → Privacy & Security → Camera.

## Run
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
On macOS, give your terminal or editor camera access in System Settings > Privacy & Security > Camera.

## Games

Launch the shared window (camera + pose stay warm while you switch titles):

```sh
python -m main
```

Opens the shared window. Camera and pose stay warm while you switch titles.

Optional: jump straight into a game (`Esc` still returns to the menu):

```sh
python -m main duel
python -m main dodgeball
python -m main cannonball
python -m main strike
python -m main strike --debug   # solo lobby while developing
```

### Menu controls

| Gesture | Action |
|---|---|
| Thumbs up | Selection up |
| Thumbs down | Selection down |
| Victory (peace) | Select / start |

Keyboard: Up/Down, Enter. In a game, `Esc` returns to the menu; on the menu, `Esc` quits. `Q` always quits.

Gesture recognition uses MediaPipe (`assets/models/gesture_recognizer.task`). It runs only while the menu (or a game with `wants_gestures`) is active. Env tunables: `MIN_SCORE` (default 0.5), `REFRACTORY_MS` (default 350), `GESTURE_MODEL_PATH`.

### Shared flags

| Flag | What it does |
|---|---|
| `--camera N` | Camera index (default 0) |
| `--imgsz 480` | Smaller YOLO input, more speed |
| `--device cpu` | Force CPU (`mps` when available is the default) |

Defaults also load from `.env` (see `.env.example`). Flags win over `.env`.

### Shared keys (in-game)

| Key | Action |
|---|---|
| `D` | Debug overlay |
| `D` | Debug view: live camera behind the UI, skeletons, pose state per player, FPS |
| `R` | Reset the match |
| `F` | Toggle fullscreen |
| `Esc` | Back to menu |
| `Q` | Quit the app |

## Games

| Game | Players | Launch | Details |
|---|---|---|---|
| Wild West Duel | 2 | `python -m main duel` | [main/games/duel/README.md](main/games/duel/README.md) |
| Dodgeball | 1–2 | `python -m main dodgeball` | [main/games/dodgeball/README.md](main/games/dodgeball/README.md) |
| Cannonball | 1–2 | `python -m main cannonball` | same package as Dodgeball |
| Strike a Pose | 2–4 | `python -m main strike` | [main/games/strike/README.md](main/games/strike/README.md) |

## Development

```sh
python -m pytest              # rules and gesture tests, no camera
python scripts/detect_yolo.py # raw YOLO pose debug view
```

Layout:

- `main/app.py` — shared pygame shell; swaps games without remounting the pose tracker
- `main/pose/` — live YOLO tracker and gesture helpers
- `main/nav/` — menu commands and MediaPipe gesture session
- `main/games/` — menu, registry, and each title
- `main/config.py` — `.env` loading and strike `Config`
- `assets/` — models, poses, fonts, sounds, sprites
- `main/pose/`: live YOLO tracker, P1/P2 assignment, full `people` list, gesture helpers; pose-file types in `library.py`
- `main/app.py`: shared pygame shell; swaps `Game` instances without remounting the pose tracker
- `main/nav.py`: menu commands and `StartGame` / `QuitApp` navigation
- `main/games/menu.py`: in-window game picker (`MenuGame`)
- `main/games/registry.py`: playable game factories for CLI + menu
- `main/games/duel/`: Wild West Duel (from `shooter-v1`)
- `main/games/dodgeball/`: Dodgeball and Cannonball (from `kaizer1v`)
- `main/games/strike/`: party pose game; `play.py` is the pygame adapter, `logic.py` rules, `game.py` compose/draw
- `main/config.py`: `.env` loading, message lists, and strike `Config`
- `assets/models/`: pose model weights
- `assets/poses/`: strike pose library
- `assets/fonts/`: Pixelify Sans (SIL Open Font License, see `OFL.txt`)
