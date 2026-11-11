"""Dodgeball Game: Avoid the bouncing ball! Each player has 5 lives; a ball hit costs one."""

from __future__ import annotations
import math
import random
import cv2
import numpy as np
import pygame
from main.pose import Person, PoseFrame
from main.pose.library import left_to_right
from .ball import Ball

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
LIVES = 5  # chances per player; at 0 the player is out
OFFSCREEN_SECONDS = 3  # out of frame this long during play = lose a life
OFFSCREEN_FRAMES = OFFSCREEN_SECONDS * FPS

# Shown on the intro (lobby) screen; mirrors "How to play" in README.md
RULES = [
    "Stand in front of the camera",
    "Dodge the ball bouncing around the live feed",
    f"Everyone starts with {LIVES} lives (hearts, top-right)",
    "Ball touches your body: lose a life and the round pauses",
    "Press R to resume. No lives left and you're out",
    f"Leave the screen for {OFFSCREEN_SECONDS} seconds: lose a life",
    "Last player standing wins. Solo: survive as long as you can",
    "NOTE: Red ball = fast, orange = medium, yellow = slow",
]

# Font style from games/pose/game.py (Strike a Pose)
FONT = cv2.FONT_HERSHEY_DUPLEX

def _draw_heart(
    canvas: pygame.Surface, cx: int, cy: int, size: int, color: tuple[int, int, int], filled: bool
) -> None:
    """Heart icon centred on (cx, cy), `size` px wide. Lost lives are drawn grey and faded."""
    pad = 3  # room for the black edge
    r = size // 4
    surf = pygame.Surface((size + pad * 2, size + pad * 2), pygame.SRCALPHA)
    ox, oy = surf.get_width() // 2, r + pad + 1  # heart origin inside the surface

    def shape(fill, grow: int) -> None:
        for lx in (ox - r, ox + r):
            pygame.draw.circle(surf, fill, (lx, oy), r + grow)
        pygame.draw.polygon(
            surf, fill, [(ox - 2 * r - grow, oy + r // 4), (ox, oy + 3 * r + grow), (ox + 2 * r + grow, oy + r // 4)]
        )

    shape((*BLACK, 255), 2)  # black edge keeps the icon readable over video
    shape((*color, 255) if filled else (*MUTED, 255), 0)
    if not filled:
        surf.set_alpha(110)
    canvas.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))


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
    """
    styling and text rendering functions
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
        # Stamp the text in black around its own position. A single thicker
        # stroke would not line up: cv2 spaces letters by stroke thickness, so a
        # thick outline drifts right of the text and gets clipped at the end.
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if dx or dy:
                    cv2.putText(
                        img,
                        text,
                        (origin_x + dx, origin_y + dy),
                        FONT,
                        scale,
                        (0, 0, 0, 255),
                        thickness,
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

        # Lives left per player (P1..Pn)
        self.lives: list[int] = []
        self.game_over = False
        # Frames each player has been missing from the frame during play
        self.missing_frames: list[int] = []
        
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
        
        # Player bounding boxes (slot, (x1, y1, x2, y2)), refreshed every frame
        self.person_boxes: list[tuple[int, tuple[float, float, float, float]]] = []
        # Body outlines used for collision, shown while the ball is moving
        self.body_polygons: list[tuple[int, list | None]] = []

    @property
    def can_start(self) -> bool:
        return MIN_PLAYERS <= len(self.lobby_people) <= MAX_PLAYERS

    def start(self, count: int) -> None:
        """Leave the lobby and play with `count` players."""
        self.in_lobby = False
        self.player_count = count
        self.lives = [LIVES] * count
        self.game_over = False
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
        if self.game_over:
            # New match: everyone gets their lives back
            self.lives = [LIVES] * self.player_count
            self.game_over = False
        self.paused = False
        self.countdown = 5 * FPS
        self.hit_registered = [False] * self.player_count
        self.missing_frames = [0] * self.player_count
        self.hit_message = "Game restarting..."
        self.hit_message_timer = 0
        self.hit_timer = 0
        self.body_polygons = []
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

        # Track players every frame (also while paused / counting down) so
        # their boxes and labels stay on screen.
        slots = self._assign_players(frame.people)
        self.person_boxes = [
            (i, tuple(person.box)) for i, person in enumerate(slots) if person is not None
        ]

        # If paused, only update message timer
        if self.paused:
            return
        
        # Handle countdown
        if self.countdown > 0:
            self.countdown -= 1
            return  # Don't update game during countdown
        
        # Store body outlines for drawing
        self.body_polygons = []
        
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
        for player_idx, person in enumerate(slots):
            if person is not None and self.lives[player_idx] > 0:
                collision, body_polygon = self.ball.check_collision(person)
                self.body_polygons.append((player_idx, body_polygon))
                
                if collision and not self.hit_registered[player_idx]:
                    # Hit! Lose ONE life (shows the message and pauses)
                    self._lose_life(player_idx, "HIT!")
                    self.hit_registered[player_idx] = True
                    self.hit_timer = 45
                    self.hit_position = (int(self.ball.x), int(self.ball.y))
                    
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

        # Players who stay out of frame too long lose a life
        if not self.paused:
            self._check_offscreen(slots)
        
        # Update ball color based on speed
        speed = math.sqrt(self.ball.vx**2 + self.ball.vy**2)
        if speed > 15:
            self.ball.color = RED
        elif speed > 8:
            self.ball.color = ORANGE
        else:
            self.ball.color = YELLOW

    def _lose_life(self, player_idx: int, reason: str) -> None:
        """Take one life from P(player_idx+1), show why, and pause until R."""
        self.lives[player_idx] = max(0, self.lives[player_idx] - 1)
        self.hit_message = self._hit_message(player_idx, reason)
        self.hit_message_timer = 0  # Keep showing until reset
        self.paused = True

    def _check_offscreen(self, slots: list[Person | None]) -> None:
        """Count how long each active player has been missing; penalise at the limit."""
        for i, person in enumerate(slots):
            if person is not None or self.lives[i] == 0:
                self.missing_frames[i] = 0
                continue
            self.missing_frames[i] += 1
            if self.missing_frames[i] >= OFFSCREEN_FRAMES:
                self.missing_frames[i] = 0
                self._lose_life(i, "LEFT THE SCREEN!")
                return  # one penalty per pause, like a hit

    def _hit_message(self, player_idx: int, reason: str = "HIT!") -> str:
        """Message after P(player_idx+1) loses a life; also flags the end of the match."""
        name = f"P{player_idx + 1}"
        alive = [i for i, lives in enumerate(self.lives) if lives > 0]
        if self.player_count == 1 and not alive:
            self.game_over = True
            return "GAME OVER! Press R to play again"
        if self.player_count > 1 and len(alive) <= 1:
            self.game_over = True
            winner = f"P{alive[0] + 1} WINS!" if alive else "Nobody wins!"
            return f"{winner} Press R to play again"
        if self.lives[player_idx] == 0:
            return f"{name} is OUT! Press R to resume"
        return f"{name} {reason} Press R to resume"

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
            " | ".join(f"P{i + 1}: {n}/{LIVES} lives" for i, n in enumerate(self.lives)),
            f"Ball speed: {math.sqrt(self.ball.vx**2 + self.ball.vy**2):.1f} px/f",
            "NOTE: Red ball = fast, orange = medium, yellow = slow",
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
        self._draw_rules(canvas, top=84 + 24, bottom=self.h - 84 - 24)

        count = len(self.lobby_people)
        if self.can_start:
            label = "player" if count == 1 else "players"
            message, color = f"{count} {label} in frame  -  press SPACE to start", ACCENT
        else:
            message = f"Need {MIN_PLAYERS} to {MAX_PLAYERS} players in frame  -  found {count}"
            color = WHITE
        draw_text(canvas, message, self.w // 2, self.h - 44, 1.0, color, "center", outline=True)
        draw_text(canvas, "or press 1 / 2 / 3 to choose", self.w // 2, self.h - 14, 0.6, MUTED, "center")

    def _draw_rules(self, canvas: pygame.Surface, top: int, bottom: int) -> None:
        """Translucent card with the rules, centred between the lobby bands.

        Kept see-through so the camera feed and player boxes show behind it.
        """
        lines = [f"{n}. {rule}" for n, rule in enumerate(RULES, 1)]
        max_w = min(self.w - 64, 980)
        scale = 0.75
        while True:  # shrink until the widest rule fits the card
            widest = max(cv2.getTextSize(l, FONT, scale, max(1, round(scale * 1.6)))[0][0] for l in lines)
            if widest <= max_w - 64 or scale <= 0.4:
                break
            scale -= 0.05
        line_h = int(46 * scale / 0.75)
        card_h = min(bottom - top, 70 + line_h * len(lines) + 16)
        card_w = widest + 64
        card_x = (self.w - card_w) // 2
        card_y = top + (bottom - top - card_h) // 2

        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        pygame.draw.rect(card, (*BLACK, 140), card.get_rect(), border_radius=12)
        canvas.blit(card, (card_x, card_y))

        draw_text(canvas, "HOW TO PLAY", self.w // 2, card_y + 44, 1.0, ACCENT, "center", outline=True)
        for k, line in enumerate(lines):
            y = card_y + 70 + line_h * (k + 1) - 12
            draw_text(canvas, line, card_x + 32, y, scale, WHITE, outline=True)

    def _draw_offscreen_warnings(self, canvas: pygame.Surface) -> None:
        """'Come back!' countdown for players who have stepped out of frame."""
        warn_after = FPS // 2  # ignore brief detection flickers
        y = self.h - 90
        for i, missing in enumerate(self.missing_frames):
            if missing < warn_after or self.lives[i] == 0:
                continue
            left = (OFFSCREEN_FRAMES - missing) / FPS
            text = f"P{i + 1} come back! {left:.1f}s"
            draw_text(canvas, text, self.w // 2, y, 1.1, PLAYER_COLORS[i], "center", outline=True)
            y -= 44

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

    def _draw_lives(self, canvas: pygame.Surface) -> None:
        """One row per player: label plus LIVES hearts (filled = left, outlined = lost)."""
        size = 26  # heart width in px
        gap = 8
        row_h = 42
        hearts_w = LIVES * size + (LIVES - 1) * gap
        right = self.w - 24
        for i in range(self.player_count):
            color = PLAYER_COLORS[i]
            cy = 36 + i * row_h
            label_color = color if self.lives[i] > 0 else MUTED
            draw_text(canvas, f"P{i + 1}", right - hearts_w - 14, cy + 10, 0.9, label_color, "right", outline=True)
            for k in range(LIVES):
                cx = right - hearts_w + k * (size + gap) + size // 2
                _draw_heart(canvas, cx, cy, size, color, filled=k < self.lives[i])

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        """Draw game elements."""
        if self.in_lobby:
            self._draw_lobby(canvas)
            return

        # Draw player bounding boxes with their labels (greyed out once a player is out)
        for player_idx, box in self.person_boxes:
            out = self.lives[player_idx] == 0
            color = MUTED if out else PLAYER_COLORS[player_idx]
            x1, y1, x2, y2 = (int(v) for v in box)
            pygame.draw.rect(canvas, color, (x1, y1, x2 - x1, y2 - y1), 2)
            label = f"P{player_idx + 1}" + (" OUT" if out else "")
            draw_text(canvas, label, x1 + 6, max(y1 - 10, 30), 0.9, color, outline=True)

        # Draw person body polygons
        for player_idx, body_polygon in self.body_polygons:
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
        
        # Draw lives in the top-right: one row per player, P1 on top
        self._draw_lives(canvas)

        # Warn players who are out of frame (only while the ball is moving)
        if not self.paused and self.countdown == 0:
            self._draw_offscreen_warnings(canvas)
        
        # Draw instructions strip at bottom
        instructions = "[D] Debug | [R] Reset | [F] Fullscreen | [Q/Esc] Quit"
        instr_scale = 0.65
        instr_thickness = max(1, round(instr_scale * 1.6))
        (instr_w, instr_h), _ = cv2.getTextSize(instructions, FONT, instr_scale, instr_thickness)
        instr_bg = pygame.Surface((instr_w + 32, instr_h + 16), pygame.SRCALPHA)
        pygame.draw.rect(instr_bg, (*BLACK, 180), (0, 0, instr_bg.get_width(), instr_bg.get_height()), border_radius=6)
        canvas.blit(instr_bg, (16, self.h - instr_h - 28))
        draw_text(canvas, instructions, 32, self.h - 18, scale=instr_scale, color=WHITE, align="left", outline=True)
