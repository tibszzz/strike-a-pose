"""Wild West Duel: pygame view + sounds on top of the pure Duel rules.

Look matches the menu / how-to / results pages: sketch-paper sheet, marker +
hand-lettered type, hand-drawn hearts for lives. Side portrait
PiPs show each player's body so they can check framing; after a hit, a slow-mo
camera replay fills the screen before the result. Final RESULTS puts a live
winner PiP in the card art slot (full-frame cover if tracking is lost) with a
winner tag on the feed. Debug overlay (D) still puts the full camera image
behind the same UI.
"""

from __future__ import annotations

import random

import numpy as np
import pygame

from main import audio, content, styles
from main.end_screen import (
    EndChoice,
    EndScreen,
    LivesRow,
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
    draw_ready_up,
    match_roster_by_seeds,
)
from main.settings import ASSETS, DuelConfig, GestureConfig, Messages, ViewConfig, from_env
from main.ui import paper, sketch
from main.ui.paper import HEART, INK, INK_FAINT, INK_SOFT, Frame, PaperStyle

from .logic import Duel, Phase
from .preview import PreviewTracker, cover_crop, resolve_results_portrait
from .replay import ReplayPlayback, ReplayRecorder

theme = styles.DUEL
copy = content.Duel

SPRITES = ASSETS / "sprites"
SOUNDS = ASSETS / "sounds"


def _still_paths() -> tuple:
    root = ASSETS / "ready_up" / "duel"
    return tuple(sorted(root.glob("pose_*.png")))


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
        self.early_text = ["", ""]  # taunt shown under a player's portrait after an early draw
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

        # Type + sizes in the menu's 1552x873 design space (see `paper.Frame`).
        self.frame = Frame(self.w, self.h)
        f = self.frame
        self.cue_face = paper.marker(f, 140)  # READY / STEADY / BANG!
        self.headline_face = paper.marker(f, 92)  # NOBODY FIRED, BOTH TOO EARLY
        self.shout_face = paper.marker(f, 58)  # GET READY, shot taunt, missing names
        self.replay_face = paper.marker(f, 54)
        self.tag_face = paper.hand(f, 38)  # Player 1 / Player 2 tags
        self.winner_tag_face = paper.hand(f, 26)  # RESULTS feed winner label
        self.body_face = paper.hand(f, 42)  # reaction times, WAITING FOR
        self.note_face = paper.hand(f, 34)  # lower your gun, preview WAITING
        self.early_face = paper.marker(f, 46)  # "too early" taunt under a locked-out portrait
        self.heart_px = f.px(50)
        self._wash: pygame.Surface | None = None
        self.cowboys = sorted((SPRITES / "cowboys").glob("*.png"))

        synth = {
            "ready": lambda: audio.tone(440, 0.25),
            "steady": lambda: audio.tone(587, 0.25),
            "bang": lambda: audio.gunshot(),
            "early": lambda: audio.tone(150, 0.4),
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

    def draw_background(self, canvas: pygame.Surface) -> None:
        """The menu's sketch-paper sheet (shell calls this instead of a flat fill)."""
        sketch.draw_sketch_backdrop(canvas)

    def reset(self) -> None:
        self.duel.reset()
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

    def debug_skip_to_results(self) -> bool:
        """`--debug` + R after ready-up: jump to final RESULTS. False → shell may reset."""
        if not self.duel.config.debug or self._in_ready_up():
            return False
        self.duel.debug_force_match_over(self.now, winner=0)
        self.win_msg = self.win_msgs.pick()
        self.win_img = self._pick_cowboy()
        self._end.reset()
        self._clear_replay()
        return True

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
            choice = self._end.update(self.gesture_snapshot, frame.timestamp, frame.people)
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
            if name == "abort":
                self._clear_replay()
            elif name == "bang":
                self.recorder.start(now)
            elif name == "early":
                self.early_text[player] = self.early_msgs.pick()
            elif name == "hit":
                self.shot_msg = self.shot_msgs.pick()
                self._begin_playback()
            elif name in ("timeout", "void"):
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
                body=lambda c, r, f: self._draw_results_body(c, r, f, frame),
                active=self._in_end_screen(),
                pose=frame,
            )
            return

        self._draw_previews(canvas, frame)
        if d.phase == Phase.ROUND_OVER or d.showing_final_round(self.now):
            self._draw_result(canvas)
        elif d.phase == Phase.WAIT_START:
            self._draw_header(canvas)
            self._draw_waiting(canvas)
        elif d.phase == Phase.INTRO:
            self._draw_header(canvas)
            self._draw_intro(canvas)
        else:
            self._draw_header(canvas)
            if d.phase in (Phase.READY, Phase.STEADY, Phase.BANG):
                word = {
                    Phase.READY: copy.phase["ready"],
                    Phase.STEADY: copy.phase["steady"],
                    Phase.BANG: copy.phase["bang"],
                }[d.phase]
                color = HEART if d.phase == Phase.BANG else INK
                paper.text(canvas, word, self.cue_face, color, (self.w / 2, self.h / 2), "center", max_width=self._mid_width())
                self._draw_early_taunts(canvas)

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
        # Torn-paper note taped over the video, like the menu's title strip.
        f = self.frame
        note = f.rect(70, 56, 330, 206)
        paper.draw_paper(canvas, note, f, PaperStyle(torn="tblr", jag=6), seed=73)
        paper.draw_tape(canvas, (note.centerx, note.y + f.px(4)), f, width=110, seed=73)
        paper.text(canvas, copy.replay_label, self.replay_face, INK, (note.centerx, note.y + f.px(84)), "midbottom")
        paper.text(canvas, f"{reaction_ms:.0f} ms", self.body_face, INK_SOFT, (note.centerx, note.y + f.px(88)), "midtop")

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
            locked = self._locked_out(i)
            if box is None:
                self._draw_preview_placeholder(canvas, rect)
            else:
                self._blit_preview_crop(canvas, frame.image, box, rect, grey=locked)
            paper.draw_marker_box(canvas, rect, self.frame, HEART if locked else INK, seed=80 + i)

    def _locked_out(self, i: int) -> bool:
        """Player `i` drew early and can't shoot for the rest of this round's draw."""
        d = self.duel
        return d.early[i] and d.phase in (Phase.READY, Phase.STEADY, Phase.BANG)

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
        canvas.fill(INK_FAINT, rect)
        paper.text(canvas, copy.preview_waiting, self.note_face, theme.bg, rect.center, "center")

    def _blit_preview_crop(
        self,
        canvas: pygame.Surface,
        image_bgr: np.ndarray,
        box: tuple[float, float, float, float],
        dest: pygame.Rect,
        *,
        cover: bool = False,
        missing_placeholder: bool = True,
        grey: bool = False,
    ) -> bool:
        """Blit person crop into `dest`. `cover` center-crops to fill; `grey` desaturates.

        Returns False if empty.
        """
        x1, y1, x2, y2 = (int(v) for v in box)
        x1, x2 = max(0, min(x1, x2)), min(image_bgr.shape[1], max(x1, x2))
        y1, y2 = max(0, min(y1, y2)), min(image_bgr.shape[0], max(y1, y2))
        if x2 <= x1 or y2 <= y1:
            if missing_placeholder:
                self._draw_preview_placeholder(canvas, dest)
            return False
        crop = np.ascontiguousarray(image_bgr[y1:y2, x1:x2, ::-1])  # BGR -> RGB
        if cover:
            cx, cy, cw, ch = cover_crop(crop.shape[1], crop.shape[0], dest.width, dest.height)
            ix, iy = int(cx), int(cy)
            iw, ih = max(1, int(cw)), max(1, int(ch))
            crop = np.ascontiguousarray(crop[iy : iy + ih, ix : ix + iw])
        if grey:
            crop = np.ascontiguousarray(np.repeat(crop.mean(axis=2, keepdims=True).astype(np.uint8), 3, axis=2))
        surf =pygame.image.frombuffer(crop.tobytes(), (crop.shape[1], crop.shape[0]), "RGB")
        canvas.blit(pygame.transform.smoothscale(surf, dest.size), dest)
        return True

    def _draw_header(self, canvas):
        """Colored player tag + hand-drawn hearts (same as the results page) per side."""
        gap = self.heart_px + self.frame.px(14)
        lives = self.duel.config.lives
        for i in (0, 1):
            cx = round(self._side_x(i))
            paper.draw_tag(
                canvas, copy.player_names[i], self.tag_face, paper.player_ink(i + 1), (cx, round(0.09 * self.h)), "center"
            )
            left = self.duel.lives_left(i)
            x0 = cx - gap * (lives - 1) / 2
            for k in range(lives):
                paper.draw_heart(canvas, (round(x0 + k * gap), round(0.18 * self.h)), self.heart_px, filled=k < left)

    def _draw_waiting(self, canvas):
        d = self.duel
        missing = [copy.player_names[i].upper() for i in (0, 1) if d.missing[i]]
        mid = self.w / 2
        if missing:
            paper.text(canvas, copy.waiting_for, self.body_face, INK_SOFT, (mid, 0.44 * self.h), "center")
            paper.text(canvas, " & ".join(missing), self.shout_face, INK, (mid, 0.52 * self.h), "center", max_width=self._mid_width())
        else:
            paper.text(canvas, copy.get_ready, self.shout_face, INK, (mid, 0.47 * self.h), "center", max_width=self._mid_width())
            self._progress(canvas, d.start_progress(self.now), 0.56 * self.h)
        for i, state in enumerate(self.states):
            if state == PoseState.DRAWN:
                paper.text(canvas, copy.lower_gun, self.note_face, INK_SOFT, (self._side_x(i), 0.877 * self.h), "center")

    def _draw_intro(self, canvas):
        """GET READY while the start fist comes down (no visible countdown)."""
        mid = self.w / 2
        paper.text(canvas, copy.get_ready, self.shout_face, INK, (mid, 0.47 * self.h), "center", max_width=self._mid_width())
        paper.text(canvas, copy.lower_guns, self.note_face, INK_SOFT, (mid, 0.56 * self.h), "center", max_width=self._mid_width())

    def _draw_result(self, canvas):
        r = self.duel.last_result
        if r is not None and r.reason == "hit":
            loser = 1 - r.winner
            self._shade_half(canvas, loser)
        self._draw_header(canvas)
        if r is None:
            return
        if r.reason == "hit":
            paper.text(
                canvas,
                self.shot_msg.upper(),
                self.shout_face,
                theme.bg,
                (self._half_center(1 - r.winner), self.h / 2),
                "center",
                max_width=self.w // 2 - self.frame.px(80),
            )
        else:
            headline = copy.result[r.reason]
            paper.text(canvas, headline, self.headline_face, INK, (self.w / 2, self.h / 2), "center", max_width=self._mid_width())
        for i in (0, 1):
            on_red = r.reason == "hit" and i == 1 - r.winner
            if r.early[i]:
                text, color = copy.too_early, HEART
            elif r.reaction_ms[i] is not None:
                text, color = f"{r.reaction_ms[i]:.0f} ms", INK
            else:
                text, color = "-", INK_SOFT
            if on_red:
                color = theme.bg  # paper-colored ink on the red wash
            paper.text(canvas, text, self.body_face, color, (self._side_x(i), 0.905 * self.h), "center")

    def _draw_results_body(
        self, canvas: pygame.Surface, rect: pygame.Rect, frame, pose: PoseFrame
    ) -> None:
        """Winner + taunt, hearts left, live winner PiP with winner tag."""
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
        self._draw_results_portrait(canvas, art_box, pose)

    def _draw_results_portrait(
        self, canvas: pygame.Surface, art_box: pygame.Rect, pose: PoseFrame
    ) -> None:
        """RESULTS portrait: winner tag above live crop (full frame if lost)."""
        if art_box.width <= 0 or art_box.height <= 0:
            return
        winner = self.duel.match_winner
        feed = art_box
        if winner is not None:
            face = self.winner_tag_face
            # Match draw_tag vertical padding so the feed starts cleanly below the label.
            tag_h = face.get_height() + 2 * max(1, face.get_height() // 12)
            gap = self.frame.px(10)
            feed = pygame.Rect(
                art_box.x, art_box.y + tag_h + gap, art_box.width, art_box.height - tag_h - gap
            )
            if feed.height <= 0:
                return
            paper.draw_tag(
                canvas,
                content.Results.player.format(player=winner + 1),
                face,
                paper.player_ink(winner + 1),
                (art_box.centerx, art_box.top),
                "midtop",
            )
        fh, fw = pose.image.shape[:2]
        full = (0.0, 0.0, float(fw), float(fh))
        if winner is None:
            box = full
        else:
            box = resolve_results_portrait(
                self.previews[winner],
                pose.players[winner],
                now=self.now,
                frame_w=fw,
                frame_h=fh,
            ) or full
        self._blit_preview_crop(
            canvas, pose.image, box, feed, cover=True, missing_placeholder=False
        )
        seed = 80 if winner is None else 80 + winner
        paper.draw_marker_box(canvas, feed, self.frame, INK, seed=seed)

    def _draw_early_taunts(self, canvas):
        """Random "too early" taunt under each locked-out player's portrait, kept to their column."""
        for i in (0, 1):
            if self._locked_out(i) and self.early_text[i]:
                width = self._preview_rect(i).width + self.frame.px(40)
                paper.text(
                    canvas,
                    self.early_text[i],
                    self.early_face,
                    HEART,
                    (self._side_x(i), 0.877 * self.h),
                    "center",
                    max_width=width,
                )

    # -- helpers ----------------------------------------------------------------------

    def _side_x(self, i: int) -> float:
        """Centre line of player `i`'s side: the middle of their preview window."""
        return float(self._preview_rect(i).centerx)

    def _half_center(self, i: int) -> float:
        """Middle of player `i`'s half of the screen (where the red wash goes)."""
        return self.w * (0.25 if i == 0 else 0.75)

    def _mid_width(self) -> int:
        """Room for centre text between the two preview windows."""
        return max(1, self._preview_rect(1).left - self._preview_rect(0).right - self.frame.px(40))

    def _shade_half(self, canvas: pygame.Surface, side: int) -> None:
        """Red marker wash over the shot player's half (paper grain shows through)."""
        size = (self.w - self.w // 2, self.h)
        if self._wash is None or self._wash.get_size() != size:
            self._wash = pygame.Surface(size, pygame.SRCALPHA)
            self._wash.fill((*theme.shot_bg, 238))
        canvas.blit(self._wash, (0 if side == 0 else self.w // 2, 0))

    def _progress(self, canvas, frac, cy):
        """Rounded hold bar like the note buttons' fist-hold progress."""
        bar = pygame.Rect(0, 0, int(self.w * 0.3), self.frame.px(16))
        bar.center = (self.w // 2, int(cy))
        radius = bar.height // 2
        pygame.draw.rect(canvas, INK_FAINT, bar, border_radius=radius)
        if frac > 0:
            fill = bar.copy()
            fill.width = max(bar.height, round(bar.width * min(1.0, frac)))
            pygame.draw.rect(canvas, paper.HOLD_RING, fill, border_radius=radius)

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
