"""Dodgeball Game: Avoid the bouncing ball! Each player has 3 lives; a ball hit costs one."""

from __future__ import annotations

import math
import random

import pygame

from main import audio, content, styles
from main.countdown import TIMER_VISIBLE_AT_SECONDS, draw_countdown_digit
from main.games.strike.screens import CountdownTick
from main import content, styles
from main.end_screen import (
    EndChoice,
    EndScreen,
    LivesRow,
    draw_card_art,
    draw_end_screen,
    draw_headline,
    draw_lives_rows,
    winners_line,
)
from main.nav import MenuCommand, StartGame
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose import KP, Person, PoseFrame
from main.pose.library import left_to_right
from main.ready_up import ReadyUp, ReadyUpConfig, draw_player_label, draw_ready_up, head_anchor
from main.settings import ASSETS, DodgeballConfig
from main.ui.paper import PLAYER_INK_DODGEBALL

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
COUNTDOWN_SECONDS = 3  # before the ball launches at match start
HIT_RESTART_SECONDS = 5  # after a hit the round restarts by itself (3, 2, 1 shown)
LIVES = _cfg.lives
OFFSCREEN_SECONDS = int(_cfg.offscreen_seconds)
OFFSCREEN_FRAMES = _cfg.offscreen_frames


def _still_paths() -> tuple:
    root = ASSETS / "ready_up" / "dodgeball"
    return tuple(sorted(root.glob("pose_*.png")))


_HEART_SPRITES = {True: ASSETS / "sprites" / "heart-alive.png", False: ASSETS / "sprites" / "heart-dead.png"}
_heart_cache: dict[tuple[bool, int], pygame.Surface] = {}


def _heart_sprite(filled: bool, size: int) -> pygame.Surface:
    """Pixel-art heart (alive or lost) scaled to `size` px, loaded once per size."""
    key = (filled, size)
    if key not in _heart_cache:
        img = pygame.image.load(str(_HEART_SPRITES[filled]))
        if pygame.display.get_surface() is not None:
            img = img.convert_alpha()
        # Nearest-neighbour keeps the pixel-art edges crisp.
        _heart_cache[key] = pygame.transform.scale(img, (size, size))
    return _heart_cache[key]


def _draw_heart(canvas: pygame.Surface, cx: int, cy: int, size: int, filled: bool) -> None:
    """Heart sprite centred on (cx, cy), `size` px wide: alive, or the lost-life outline."""
    sprite = _heart_sprite(filled, size)
    canvas.blit(sprite, sprite.get_rect(center=(cx, cy)))


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


LABEL_SCALE = 1.1  # player "P1" labels over heads (base label size is 0.9)
LABEL_PAD = 16  # px between the top of the head and the label baseline


def _label_anchor(person: Person, min_conf: float = 0.3) -> tuple[float, float]:
    """Baseline point for a player label, padded clear of the top of the head.

    The head top is estimated from the nose: it sits about 0.8x the
    nose-to-shoulder drop above the nose, so the gap scales with how close the
    player stands. Falls back to the top of the person box.
    """
    x1, y1, x2, _ = person.box
    conf, xy = person.conf, person.xy
    if float(conf[KP.NOSE]) < min_conf:
        return (x1 + x2) / 2, y1 - LABEL_PAD
    nx, ny = float(xy[KP.NOSE][0]), float(xy[KP.NOSE][1])
    shoulders = [
        float(xy[k][1]) for k in (KP.L_SHOULDER, KP.R_SHOULDER) if float(conf[k]) >= min_conf
    ]
    if shoulders:
        drop = max(0.0, sum(shoulders) / len(shoulders) - ny)
        head_top = ny - 0.8 * drop
    else:
        head_top = ny - 0.12 * (person.box[3] - y1)  # ~ head size from body height
    return nx, head_top - LABEL_PAD


class DodgeballGame:
    title = copy.window_title

    def __init__(self, size, config: DodgeballConfig | None = None):
        self.w, self.h = size
        # Same recipes as Duel (and the same optional assets/sounds/*.wav overrides):
        # its short "steady" tone for wall bounces, its "hit" gunshot for player hits.
        # Match flow: start jingle, countdown ticks + "go", game-over sting, then
        # the winner fanfare (Duel's match_over recipe, extended). Each can be
        # replaced by dropping assets/sounds/<name>.wav in.
        synth = {
            "steady": lambda: audio.tone(587, 0.25),
            "hit": lambda: audio.gunshot(0.4, seed=7),
            "match_start": lambda: audio.arpeggio([523, 659, 784, 1047], step=0.1),
            "tick": lambda: audio.tone(440, 0.12, decay=0.05),
            "go": lambda: audio.tone(880, 0.35, decay=0.12),
            "game_over": lambda: audio.arpeggio([392, 330, 262, 196], step=0.2),
            "match_over": lambda: audio.arpeggio([392, 494, 587, 784, 587, 784, 988], step=0.13),
        }
        self.sounds = {
            name: audio.load_or(ASSETS / "sounds" / f"{name}.wav", make) for name, make in synth.items()
        }
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
        self._countdown_total = COUNTDOWN_SECONDS
        self._last_tick: int | None = None

        self.hit_message = ""
        self.hit_message_timer = 0

        self.person_boxes: list[tuple[int, tuple[float, float, float, float]]] = []
        self.person_label_anchors: list[tuple[int, tuple[float, float]]] = []

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
        audio.play(self.sounds["match_start"])  # stands in for the first countdown tick
        self._begin_round(tick=False)
        self.hit_message = copy.get_ready

    def _begin_round(self, seconds: int = COUNTDOWN_SECONDS, tick: bool = True) -> None:
        """New ball, then a `seconds` countdown before it launches."""
        self.paused = False
        self.countdown = seconds * FPS
        self._countdown_total = seconds
        # tick=False: the caller's own sound stands in for the first digit.
        self._last_tick = None if tick else self._countdown_digit()[0]
        self._emit_countdown_tick()
        self.hit_registered = [False] * self.player_count
        self.missing_frames = [0] * self.player_count
        self.hit_message_timer = 0
        self._start_ball()

    def _countdown_digit(self) -> tuple[int, float]:
        """(seconds_left, digit_age), computed exactly like Strike's round countdown."""
        remaining = self.countdown / FPS
        # Capped so rounding can never show one more than the countdown length.
        seconds_left = min(math.ceil(remaining), math.ceil(self._countdown_total))
        return seconds_left, max(0.0, seconds_left - remaining)

    def _emit_countdown_tick(self) -> None:
        """Strike's CountdownTick: once per new digit; audible for the shown 3, 2, 1."""
        if self.countdown <= 0:
            return
        seconds_left, _ = self._countdown_digit()
        if seconds_left == self._last_tick:
            return
        self._last_tick = seconds_left
        self._on_countdown_tick(CountdownTick(seconds_left=seconds_left))

    def _on_countdown_tick(self, tick: CountdownTick) -> None:
        if tick.seconds_left <= TIMER_VISIBLE_AT_SECONDS:
            audio.play(self.sounds["tick"])

    def reset(self) -> None:
        """R key: clear ready-up choices, or rematch into ready-up after game over.

        Mid-match it does nothing: after a hit the round restarts by itself.
        """
        if self.in_lobby:
            self.ready_up.reset()
            return
        if self.game_over:
            self._enter_ready_up()

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
        self.person_label_anchors = [
            (i, _label_anchor(person)) for i, person in enumerate(slots) if person is not None
        ]

        if self.paused:
            return

        if self.countdown > 0:
            self.countdown -= 1
            if self.countdown == 0:
                audio.play(self.sounds["go"])  # ball launches next frame
            else:
                self._emit_countdown_tick()
            return

        self.ball.move()
        if self.ball.bounce(self.w, self.h):
            audio.play(self.sounds["steady"])

        if self.hit_message_timer > 0:
            self.hit_message_timer -= 1

        for i in range(len(self.hit_registered)):
            if not self.paused:
                self.hit_registered[i] = False

        for player_idx, person in enumerate(slots):
            if person is not None and self.lives[player_idx] > 0:
                collision, body_polygon = self.ball.check_collision(person)

                if collision and not self.hit_registered[player_idx]:
                    self._lose_life(player_idx, "HIT!")
                    audio.play(self.sounds["hit"])
                    self.hit_registered[player_idx] = True
                    break

        if not self.paused:
            self._check_offscreen(slots)

        speed = math.sqrt(self.ball.vx**2 + self.ball.vy**2)
        if speed > 15:
            self.ball.color, self.ball.pace = RED, "fast"
        elif speed > 8:
            self.ball.color, self.ball.pace = ORANGE, "medium"
        else:
            self.ball.color, self.ball.pace = YELLOW, "slow"

    def _lose_life(self, player_idx: int, reason: str) -> None:
        self.lives[player_idx] = max(0, self.lives[player_idx] - 1)
        was_over = self.game_over
        self.hit_message = self._hit_message(player_idx, reason)
        self.hit_message_timer = 0
        if not self.game_over:
            # Fresh ball and an automatic restart; the hit message stays up meanwhile.
            self._begin_round(seconds=HIT_RESTART_SECONDS)
            return
        self.paused = True
        if not was_over:
            alive = [i for i, lives in enumerate(self.lives) if lives > 0]
            has_winner = self.player_count > 1 and len(alive) == 1
            # Sting first; a winner then gets the fanfare queued right after it.
            fanfare = self.sounds["match_over"] if has_winner else None
            audio.play_then(self.sounds["game_over"], fanfare)

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
            return f"{name} is OUT!"
        return f"{name} {reason}"

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

    def _draw_results_body(self, canvas: pygame.Surface, rect: pygame.Rect, frame) -> None:
        """Winner (or solo game over), hearts left per player, dodge illustration."""
        results = content.Results
        if self.player_count <= 1:
            headline, sub = results.solo_over, results.solo_sub
        else:
            alive = [i + 1 for i, lives in enumerate(self.lives) if lives > 0]
            headline, sub = winners_line(alive), ""
        bottom = draw_headline(canvas, frame, rect, headline, sub, size=64)
        top = bottom + frame.px(28)
        rows_rect = pygame.Rect(rect.x, top, min(int(rect.width * 0.6), frame.px(660)), rect.bottom - top)
        alive_count = sum(1 for lives in self.lives if lives > 0)
        draw_lives_rows(
            canvas,
            frame,
            rows_rect,
            [
                LivesRow(
                    player=i + 1,
                    lives=lives,
                    max_lives=LIVES,
                    winner=self.player_count > 1 and lives > 0 and alive_count == 1,
                )
                for i, lives in enumerate(self.lives)
            ],
            palette=PLAYER_INK_DODGEBALL,
        )
        art_box = pygame.Rect(rows_rect.right + frame.px(40), rect.y, rect.right - rows_rect.right - frame.px(40), rect.height)
        draw_card_art(canvas, ASSETS / "ui" / "how_to_play" / "dodgeball" / "step_2.png", art_box)

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
                _draw_heart(canvas, cx, cy, size, filled=k < self.lives[i])

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        if self.in_lobby:
            draw_ready_up(canvas, self.ready_up, theme=theme, snap=self.gesture_snapshot)
            return
        if self.game_over:
            draw_end_screen(
                canvas,
                self._end,
                snap=self.gesture_snapshot,
                title=content.Results.dodgeball_title,
                body=self._draw_results_body,
            )
            return

        anchor_by_slot = dict(self.person_label_anchors)
        for player_idx, box in self.person_boxes:
            out = self.lives[player_idx] == 0
            color = MUTED if out else PLAYER_COLORS[player_idx % len(PLAYER_COLORS)]
            anchor = anchor_by_slot.get(player_idx) or head_anchor(box)
            label = f"P{player_idx + 1}" + (" OUT" if out else "")
            draw_player_label(canvas, label, anchor, color, scale=LABEL_SCALE, face=theme.font)

        if self.countdown > 0:
            self._draw_launch_marker(canvas)
        self.ball.draw(canvas)

        if self.hit_message and (
            self.hit_message_timer > 0 or self.paused or self.countdown > 0
        ):
            draw_text(
                canvas,
                self.hit_message,
                self.w // 2,
                # Above the big countdown digit while it shows; else just above centre.
                int(self.h * 0.22) if self.game_over or self.countdown > 0 else self.h // 2 - 100,
                scale=1.4,
                color=RED,
                align="center",
                outline=True,
            )

        if self.countdown > 0:
            # Strike's round timer: same digit maths, font, size, blink and fade.
            seconds_left, digit_age = self._countdown_digit()
            draw_countdown_digit(canvas, seconds_left, digit_age, face=styles.STRIKE.font)

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
