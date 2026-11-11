"""Dodgeball Game: Avoid the bouncing ball! Ball hits body = lose points."""

from __future__ import annotations
import math
import random
import cv2
import numpy as np
import pygame
from main.pose import Person, PoseFrame
from main.pose.library import left_to_right

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
MUTED = (175, 175, 175)
ACCENT = (70, 215, 255)
BLUE = (80, 170, 255)
RED = (255, 80, 80)
GREEN = (100, 255, 100)
YELLOW = (255, 255, 100)
ORANGE = (255, 165, 0)

# Player colors, P1..P3 left to right
PLAYER_COLORS = [BLUE, RED, GREEN]

# Same lobby idea as Strike a Pose: count the people in frame, then confirm.
MIN_PLAYERS = 1
MAX_PLAYERS = 3
FPS = 30

# Font style from games/pose/game.py (Strike a Pose)
FONT = cv2.FONT_HERSHEY_DUPLEX


def draw_text(
    canvas: pygame.Surface,
    text: str,
    x: int,
    y: int,
    scale: float = 1.0,
    color: tuple[int, int, int] = WHITE,
    align: str = "left",
    outline: bool = False,
) -> pygame.Rect:
    """Draw text matching games/pose/game.py font style (cv2.FONT_HERSHEY_DUPLEX).

    `y` is the baseline position. `align` places `x` at left, center, or right.
    `outline` keeps text readable over video with a black border.
    """
    if not text:
        return pygame.Rect(x, y, 0, 0)
    thickness = max(1, round(scale * 1.6))
    (text_w, text_h), baseline = cv2.getTextSize(text, FONT, scale, thickness)
    pad = thickness + 4
    buf_w = text_w + pad * 2
    buf_h = text_h + baseline + pad * 2

    img = np.zeros((buf_h, buf_w, 4), dtype=np.uint8)
    origin_x = pad
    origin_y = pad + text_h

    if outline:
        cv2.putText(
            img,
            text,
            (origin_x, origin_y),
            FONT,
            scale,
            (0, 0, 0, 255),
            thickness + 4,
            cv2.LINE_AA,
        )
    r, g, b = color[:3]
    cv2.putText(
        img,
        text,
        (origin_x, origin_y),
        FONT,
        scale,
        (r, g, b, 255),
        thickness,
        cv2.LINE_AA,
    )

    surf = pygame.image.frombuffer(img.tobytes(), (buf_w, buf_h), "RGBA")

    if align == "center":
        blit_x = x - text_w // 2 - pad
    elif align == "right":
        blit_x = x - text_w - pad
    else:
        blit_x = x - pad
    blit_y = y - text_h - pad

    canvas.blit(surf, (blit_x, blit_y))
    return pygame.Rect(blit_x + pad, blit_y + pad, text_w, text_h)



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


NUMBER_KEYS = {
    pygame.K_1: 1, pygame.K_KP1: 1,
    pygame.K_2: 2, pygame.K_KP2: 2,
    pygame.K_3: 3, pygame.K_KP3: 3,
}


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
        
        # Lobby: wait for people to step in and confirm how many are playing
        self.in_lobby = True
        self.lobby_people: list[Person] = []
        self.player_count = 0
        self.last_x: list[float] = []  # last known centre x per player slot

        # Hit counters per player (P1..Pn)
        self.hits: list[int] = []
        
        # Game state
        self.paused = False  # Pause after hit
        self.hit_registered: list[bool] = []  # Track if hit was already counted for each player
        self.countdown = 0  # Countdown timer for restart
        
        # Hit tracking
        self.hit_message = ""
        self.hit_message_timer = 0
        
        # Visual effects
        self.hit_timer = 0
        self.hit_position = (0, 0)
        
        # Person bounding boxes for visualization
        self.person_boxes = []

    @property
    def can_start(self) -> bool:
        return MIN_PLAYERS <= len(self.lobby_people) <= MAX_PLAYERS

    def start(self, count: int) -> None:
        """Leave the lobby and play with `count` players."""
        self.in_lobby = False
        self.player_count = count
        self.hits = [0] * count
        # Seed slots from the lobby layout so P1..Pn keep their left-to-right order.
        lobby_x = [p.center_x for p in self.lobby_people]
        self.last_x = [
            lobby_x[i] if i < len(lobby_x) else self.w * (i + 1) / (count + 1)
            for i in range(count)
        ]
        self.reset()
        self.hit_message = "Get ready!"

    def reset(self) -> None:
        """Reset the game - start countdown to restart."""
        if self.in_lobby:
            return
        self.paused = False
        self.countdown = 5 * FPS
        self.hit_registered = [False] * self.player_count
        self.hit_message = "Game restarting..."
        self.hit_message_timer = 0
        self.hit_timer = 0
        self.person_boxes = []
        # Pick the launch spot now so players can see it during the countdown.
        self._start_ball()

    def _start_ball(self) -> None:
        """Place the ball at a random position with a random launch velocity."""
        self.ball = Ball(
            x=random.randint(50, self.w - 50),
            y=random.randint(50, self.h - 50),
            radius=20,
            max_speed=40.0,
            elasticity=0.95,
        )

    def _assign_players(self, people: list[Person]) -> list[Person | None]:
        """Map detections to player slots P1..Pn.

        Like Strike a Pose, the tallest people are the players and extras are
        bystanders. With everyone in frame, slots go left to right; when some
        are missing, each person takes the free slot nearest where it was last seen.
        """
        n = self.player_count
        tallest = sorted(people, key=lambda p: p.box[3] - p.box[1], reverse=True)[:n]
        slots: list[Person | None] = [None] * n
        if len(tallest) == n:
            for i, person in enumerate(left_to_right(tallest)):
                slots[i] = person
        else:
            free = set(range(n))
            for person in tallest:
                i = min(free, key=lambda s: abs(self.last_x[s] - person.center_x))
                slots[i] = person
                free.discard(i)
        for i, person in enumerate(slots):
            if person is not None:
                self.last_x[i] = person.center_x
        return slots

    def update(self, frame: PoseFrame) -> None:
        """Update game state."""
        if self.in_lobby:
            self.lobby_people = left_to_right(frame.people)
            return

        # If paused, only update message timer
        if self.paused:
            return
        
        # Handle countdown
        if self.countdown > 0:
            self.countdown -= 1
            if self.countdown == 0:
                self.hits = [0] * self.player_count  # Reset counters when ball starts
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
        for i in range(len(self.hit_registered)):
            if not self.paused:
                self.hit_registered[i] = False
        
        # Check for collisions
        for player_idx, person in enumerate(self._assign_players(frame.people)):
            if person is not None:
                collision, body_polygon = self.ball.check_collision(person)
                self.person_boxes.append((player_idx, body_polygon))
                
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
        """Handle keyboard input. (R is routed to reset() by the app shell.)"""
        if not self.in_lobby:
            return
        if key == pygame.K_SPACE and self.can_start:
            self.start(len(self.lobby_people))
        elif key in NUMBER_KEYS:
            self.start(NUMBER_KEYS[key])
    
    def render_camera(self, image_bgr):
        """Pass through camera image."""
        return image_bgr

    def debug_lines(self) -> list[str]:
        if self.in_lobby:
            return [f"Lobby: {len(self.lobby_people)} people in frame"]
        return [
            " | ".join(f"P{i + 1}: {h}" for i, h in enumerate(self.hits)),
            f"Ball speed: {math.sqrt(self.ball.vx**2 + self.ball.vy**2):.1f} px/f",
        ]

    def _draw_lobby(self, canvas: pygame.Surface) -> None:
        """Boxes around everyone in frame, numbered left to right, plus a prompt."""
        for i, person in enumerate(self.lobby_people):
            color = PLAYER_COLORS[i] if i < MAX_PLAYERS else MUTED
            x1, y1, x2, y2 = (int(v) for v in person.box)
            pygame.draw.rect(canvas, color, (x1, y1, x2 - x1, y2 - y1), 2)
            draw_text(canvas, f"P{i + 1}", x1 + 6, max(y1 - 10, 30), 0.9, color, outline=True)

        band = pygame.Surface((self.w, 84), pygame.SRCALPHA)
        band.fill((*BLACK, 160))
        canvas.blit(band, (0, 0))
        canvas.blit(band, (0, self.h - 84))
        draw_text(canvas, "DODGEBALL", self.w // 2, 58, 1.6, WHITE, "center")

        count = len(self.lobby_people)
        if self.can_start:
            label = "player" if count == 1 else "players"
            message, color = f"{count} {label} in frame  -  press SPACE to start", ACCENT
        else:
            message = f"Need {MIN_PLAYERS} to {MAX_PLAYERS} players in frame  -  found {count}"
            color = WHITE
        draw_text(canvas, message, self.w // 2, self.h - 44, 1.0, color, "center", outline=True)
        draw_text(canvas, "or press 1 / 2 / 3 to choose", self.w // 2, self.h - 14, 0.6, MUTED, "center")

    def _draw_launch_marker(self, canvas: pygame.Surface) -> None:
        """Pulsing ring plus an arrow showing the direction the ball will fly."""
        bx, by = int(self.ball.x), int(self.ball.y)
        r = int(self.ball.radius)
        pulse = (math.sin(self.countdown * 0.25) + 1) / 2  # 0..1
        overlay = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (*YELLOW, int(90 + 120 * pulse)), (bx, by), r + 12 + int(14 * pulse), 4)

        speed = math.hypot(self.ball.vx, self.ball.vy) or 1.0
        ux, uy = self.ball.vx / speed, self.ball.vy / speed
        start = (bx + ux * (r + 10), by + uy * (r + 10))
        tip = (bx + ux * (r + 90), by + uy * (r + 90))
        pygame.draw.line(overlay, (*YELLOW, 220), start, tip, 6)
        head = 22
        left = (tip[0] - ux * head - uy * head * 0.6, tip[1] - uy * head + ux * head * 0.6)
        right = (tip[0] - ux * head + uy * head * 0.6, tip[1] - uy * head - ux * head * 0.6)
        pygame.draw.polygon(overlay, (*YELLOW, 220), [tip, left, right])
        canvas.blit(overlay, (0, 0))

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        """Draw game elements."""
        if self.in_lobby:
            self._draw_lobby(canvas)
            return

        # Draw person body polygons
        for player_idx, body_polygon in self.person_boxes:
            if body_polygon is not None:
                color = PLAYER_COLORS[player_idx]
                temp_surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
                pygame.draw.polygon(temp_surf, (*color, 80), body_polygon, 2)
                canvas.blit(temp_surf, (0, 0))
        
        # Draw ball (during the countdown, also flag where it launches from)
        if self.countdown > 0:
            self._draw_launch_marker(canvas)
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
        
        # Draw hit message in center (timer > 0, or paused with a sticky message)
        if self.hit_message and (self.hit_message_timer > 0 or self.paused or self.countdown > 0):
            draw_text(
                canvas,
                self.hit_message,
                self.w // 2,
                self.h // 2 - 100,
                scale=1.4,
                color=RED,
                align="center",
                outline=True,
            )
        
        # Draw countdown in center
        if self.countdown > 0:
            countdown_sec = (self.countdown + 29) // 30  # Convert frames to seconds
            countdown_text = f"Starting in {countdown_sec}..."
            draw_text(
                canvas,
                countdown_text,
                self.w // 2,
                self.h // 2,
                scale=1.5,
                color=YELLOW,
                align="center",
                outline=True,
            )
        
        # Draw scoreboard in top-right, P1..Pn reading left to right
        score_scale = 0.95
        score_thickness = max(1, round(score_scale * 1.6))
        right = self.w - 24
        for i in reversed(range(self.player_count)):
            text = f"P{i + 1}: {self.hits[i]}"
            draw_text(canvas, text, right, 48, scale=score_scale, color=PLAYER_COLORS[i], align="right", outline=True)
            (text_w, _), _ = cv2.getTextSize(text, FONT, score_scale, score_thickness)
            right -= text_w + 28
        
        # Draw instructions strip at bottom
        instructions = "[D] Debug | [R] Reset | [F] Fullscreen | [Q/Esc] Quit"
        instr_scale = 0.65
        instr_thickness = max(1, round(instr_scale * 1.6))
        (instr_w, instr_h), _ = cv2.getTextSize(instructions, FONT, instr_scale, instr_thickness)
        instr_bg = pygame.Surface((instr_w + 32, instr_h + 16), pygame.SRCALPHA)
        pygame.draw.rect(instr_bg, (*BLACK, 180), (0, 0, instr_bg.get_width(), instr_bg.get_height()), border_radius=6)
        canvas.blit(instr_bg, (16, self.h - instr_h - 28))
        draw_text(canvas, instructions, 32, self.h - 18, scale=instr_scale, color=WHITE, align="left", outline=True)
