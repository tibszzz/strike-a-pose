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
from main.pose import Person, PoseFrame, PoseState, classify
from main.ready_up import (
    ReadyUp,
    ReadyUpConfig,
    draw_player_label,
    draw_ready_up,
    head_anchor,
    match_roster_by_seeds,
)
from main.settings import ASSETS, DuelConfig, GestureConfig, Messages, ViewConfig, from_env

from .float_path import FloatPath, ease_out, fade
from .logic import Duel, Phase
from .preview import PreviewTracker
from .replay import ReplayPlayback, ReplayRecorder

theme = styles.DUEL
copy = content.Duel

SPRITES = ASSETS / "sprites"
SOUNDS = ASSETS / "sounds"


def _still_paths() -> tuple:
    root = ASSETS / "ready_up" / "duel"
    return tuple(sorted(root.glob("pose_*.png")))


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

        self.gesture_snapshot = None
        self._roster_seed_x: list[float] = []
        self._slot_people: tuple[Person | None, Person | None] = (None, None)
        self._needs_ready_up = True
        self._ready = self._make_ready()
        self._end = EndScreen((self.w, self.h))
        self._pending_nav = None

    def _make_ready(self) -> ReadyUp:
        return ReadyUp(
            self.w,
            ReadyUpConfig(
                min_players=2,
                max_players=2,
                title=content.ReadyUp.how_to_play,
                how_to_lines=copy.ready_how_to,
                pose_stills=_still_paths(),
                hold_frames=max(1, 10),
                fist_hold_frames=max(1, 15),
                forget_frames=30,
                debug=bool(self.duel.config.debug),
            ),
        )

    @property
    def gesture_hands(self) -> int:
        if self._in_end_screen():
            return NAV_GESTURE_HANDS
        return 4

    @property
    def wants_gestures(self) -> bool:
        return self._in_ready_up() or self._in_end_screen()

    def _in_ready_up(self) -> bool:
        return self._needs_ready_up

    def _in_end_screen(self) -> bool:
        return (
            not self._needs_ready_up
            and self.duel.phase == Phase.MATCH_OVER
            and self.duel.can_restart(self.now)
        )

    # -- Game protocol ----------------------------------------------------------------

    def reset(self) -> None:
        self.duel.reset()
        self.floaters.clear()
        for tracker in self.previews:
            tracker.reset()
        self.recorder.discard()
        self.playback = None
        self._roster_seed_x = []
        self._slot_people = (None, None)
        self._needs_ready_up = True
        self._ready = self._make_ready()
        self._end.reset()
        self._pending_nav = None
        self.gesture_snapshot = None

    def handle_key(self, key: int) -> None:
        if key == pygame.K_SPACE and self.duel.config.debug and self._in_ready_up():
            started = self._ready.force_start()
            if started is not None:
                self._apply_started(started, self.now)

    def handle_command(self, command: MenuCommand) -> None:
        if not self._in_end_screen():
            return
        choice = self._end.handle_command(command)
        if choice is not None:
            self._apply_end_choice(choice)

    def poll_nav(self):
        nav = self._pending_nav
        self._pending_nav = None
        return nav

    def update(self, frame: PoseFrame) -> None:
        self.now = frame.timestamp
        if self._in_ready_up():
            # Full-bleed ready-up: ignore white-page waiting UI
            snap = self.gesture_snapshot
            hands = snap.hands if snap is not None else ()
            started = self._ready.update(frame.people, hands)
            if started is not None:
                self._apply_started(started, frame.timestamp)
            return

        if self._in_end_screen():
            choice = self._end.update(self.gesture_snapshot, frame.timestamp)
            if choice is not None:
                self._apply_end_choice(choice)
            return

        slots = self._slots_from_frame(frame)
        self._slot_people = slots
        self.step(frame.timestamp, tuple(classify(p, self.gestures) for p in slots))
        if self.duel.phase == Phase.BANG and self.recorder.active:
            self.recorder.push(frame.image, frame.timestamp)

    def _apply_end_choice(self, choice: EndChoice) -> None:
        if choice is EndChoice.MENU:
            self._pending_nav = StartGame(None)
            return
        # Replay → fresh ReadyUp
        self.duel.reset()
        self.floaters.clear()
        for tracker in self.previews:
            tracker.reset()
        self.recorder.discard()
        self.playback = None
        self._roster_seed_x = []
        self._slot_people = (None, None)
        self._needs_ready_up = True
        self._ready = self._make_ready()
        self._end.reset()

    def _apply_started(self, started, now: float) -> None:
        roster = [p for p in started.roster if isinstance(p, Person)]
        self._roster_seed_x = [p.center_x for p in roster]
        while len(self._roster_seed_x) < 2 and self.duel.config.debug:
            self._roster_seed_x.append(self.w * 0.75)
        self._needs_ready_up = False
        self._end.reset()
        for name, player in self.duel.request_start(now):
            if name == "ready":
                self.floaters.clear()
            audio.play(self.sounds.get(name))

    def _slots_from_frame(self, frame: PoseFrame) -> tuple[Person | None, Person | None]:
        if not self._roster_seed_x:
            # Fallback before first ready-up freeze (tests that call step() directly)
            return frame.players
        matched = match_roster_by_seeds(frame.people, self._roster_seed_x)
        if matched is None:
            # Keep last known or partial fill by nearest seed
            slots: list[Person | None] = [None, None]
            people = list(frame.people)
            for i, seed in enumerate(self._roster_seed_x[:2]):
                if not people:
                    break
                best = min(range(len(people)), key=lambda j: abs(people[j].center_x - seed))
                slots[i] = people.pop(best)
            return (slots[0], slots[1])
        if len(matched) == 1:
            return (matched[0], None)
        return (matched[0], matched[1])

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
                self._end.reset()
            audio.play(self.sounds.get(name))
        if was_replay and self.duel.phase != Phase.REPLAY:
            self._clear_replay()  # drop bang→draw frames once the clip has played

    def debug_lines(self) -> list[str]:
        d = self.duel
        if self._in_ready_up():
            return [
                f"Ready-up: {self._ready.ready_count} ready / "
                f"{len(self._ready.eligible)} eligible"
            ]
        if self._in_end_screen():
            locked = (
                EndScreen.OPTIONS[self._end.hard_lock].name
                if self._end.hard_lock is not None
                else "-"
            )
            return [f"end-screen lock {locked}"]
        return [
            f"phase {d.phase.value}  P1 {self.states[0].value}  P2 {self.states[1].value}",
            f"early {d.early}  draw_t {[None if t is None else round(t, 3) for t in d.draw_time]}",
        ]

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        d = self.duel
        if self._in_ready_up():
            # Full-bleed camera under ready-up chrome (duel play stays on white page).
            rgb = frame.image[:, :, ::-1]
            surf = pygame.image.frombuffer(
                np.ascontiguousarray(rgb).tobytes(),
                (frame.image.shape[1], frame.image.shape[0]),
                "RGB",
            )
            if surf.get_size() != canvas.get_size():
                surf = pygame.transform.smoothscale(surf, canvas.get_size())
            canvas.blit(surf, (0, 0))
            draw_ready_up(canvas, self._ready, theme=theme, snap=self.gesture_snapshot)
            return
        if d.phase == Phase.REPLAY:
            self._draw_replay(canvas)
            return
        if d.phase == Phase.MATCH_OVER and not d.showing_final_round(self.now):
            # Results page; buttons + pointer go live once restart is allowed.
            draw_end_screen(
                canvas,
                self._end,
                snap=self.gesture_snapshot,
                title=content.Results.duel_title,
                body=self._draw_results_body,
                active=self._in_end_screen(),
            )
            return

        self._draw_previews(canvas, frame)
        if d.phase == Phase.ROUND_OVER or d.showing_final_round(self.now):
            self._draw_result(canvas)
        elif d.phase == Phase.WAIT_START:
            self._draw_header(canvas)
            self._draw_waiting(canvas)
        else:
            self._draw_header(canvas)
            if d.phase in (Phase.READY, Phase.STEADY, Phase.BANG):
                word = {
                    Phase.READY: copy.phase["ready"],
                    Phase.STEADY: copy.phase["steady"],
                    Phase.BANG: copy.phase["bang"],
                }[d.phase]
                self._text(canvas, word, self.sz_main, (self.w / 2, self.h / 2), bold=True, shadow=True)
            for i, person in enumerate(self._slot_people):
                if person is None:
                    continue
                nose = None
                if float(person.conf[0]) >= 0.3:
                    nose = (float(person.xy[0][0]), float(person.xy[0][1]))
                anchor = head_anchor(person.box, nose)
                draw_player_label(
                    canvas,
                    f"P{i + 1}",
                    anchor,
                    theme.player[i % len(theme.player)],
                    face=theme.font,
                )
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

    def _draw_results_body(self, canvas: pygame.Surface, rect: pygame.Rect, frame) -> None:
        """Winner + taunt, hearts left per gunslinger, and the draw illustration."""
        d = self.duel
        winners = [] if d.match_winner is None else [d.match_winner + 1]
        bottom = draw_headline(canvas, frame, rect, winners_line(winners), self.win_msg, size=64)
        top = bottom + frame.px(30)
        rows_rect = pygame.Rect(rect.x, top, min(int(rect.width * 0.6), frame.px(660)), min(frame.px(150), rect.bottom - top))
        lives = d.config.lives
        draw_lives_rows(
            canvas,
            frame,
            rows_rect,
            [
                LivesRow(player=i + 1, lives=d.lives_left(i), max_lives=lives, winner=d.match_winner == i)
                for i in (0, 1)
            ],
        )
        art_box = pygame.Rect(rows_rect.right + frame.px(40), rect.y, rect.right - rows_rect.right - frame.px(40), rect.height)
        draw_card_art(canvas, ASSETS / "ui" / "how_to_play" / "duel" / "step_3.png", art_box)

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
