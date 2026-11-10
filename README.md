# strike-a-pose

Steps to run:

1. Create and activate a virtualenv
    a. python -m venv .venv
    b. source .venv/bin.activate

2.Install dependencies
    a. pip install -r requirements.txt

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