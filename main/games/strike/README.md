# Strike a Pose

Party game for 2 to 4 players on one webcam. Each round shows a stick-figure pose, takes a snapshot at zero, and scores each player from 0 to 100 on how closely they match it. After 5 rounds the highest total wins.

```sh
python -m main strike
```

For solo testing while developing, pass `--debug` so ready-up / lobby accept one person:

```sh
python -m main strike --debug
```

With `--debug`, after ready-up / gameplay has begun, `R` jumps to the final RESULTS card (shell `R` still resets in ready-up).

## How to play

- Stand far enough back that everyone's whole body is in frame. Players are numbered left to right as they appear on screen.
- The screen is a mirror: if the figure's raised arm is on the left of the screen, raise the arm you see on the left of your own image.
- After scores lock, the next round starts on a timer. `Esc` returns to the menu; `Q` quits.
- People in the background are ignored: the snapshot scores the tallest figures in frame, as many as started the game.
- If the snapshot finds fewer people than started the game, the round is replayed with the same pose.

Settings (rounds, countdown length, scoring strictness, camera, model) live in `main/settings/strike.py`.

## Adding poses

Poses are JSON files in `assets/poses/`. Each game picks 5 of them at random.

Capture one from the webcam:

```sh
python -m main.games.strike.capture my-new-pose
```

Press SPACE, hold the pose with your whole body in frame for 3 seconds, and it is saved as `assets/poses/my-new-pose.json`.

Create or edit a pose by dragging joints on a stick figure:

```sh
python -m main.games.strike.edit my-new-pose
```

New names start from `t-pose`. Drag a joint freely — limb bone lengths stay locked (live IK); drag the background to move the whole figure. `C` snaps a pose from the webcam into the editor. SPACE saves (existing files ask before overwrite), `R` resets, `N` toggles the nose, `Q` quits. Restart the game to play a pose you just saved.

A pose file can also be written or edited by hand. Coordinates run from 0 to 1, with x growing toward the right of the screen and y growing downward. `left_*` joints are the figure's own left, which is the right side of the screen. All 12 body joints are required; `nose` is optional and only places the head.
