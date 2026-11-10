"""Wild West Duel: pygame view + sounds on top of the pure Duel rules.

Look follows refrences/: white page, pixel font, hearts for lives. Players don't see the
camera; debug mode (D) puts the camera image behind the same UI.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

from strike_a_pose import audio
from strike_a_pose.config import ASSETS, Messages, from_env
from strike_a_pose.pose import GestureConfig, PoseFrame, PoseState, classify

from .float_path import FloatPath, ease_out, fade
from .logic import Duel, DuelConfig, Phase

WHITE = (255, 255, 255)
INK = (0, 0, 0)
SHADOW = (190, 190, 190)
HINT = (140, 140, 140)
SHOT_BG = (255, 133, 133)
NAMES = ("Player 1", "Player 2")
FONT_PATH = ASSETS / "fonts" / "PixelifySans.ttf"
SPRITES = ASSETS / "sprites"
MESSAGES = ASSETS / "messages"
SOUNDS = ASSETS / "sounds"


@dataclass(frozen=True)
class ViewConfig:
    early_float_time: float = 2.0  # seconds for "too early" to drift up the path and vanish
    early_fade_start: float = 0.5  # fraction of the trip after which it starts fading


@dataclass
class _Floater:
    path: FloatPath
    text: str
    start: float


class DuelGame:
    title = "Strike a Pose: Wild West Duel"
    background = WHITE

    def __init__(
        self,
        size,
        config: DuelConfig | None = None,
        gestures: GestureConfig | None = None,
        view: ViewConfig | None = None,
        rng: random.Random | None = None,
    ):
        self.w, self.h = size
        self.gestures = gestures or from_env(GestureConfig)
        self.view = view or from_env(ViewConfig)
        self.duel = Duel(config or from_env(DuelConfig))
        self.rng = rng or random.Random()
        self.states = (PoseState.MISSING, PoseState.MISSING)
        self.now = 0.0

        self.shot_msgs = Messages(MESSAGES / "shot.txt", "TOO SLOW HOMBRE", self.rng)
        self.win_msgs = Messages(MESSAGES / "win.txt", "PAY UP YOU SON OF A GUN!", self.rng)
        self.early_msgs = Messages(MESSAGES / "early.txt", "too early....", self.rng)
        self.shot_msg = ""
        self.win_msg = ""
        self.win_img: pygame.Surface | None = None
        self.floaters: list[_Floater] = []
        self.paths = (FloatPath(size, 0), FloatPath(size, 1))

        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self.sz_main = int(0.11 * self.h)  # READY / STEADY / BANG!
        self.sz_label = int(0.042 * self.h)  # Player N, ms, too early
        self.sz_shot = int(0.05 * self.h)  # TOO SLOW HOMBRE
        self.sz_title = int(0.05 * self.h)  # PLAYER N WINS
        self.sz_msg = int(0.034 * self.h)  # win message, hints

        heart = int(0.057 * self.h)
        self.heart_alive = pygame.transform.scale(_load_png(SPRITES / "heart-alive.png"), (heart, heart))
        self.heart_dead = pygame.transform.scale(_load_png(SPRITES / "heart-dead.png"), (heart, heart))
        self.cowboys = sorted((SPRITES / "cowboys").glob("*.png"))

        synth = {
            "ready": lambda: audio.tone(440, 0.25),
            "steady": lambda: audio.tone(587, 0.25),
            "bang": lambda: audio.gunshot(),
            "early": lambda: audio.tone(150, 0.4),
            "hit": lambda: audio.gunshot(0.4, seed=7),
            "match_over": lambda: audio.arpeggio([392, 494, 587, 784]),
        }
        self.sounds = {name: audio.load_or(SOUNDS / f"{name}.wav", make) for name, make in synth.items()}

    # -- Game protocol ----------------------------------------------------------------

    def reset(self) -> None:
        self.duel.reset()
        self.floaters.clear()

    def update(self, frame: PoseFrame) -> None:
        self.step(frame.timestamp, tuple(classify(p, self.gestures) for p in frame.players))

    def step(self, now: float, states: tuple[PoseState, PoseState]) -> None:
        self.now = now
        self.states = states
        for name, player in self.duel.update(now, states):
            if name in ("ready", "abort"):
                self.floaters.clear()
            elif name == "early":
                self.floaters.append(_Floater(self.paths[player], self.early_msgs.pick(), self.now))
            elif name == "hit":
                self.shot_msg = self.shot_msgs.pick()
            elif name == "match_over":
                self.win_msg = self.win_msgs.pick()
                self.win_img = self._pick_cowboy()
            audio.play(self.sounds.get(name))

    def debug_lines(self) -> list[str]:
        d = self.duel
        return [
            f"phase {d.phase.value}  P1 {self.states[0].value}  P2 {self.states[1].value}",
            f"early {d.early}  draw_t {[None if t is None else round(t, 3) for t in d.draw_time]}",
        ]

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        d = self.duel
        if d.phase == Phase.MATCH_OVER and not d.showing_final_round(self.now):
            self._draw_winner(canvas)
            return

        if d.phase == Phase.ROUND_OVER or d.showing_final_round(self.now):
            self._draw_result(canvas)
        else:
            self._draw_header(canvas)
            if d.phase == Phase.WAIT_START:
                self._draw_waiting(canvas)
            elif d.phase in (Phase.READY, Phase.STEADY, Phase.BANG):
                word = {Phase.READY: "READY", Phase.STEADY: "STEADY", Phase.BANG: "BANG!"}[d.phase]
                self._text(canvas, word, self.sz_main, (self.w / 2, self.h / 2), bold=True, shadow=True)
        self._draw_floaters(canvas)

    # -- screens ----------------------------------------------------------------------

    def _draw_header(self, canvas):
        heart_w = self.heart_alive.get_width()
        gap = int(0.079 * self.h)
        lives = self.duel.config.lives
        for i in (0, 1):
            cx = self._side_x(i)
            self._text(canvas, NAMES[i], self.sz_label, (cx, 0.09 * self.h))
            left = self.duel.lives_left(i)
            x0 = cx - gap * (lives - 1) / 2
            for k in range(lives):
                img = self.heart_alive if k < left else self.heart_dead
                canvas.blit(img, (int(x0 + k * gap - heart_w / 2), int(0.18 * self.h - heart_w / 2)))

    def _draw_waiting(self, canvas):
        d = self.duel
        missing = [NAMES[i].upper() for i in (0, 1) if d.missing[i]]
        if missing:
            self._text(canvas, "WAITING FOR", self.sz_msg, (self.w / 2, 0.44 * self.h))
            self._text(canvas, " & ".join(missing), self.sz_shot, (self.w / 2, 0.52 * self.h), bold=True)
        else:
            self._text(canvas, "GET READY, PARTNERS", self.sz_shot, (self.w / 2, 0.47 * self.h), bold=True, shadow=True)
            self._progress(canvas, d.start_progress(self.now), 0.56 * self.h)
        for i, state in enumerate(self.states):
            if state == PoseState.DRAWN:
                self._text(canvas, "lower your gun", self.sz_label, (self._side_x(i), 0.877 * self.h), color=HINT)

    def _draw_result(self, canvas):
        r = self.duel.last_result
        if r is not None and r.reason == "hit":
            loser = 1 - r.winner
            canvas.fill(SHOT_BG, pygame.Rect(0 if loser == 0 else self.w // 2, 0, self.w - self.w // 2, self.h))
        self._draw_header(canvas)
        if r is None:
            return
        if r.reason == "hit":
            self._text(canvas, self.shot_msg.upper(), self.sz_shot, (self._side_x(1 - r.winner), self.h / 2), color=WHITE, bold=True, max_width=0.44 * self.w)
        else:
            headline = {"tie": "DEAD EVEN", "timeout": "NOBODY FIRED", "void": "BOTH TOO EARLY"}[r.reason]
            self._text(canvas, headline, self.sz_main * 2 // 3, (self.w / 2, self.h / 2), bold=True, shadow=True)
        for i in (0, 1):
            if r.early[i]:
                text = "too early"
            elif r.reaction_ms[i] is not None:
                text = f"{r.reaction_ms[i]:.0f} ms"
            else:
                text = "-"
            self._text(canvas, text, self.sz_label, (self._side_x(i), 0.905 * self.h))

    def _draw_winner(self, canvas):
        d = self.duel
        self._text(canvas, f"{NAMES[d.match_winner].upper()} WINS", self.sz_title, (self.w / 2, 0.15 * self.h), bold=True)
        if self.win_img is not None:
            canvas.blit(self.win_img, self.win_img.get_rect(center=(self.w // 2, int(0.49 * self.h))))
        self._text(canvas, self.win_msg.upper(), self.sz_msg, (self.w / 2, 0.68 * self.h), bold=True, max_width=0.9 * self.w)
        if d.can_restart(self.now):
            self._text(canvas, "lower your guns to play again", self.sz_msg, (self.w / 2, 0.9 * self.h), color=HINT)

    def _draw_floaters(self, canvas):
        dur = max(0.01, self.view.early_float_time)
        alive = []
        for f in self.floaters:
            t = (self.now - f.start) / dur
            if t >= 1:
                continue
            alive.append(f)
            alpha = int(255 * fade(t, self.view.early_fade_start))
            x, y = f.path.at(ease_out(t))
            # keep the whole text inside its player's half, even where the path hugs the edge
            half_w = self._font(self.sz_label, False).size(f.text)[0] / 2
            margin = 0.02 * self.w
            lo, hi = (0, self.w / 2) if f.path.player == 0 else (self.w / 2, self.w)
            x = min(max(x, lo + margin + half_w), hi - margin - half_w)
            self._text(canvas, f.text, self.sz_label, (x, y), alpha=alpha)
        self.floaters = alive

    # -- helpers ----------------------------------------------------------------------

    def _side_x(self, i: int) -> float:
        return self.w * (0.25 if i == 0 else 0.75)

    def _font(self, size: int, bold: bool) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            try:
                font = pygame.font.Font(str(FONT_PATH), size)
            except (FileNotFoundError, OSError):
                font = pygame.font.SysFont("menlo,courier", size)
            font.bold = bold
            self._fonts[key] = font
        return self._fonts[key]

    def _text(self, canvas, text, size, center, color=INK, bold=False, shadow=False, alpha=255, max_width=None):
        font = self._font(size, bold)
        if max_width is not None and font.size(text)[0] > max_width:  # shrink to fit
            size = max(8, int(size * max_width / font.size(text)[0]))
            font = self._font(size, bold)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(int(center[0]), int(center[1])))
        if shadow:
            off = max(2, size // 22)
            shade = font.render(text, True, SHADOW)
            shade.set_alpha(alpha)
            canvas.blit(shade, rect.move(off, off))
        surf.set_alpha(alpha)
        canvas.blit(surf, rect)

    def _progress(self, canvas, frac, cy):
        bw, bh = int(self.w * 0.3), int(self.h * 0.03)
        border = max(2, self.h // 240)
        rect = pygame.Rect(0, 0, bw, bh)
        rect.center = (self.w // 2, int(cy))
        pygame.draw.rect(canvas, WHITE, rect)
        pygame.draw.rect(canvas, INK, (rect.x, rect.y, int(bw * frac), bh))
        pygame.draw.rect(canvas, INK, rect, border)

    def _pick_cowboy(self) -> pygame.Surface | None:
        if not self.cowboys:
            return None
        img = _load_png(self.rng.choice(self.cowboys))
        target_h = int(0.27 * self.h)
        w, h = img.get_size()
        return pygame.transform.smoothscale(img, (max(1, round(w * target_h / h)), target_h))


def _load_png(path) -> pygame.Surface:
    img = pygame.image.load(str(path))
    return img.convert_alpha() if pygame.display.get_surface() else img
