"""Dodgeball Game: Avoid the bouncing ball! Each player has 5 lives; a ball hit costs one."""

from __future__ import annotations

import math
import random

import pygame

from main import content, styles
from main.end_screen import EndChoice, EndScreen, draw_end_screen
from main.nav import MenuCommand, StartGame
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose import Person, PoseFrame
from main.pose.library import left_to_right
from main.ready_up import ReadyUp, ReadyUpConfig, draw_player_label, draw_ready_up, head_anchor
from main.settings import ASSETS, DodgeballConfig

from .ball import Ball

theme = styles.DODGEBALL
copy = content.Dodgeball
_cfg = DodgeballConfig()

WHITE = theme.ink
BLACK = theme.bg
MUTED = theme.muted
ACCENT = theme.accent
RED = theme.danger
YELLOW = theme.ball_slow
ORANGE = theme.ball_medium
PLAYER_COLORS = list(theme.player)

MIN_PLAYERS = _cfg.min_players
MAX_PLAYERS = _cfg.max_players
FPS = _cfg.fps
LIVES = _cfg.lives
OFFSCREEN_SECONDS = int(_cfg.offscreen_seconds)
OFFSCREEN_FRAMES = _cfg.offscreen_frames


def _still_paths() -> tuple:
    root = ASSETS / "ready_up" / "dodgeball"
    return tuple(sorted(root.glob("pose_*.png")))


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
    return styles.draw_text(
        canvas, text, x, y, scale, color, align, outline, face=theme.font
    )


class DodgeballGame:
    title = copy.window_title

    def __init__(self, size, config: DodgeballConfig | None = None):
        self.w, self.h = size
        self.config = config if config is not None else DodgeballConfig()
        self.debug = bool(self.config.debug)

        self.ball = Ball(
            x=self.w // 2,
            y=self.h // 2,
            radius=50,
            max_speed=40.0,
            elasticity=0.95,
            color=theme.ball_medium,
        )

        self.in_lobby = True
        self.ready_up = self._new_ready_up()
        self.gesture_snapshot = None
        self.player_count = 0
        self.last_x: list[float] = []

        self.lives: list[int] = []
        self.game_over = False
        self.missing_frames: list[int] = []

        self.paused = False
        self.hit_registered: list[bool] = []
        self.countdown = 0

        self.hit_message = ""
        self.hit_message_timer = 0

        self.hit_timer = 0
        self.hit_position = (0, 0)

        self.person_boxes: list[tuple[int, tuple[float, float, float, float]]] = []
        self.person_noses: list[tuple[int, tuple[float, float] | None]] = []
        self.body_polygons: list[tuple[int, list | None]] = []

        self._end = EndScreen((self.w, self.h))
        self._pending_nav = None
        self._frame_ts = 0.0

    def _new_ready_up(self) -> ReadyUp:
        return ReadyUp(
            self.w,
            ReadyUpConfig(
                min_players=self.config.min_players,
                max_players=self.config.max_players,
                title=copy.how_to_play,
                how_to_lines=copy.ready_how_to,
                pose_stills=_still_paths(),
                hold_frames=self.config.gesture_hold_frames,
                fist_hold_frames=max(1, self.config.fps // 2),
                forget_frames=self.config.fps,
                debug=self.debug,
            ),
        )

    @property
    def gesture_hands(self) -> int:
        if self.game_over and not self.in_lobby:
            return NAV_GESTURE_HANDS
        return self.config.max_players * 2

    @property
    def wants_gestures(self) -> bool:
        return self.in_lobby or self.game_over

    def start(self, count: int, seed_x: list[float] | None = None) -> None:
        """Leave ready-up and play with `count` players."""
        self.in_lobby = False
        self.player_count = count
        self.lives = [LIVES] * count
        self.game_over = False
        self._end.reset()
        lobby_x = seed_x if seed_x is not None else []
        self.last_x = [
            lobby_x[i] if i < len(lobby_x) else self.w * (i + 1) / (count + 1)
            for i in range(count)
        ]
        self._begin_round()
        self.hit_message = copy.get_ready

    def _begin_round(self) -> None:
        self.paused = False
        self.countdown = 5 * FPS
        self.hit_registered = [False] * self.player_count
        self.missing_frames = [0] * self.player_count
        self.hit_message_timer = 0
        self.hit_timer = 0
        self.body_polygons = []
        self._start_ball()

    def reset(self) -> None:
        """R key: clear ready-up choices, rematch into ready-up, or resume mid-match."""
        if self.in_lobby:
            self.ready_up.reset()
            return
        if self.game_over:
            self._enter_ready_up()
            return
        self.hit_message = copy.restarting
        self._begin_round()

    def _enter_ready_up(self) -> None:
        self.in_lobby = True
        self.game_over = False
        self.ready_up = self._new_ready_up()
        self._end.reset()
        self.hit_message = ""
        self._pending_nav = None

    def handle_command(self, command: MenuCommand) -> None:
        if not self.game_over or self.in_lobby:
            return
        choice = self._end.handle_command(command)
        if choice is not None:
            self._apply_end_choice(choice)

    def poll_nav(self):
        nav = self._pending_nav
        self._pending_nav = None
        return nav

    def _apply_end_choice(self, choice: EndChoice) -> None:
        if choice is EndChoice.MENU:
            self._pending_nav = StartGame(None)
            return
        self._enter_ready_up()

    def _start_ball(self) -> None:
        self.ball = Ball(
            x=random.randint(50, self.w - 50),
            y=random.randint(50, self.h - 50),
            radius=20,
            max_speed=40.0,
            elasticity=0.95,
        )

    def _assign_players(self, people: list[Person]) -> list[Person | None]:
        """Map detections to player slots P1..Pn using last known positions."""
        n = self.player_count
        tallest = self._nearest_to_players(people) if len(people) > n else list(people)
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

    def _nearest_to_players(self, people: list[Person]) -> list[Person]:
        pairs = sorted(
            (abs(self.last_x[s] - p.center_x), s, i)
            for s in range(self.player_count)
            for i, p in enumerate(people)
        )
        used_s: set[int] = set()
        used_i: set[int] = set()
        for _, s, i in pairs:
            if s not in used_s and i not in used_i:
                used_s.add(s)
                used_i.add(i)
        return [people[i] for i in sorted(used_i)]

    def update(self, frame: PoseFrame) -> None:
        self._frame_ts = frame.timestamp
        if self.in_lobby:
            snap = self.gesture_snapshot
            hands = snap.hands if snap is not None else ()
            started = self.ready_up.update(frame.people, hands)
            if started is not None:
                roster = [p for p in started.roster if isinstance(p, Person)]
                if not roster and started.roster:
                    # Candidate fallbacks shouldn't happen when people were tracked
                    roster = list(frame.people)[: len(started.roster)]
                self.start(len(roster), seed_x=[p.center_x for p in roster])
            return

        if self.game_over:
            choice = self._end.update(self.gesture_snapshot, frame.timestamp)
            if choice is not None:
                self._apply_end_choice(choice)
            return

        slots = self._assign_players(frame.people)
        self.person_boxes = [
            (i, tuple(person.box)) for i, person in enumerate(slots) if person is not None
        ]
        self.person_noses = []
        for i, person in enumerate(slots):
            if person is None:
                continue
            nose = None
            if float(person.conf[0]) >= 0.3:
                nose = (float(person.xy[0][0]), float(person.xy[0][1]))
            self.person_noses.append((i, nose))

        if self.paused:
            return

        if self.countdown > 0:
            self.countdown -= 1
            return

        self.body_polygons = []

        self.ball.move()
        self.ball.bounce(self.w, self.h)

        if self.hit_timer > 0:
            self.hit_timer -= 1
        if self.hit_message_timer > 0:
            self.hit_message_timer -= 1

        for i in range(len(self.hit_registered)):
            if not self.paused:
                self.hit_registered[i] = False

        for player_idx, person in enumerate(slots):
            if person is not None and self.lives[player_idx] > 0:
                collision, body_polygon = self.ball.check_collision(person)
                self.body_polygons.append((player_idx, body_polygon))

                if collision and not self.hit_registered[player_idx]:
                    self._lose_life(player_idx, "HIT!")
                    self.hit_registered[player_idx] = True
                    self.hit_timer = 45
                    self.hit_position = (int(self.ball.x), int(self.ball.y))

                    if body_polygon:
                        polygon_center_x = sum(p[0] for p in body_polygon) / len(body_polygon)
                        polygon_center_y = sum(p[1] for p in body_polygon) / len(body_polygon)
                    else:
                        polygon_center_x = self.w / 2
                        polygon_center_y = self.h / 2

                    dx = self.ball.x - polygon_center_x
                    dy = self.ball.y - polygon_center_y
                    dist = math.sqrt(dx * dx + dy * dy)

                    if dist < 1:
                        angle = random.uniform(0, 2 * math.pi)
                        self.ball.vx = math.cos(angle) * 15
                        self.ball.vy = math.sin(angle) * 15
                        self.ball.x = polygon_center_x + math.cos(angle) * (self.ball.radius + 30)
                        self.ball.y = polygon_center_y + math.sin(angle) * (self.ball.radius + 30)
                    else:
                        self.ball.vx = (dx / dist) * 15
                        self.ball.vy = (dy / dist) * 15
                        push_dist = self.ball.radius + 30
                        self.ball.x = polygon_center_x + (dx / dist) * push_dist
                        self.ball.y = polygon_center_y + (dy / dist) * push_dist

                    break

        if not self.paused:
            self._check_offscreen(slots)

        speed = math.sqrt(self.ball.vx**2 + self.ball.vy**2)
        if speed > 15:
            self.ball.color = RED
        elif speed > 8:
            self.ball.color = ORANGE
        else:
            self.ball.color = YELLOW

    def _lose_life(self, player_idx: int, reason: str) -> None:
        self.lives[player_idx] = max(0, self.lives[player_idx] - 1)
        self.hit_message = self._hit_message(player_idx, reason)
        self.hit_message_timer = 0
        self.paused = True

    def _check_offscreen(self, slots: list[Person | None]) -> None:
        for i, person in enumerate(slots):
            if person is not None or self.lives[i] == 0:
                self.missing_frames[i] = 0
                continue
            self.missing_frames[i] += 1
            if self.missing_frames[i] >= OFFSCREEN_FRAMES:
                self.missing_frames[i] = 0
                self._lose_life(i, "LEFT THE SCREEN!")
                return

    def _hit_message(self, player_idx: int, reason: str = "HIT!") -> str:
        name = f"P{player_idx + 1}"
        alive = [i for i, lives in enumerate(self.lives) if lives > 0]
        if self.player_count == 1 and not alive:
            self.game_over = True
            self._end.reset()
            return "GAME OVER!"
        if self.player_count > 1 and len(alive) <= 1:
            self.game_over = True
            self._end.reset()
            winner = f"P{alive[0] + 1} WINS!" if alive else "Nobody wins!"
            return winner
        if self.lives[player_idx] == 0:
            return f"{name} is OUT! Press R to resume"
        return f"{name} {reason} Press R to resume"

    def handle_key(self, key: int) -> None:
        if not self.in_lobby:
            return
        if key == pygame.K_SPACE and self.debug:
            started = self.ready_up.force_start()
            if started is not None:
                roster = [p for p in started.roster if isinstance(p, Person)]
                self.start(len(roster), seed_x=[p.center_x for p in roster])

    def render_camera(self, image_bgr):
        return image_bgr

    def debug_lines(self) -> list[str]:
        if self.in_lobby:
            return [
                f"Ready-up: {self.ready_up.ready_count} ready / "
                f"{len(self.ready_up.eligible)} eligible"
            ]
        return [
            " | ".join(f"P{i + 1}: {n}/{LIVES} lives" for i, n in enumerate(self.lives)),
            f"Ball speed: {math.sqrt(self.ball.vx**2 + self.ball.vy**2):.1f} px/f",
            "NOTE: Red ball = fast, orange = medium, yellow = slow",
        ]

    def _draw_offscreen_warnings(self, canvas: pygame.Surface) -> None:
        warn_after = FPS // 2
        y = self.h - 90
        for i, missing in enumerate(self.missing_frames):
            if missing < warn_after or self.lives[i] == 0:
                continue
            left = (OFFSCREEN_FRAMES - missing) / FPS
            text = f"P{i + 1} come back! {left:.1f}s"
            draw_text(canvas, text, self.w // 2, y, 1.1, PLAYER_COLORS[i], "center", outline=True)
            y -= 44

    def _draw_launch_marker(self, canvas: pygame.Surface) -> None:
        bx, by = int(self.ball.x), int(self.ball.y)
        r = int(self.ball.radius)
        pulse = (math.sin(self.countdown * 0.25) + 1) / 2
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
        size = 26
        gap = 8
        row_h = 42
        hearts_w = LIVES * size + (LIVES - 1) * gap
        right = self.w - 24
        for i in range(self.player_count):
            color = PLAYER_COLORS[i % len(PLAYER_COLORS)]
            cy = 36 + i * row_h
            label_color = color if self.lives[i] > 0 else MUTED
            draw_text(canvas, f"P{i + 1}", right - hearts_w - 14, cy + 10, 0.9, label_color, "right", outline=True)
            for k in range(LIVES):
                cx = right - hearts_w + k * (size + gap) + size // 2
                _draw_heart(canvas, cx, cy, size, color, filled=k < self.lives[i])

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        if self.in_lobby:
            draw_ready_up(canvas, self.ready_up, theme=theme)
            return

        nose_by_slot = {i: nose for i, nose in self.person_noses}
        for player_idx, box in self.person_boxes:
            out = self.lives[player_idx] == 0
            color = MUTED if out else PLAYER_COLORS[player_idx % len(PLAYER_COLORS)]
            anchor = head_anchor(box, nose_by_slot.get(player_idx))
            label = f"P{player_idx + 1}" + (" OUT" if out else "")
            draw_player_label(canvas, label, anchor, color, face=theme.font)

        for player_idx, body_polygon in self.body_polygons:
            if body_polygon is not None:
                color = PLAYER_COLORS[player_idx % len(PLAYER_COLORS)]
                temp_surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
                pygame.draw.polygon(temp_surf, (*color, 80), body_polygon, 2)
                canvas.blit(temp_surf, (0, 0))

        if self.countdown > 0:
            self._draw_launch_marker(canvas)
        self.ball.draw(canvas)

        if self.hit_timer > 0:
            alpha = int(255 * (self.hit_timer / 45))
            temp_surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
            radius = int(30 + (45 - self.hit_timer))
            pygame.draw.circle(temp_surf, (*RED, alpha), self.hit_position, radius, 3)
            x, y = self.hit_position
            pygame.draw.line(temp_surf, (*RED, alpha), (x - 25, y - 25), (x + 25, y + 25), 3)
            pygame.draw.line(temp_surf, (*RED, alpha), (x - 25, y + 25), (x + 25, y - 25), 3)
            canvas.blit(temp_surf, (0, 0))

        if self.hit_message and (
            self.hit_message_timer > 0 or self.paused or self.countdown > 0 or self.game_over
        ):
            draw_text(
                canvas,
                self.hit_message,
                self.w // 2,
                self.h // 2 - 100 if not self.game_over else int(self.h * 0.22),
                scale=1.4,
                color=RED,
                align="center",
                outline=True,
            )

        if self.game_over:
            draw_end_screen(
                canvas,
                self._end,
                theme=styles.SHELL,
                snap=self.gesture_snapshot,
                timestamp=self._frame_ts,
            )
            return

        if self.countdown > 0:
            countdown_sec = (self.countdown + 29) // 30
            draw_text(
                canvas,
                f"Starting in {countdown_sec}...",
                self.w // 2,
                self.h // 2,
                scale=1.5,
                color=YELLOW,
                align="center",
                outline=True,
            )

        self._draw_lives(canvas)

        if not self.paused and self.countdown == 0:
            self._draw_offscreen_warnings(canvas)

        instructions = "[D] Debug | [R] Reset | [F] Fullscreen | [Q/Esc] Quit"
        instr_scale = 0.65
        (instr_w, instr_h), _ = styles.text_size(instructions, instr_scale, theme.font)
        instr_bg = pygame.Surface((instr_w + 32, instr_h + 16), pygame.SRCALPHA)
        pygame.draw.rect(instr_bg, (*BLACK, 180), (0, 0, instr_bg.get_width(), instr_bg.get_height()), border_radius=6)
        canvas.blit(instr_bg, (16, self.h - instr_h - 28))
        draw_text(canvas, instructions, 32, self.h - 18, scale=instr_scale, color=WHITE, align="left", outline=True)
