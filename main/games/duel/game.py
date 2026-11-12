"""Wild West Duel: pygame view + sounds on top of the pure Duel rules.

Look follows refrences/: white page, pixel font, hearts for lives. Side portrait
PiPs show each player's body so they can check framing; after a hit, a slow-mo
camera replay fills the screen before the result. Debug mode (D) still puts the
full camera image behind the same UI.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
import pygame

from main import audio, content, styles
from main.pose import PoseFrame, PoseState, classify
from main.settings import ASSETS, DuelConfig, GestureConfig, Messages, ViewConfig, from_env

from .float_path import FloatPath, ease_out, fade
from .logic import Duel, Phase
from .preview import PreviewTracker
from .replay import ReplayPlayback, ReplayRecorder

theme = styles.DUEL
copy = content.Duel

SPRITES = ASSETS / "sprites"
SOUNDS = ASSETS / "sounds"


@dataclass
class _Floater:
    path: FloatPath
    text: str
    start: float


class DuelGame:
    title = copy.window_title
    background = theme.bg

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

        self.shot_msgs = Messages(copy.shot_messages, copy.shot_messages[0], self.rng)
        self.win_msgs = Messages(copy.win_messages, copy.win_messages[0], self.rng)
        self.early_msgs = Messages(copy.early_messages, copy.early_messages[0], self.rng)
        self.shot_msg = ""
        self.win_msg = ""
        self.win_img: pygame.Surface | None = None
        self.floaters: list[_Floater] = []
        self.paths = (FloatPath(size, 0), FloatPath(size, 1))
        aspect = (self.view.preview_width * self.w) / max(1.0, self.view.preview_height * self.h)
        self.previews = (
            PreviewTracker(
                pad=self.view.preview_pad,
                smooth=self.view.preview_smooth,
                grace=self.view.preview_grace,
                target_aspect=aspect,
            ),
            PreviewTracker(
                pad=self.view.preview_pad,
                smooth=self.view.preview_smooth,
                grace=self.view.preview_grace,
                target_aspect=aspect,
            ),
        )
        self.recorder = ReplayRecorder(scale=self.view.replay_scale)
        self.playback: ReplayPlayback | None = None

        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self.sz_main = theme.duel_main_px(self.h)
        self.sz_label = theme.duel_label_px(self.h)
        self.sz_shot = theme.duel_shot_px(self.h)
        self.sz_title = theme.duel_title_px(self.h)
        self.sz_msg = theme.duel_msg_px(self.h)

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
        for tracker in self.previews:
            tracker.reset()
        self.recorder.discard()
        self.playback = None

    def update(self, frame: PoseFrame) -> None:
        self.step(frame.timestamp, tuple(classify(p, self.gestures) for p in frame.players))
        if self.duel.phase == Phase.BANG and self.recorder.active:
            self.recorder.push(frame.image, frame.timestamp)

    def step(self, now: float, states: tuple[PoseState, PoseState]) -> None:
        self.now = now
        self.states = states
        was_replay = self.duel.phase == Phase.REPLAY
        for name, player in self.duel.update(now, states):
            if name in ("ready", "abort"):
                self.floaters.clear()
                if name == "abort":
                    self._clear_replay()
            elif name == "bang":
                self.recorder.start(now)
            elif name == "early":
                self.floaters.append(_Floater(self.paths[player], self.early_msgs.pick(), self.now))
            elif name == "hit":
                self.shot_msg = self.shot_msgs.pick()
                self._begin_playback()
            elif name in ("tie", "timeout", "void"):
                self._clear_replay()
            elif name == "match_over":
                self.win_msg = self.win_msgs.pick()
                self.win_img = self._pick_cowboy()
            audio.play(self.sounds.get(name))
        if was_replay and self.duel.phase != Phase.REPLAY:
            self._clear_replay()  # drop bang→draw frames once the clip has played

    def debug_lines(self) -> list[str]:
        d = self.duel
        return [
            f"phase {d.phase.value}  P1 {self.states[0].value}  P2 {self.states[1].value}",
            f"early {d.early}  draw_t {[None if t is None else round(t, 3) for t in d.draw_time]}",
        ]

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        d = self.duel
        if d.phase == Phase.REPLAY:
            self._draw_replay(canvas)
            return
        if d.phase == Phase.MATCH_OVER and not d.showing_final_round(self.now):
            self._draw_winner(canvas)
            return

        self._draw_previews(canvas, frame)
        if d.phase == Phase.ROUND_OVER or d.showing_final_round(self.now):
            self._draw_result(canvas)
        else:
            self._draw_header(canvas)
            if d.phase == Phase.WAIT_START:
                self._draw_waiting(canvas)
            elif d.phase in (Phase.READY, Phase.STEADY, Phase.BANG):
                word = {
                    Phase.READY: copy.phase["ready"],
                    Phase.STEADY: copy.phase["steady"],
                    Phase.BANG: copy.phase["bang"],
                }[d.phase]
                self._text(canvas, word, self.sz_main, (self.w / 2, self.h / 2), bold=True, shadow=True)
        self._draw_floaters(canvas)

    # -- screens ----------------------------------------------------------------------

    def _clear_replay(self) -> None:
        self.recorder.discard()
        self.playback = None

    def _begin_playback(self) -> None:
        times = [t for t in self.duel.draw_time if t is not None]
        end = min(times) if times else self.now
        clip = self.recorder.clip(end)
        if clip is None:
            self.playback = None
            return
        cfg = self.duel.config
        self.playback = ReplayPlayback(clip, speed=cfg.replay_speed, freeze=cfg.replay_freeze)

    def _draw_replay(self, canvas: pygame.Surface) -> None:
        elapsed = self.now - self.duel.phase_start
        if self.playback is None:
            canvas.fill(theme.ink)
            reaction_ms = 0.0
        else:
            rgb, reaction_ms, _ = self.playback.sample(elapsed)
            self._blit_cover(canvas, rgb)
        label_x = 0.14 * self.w
        self._text(
            canvas,
            copy.replay_label,
            self.sz_label,
            (label_x, 0.08 * self.h),
            color=theme.bg,
            bold=True,
            shadow=True,
        )
        self._text(
            canvas,
            f"{reaction_ms:.0f} ms",
            self.sz_label,
            (label_x, 0.14 * self.h),
            color=theme.bg,
            bold=True,
            shadow=True,
        )

    def _blit_cover(self, canvas: pygame.Surface, rgb: np.ndarray) -> None:
        h, w = rgb.shape[:2]
        if w <= 0 or h <= 0:
            canvas.fill(theme.ink)
            return
        scale = max(self.w / w, self.h / h)
        tw, th = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        buf = np.ascontiguousarray(rgb)
        surf = pygame.image.frombuffer(buf.tobytes(), (w, h), "RGB")
        scaled = pygame.transform.smoothscale(surf, (tw, th))
        canvas.blit(scaled, ((self.w - tw) // 2, (self.h - th) // 2))

    def _draw_previews(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        fh, fw = frame.image.shape[:2]
        for i in (0, 1):
            rect = self._preview_rect(i)
            box = self.previews[i].update(frame.players[i], self.now, fw, fh)
            if box is None:
                self._draw_preview_placeholder(canvas, rect)
            else:
                self._blit_preview_crop(canvas, frame.image, box, rect)
            border = max(2, self.h // 240)
            pygame.draw.rect(canvas, theme.ink, rect, border)

    def _preview_rect(self, i: int) -> pygame.Rect:
        pw = int(self.view.preview_width * self.w)
        ph = int(self.view.preview_height * self.h)
        margin = int(self.view.preview_margin_x * self.w)
        rect = pygame.Rect(0, 0, pw, ph)
        rect.top = int(self.view.preview_top * self.h)
        if i == 0:
            rect.left = margin
        else:
            rect.right = self.w - margin
        return rect

    def _draw_preview_placeholder(self, canvas: pygame.Surface, rect: pygame.Rect) -> None:
        canvas.fill(theme.hint, rect)
        self._text(
            canvas,
            copy.preview_waiting,
            self.sz_label,
            rect.center,
            color=theme.bg,
            bold=True,
        )

    def _blit_preview_crop(
        self,
        canvas: pygame.Surface,
        image_bgr: np.ndarray,
        box: tuple[float, float, float, float],
        dest: pygame.Rect,
    ) -> None:
        x1, y1, x2, y2 = (int(v) for v in box)
        x1, x2 = max(0, min(x1, x2)), min(image_bgr.shape[1], max(x1, x2))
        y1, y2 = max(0, min(y1, y2)), min(image_bgr.shape[0], max(y1, y2))
        if x2 <= x1 or y2 <= y1:
            self._draw_preview_placeholder(canvas, dest)
            return
        crop = np.ascontiguousarray(image_bgr[y1:y2, x1:x2, ::-1])  # BGR -> RGB
        surf = pygame.image.frombuffer(crop.tobytes(), (crop.shape[1], crop.shape[0]), "RGB")
        canvas.blit(pygame.transform.smoothscale(surf, dest.size), dest)

    def _draw_header(self, canvas):
        heart_w = self.heart_alive.get_width()
        gap = int(0.079 * self.h)
        lives = self.duel.config.lives
        for i in (0, 1):
            cx = self._side_x(i)
            self._text(canvas, copy.player_names[i], self.sz_label, (cx, 0.09 * self.h))
            left = self.duel.lives_left(i)
            x0 = cx - gap * (lives - 1) / 2
            for k in range(lives):
                img = self.heart_alive if k < left else self.heart_dead
                canvas.blit(img, (int(x0 + k * gap - heart_w / 2), int(0.18 * self.h - heart_w / 2)))

    def _draw_waiting(self, canvas):
        d = self.duel
        missing = [copy.player_names[i].upper() for i in (0, 1) if d.missing[i]]
        if missing:
            self._text(canvas, copy.waiting_for, self.sz_msg, (self.w / 2, 0.44 * self.h))
            self._text(canvas, " & ".join(missing), self.sz_shot, (self.w / 2, 0.52 * self.h), bold=True)
        else:
            self._text(canvas, copy.get_ready, self.sz_shot, (self.w / 2, 0.47 * self.h), bold=True, shadow=True)
            self._progress(canvas, d.start_progress(self.now), 0.56 * self.h)
        for i, state in enumerate(self.states):
            if state == PoseState.DRAWN:
                self._text(
                    canvas,
                    copy.lower_gun,
                    self.sz_label,
                    (self._side_x(i), 0.877 * self.h),
                    color=theme.hint,
                )

    def _draw_result(self, canvas):
        r = self.duel.last_result
        if r is not None and r.reason == "hit":
            loser = 1 - r.winner
            canvas.fill(theme.shot_bg, pygame.Rect(0 if loser == 0 else self.w // 2, 0, self.w - self.w // 2, self.h))
        self._draw_header(canvas)
        if r is None:
            return
        if r.reason == "hit":
            self._text(
                canvas,
                self.shot_msg.upper(),
                self.sz_shot,
                (self._side_x(1 - r.winner), self.h / 2),
                color=theme.bg,
                bold=True,
                max_width=0.44 * self.w,
            )
        else:
            headline = copy.result[r.reason]
            self._text(canvas, headline, self.sz_main * 2 // 3, (self.w / 2, self.h / 2), bold=True, shadow=True)
        for i in (0, 1):
            if r.early[i]:
                text = copy.too_early
            elif r.reaction_ms[i] is not None:
                text = f"{r.reaction_ms[i]:.0f} ms"
            else:
                text = "-"
            self._text(canvas, text, self.sz_label, (self._side_x(i), 0.905 * self.h))

    def _draw_winner(self, canvas):
        d = self.duel
        self._text(
            canvas,
            f"{copy.player_names[d.match_winner].upper()} {copy.wins_suffix}",
            self.sz_title,
            (self.w / 2, 0.15 * self.h),
            bold=True,
        )
        if self.win_img is not None:
            canvas.blit(self.win_img, self.win_img.get_rect(center=(self.w // 2, int(0.49 * self.h))))
        self._text(canvas, self.win_msg.upper(), self.sz_msg, (self.w / 2, 0.68 * self.h), bold=True, max_width=0.9 * self.w)
        if d.can_restart(self.now):
            self._text(canvas, copy.lower_guns_again, self.sz_msg, (self.w / 2, 0.9 * self.h), color=theme.hint)

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
            font = styles.load_font(theme.font, size)
            font.bold = bold
            self._fonts[key] = font
        return self._fonts[key]

    def _text(self, canvas, text, size, center, color=None, bold=False, shadow=False, alpha=255, max_width=None):
        if color is None:
            color = theme.ink
        font = self._font(size, bold)
        if max_width is not None and font.size(text)[0] > max_width:  # shrink to fit
            size = max(8, int(size * max_width / font.size(text)[0]))
            font = self._font(size, bold)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(int(center[0]), int(center[1])))
        if shadow:
            off = max(2, size // 22)
            shade = font.render(text, True, theme.shadow)
            shade.set_alpha(alpha)
            canvas.blit(shade, rect.move(off, off))
        surf.set_alpha(alpha)
        canvas.blit(surf, rect)

    def _progress(self, canvas, frac, cy):
        bw, bh = int(self.w * 0.3), int(self.h * 0.03)
        border = max(2, self.h // 240)
        rect = pygame.Rect(0, 0, bw, bh)
        rect.center = (self.w // 2, int(cy))
        pygame.draw.rect(canvas, theme.bg, rect)
        pygame.draw.rect(canvas, theme.ink, (rect.x, rect.y, int(bw * frac), bh))
        pygame.draw.rect(canvas, theme.ink, rect, border)

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
