"""Cannonball Game: Ball thrown on a Z-axis path towards the screen.

This module simulates a ball moving along a Z-axis trajectory (3D depth) 
towards the camera/screen plane, with perspective scaling for visual effect.
Includes collision detection with person keypoints, camera passthrough,
and person tracking visualization.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Literal

import pygame

if TYPE_CHECKING:
    from main.pose import PoseFrame

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (80, 170, 255)
RED = (255, 80, 80)
GREEN = (100, 255, 100)
YELLOW = (255, 255, 100)
ORANGE = (255, 165, 0)
PURPLE = (180, 80, 255)
CYAN = (80, 255, 255)

# Player colors
PLAYER_COLORS = [BLUE, RED]

# Edge types for screen boundaries
EdgeType = Literal["left", "right", "top", "bottom"]


class ZAxisBall:
    """A ball that moves along a Z-axis path towards the screen.
    
    The ball starts at a distance (max_z) from the screen and moves towards z=0.
    The endpoint is always on one of the screen edges (left, right, top, bottom).
    The 2D screen position is calculated based on the ball's 3D coordinates using
    perspective projection. The ball's visual size scales with its distance from
    the screen (closer = larger) but is capped at max_screen_radius.
    
    Attributes:
        x, y, z: 3D position of the ball
        vx, vy, vz: 3D velocity components
        radius: Base radius of the ball at z=0
        color: Ball color
        max_z: Starting Z distance
        speed: Movement speed along Z-axis
        path: List of (x, y, z) points for the trajectory
        path_index: Current position in the path
        max_screen_radius: Maximum visual radius on screen
        edge: The screen edge where the ball will land
    """
    
    def __init__(
        self,
        screen_width: float,
        screen_height: float,
        radius: float = 30,
        max_z: float = 1000.0,
        speed: float = 5.0,
        color: tuple[int, int, int] = ORANGE,
        max_screen_radius: float = 200,
        edge: EdgeType | None = None,
    ):
        self.screen_w = screen_width
        self.screen_h = screen_height
        self.radius = radius
        self.max_z = max_z
        self.speed = speed
        self.color = color
        self.max_screen_radius = max_screen_radius
        
        # Choose a random edge if not specified
        self.edge = edge if edge is not None else random.choice(["left", "right", "top", "bottom"])
        
        # Set target position on the chosen edge
        self.target_x, self.target_y = self._get_edge_position(self.edge)
        
        # Initialize 3D position
        # Start at max_z with some X/Y offset from target (but towards screen center)
        self.x = self.target_x + random.uniform(-200, 200)
        self.y = self.target_y + random.uniform(-200, 200)
        self.z = max_z
        
        # Clamp start position to keep it on-screen when projected
        self.x = max(0, min(self.screen_w, self.x))
        self.y = max(0, min(self.screen_h, self.y))
        
        # Velocity: mostly towards screen (negative z), with slight x/y movement towards target
        self.vx = (self.target_x - self.x) / (self.max_z / self.speed) if self.max_z > 0 else 0
        self.vy = (self.target_y - self.y) / (self.max_z / self.speed) if self.max_z > 0 else 0
        self.vz = -speed  # Negative because we're moving towards z=0
        
        # Generate the path
        self.path = self._generate_z_axis_path()
        self.path_index = 0
        
        # Trail for visual effect
        self.trail: list[tuple[float, float, float, float]] = []  # (x, y, radius, alpha)
        self.max_trail_length = 20
    
    def _get_edge_position(self, edge: EdgeType) -> tuple[float, float]:
        """Get a random position on the specified screen edge.
        
        Args:
            edge: One of 'left', 'right', 'top', 'bottom'
            
        Returns:
            (x, y) position on that edge
        """
        if edge == "left":
            return (0, random.uniform(0, self.screen_h))
        elif edge == "right":
            return (self.screen_w, random.uniform(0, self.screen_h))
        elif edge == "top":
            return (random.uniform(0, self.screen_w), 0)
        elif edge == "bottom":
            return (random.uniform(0, self.screen_w), self.screen_h)
        else:
            # Default to right edge
            return (self.screen_w, random.uniform(0, self.screen_h))
    
    def _generate_z_axis_path(
        self,
        num_points: int = 100,
        gravity: float = 0.01,
    ) -> list[tuple[float, float, float]]:
        """Generate a 3D path for the ball moving along Z-axis.
        
        This simulates a parabolic trajectory under gravity as the ball
        moves towards the screen. The path starts at max_z and ends at z=0
        on the specified screen edge.
        
        Args:
            num_points: Number of points in the path
            gravity: Gravity effect on the Y-axis (positive = downward)
            
        Returns:
            List of (x, y, z) tuples representing the ball's path
        """
        path = []
        
        # Starting position
        start_x = self.x
        start_y = self.y
        start_z = self.z
        
        # Time step for each segment
        total_time = self.max_z / abs(self.vz)
        dt = total_time / num_points
        
        for i in range(num_points):
            t = i * dt
            
            # Calculate position at time t
            # Z decreases linearly
            z = start_z + self.vz * t
            
            # X and Y follow parabolic paths towards target
            x = start_x + self.vx * t
            y = start_y + self.vy * t + 0.5 * gravity * t**2
            
            # Clamp z to be non-negative
            z = max(0, z)
            
            path.append((x, y, z))
        
        # Ensure last point is at z=0 on the target edge
        # Use the exact target position (on edge)
        if path:
            path.append((self.target_x, self.target_y, 0))
        
        return path
    
    def get_path(self) -> list[tuple[float, float, float]]:
        """Get the generated Z-axis path.
        
        Returns:
            List of (x, y, z) points along the ball's trajectory
        """
        return self.path
    
    def get_edge(self) -> EdgeType:
        """Get the edge where the ball will land.
        
        Returns:
            The edge type ('left', 'right', 'top', 'bottom')
        """
        return self.edge
    
    def check_collision(self, person, z_scale: float = 1000.0) -> tuple[bool, list | None]:
        """Check if ball collides with person's body shape (keypoints polygon).
        
        Uses the 2D projected position and radius of the ball to check
        against the person's body polygon formed from COCO keypoints.
        
        Args:
            person: Person object with xy keypoints
            z_scale: Perspective scaling factor
            
        Returns:
            Tuple of (collision: bool, body_polygon_points: list | None)
        """
        if person is None:
            return False, None
        
        # Get the ball's 2D position and effective radius
        screen_x, screen_y, screen_radius = self.get_2d_position_and_radius(z_scale)
        
        # Get all keypoints from the person
        keypoints = person.xy
        
        # Create a polygon from the keypoints for more accurate collision
        # Use all 17 COCO keypoints to form the body shape
        body_polygon = []
        for i in range(len(keypoints)):
            # Handle both numpy array (keypoints[i, 0]) and list (keypoints[i][0])
            if hasattr(keypoints, 'shape'):
                # Numpy array
                x, y = float(keypoints[i, 0]), float(keypoints[i, 1])
            else:
                # List or other sequence
                x, y = float(keypoints[i][0]), float(keypoints[i][1])
            body_polygon.append((x, y))
        
        # Check if ball center is inside the polygon
        if self._point_in_polygon((screen_x, screen_y), body_polygon):
            return True, body_polygon
        
        # Also check if ball is close to any edge of the polygon
        # This gives a little buffer space based on the ball's screen radius
        for i in range(len(body_polygon)):
            p1 = body_polygon[i]
            p2 = body_polygon[(i + 1) % len(body_polygon)]
            if self._point_to_line_distance((screen_x, screen_y), p1, p2) < screen_radius:
                return True, body_polygon
        
        return False, body_polygon
    
    def _point_in_polygon(self, point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
        """Check if a point is inside a polygon using ray casting algorithm."""
        x, y = point
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside
    
    def _point_to_line_distance(self, point: tuple[float, float], line_p1: tuple[float, float], line_p2: tuple[float, float]) -> float:
        """Calculate distance from point to line segment."""
        x, y = point
        x1, y1 = line_p1
        x2, y2 = line_p2
        
        # Calculate the line equation: ax + by + c = 0
        a = y2 - y1
        b = x1 - x2
        c = x2 * y1 - x1 * y2
        
        # Distance from point to infinite line
        distance = abs(a * x + b * y + c) / math.sqrt(a * a + b * b)
        
        # Check if the closest point on the line is within the segment
        # Project point onto line
        dot = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / ((x2 - x1) ** 2 + (y2 - y1) ** 2 + 0.0001)
        
        if dot < 0:
            # Closest to p1
            return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)
        elif dot > 1:
            # Closest to p2
            return math.sqrt((x - x2) ** 2 + (y - y2) ** 2)
        else:
            # Closest to line segment
            return distance
    
    def move(self) -> None:
        """Update ball position along Z-axis path.
        
        Moves the ball one step along its pre-generated path.
        Adds current position to trail.
        """
        if self.path_index < len(self.path) - 1:
            self.path_index += 1
            self.x, self.y, self.z = self.path[self.path_index]
        
        # Add to trail with perspective-scaled radius and fading alpha
        if self.z > 0:
            screen_x, screen_y, screen_radius = self.get_2d_position_and_radius()
            self.trail.append((screen_x, screen_y, screen_radius, 200))
            
            # Limit trail length
            if len(self.trail) > self.max_trail_length:
                self.trail.pop(0)
    
    def get_2d_position_and_radius(self, z_scale: float = 1000.0) -> tuple[float, float, float]:
        """Project 3D position to 2D screen coordinates with perspective.
        
        Uses simple perspective projection: closer objects appear larger.
        The radius is capped at max_screen_radius.
        
        Args:
            z_scale: Scaling factor for perspective effect
            
        Returns:
            Tuple of (screen_x, screen_y, screen_radius)
        """
        # Perspective scaling factor (closer = larger)
        scale = z_scale / (self.z + z_scale) if self.z > 0 else 1.0
        
        screen_x = self.x
        screen_y = self.y
        screen_radius = self.radius * scale
        
        # Cap the radius to prevent it from becoming too large
        screen_radius = min(screen_radius, self.max_screen_radius)
        
        return screen_x, screen_y, screen_radius
    
    def is_at_screen(self, threshold: float = 10.0) -> bool:
        """Check if ball has reached the screen (z near 0).
        
        Args:
            threshold: Z distance considered as "at screen"
            
        Returns:
            True if ball is at or very close to the screen
        """
        return self.z <= threshold
    
    def is_finished(self) -> bool:
        """Check if ball has completed its path.
        
        Returns:
            True if ball has reached the end of its path
        """
        return self.path_index >= len(self.path) - 1 or self.z <= 0
    
    def reset(
        self,
        edge: EdgeType | None = None,
    ) -> None:
        """Reset the ball to starting position with new edge target.
        
        Args:
            edge: New edge to target (random if None)
        """
        self.edge = edge if edge is not None else random.choice(["left", "right", "top", "bottom"])
        self.target_x, self.target_y = self._get_edge_position(self.edge)
        
        self.x = self.target_x + random.uniform(-200, 200)
        self.y = self.target_y + random.uniform(-200, 200)
        self.x = max(0, min(self.screen_w, self.x))
        self.y = max(0, min(self.screen_h, self.y))
        self.z = self.max_z
        
        self.vx = (self.target_x - self.x) / (self.max_z / self.speed) if self.max_z > 0 else 0
        self.vy = (self.target_y - self.y) / (self.max_z / self.speed) if self.max_z > 0 else 0
        self.vz = -self.speed
        
        self.path = self._generate_z_axis_path()
        self.path_index = 0
        self.trail = []
    
    def draw(self, canvas: pygame.Surface, z_scale: float = 1000.0) -> None:
        """Draw the ball and its trail on the canvas.
        
        Args:
            canvas: Pygame surface to draw on
            z_scale: Perspective scaling factor
        """
        # Draw trail
        for i, (tx, ty, tr, alpha) in enumerate(self.trail):
            # Fade trail points
            trail_alpha = int(alpha * (i / len(self.trail)))
            if trail_alpha > 0:
                pygame.draw.circle(
                    canvas,
                    (*self.color, trail_alpha),
                    (int(tx), int(ty)),
                    int(tr),
                )
        
        # Draw main ball
        screen_x, screen_y, screen_radius = self.get_2d_position_and_radius(z_scale)
        
        # Draw outer glow
        glow_radius = int(screen_radius * 1.2)
        pygame.draw.circle(
            canvas,
            (*self.color, 120),
            (int(screen_x), int(screen_y)),
            glow_radius,
        )
        
        # Draw ball body
        pygame.draw.circle(
            canvas,
            self.color,
            (int(screen_x), int(screen_y)),
            int(screen_radius),
        )
        
        # Draw highlight
        highlight_x = screen_x - screen_radius * 0.3
        highlight_y = screen_y - screen_radius * 0.3
        pygame.draw.circle(
            canvas,
            WHITE,
            (int(highlight_x), int(highlight_y)),
            int(screen_radius * 0.2),
        )


def simulate_z_axis_path(
    start_z: float,
    end_z: float,
    screen_width: float,
    screen_height: float,
    num_points: int = 100,
    start_x: float | None = None,
    start_y: float | None = None,
    end_edge: EdgeType | None = None,
    gravity: float = 0.01,
    initial_vx: float = 0,
    initial_vy: float = 0,
) -> tuple[list[tuple[float, float, float]], tuple[float, float]]:
    """Simulate a ball's path along the Z-axis from start to end.
    
    The endpoint is always on one of the screen edges.
    
    Args:
        start_z: Starting Z position (distance from screen)
        end_z: Ending Z position (0 = at screen)
        screen_width: Width of the screen
        screen_height: Height of the screen
        num_points: Number of points in the path
        start_x, start_y: Starting X,Y position (random if None)
        end_edge: Which edge to end at (random if None)
        gravity: Gravity effect on Y-axis
        initial_vx, initial_vy: Initial X,Y velocity
        
    Returns:
        Tuple of (path, end_position) where:
        - path: List of (x, y, z) tuples representing the path
        - end_position: (x, y) position on the edge
    """
    path = []
    
    # Choose end edge if not specified
    edge = end_edge if end_edge is not None else random.choice(["left", "right", "top", "bottom"])
    
    # Get end position on the chosen edge
    if edge == "left":
        end_x, end_y = (0, random.uniform(0, screen_height))
    elif edge == "right":
        end_x, end_y = (screen_width, random.uniform(0, screen_height))
    elif edge == "top":
        end_x, end_y = (random.uniform(0, screen_width), 0)
    elif edge == "bottom":
        end_x, end_y = (random.uniform(0, screen_width), screen_height)
    else:
        end_x, end_y = (screen_width, random.uniform(0, screen_height))
    
    # Choose start position if not specified
    if start_x is None:
        start_x = end_x + random.uniform(-200, 200)
    if start_y is None:
        start_y = end_y + random.uniform(-200, 200)
    
    # Clamp start position
    start_x = max(0, min(screen_width, start_x))
    start_y = max(0, min(screen_height, start_y))
    
    # Calculate initial velocity in Z direction
    total_z_distance = start_z - end_z
    total_time = 1.0  # Normalized time
    vz = -total_z_distance / total_time  # Negative for moving towards screen
    
    # Time step
    dt = total_time / num_points
    
    for i in range(num_points):
        t = i * dt
        
        # Z position (linear motion towards screen)
        z = start_z + vz * t
        
        # X and Y follow parabolic paths towards target
        progress = t / total_time
        x = start_x + (end_x - start_x) * progress + initial_vx * t
        y = start_y + (end_y - start_y) * progress + initial_vy * t + 0.5 * gravity * t**2
        
        # Ensure z doesn't go below end_z
        z = max(end_z, z)
        
        path.append((x, y, z))
    
    # Add final point at end_z on the edge
    path.append((end_x, end_y, end_z))
    
    return path, (end_x, end_y)


def draw_ball_on_z_path(
    canvas: pygame.Surface,
    path: list[tuple[float, float, float]],
    ball_radius: float = 30,
    ball_color: tuple[int, int, int] = ORANGE,
    current_index: int = 0,
    z_scale: float = 1000.0,
    show_trail: bool = True,
    trail_length: int = 10,
    max_screen_radius: float = 200,
) -> None:
    """Draw a ball at a specific position along a Z-axis path.
    
    This function visualizes a ball moving through its Z-axis trajectory,
    showing perspective scaling (capped at max_screen_radius) and an optional trail.
    
    Args:
        canvas: Pygame surface to draw on
        path: List of (x, y, z) points from simulate_z_axis_path
        ball_radius: Base radius of the ball
        ball_color: Color of the ball
        current_index: Current position in the path (0 to len(path)-1)
        z_scale: Perspective scaling factor
        show_trail: Whether to show a trail behind the ball
        trail_length: Number of trail points to show
        max_screen_radius: Maximum visual radius on screen
    """
    if not path or current_index >= len(path):
        return
    
    # Get current position
    x, y, z = path[current_index]
    
    # Calculate perspective scale
    scale = z_scale / (z + z_scale) if z > 0 else 1.0
    screen_radius = ball_radius * scale
    
    # Cap the radius
    screen_radius = min(screen_radius, max_screen_radius)
    
    # Draw trail
    if show_trail:
        start_idx = max(0, current_index - trail_length)
        for i in range(start_idx, current_index):
            if i >= len(path):
                continue
            
            tx, ty, tz = path[i]
            trail_scale = z_scale / (tz + z_scale) if tz > 0 else 1.0
            trail_radius = ball_radius * trail_scale * 0.7
            trail_radius = min(trail_radius, max_screen_radius * 0.7)
            
            # Calculate alpha based on distance from current position
            alpha = int(255 * (i - start_idx) / (current_index - start_idx + 1) * 0.5)
            
            pygame.draw.circle(
                canvas,
                (*ball_color, alpha),
                (int(tx), int(ty)),
                int(trail_radius),
            )
    
    # Draw main ball with glow effect
    glow_radius = int(screen_radius * 1.4)
    pygame.draw.circle(
        canvas,
        (*ball_color, 80),
        (int(x), int(y)),
        glow_radius,
    )
    
    # Draw ball
    pygame.draw.circle(
        canvas,
        ball_color,
        (int(x), int(y)),
        int(screen_radius),
    )
    
    # Draw highlight
    highlight_radius = int(screen_radius * 0.25)
    pygame.draw.circle(
        canvas,
        WHITE,
        (int(x - screen_radius * 0.3), int(y - screen_radius * 0.3)),
        highlight_radius,
    )
    
    # Draw path line (optional visualization)
    if current_index < len(path) - 1:
        next_x, next_y, next_z = path[current_index + 1]
        pygame.draw.line(
            canvas,
            (*ball_color, 50),
            (int(x), int(y)),
            (int(next_x), int(next_y)),
            max(1, int(screen_radius * 0.3)),
        )


class CannonballGame:
    """Cannonball Game: Avoid the incoming cannonball!
    
    A game where a ball is thrown along a Z-axis path towards the screen.
    Players must dodge the ball as it approaches. Features collision detection
    with person body polygons, camera passthrough, and person tracking.
    
    Attributes:
        title: Game title
        w, h: Screen dimensions
        ball: The Z-axis ball
        hits: Hit counters per player
        paused: Whether game is paused after a hit
        hit_registered: Track if hit was already counted per player
        hit_message: Message to display
        hit_message_timer: Timer for hit message
        hit_timer: Timer for hit visual effect
        hit_position: Position of last hit
        person_polygons: List of (person, polygon) for visualization
        z_scale: Perspective scaling factor
    """
    
    title = "Cannonball"
    
    def __init__(self, size):
        self.w, self.h = size
        
        # Ball
        self.ball = ZAxisBall(
            screen_width=self.w,
            screen_height=self.h,
            radius=40,
            max_z=1000,
            speed=8,
            color=ORANGE,
            max_screen_radius=150,
        )
        
        # Hit counters per player (P1, P2)
        self.hits = [0, 0]  # [P1, P2] - count of hits
        
        # Game state
        self.paused = False  # Pause after hit
        self.hit_registered = [False, False]  # Track if hit was already counted for each player
        self.countdown = 0  # Countdown timer for restart
        
        # Hit tracking
        self.hit_message = ""
        self.hit_message_timer = 0
        
        # Visual effects
        self.hit_timer = 0
        self.hit_position = (0, 0)
        
        # Person polygons for visualization
        self.person_polygons: list[tuple] = []
        
        # Perspective scaling
        self.z_scale = 1000.0
    
    def reset(self) -> None:
        """Reset the game - start countdown to restart."""
        self.paused = False
        self.countdown = 5 * 30  # 5 seconds * 30 FPS = 150 frames
        self.hit_registered = [False, False]
        self.hit_message = "Game restarting..."
        self.hit_message_timer = 0
        self.hit_timer = 0
        self.person_polygons = []
    
    def _start_ball(self) -> None:
        """Start a new ball at a random edge with random velocity."""
        self.ball = ZAxisBall(
            screen_width=self.w,
            screen_height=self.h,
            radius=40,
            max_z=1000,
            speed=8,
            color=ORANGE,
            max_screen_radius=150,
            edge=random.choice(["left", "right", "top", "bottom"]),
        )
    
    def update(self, frame: PoseFrame) -> None:
        """Update game state.
        
        Args:
            frame: PoseFrame containing detected persons
        """
        # If paused, only update message timer
        if self.paused:
            return
        
        # Handle countdown
        if self.countdown > 0:
            self.countdown -= 1
            if self.countdown == 0:
                self._start_ball()
                self.hits = [0, 0]  # Reset counters when ball starts
            return  # Don't update game during countdown
        
        # Store person polygons for drawing
        self.person_polygons = []
        
        # Reset hit registration at start of each frame
        for i in range(len(self.hit_registered)):
            self.hit_registered[i] = False
        
        # Move ball
        self.ball.move()
        
        # Update timers
        if self.hit_timer > 0:
            self.hit_timer -= 1
        if self.hit_message_timer > 0:
            self.hit_message_timer -= 1
        
        # Check for collisions
        for player_idx, person in enumerate(frame.players):
            if person is not None:
                # Check collision with ball
                collision, body_polygon = self.ball.check_collision(person, self.z_scale)
                self.person_polygons.append((person, body_polygon))
                
                if collision and not self.hit_registered[player_idx]:
                    # Hit! Increment hit counter ONCE
                    self.hits[player_idx] += 1
                    self.hit_registered[player_idx] = True
                    self.hit_timer = 45
                    self.hit_position = (int(self.ball.x), int(self.ball.y))
                    
                    # Show hit message
                    self.hit_message = f"P{player_idx + 1} HIT! Press R to resume"
                    self.hit_message_timer = 0  # Keep showing until reset
                    
                    # Pause the game
                    self.paused = True
                    
                    break  # Only check first collision
        
        # If ball reached the screen without hitting anyone
        if self.ball.is_at_screen():
            self.hit_message = "Ball missed! Press R to restart"
            self.hit_message_timer = 0
            self.paused = True
    
    def handle_key(self, key: int) -> None:
        """Handle keyboard input.
        
        Args:
            key: Pygame key constant
        """
        if key == pygame.K_r:
            self.reset()
    
    def render_camera(self, image_bgr):
        """Pass through camera image.
        
        Args:
            image_bgr: Camera frame (BGR format from OpenCV)
            
        Returns:
            The camera image (passthrough)
        """
        return image_bgr
    
    def debug_lines(self) -> list[str]:
        """Get debug information lines.
        
        Returns:
            List of debug strings
        """
        return [
            f"P1: {self.hits[0]} | P2: {self.hits[1]}",
            f"Ball Z: {self.ball.z:.1f} | Edge: {self.ball.edge}",
            f"Ball at screen: {self.ball.is_at_screen()}",
        ]
    
    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        """Draw game elements on the canvas.
        
        Args:
            canvas: Pygame surface to draw on
            frame: PoseFrame containing detected persons
        """
        # Draw person body polygons
        for player_idx, (person, body_polygon) in enumerate(self.person_polygons):
            if body_polygon is not None:
                color = PLAYER_COLORS[player_idx]
                temp_surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
                pygame.draw.polygon(temp_surf, (*color, 80), body_polygon, 2)
                canvas.blit(temp_surf, (0, 0))
        
        # Draw ball
        self.ball.draw(canvas, self.z_scale)
        
        # Draw hit effect
        if self.hit_timer > 0:
            alpha = int(255 * (self.hit_timer / 45))
            temp_surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
            radius = int(30 + (45 - self.hit_timer))
            pygame.draw.circle(temp_surf, (*RED, alpha), self.hit_position, radius, 3)
            
            # X mark
            x, y = self.hit_position
            pygame.draw.line(temp_surf, (*RED, alpha),
                            (x - 25, y - 25), (x + 25, y + 25), 3)
            pygame.draw.line(temp_surf, (*RED, alpha),
                            (x - 25, y + 25), (x + 25, y - 25), 3)
            canvas.blit(temp_surf, (0, 0))
        
        # Draw hit message in center
        if self.hit_message:
            font_large = pygame.font.SysFont("menlo,monaco,courier", 48)
            msg_color = RED
            msg_text = font_large.render(self.hit_message, True, msg_color)
            msg_rect = msg_text.get_rect(center=(self.w // 2, self.h // 2 - 100))
            canvas.blit(msg_text, msg_rect)
        
        # Draw countdown in center
        if self.countdown > 0:
            countdown_sec = (self.countdown + 29) // 30  # Convert frames to seconds
            countdown_text = f"Starting in {countdown_sec}..."
            font_large = pygame.font.SysFont("menlo,monaco,courier", 48)
            msg_text = font_large.render(countdown_text, True, YELLOW)
            msg_rect = msg_text.get_rect(center=(self.w // 2, self.h // 2))
            canvas.blit(msg_text, msg_rect)
        
        # Draw scoreboard in top-right
        font = pygame.font.SysFont("menlo,monaco,courier", 28)
        p1_text = font.render(f"P1: {self.hits[0]}", True, PLAYER_COLORS[0], BLACK)
        p2_text = font.render(f"P2: {self.hits[1]}", True, PLAYER_COLORS[1], BLACK)
        
        # Position in top-right
        p2_rect = p2_text.get_rect(topright=(self.w - 20, 20))
        p1_rect = p1_text.get_rect(topright=(p2_rect.left - 20, 20))
        
        canvas.blit(p2_text, p2_rect)
        canvas.blit(p1_text, p1_rect)
        
        # Draw target indicator on edge
        target_color = YELLOW
        pygame.draw.circle(
            canvas, 
            target_color, 
            (int(self.ball.target_x), int(self.ball.target_y)), 
            10, 
            2
        )
        
        # Draw instructions strip at bottom
        instr_font = pygame.font.SysFont("menlo,monaco,courier", 20)
        instructions = "[D] Debug | [R] Reset | [F] Fullscreen | [Q/Esc] Quit"
        instr_text = instr_font.render(instructions, True, WHITE, BLACK)
        instr_rect = instr_text.get_rect(bottomleft=(20, self.h - 20))
        
        # Draw semi-transparent background for instructions
        instr_bg = pygame.Surface((instr_rect.width + 40, instr_rect.height + 10), pygame.SRCALPHA)
        pygame.draw.rect(instr_bg, (*BLACK, 180), (0, 0, instr_bg.get_width(), instr_bg.get_height()), border_radius=5)
        canvas.blit(instr_bg, (instr_rect.x - 20, instr_rect.y - 5))
        
        canvas.blit(instr_text, instr_rect)


# Example usage demonstration
if __name__ == "__main__":
    """Demonstration of Cannonball game with collision and camera capabilities."""
    
    # Initialize pygame for demonstration
    pygame.init()
    WIDTH, HEIGHT = 800, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Cannonball Game Demo")
    
    clock = pygame.time.Clock()
    
    # Create the game
    game = CannonballGame((WIDTH, HEIGHT))
    
    # Mock PoseFrame for testing (since we don't have a real camera)
    class MockPerson:
        def __init__(self, box, xy):
            self.box = box
            self.xy = xy
    
    class MockPoseFrame:
        def __init__(self):
            self.players = [
                MockPerson(
                    box=(100, 100, 200, 400),  # x1, y1, x2, y2
                    xy=[
                        [150, 150], [150, 200], [150, 250], [150, 300], [150, 350],
                        [130, 130], [170, 130], [130, 180], [170, 180], [130, 230],
                        [170, 230], [130, 280], [170, 280], [130, 330], [170, 330],
                        [150, 100], [150, 400]
                    ]
                ),
                None,  # Second player not present
            ]
    
    mock_frame = MockPoseFrame()
    
    # Font for demo info
    font = pygame.font.SysFont("menlo,monaco,courier", 24)
    small_font = pygame.font.SysFont("menlo,monaco,courier", 18)
    
    running = True
    demo_mode = True
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_SPACE:
                    # Randomize player position for testing
                    new_xy = [
                        [random.randint(100, WIDTH-100), random.randint(100, HEIGHT-100)]
                        for _ in range(17)
                    ]
                    mock_frame.players[0] = MockPerson(
                        box=(random.randint(50, WIDTH-50), random.randint(50, HEIGHT-50),
                             random.randint(100, WIDTH), random.randint(100, HEIGHT)),
                        xy=new_xy
                    )
                game.handle_key(event.key)
        
        # Clear screen
        screen.fill(BLACK)
        
        # Update game
        game.update(mock_frame)
        
        # Draw game
        game.draw(screen, mock_frame)
        
        # Draw debug info
        debug_lines = game.debug_lines()
        for i, line in enumerate(debug_lines):
            debug_text = small_font.render(line, True, (180, 180, 180))
            screen.blit(debug_text, (20, HEIGHT - 100 + i * 25))
        
        # Draw demo info
        demo_text = "Cannonball Game | Collision Detection Active | Press R to reset"
        demo_surface = small_font.render(demo_text, True, (200, 200, 200))
        screen.blit(demo_surface, (20, HEIGHT - 130))
        
        # Draw player controls info
        controls = "Move player with SPACE (random pos) | R: Reset"
        controls_surface = small_font.render(controls, True, (150, 150, 150))
        screen.blit(controls_surface, (20, HEIGHT - 160))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()
