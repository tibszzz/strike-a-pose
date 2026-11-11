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

Settings (rounds, countdown length, scoring strictness, camera, model) are in `main/settings/strike.py`.

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

Opens the shared window on a splash screen. Hold thumbs up (or Enter with
`--debug`) advances to the game menu. Camera and pose stay warm while you
switch titles.

Optional: jump straight into a game (`Esc` still returns to the menu):

```sh
python -m main duel
python -m main dodgeball
python -m main strike
python -m main --debug          # keyboard menu nav + strike solo lobby
python -m main strike --debug
```

### Splash / menu controls

| Gesture | Splash | Menu |
|---|---|---|
| Thumbs up | Hold ~1s to open the menu | Hold ~1s to confirm the selected game |
| Pointing up | — | Select the tile under the index fingertip (follows as you move) |
| Tip over tile | — | Soft-hover highlight (not enough to select) |

Hold Thumbs_Up for 1s on the splash to open the menu. Menu shows large square
tiles: Pointing_Up over a tile selects it (selection follows the fingertip
while you keep pointing), then hold Thumbs_Up for 1s to start. With
`--debug`, arrow keys (including Left/Right) move the menu selection and Enter
confirms instantly (on splash, Enter / Up also advances). In a game, `Esc`
returns to the menu; on splash or menu, `Esc` quits. `Q` always quits.

Gesture recognition uses MediaPipe (`assets/models/gesture_recognizer.task`). It runs only while the splash/menu (or a game with `wants_gestures`) is active. When YOLO sees wrists raised above the hip, the shell crops and upscales those regions before MediaPipe so hands stay recognizable farther from the camera. If people are visible but no wrists are above the hip, hand detection is skipped entirely (no full-frame fallback). Env tunables: `MIN_SCORE` (default 0.5), `REFRACTORY_MS` (default 350), `GESTURE_MODEL_PATH`, `ROI` (1/0), `ROI_SIZE` (320), `ROI_SCALE` (2.5), `ROI_MIN_PX` (80), `ROI_MAX` (2), `MIN_WRIST_CONF` (0.35), `RAISE_GATE` (1/0), `RAISE_LIFT_FRAC` (0.08), `RAISE_MATCH_FRAC` (0.35), `THUMB_HOLD_S` (1.0).

### Shared flags

| Flag | What it does |
|---|---|
| `--camera N` | Camera index (default 0) |
| `--width` / `--height` | Requested capture size (default 1920×1080) |
| `--imgsz 480` | Smaller YOLO input, more speed |
| `--device cpu` | Force CPU (`mps` when available is the default) |
| `--windowed` | Start windowed instead of fullscreen |

Defaults also load from `.env` (see `.env.example`). Flags win over `.env`.

### Shared keys (in-game)

| Key | Action |
|---|---|
| `D` | Pose/FPS overlay |
| `R` | Reset the match |
| `F` | Toggle fullscreen / windowed |
| `Esc` | Back to menu |
| `Q` | Quit the app |

## Games

| Game | Players | Launch | Details |
|---|---|---|---|
| Wild West Duel | 2 | `python -m main duel` | [main/games/duel/README.md](main/games/duel/README.md) |
| Dodgeball | 1–2 | `python -m main dodgeball` | [main/games/dodgeball/README.md](main/games/dodgeball/README.md) |
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
- `main/content.py` — user-facing copy
- `main/styles.py` — Theme (brand tokens + per-game deltas)
- `main/settings/` — shell + per-game tunables (`from_env`)
- `main/config.py` — thin re-export of settings helpers
- `assets/` — models, poses, fonts, sounds, sprites
- `main/pose/`: live YOLO tracker, P1/P2 assignment, full `people` list, gesture helpers; pose-file types in `library.py`
- `main/app.py`: shared pygame shell; swaps `Game` instances without remounting the pose tracker
- `main/nav.py`: menu commands and `StartGame` / `QuitApp` navigation
- `main/games/menu.py`: in-window game picker (`MenuGame`)
- `main/games/registry.py`: playable game factories for CLI + menu
- `main/games/duel/`: Wild West Duel (from `shooter-v1`)
- `main/games/dodgeball/`: Dodgeball and Cannonball (from `kaizer1v`)
- `main/games/strike/`: party pose game; `play.py` is the pygame adapter, `logic.py` rules, `game.py` compose/draw
- `assets/models/`: pose model weights
- `assets/poses/`: strike pose library
- `assets/fonts/`: Monofett, VT323, Pixelify Sans (SIL OFL; see `*-OFL.txt` / `OFL.txt`)
