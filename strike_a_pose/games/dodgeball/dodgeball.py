"""Dodgeball Game: Avoid the bouncing ball! Ball hits body = lose points."""

from __future__ import annotations
import math
import random
import pygame
from strike_a_pose.games.pose import PoseFrame

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (80, 170, 255)
RED = (255, 80, 80)
GREEN = (100, 255, 100)
YELLOW = (255, 255, 100)
ORANGE = (255, 165, 0)

# Player colors
PLAYER_COLORS = [BLUE, RED]


class Ball:
    """Ball that bounces around the screen randomly."""
    
    def __init__(
        self,
        x: float,
        y: float,
        radius: float = 25,
        max_speed: float = 40.0,
        elasticity: float = 0.95,
    ):
        self.x = x
        self.y = y
        self.radius = radius
        self.max_speed = max_speed
        self.elasticity = elasticity
        self.vx = 0.0
        self.vy = 0.0
        self.reset_velocity()
        self.color = ORANGE
    
    def reset_velocity(self) -> None:
        """Give the ball a random initial velocity."""
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(10, self.max_speed)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
    
    def move(self) -> None:
        """Update ball position."""
        self.x += self.vx
        self.y += self.vy
        
        # Clamp speed
        speed = math.sqrt(self.vx**2 + self.vy**2)
        if speed > self.max_speed:
            scale = self.max_speed / speed
            self.vx *= scale
            self.vy *= scale
    
    def bounce(self, width: float, height: float) -> None:
        """Bounce off screen boundaries with randomness."""
        if self.x - self.radius < 0:
            self.x = self.radius
            self.vx = -self.vx * self.elasticity
            self.vy += random.uniform(-3, 3)
            if random.random() < 0.1:
                self.vy = random.uniform(-10, 10)
        elif self.x + self.radius > width:
            self.x = width - self.radius
            self.vx = -self.vx * self.elasticity
            self.vy += random.uniform(-3, 3)
            if random.random() < 0.1:
                self.vy = random.uniform(-10, 10)
        
        if self.y - self.radius < 0:
            self.y = self.radius
            self.vy = -self.vy * self.elasticity
            self.vx += random.uniform(-3, 3)
            if random.random() < 0.1:
                self.vx = random.uniform(-10, 10)
        elif self.y + self.radius > height:
            self.y = height - self.radius
            self.vy = -self.vy * self.elasticity
            self.vx += random.uniform(-3, 3)
            if random.random() < 0.1:
                self.vx = random.uniform(-10, 10)
        
        # Random direction change (1% chance)
        if random.random() < 0.01:
            angle_change = random.uniform(-math.pi/4, math.pi/4)
            current_angle = math.atan2(self.vy, self.vx)
            new_angle = current_angle + angle_change
            speed = math.sqrt(self.vx**2 + self.vy**2)
            self.vx = math.cos(new_angle) * speed
            self.vy = math.sin(new_angle) * speed
    
    def check_collision(self, person) -> tuple[bool, list | None]:
        """Check if ball collides with person's body shape (keypoints polygon).
        
        Returns:
            Tuple of (collision: bool, body_polygon_points: list | None)
        """
        if person is None:
            return False, None
        
        # Get all keypoints from the person
        keypoints = person.xy
        
        # Create a polygon from the keypoints for more accurate collision
        # Use all 17 COCO keypoints to form the body shape
        body_polygon = []
        for i in range(len(keypoints)):
            x, y = float(keypoints[i, 0]), float(keypoints[i, 1])
            body_polygon.append((x, y))
        
        # Check if ball center is inside the polygon
        if self._point_in_polygon((self.x, self.y), body_polygon):
            return True, body_polygon
        
        # Also check if ball is close to any edge of the polygon
        # This gives a little buffer space
        for i in range(len(body_polygon)):
            p1 = body_polygon[i]
            p2 = body_polygon[(i + 1) % len(body_polygon)]
            if self._point_to_line_distance((self.x, self.y), p1, p2) < self.radius:
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
        dot = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / ((x2 - x1) ** 2 + (y2 - y1) ** 2)
        
        if dot < 0:
            # Closest to p1
            return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)
        elif dot > 1:
            # Closest to p2
            return math.sqrt((x - x2) ** 2 + (y - y2) ** 2)
        else:
            # Closest to line segment
            return distance
    
    def draw(self, canvas: pygame.Surface) -> None:
        """Draw the ball."""
        pygame.draw.circle(canvas, self.color, (int(self.x), int(self.y)), int(self.radius) + 4, 2)
        pygame.draw.circle(canvas, self.color, (int(self.x), int(self.y)), int(self.radius))
        pygame.draw.circle(canvas, WHITE, (int(self.x) - 5, int(self.y) - 5), 4)


class DodgeballGame:
    title = "Dodgeball"

    def __init__(self, size):
        self.w, self.h = size
        
        # Ball
        self.ball = Ball(
            x=self.w // 2,
            y=self.h // 2,
            radius=50,
            max_speed=40.0,
            elasticity=0.95,
        )
        
        # Simple hit counters per player (P1, P2)
        self.hits = [0, 0]  # [P1, P2] - count of hits
        
        # Game state
        self.paused = False  # Pause after hit
        self.hit_Registered = [False, False]  # Track if hit was already counted for each player
        self.countdown = 0  # Countdown timer for restart
        
        # Hit tracking
        self.hit_message = ""
        self.hit_message_timer = 0
        
        # Visual effects
        self.hit_timer = 0
        self.hit_position = (0, 0)
        
        # Person bounding boxes for visualization
        self.person_boxes = []

    def reset(self) -> None:
        """Reset the game - start countdown to restart."""
        self.paused = False
        self.countdown = 5 * 30  # 5 seconds * 30 FPS = 150 frames
        self.hit_Registered = [False, False]
        self.hit_message = "Game restarting..."
        self.hit_message_timer = 0
        self.hit_timer = 0
        self.person_boxes = []
    
    def _start_ball(self) -> None:
        """Start the ball at a random position with random velocity."""
        self.ball = Ball(
            x=random.randint(50, self.w - 50),
            y=random.randint(50, self.h - 50),
            radius=50,
            max_speed=40.0,
            elasticity=0.95,
        )

    def update(self, frame: PoseFrame) -> None:
        """Update game state."""
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
        
        # Store person boxes for drawing
        self.person_boxes = []
        
        # Move ball
        self.ball.move()
        self.ball.bounce(self.w, self.h)
        
        # Update timers
        if self.hit_timer > 0:
            self.hit_timer -= 1
        if self.hit_message_timer > 0:
            self.hit_message_timer -= 1
        
        # Reset hit registration at start of each frame
        # (only register one hit per player per collision event)
        for i in range(len(self.hit_Registered)):
            if not self.paused:
                self.hit_Registered[i] = False
        
        # Check for collisions
        for player_idx, person in enumerate(frame.players):
            if person is not None:
                collision, body_polygon = self.ball.check_collision(person)
                self.person_boxes.append((person, body_polygon))
                
                if collision and not self.hit_Registered[player_idx]:
                    # Hit! Increment hit counter ONCE
                    self.hits[player_idx] += 1
                    self.hit_Registered[player_idx] = True
                    self.hit_timer = 45
                    self.hit_position = (int(self.ball.x), int(self.ball.y))
                    
                    # Show hit message
                    self.hit_message = f"P{player_idx + 1} HIT! Press R to resume"
                    self.hit_message_timer = 0  # Keep showing until reset
                    
                    # Pause the game
                    self.paused = True
                    
                    # Bounce ball away from person
                    # Calculate center from body polygon
                    if body_polygon:
                        polygon_center_x = sum(p[0] for p in body_polygon) / len(body_polygon)
                        polygon_center_y = sum(p[1] for p in body_polygon) / len(body_polygon)
                    else:
                        polygon_center_x = self.w / 2
                        polygon_center_y = self.h / 2
                    
                    dx = self.ball.x - polygon_center_x
                    dy = self.ball.y - polygon_center_y
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    if dist < 1:
                        # Ball is at center, push in random direction
                        angle = random.uniform(0, 2 * math.pi)
                        self.ball.vx = math.cos(angle) * 15
                        self.ball.vy = math.sin(angle) * 15
                        self.ball.x = polygon_center_x + math.cos(angle) * (self.ball.radius + 30)
                        self.ball.y = polygon_center_y + math.sin(angle) * (self.ball.radius + 30)
                    else:
                        # Push ball away
                        self.ball.vx = (dx / dist) * 15
                        self.ball.vy = (dy / dist) * 15
                        push_dist = self.ball.radius + 30
                        self.ball.x = polygon_center_x + (dx / dist) * push_dist
                        self.ball.y = polygon_center_y + (dy / dist) * push_dist
                    
                    break  # Only check first person
        
        # Update ball color based on speed
        speed = math.sqrt(self.ball.vx**2 + self.ball.vy**2)
        if speed > 15:
            self.ball.color = RED
        elif speed > 8:
            self.ball.color = ORANGE
        else:
            self.ball.color = YELLOW

    def handle_key(self, key: int) -> None:
        """Handle keyboard input."""
        if key == pygame.K_r:
            self.reset()
    
    def render_camera(self, image_bgr):
        """Pass through camera image."""
        return image_bgr

    def debug_lines(self) -> list[str]:
        return [
            f"P1: {self.hits[0]} | P2: {self.hits[1]}",
            f"Ball speed: {math.sqrt(self.ball.vx**2 + self.ball.vy**2):.1f} px/f",
        ]

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        """Draw game elements."""
        # Draw person body polygons
        for player_idx, (person, body_polygon) in enumerate(self.person_boxes):
            if body_polygon is not None:
                color = PLAYER_COLORS[player_idx]
                temp_surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
                pygame.draw.polygon(temp_surf, (*color, 80), body_polygon, 2)
                canvas.blit(temp_surf, (0, 0))
        
        # Draw ball
        self.ball.draw(canvas)
        
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
        if self.hit_message_timer > 0:
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
