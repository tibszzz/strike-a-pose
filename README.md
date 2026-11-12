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
- After scores lock, the next round starts on a timer. Q quits.
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

Opens the shared window straight on the game menu. Camera and pose stay warm
while you switch titles.

Optional: jump straight into a game (`Esc` still returns to the menu):

```sh
python -m main duel
python -m main dodgeball
python -m main strike
python -m main --debug          # keyboard menu nav + strike/duel solo
python -m main duel --debug
python -m main strike --debug
```

### Menu / how-to-play / results controls

| Gesture | Menu | How to play | Results |
|---|---|---|---|
| Open palm over a note | Selects it | Moving the cursor onto **Let's go!** / **Back** selects it | Selects Play again / Menu |
| Closed fist (hold ~0.5s), anywhere | Presses the selected note | Presses the selected button | Presses the selected note |

Hovering selects, and the selection stays after your hand moves away; the fist
then presses it from wherever your hand is (a bar fills on the selected note).
Nothing is selected when a page opens, so a fist does nothing until you hover.

On a game's ready-up screen, each player gets a "P1"/"P2"… triangle above
their head: grey while waiting, filled with their colour after a thumbs up
(thumbs down sits out). Any ready player holds a fist to start. Two stacked hints
bottom-left read "Thumbs up to join" and "Fist to start"; the second stays
faded until enough players are ready.

Flow: menu → the game's how-to-play page → the game's ready-up → play →
results page (Play again returns to ready-up, Menu to the menu).

The menu, how-to-play and results pages don't show the live video. Instead,
everyone the pose model sees is drawn as a marker stick figure (the Strike a
Pose figure: torso box, limbs, joint knobs, ring head) on a paper backdrop
(`main/ui/sketch.py`), so players still see themselves move.

The menu has a row of torn-paper notes across the top
(High Noon, Strike a pose, Dodgeball, Quit), stacked gesture hints bottom-left
and the title bottom-right. The hand cursor (`main/nav/cursor.py`) follows
your palm centre (so closing a fist doesn't knock it off a button), is
smoothed, and rides out brief detection dropouts. Its reach is sized to your
body: the hand is matched to the player whose wrist it's on, and a zone around
their shoulders (measured in torso lengths) maps onto the screen, so the edges
take the same arm movement whether you stand far from the camera or close. How-to-play uses the same mapping, so the
cursor carries on from the menu without jumping; the fist that picked the game
can't press anything there, as the hand must open before a new fist counts. A fist hold survives a split-second
detector flicker instead of starting over. Tuning lives in `GestureNavConfig`
(`REACH_BODY`, `REACH_HALF_W`, `REACH_TOP`, `REACH_BOTTOM`, `CURSOR_GAIN`, `CURSOR_REL_GAIN`, `CURSOR_GRACE_S`, `CURSOR_MIN_CUTOFF`,
`CURSOR_BETA`, `HOLD_GRACE_S`, `RELEASE_OPEN_S`; all env-overridable). The menu does the same
open-first check when you come back from results. With `--debug`, arrow keys
move the selection and Enter confirms instantly. In a game or on the
how-to-play page, `Esc` returns to the menu; on the menu, `Esc` quits. `Q`
always quits.

The paper look (menu, how-to-play, results) lives in `main/ui/`. How-to-play
copy is `content.HowToPlay`; its illustrations are
`assets/ui/how_to_play/<game>/step_{1,2,3}.png` + `info.png` (replace the PNGs
to restyle). Fonts: Permanent Marker (Apache 2.0) and Patrick Hand (SIL OFL)
in `assets/fonts/`.

Gesture recognition uses MediaPipe (`assets/models/gesture_recognizer.task`). It runs only while the menu, how-to-play page (or a game with `wants_gestures`) is active. When YOLO sees wrists raised above the elbow, the shell crops and upscales those regions before MediaPipe so hands stay recognizable farther from the camera. If people are visible but no wrists are above the elbow, hand detection is skipped entirely (no full-frame fallback). Env tunables: `MIN_SCORE` (default 0.5), `REFRACTORY_MS` (default 350), `GESTURE_MODEL_PATH`, `ROI` (1/0), `ROI_SIZE` (320), `ROI_SCALE` (2.5), `ROI_MIN_PX` (80), `ROI_MAX` (2), `MIN_WRIST_CONF` (0.35), `RAISE_GATE` (1/0), `RAISE_LIFT_FRAC` (0.08), `RAISE_MATCH_FRAC` (0.35), `THUMB_HOLD_S` (0.5).

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
- `assets/fonts/`: Press Start 2P (SIL OFL; see `PressStart2P-OFL.txt`)
- `assets/ready_up/`: placeholder pose stills for the shared ready-up rules card (swap art in place)
