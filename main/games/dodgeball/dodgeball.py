"""Dodgeball Game: Avoid the bouncing ball! Lives scale with player count; a hit costs one."""

from __future__ import annotations

import math
import random

import pygame

from main import audio, content, styles
from main.countdown import TIMER_VISIBLE_AT_SECONDS
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
from main.games.strike.game import draw_countdown_timer
from main.games.strike.play import _load_sounds
from main.games.strike.screens import CountdownTick
from main.nav import MenuCommand, StartGame
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose import Person, PoseFrame
from main.ready_up import ReadyUp, ReadyUpConfig, draw_ready_up
from main.settings import ASSETS, DodgeballConfig
from main.ui import paper
from main.ui.paper import INK_FAINT, MARKER_FONT, Frame

from . import sketches
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
OFFSCREEN_SECONDS = int(_cfg.offscreen_seconds)
OFFSCREEN_FRAMES = _cfg.offscreen_frames

# Match length by roster size. 1p kept for debug / soft solo bones.
LIVES_BY_COUNT = {1: 3, 2: 3, 3: 2, 4: 1}


def lives_for_player_count(count: int) -> int:
    """Hearts each seat starts with for this roster size."""
    if count in LIVES_BY_COUNT:
        return LIVES_BY_COUNT[count]
    raise ValueError(f"unsupported dodgeball player count: {count}")


def seat_label_color(player: int, lives: int) -> tuple[int, int, int]:
    """P# ink while alive; faint gray when out (1-based `player`)."""
    return paper.player_ink(player) if lives > 0 else INK_FAINT


def _still_paths() -> tuple:
    root = ASSETS / "ready_up" / "dodgeball"
    return tuple(sorted(root.glob("pose_*.png")))


def _draw_heart(canvas: pygame.Surface, cx: int, cy: int, size: int, filled: bool) -> None:
    """Hand-drawn heart centred on (cx, cy), `size` px wide: alive, or a crossed-out lost life."""
    sprite = sketches.heart_surface(filled, size)
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
    face=None,
) -> pygame.Rect:
    return styles.draw_text(
        canvas, text, x, y, scale, color, align, outline, face=face or theme.font
    )


# Hand-drawn faces like the rest of the paper UI: Patrick Hand for labels,
# Permanent Marker for banners (hit / win messages) and the countdown digit.
BANNER_SCALE = 3.6  # "P1 HIT!" / "P2 WINS!"
WARNING_SCALE = 2.6  # "P1 come back! 1.5s"
OFFSCREEN_SCALE = 3.0  # "P1 LEFT THE SCREEN!": white Patrick Hand, like Strike's "Next round in"

# Life counter sized like High Noon's header (design px in the menu's 1552x873 space).
HEART_DESIGN_PX = 50
HEART_GAP_DESIGN_PX = 14
TAG_DESIGN_PX = 38


class DodgeballGame:
    title = copy.window_title

    def __init__(self, size, config: DodgeballConfig | None = None):
        self.w, self.h = size
        # Rubber-ball "bounce" thump for wall bounces; Duel's "hit" gunshot for player hits.
        # Match flow: start jingle, countdown ticks + "go", game-over sting, then
        # the winner fanfare (Duel's match_over recipe, extended). Each can be
        # replaced by dropping assets/sounds/<name>.wav in.
        synth = {
            "bounce": lambda: audio.bounce(),
            "hit": lambda: audio.gunshot(0.4, seed=7),
            "match_start": lambda: audio.arpeggio([523, 659, 784, 1047], step=0.1),
            "go": lambda: audio.tone(880, 0.35, decay=0.12),
            "game_over": lambda: audio.arpeggio([392, 330, 262, 196], step=0.2),
            "match_over": lambda: audio.arpeggio([392, 494, 587, 784, 587, 784, 988], step=0.13),
        }
        self.sounds = {
            name: audio.load_or(ASSETS / "sounds" / f"{name}.wav", make) for name, make in synth.items()
        }
        # Countdown tick: Strike's own sound, so both countdowns sound the same.
        self.sounds["tick"] = _load_sounds()["tick"]
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
        self.max_lives = 0  # hearts each seat started with this match
        self.game_over = False
        self.missing_frames: list[int] = []

        self.paused = False
        self.hit_registered: list[bool] = []
        self.countdown = 0
        self._countdown_total = COUNTDOWN_SECONDS
        self._last_tick: int | None = None

        self.hit_message = ""
        self.hit_message_timer = 0
        # Who the message is about, and whether it's an off-screen loss (white) or a ball hit (their colour).
        self.hit_message_player: int | None = None
        self.hit_message_offscreen = False

        self._frame = Frame(self.w, self.h)
        self._tag_face = paper.hand(self._frame, TAG_DESIGN_PX)

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
        self.max_lives = lives_for_player_count(count)
        self.lives = [self.max_lives] * count
        self.game_over = False
        self._end.reset()
        lobby_x = seed_x if seed_x is not None else []
        self.last_x = [
            lobby_x[i] if i < len(lobby_x) else self.w * (i + 1) / (count + 1)
            for i in range(count)
        ]
        audio.play(self.sounds["match_start"])  # stands in for the first countdown tick
        self._begin_round(tick=False)
        self.hit_message = ""

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
        """Sticky map detections → seats P1..Pn by nearest `last_x` (never L→R rebind)."""
        n = self.player_count
        slots: list[Person | None] = [None] * n
        if n <= 0 or not people:
            return slots
        pairs = sorted(
            (abs(self.last_x[s] - p.center_x), s, i)
            for s in range(n)
            for i, p in enumerate(people)
        )
        used_s: set[int] = set()
        used_i: set[int] = set()
        for _, s, i in pairs:
            if s in used_s or i in used_i:
                continue
            slots[s] = people[i]
            used_s.add(s)
            used_i.add(i)
            if len(used_s) == n or len(used_i) == len(people):
                break
        for i, person in enumerate(slots):
            if person is not None:
                self.last_x[i] = person.center_x
        return slots

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
            choice = self._end.update(self.gesture_snapshot, frame.timestamp, frame.people)
            if choice is not None:
                self._apply_end_choice(choice)
            return

        slots = self._assign_players(frame.people)

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
            audio.play(self.sounds["bounce"])

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
        self.hit_message_player = player_idx
        self.hit_message_offscreen = reason == "LEFT THE SCREEN!"
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

    def debug_skip_to_results(self) -> bool:
        """`--debug` + R after ready-up: jump to game-over RESULTS. False → shell may reset."""
        if not self.debug or self.in_lobby or not self.lives:
            return False
        if len(self.lives) == 1:
            # Solo bone: keep the one player alive and end the match.
            pass
        else:
            self.lives = [self.max_lives if i == 0 else 0 for i in range(len(self.lives))]
        self.game_over = True
        self.paused = True
        self._end.reset()
        return True

    def render_camera(self, image_bgr):
        if self.in_lobby or self.game_over or self.countdown <= 0:
            return image_bgr
        # Strike's countdown digit, drawn by Strike's own renderer onto the camera
        # image (translucent, no background), before the pygame overlays go on top.
        image = image_bgr.copy()
        draw_countdown_timer(image, *self._countdown_digit(), face=MARKER_FONT)
        return image

    def debug_lines(self) -> list[str]:
        if self.in_lobby:
            return [
                f"Ready-up: {self.ready_up.ready_count} ready / "
                f"{len(self.ready_up.eligible)} eligible"
            ]
        max_lives = self.max_lives or lives_for_player_count(max(1, self.player_count))
        return [
            " | ".join(f"P{i + 1}: {n}/{max_lives} lives" for i, n in enumerate(self.lives)),
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
                    max_lives=self.max_lives,
                    winner=self.player_count > 1 and lives > 0 and alive_count == 1,
                )
                for i, lives in enumerate(self.lives)
            ],
            palette=paper.PLAYER_INK,
        )
        art_box = pygame.Rect(rows_rect.right + frame.px(40), rect.y, rect.right - rows_rect.right - frame.px(40), rect.height)
        draw_card_art(canvas, ASSETS / "ui" / "how_to_play" / "dodgeball" / "step_2.png", art_box)

    def _draw_offscreen_warnings(self, canvas: pygame.Surface) -> None:
        warn_after = FPS // 2
        y = self.h - 40
        for i, missing in enumerate(self.missing_frames):
            if missing < warn_after or self.lives[i] == 0:
                continue
            left = (OFFSCREEN_FRAMES - missing) / FPS
            text = f"P{i + 1} come back! {left:.1f}s"
            draw_text(canvas, text, self.w // 2, y, WARNING_SCALE, WHITE, "center", outline=True)
            y -= 52

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
        """Top right, one row per player: coloured tag + hearts, at High Noon's sizes."""
        f = self._frame
        size = f.px(HEART_DESIGN_PX)
        step = size + f.px(HEART_GAP_DESIGN_PX)
        max_lives = max(1, self.max_lives)
        hearts_w = size + step * (max_lives - 1)
        right = self.w - f.px(28)
        row_h = size + f.px(22)
        top = f.px(28) + size // 2
        for i in range(self.player_count):
            cy = top + i * row_h
            hearts_left = right - hearts_w
            tag_color = seat_label_color(i + 1, self.lives[i])
            paper.draw_tag(
                canvas, f"P{i + 1}", self._tag_face, tag_color, (hearts_left - f.px(16), cy), "midright"
            )
            for k in range(max_lives):
                _draw_heart(canvas, hearts_left + k * step + size // 2, cy, size, filled=k < self.lives[i])

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
                pose=frame,
            )
            return

        if self.countdown > 0:
            self._draw_launch_marker(canvas)
        self.ball.draw(canvas)

        if self.hit_message and (
            self.hit_message_timer > 0 or self.paused or self.countdown > 0
        ):
            if self.hit_message_offscreen:
                # Off-screen loss: plain white hand lettering, like Strike's "Next round in".
                color, scale, face = WHITE, OFFSCREEN_SCALE, theme.font
            else:
                # Ball hit: Marker banner in the hit player's colour.
                idx = self.hit_message_player
                color = PLAYER_COLORS[idx % len(PLAYER_COLORS)] if idx is not None else RED
                scale, face = BANNER_SCALE, MARKER_FONT
            draw_text(
                canvas,
                self.hit_message,
                self.w // 2,
                # High on the frame during countdown / game-over; else just above centre.
                int(self.h * 0.22) if self.game_over or self.countdown > 0 else self.h // 2 - 100,
                scale=scale,
                color=color,
                align="center",
                outline=True,
                face=face,
            )

        self._draw_lives(canvas)

        if not self.paused and self.countdown == 0:
            self._draw_offscreen_warnings(canvas)
