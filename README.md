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
| Thumbs up | Hold ~1.5s to open the menu | Hold ~1.5s to confirm the selected game |
| Pointing up | — | Select the tile under the index fingertip (follows as you move) |
| Tip over tile | — | Soft-hover highlight (not enough to select) |

Hold Thumbs_Up for 1.5s on the splash to open the menu. Menu shows large square
tiles: Pointing_Up over a tile selects it (selection follows the fingertip
while you keep pointing), then hold Thumbs_Up for 1.5s to start. With
`--debug`, arrow keys (including Left/Right) move the menu selection and Enter
confirms instantly (on splash, Enter / Up also advances). In a game, `Esc`
returns to the menu; on splash or menu, `Esc` quits. `Q` always quits.

Gesture recognition uses MediaPipe (`assets/models/gesture_recognizer.task`). It runs only while the splash/menu (or a game with `wants_gestures`) is active. When YOLO sees wrists raised above the hip, the shell crops and upscales those regions before MediaPipe so hands stay recognizable farther from the camera. If people are visible but no wrists are above the hip, hand detection is skipped entirely (no full-frame fallback). Env tunables: `MIN_SCORE` (default 0.5), `REFRACTORY_MS` (default 350), `GESTURE_MODEL_PATH`, `ROI` (1/0), `ROI_SIZE` (320), `ROI_SCALE` (2.5), `ROI_MIN_PX` (80), `ROI_MAX` (2), `MIN_WRIST_CONF` (0.35), `RAISE_GATE` (1/0), `RAISE_LIFT_FRAC` (0.08), `RAISE_MATCH_FRAC` (0.35), `THUMB_HOLD_S` (1.5).

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
- `main/config.py` — `.env` loading and strike `Config`
- `assets/` — models, poses, fonts, sounds, sprites
