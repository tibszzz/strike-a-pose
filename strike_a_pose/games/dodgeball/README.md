# Dodgeball Game

A body-controlled dodgeball game where players must avoid a bouncing ball using their real body movements detected via camera.

## 🎮 How to Play

### Starting the Game
```bash
cd /Users/kaizer1v/Documents/pprj/strike-a-pose
.venv/bin/python -m strike_a_pose dodgeball
```

### Gameplay
- Stand in front of the camera
- A ball will appear and bounce around the screen randomly
- **Avoid** getting hit by the ball
- If the ball touches your body shape, you get a hit
- The player with the **lowest hit count wins**

### Controls
| Key | Action |
|-----|--------|
| **R** | Reset game (starts 5-second countdown) |
| **D** | Toggle debug overlay |
| **F** | Toggle fullscreen |
| **Q** / **Esc** | Quit game |

## 📊 Scoring
- **Hit Counter**: Each player (P1, P2) has a counter that increments by 1 each time the ball touches them
- **Score Display**: Shows in the top-right corner (P1: X | P2: X)
- **Hit Message**: "P1 HIT! Press R to resume" appears in center when hit
- **Lower score = better player**

## ⏱️ Game Flow
1. Ball spawns at random position with random velocity
2. Ball bounces off screen edges with physics
3. Ball randomly changes direction occasionally
4. If ball touches player body → hit registered, game pauses
5. Press **R** to reset → 5-second countdown starts
6. After countdown → ball spawns at new random position
7. Repeat!

## 🎨 Visual Elements

### Ball
- **Orange/Yellow/Red**: Changes color based on speed
  - Yellow = Slow (< 8 px/f)
  - Orange = Medium (8-15 px/f)
  - Red = Fast (> 15 px/f)
- **Size**: 50 pixels radius
- **Max Speed**: 40 px/f

### Body Detection
- **Blue Polygon**: Player 1 body shape (17 COCO keypoints)
- **Red Polygon**: Player 2 body shape (17 COCO keypoints)
- **Transparency**: 80/255 alpha (semi-transparent)

### Hit Effects
- Red expanding circle at collision point
- Red "X" mark at collision
- Fades out over 45 frames

### UI Elements
- **Scoreboard**: Top-right corner
- **Hit Message**: Center screen (persistent until reset)
- **Countdown**: Center screen during restart
- **Instructions**: Bottom-left corner

## 🏗️ Architecture

### File Structure
```
strike_a_pose/games/dodgeball/
├── __init__.py         # Empty, required for Python package
├── game.py            # Main game implementation
└── README.md          # This file
```

### Classes

#### `Ball`
Represents the dodgeball with physics.

**Attributes:**
- `x`, `y`: Position (float)
- `radius`: Ball radius in pixels (default: 50)
- `vx`, `vy`: Velocity components
- `max_speed`: Maximum speed (default: 40.0)
- `elasticity`: Bounce coefficient (default: 0.95)
- `color`: Ball color (changes with speed)

**Methods:**
- `__init__(x, y, radius, max_speed, elasticity)`: Initialize ball
- `reset_velocity()`: Give ball random initial velocity
- `move()`: Update ball position based on velocity
- `bounce(width, height)`: Bounce off screen boundaries with randomness
- `check_collision(person)`: Check collision with person's body polygon
- `_point_in_polygon(point, polygon)`: Ray casting to check if point is inside polygon
- `_point_to_line_distance(point, line_p1, line_p2)`: Distance from point to line segment
- `draw(canvas)`: Draw ball on canvas

#### `DodgeballGame`
Main game class implementing the game logic.

**Attributes:**
- `w`, `h`: Screen dimensions
- `ball`: Ball instance
- `hits`: List of hit counters per player [P1, P2]
- `paused`: Whether game is paused after a hit
- `hit_Registered`: Track if hit was already counted per player
- `countdown`: Countdown timer for restart (in frames)
- `hit_message`: Message to display when hit occurs
- `hit_timer`: Timer for hit visual effect
- `hit_position`: Position of last hit
- `person_boxes`: List of detected persons and their body polygons

**Methods:**
- `__init__(size)`: Initialize game
- `reset()`: Start countdown to restart game
- `_start_ball()`: Spawn ball at random position with random velocity
- `update(frame)`: Update game state each frame
- `handle_key(key)`: Handle keyboard input
- `render_camera(image_bgr)`: Pass through camera image
- `debug_lines()`: Return debug text lines
- `draw(canvas, frame)`: Draw all game elements

## 🔧 Configuration

### Physics Parameters
- **Ball Radius**: 50 pixels
- **Max Speed**: 40 px/f
- **Elasticity**: 0.95 (95% bounce energy retention)
- **Initial Speed**: 10-40 px/f (random)
- **Random Direction Change**: 1% chance per frame (±45°)
- **Wall Bounce Randomness**: ±3 px/f velocity addition, 10% chance for ±10 px/f

### Collision Detection
- Uses **polygon-based** collision (17 COCO keypoints)
- Detects if ball center is inside body polygon
- Detects if ball is within radius of any body edge
- More accurate than bounding box
- Allows ball to pass between arms/legs

### Timing
- **Hit Effect Duration**: 45 frames (~1.5 seconds)
- **Countdown Duration**: 5 seconds (150 frames)
- **Frame Rate**: ~30 FPS (depends on system)

## 🤖 Dependencies

- Python 3.14+
- Pygame CE 2.5.8+
- NumPy
- OpenCV
- Ultralytics YOLO (for pose detection)

## 🐛 Known Issues

- Ball may occasionally get stuck if moving very fast into a corner
- Collision detection assumes person is facing the camera
- Only detects up to 2 players

## 📝 Changelog

### Current Version
- Polygon-based collision detection
- Single hit counting (no continuous increment)
- Game pause on hit
- 5-second countdown restart
- Random ball spawn position
- Hit counters per player
- Scoreboard in top-right
- Instructions strip at bottom

## 🎓 Technical Details

### COCO-17 Keypoints
The game uses all 17 COCO keypoints for body shape detection:
- Nose, Eyes, Ears
- Shoulders, Elbows, Wrists
- Hips, Knees, Ankles

This creates an accurate polygon representation of the person's body.

### Pose Detection
- Uses YOLO pose model (yolo26n-pose.pt)
- Runs on MPS (Apple Metal) for best performance
- Detects up to 2 players
- Players divided by screen half (left = P1, right = P2)

## 💡 Tips

1. **Stay in frame**: Make sure your full body is visible to the camera
2. **Move naturally**: The game detects your actual body movements
3. **Use space**: The polygon collision gives you more room to dodge
4. **Watch the ball**: The color indicates speed (red = dangerous!)
5. **Reset quickly**: After a hit, press R to restart the countdown

## 📜 License

This game is part of the Strike-a-Pose project. See the main repository for licensing information.
