"""Wild West Duel: pygame view + sounds on top of the pure Duel rules."""

from __future__ import annotations

import pygame

from strike_a_pose import audio
from strike_a_pose.app import sepia
from strike_a_pose.games.pose import GestureConfig, PoseFrame, PoseState, classify

from .logic import Duel, DuelConfig, Phase

INK = (40, 22, 10)
PAPER = (245, 225, 180)
RED = (200, 30, 20)
NAMES = ("PLAYER 1", "PLAYER 2")
FONT = "rockwell,georgia,timesnewroman,serif"
FLASH_TIME = 0.5


class DuelGame:
    title = "Strike a Pose: Wild West Duel"

    def __init__(self, size, config: DuelConfig | None = None, gestures: GestureConfig | None = None):
        self.w, self.h = size
        self.gestures = gestures or GestureConfig()
        self.duel = Duel(config or DuelConfig())
        self.states = (PoseState.MISSING, PoseState.MISSING)
        self.now = 0.0
        self.flash: tuple[int, float] | None = None  # (loser index, start time)

        s = self.h / 720
        self.font_huge = pygame.font.SysFont(FONT, int(170 * s), bold=True)
        self.font_big = pygame.font.SysFont(FONT, int(80 * s), bold=True)
        self.font_med = pygame.font.SysFont(FONT, int(44 * s), bold=True)
        self.font_small = pygame.font.SysFont(FONT, int(30 * s))

        self.sounds = {
            "ready": audio.tone(440, 0.25),
            "steady": audio.tone(587, 0.25),
            "bang": audio.gunshot(),
            "early": audio.tone(150, 0.4),
            "hit": audio.gunshot(0.4, seed=7),
            "match_over": audio.arpeggio([392, 494, 587, 784]),
        }

    # -- Game protocol ----------------------------------------------------------------

    def reset(self) -> None:
        self.duel.reset()
        self.flash = None

    def update(self, frame: PoseFrame) -> None:
        self.now = frame.timestamp
        self.states = tuple(classify(p, self.gestures) for p in frame.players)
        for name, player in self.duel.update(frame.timestamp, self.states):
            if name == "hit":
                self.flash = (1 - player, frame.timestamp)
            audio.play(self.sounds.get(name))

    def render_camera(self, image_bgr):
        return sepia(image_bgr)

    def debug_lines(self) -> list[str]:
        d = self.duel
        return [
            f"phase {d.phase.value}  P1 {self.states[0].value}  P2 {self.states[1].value}",
            f"early {d.early}  draw_t {[None if t is None else round(t, 3) for t in d.draw_time]}",
        ]

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        d = self.duel
        self._draw_flash(canvas)
        pygame.draw.line(canvas, INK, (self.w // 2, 0), (self.w // 2, self.h), 3)
        self._draw_scoreboard(canvas)

        if d.phase == Phase.WAIT_START:
            missing = [NAMES[i] for i in (0, 1) if d.missing[i]]
            if missing:
                self._banner(canvas, "WAITING FOR", self.font_med, self.h * 0.40)
                self._banner(canvas, " & ".join(missing), self.font_big, self.h * 0.50)
            else:
                self._banner(canvas, "GET READY, PARTNERS", self.font_big, self.h * 0.45)
                self._progress(canvas, d.start_progress(self.now), self.h * 0.55)
            self._side_hints(canvas)
        elif d.phase == Phase.READY:
            self._banner(canvas, "READY", self.font_huge, self.h * 0.5)
        elif d.phase == Phase.STEADY:
            self._banner(canvas, "STEADY", self.font_huge, self.h * 0.5)
        elif d.phase == Phase.BANG:
            self._banner(canvas, "BANG!", self.font_huge, self.h * 0.5, color=RED)
        elif d.phase in (Phase.ROUND_OVER, Phase.MATCH_OVER):
            self._draw_result(canvas)

        if d.phase in (Phase.READY, Phase.STEADY, Phase.BANG):
            for i in (0, 1):
                if d.early[i]:
                    self._side_label(canvas, i, "TOO EARLY - MISSED!", self.font_med, RED)

    # -- drawing helpers --------------------------------------------------------------

    def _banner(self, canvas, text, font, cy, color=INK, cx=None):
        surf = font.render(text, True, color)
        cx = self.w / 2 if cx is None else cx
        rect = surf.get_rect(center=(int(cx), int(cy)))
        bg = rect.inflate(40, 16)
        plate = pygame.Surface(bg.size, pygame.SRCALPHA)
        plate.fill((*PAPER, 215))
        canvas.blit(plate, bg)
        pygame.draw.rect(canvas, INK, bg, 3)
        canvas.blit(surf, rect)

    def _side_label(self, canvas, i, text, font, color=INK, cy=None):
        cx = self.w * (0.25 if i == 0 else 0.75)
        self._banner(canvas, text, font, cy or self.h * 0.78, color=color, cx=cx)

    def _progress(self, canvas, frac, cy):
        bw, bh = int(self.w * 0.3), int(self.h * 0.03)
        rect = pygame.Rect(0, 0, bw, bh)
        rect.center = (self.w // 2, int(cy))
        pygame.draw.rect(canvas, PAPER, rect)
        pygame.draw.rect(canvas, INK, (rect.x, rect.y, int(bw * frac), bh))
        pygame.draw.rect(canvas, INK, rect, 3)

    def _side_hints(self, canvas):
        for i, state in enumerate(self.states):
            if state == PoseState.DRAWN:
                self._side_label(canvas, i, "lower your gun", self.font_small)

    def _draw_scoreboard(self, canvas):
        d = self.duel
        for i in (0, 1):
            cx = self.w * (0.25 if i == 0 else 0.75)
            self._banner(canvas, f"{NAMES[i]}  {d.scores[i]}", self.font_med, self.h * 0.07, cx=cx)
        self._banner(canvas, f"first to {d.config.points_to_win}", self.font_small, self.h * 0.07)

    def _draw_result(self, canvas):
        d = self.duel
        r = d.last_result
        if d.phase == Phase.MATCH_OVER:
            self._banner(canvas, NAMES[d.match_winner], self.font_big, self.h * 0.33)
            self._banner(canvas, "WINS THE DUEL!", self.font_big, self.h * 0.47)
            if self.now - d.phase_start >= d.config.match_result_min_time:
                self._banner(canvas, "lower your guns to play again", self.font_small, self.h * 0.60)
        elif r is not None:
            headline = {
                "hit": f"{NAMES[r.winner]} SCORES" if r.winner is not None else "",
                "tie": "DEAD EVEN - REPLAY",
                "timeout": "NOBODY FIRED",
                "void": "BOTH TOO EARLY - REPLAY",
            }[r.reason]
            self._banner(canvas, headline, self.font_big, self.h * 0.45)
        if r is None:
            return
        for i in (0, 1):
            if r.early[i]:
                text = "TOO EARLY"
            elif r.reaction_ms[i] is not None:
                text = f"{r.reaction_ms[i]:.0f} ms"
            else:
                text = "-"
            self._side_label(canvas, i, text, self.font_med, color=RED if r.early[i] else INK)

    def _draw_flash(self, canvas):
        if self.flash is None:
            return
        loser, start = self.flash
        age = self.now - start
        if age > FLASH_TIME:
            self.flash = None
            return
        alpha = int(170 * (1 - age / FLASH_TIME))
        overlay = pygame.Surface((self.w // 2, self.h), pygame.SRCALPHA)
        overlay.fill((*RED, alpha))
        canvas.blit(overlay, (0 if loser == 0 else self.w // 2, 0))
