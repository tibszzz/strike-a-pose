"""Strike play path on the shared pygame shell + PoseTracker."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import pygame

from main import audio, content, styles
from main.end_screen import (
    EndChoice,
    EndScreen,
    TableRow,
    draw_end_screen,
    draw_headline,
    draw_points_table,
    winners_line,
)
from main.nav import GestureSnapshot, MenuCommand, StartGame
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose import PoseFrame
from main.pose.library import Pose, from_coco_person, load_library
from main.pose.types import Person as CocoPerson
from main.ready_up import ReadyUp, ReadyUpConfig, Started, draw_ready_up, match_roster_slots
from main.settings import ASSETS, StrikeConfig
from main.ui import paper
from main.ui.paper import INK
from main.ui.preview import PreviewTracker, cover_crop, resolve_results_portrait

from .game import compose
from .logic import Game as StrikeLogic
from .screens import (
    CountdownTick,
    Event,
    FinalScreen,
    LobbyScreen,
    ResultsScreen,
    ScoreRevealLocked,
    ScoreRevealTick,
    Screen,
    SnapshotTaken,
)

SOUNDS = ASSETS / "sounds"


def _still_paths() -> tuple:
    root = ASSETS / "ready_up" / "strike"
    return tuple(sorted(root.glob("pose_*.png")))


def _load_sounds(
    sounds_dir: Path = SOUNDS,
    *,
    reveal_s: float = 2.0,
    reveal_hz: float = 20.0,
) -> dict[str, pygame.mixer.Sound | None]:
    """Countdown ticks, snapshot shutter, results drumroll + sting."""
    synth = {
        "tick": lambda: audio.tone(440, 0.25),
        "shutter": lambda: audio.camera_shutter(),
        "drumroll": lambda: audio.drumroll(reveal_s, hz=reveal_hz),
        "sting": lambda: audio.reveal_sting(),
    }
    files = {
        "tick": "tick.wav",
        "shutter": "shutter.wav",
        "drumroll": "drumroll.wav",
        "sting": "sting.wav",
    }
    return {
        name: audio.load_or(sounds_dir / files[name], make)
        for name, make in synth.items()
    }


class StrikeGame:
    title = content.Strike.window_title
    background = styles.STRIKE.bg

    def __init__(
        self,
        size: tuple[int, int],
        config: StrikeConfig | None = None,
        poses: Sequence[Pose] | None = None,
    ) -> None:
        self.w, self.h = size
        self._config = config if config is not None else StrikeConfig()
        library = list(poses) if poses is not None else load_library(self._config.poses_dir)
        self._logic = StrikeLogic(self._config, library)
        self._logic.subscribe(self._on_logic_event)
        self._sounds = _load_sounds(
            reveal_s=self._config.results_reveal_s,
            reveal_hz=self._config.results_reveal_hz,
        )
        self._drumroll_channel: pygame.mixer.Channel | None = None
        self._screen: Screen = LobbyScreen(
            markers=(),
            can_start=False,
            min_players=self._config.min_players,
            max_players=self._config.max_players,
        )
        self._image = None
        self._confirm = False
        self.gesture_snapshot: GestureSnapshot | None = None
        self._in_ready_up = True
        self._ready = self._make_ready()
        self._end = EndScreen((self.w, self.h))
        self._pending_nav = None
        self._frame_ts = 0.0
        self._results_preview = PreviewTracker()

    def _on_logic_event(self, event: Event) -> None:
        if isinstance(event, CountdownTick) and event.seconds_left <= 3:
            audio.play(self._sounds.get("tick"))
        elif isinstance(event, SnapshotTaken):
            audio.play(self._sounds.get("shutter"))
        elif isinstance(event, ScoreRevealTick):
            self._start_drumroll()
        elif isinstance(event, ScoreRevealLocked):
            self._stop_drumroll()
            audio.play(self._sounds.get("sting"))

    def _start_drumroll(self) -> None:
        if self._drumroll_channel is not None:
            return
        self._drumroll_channel = audio.play(self._sounds.get("drumroll"))

    def _stop_drumroll(self) -> None:
        if self._drumroll_channel is not None:
            self._drumroll_channel.stop()
            self._drumroll_channel = None

    def _make_ready(self) -> ReadyUp:
        return ReadyUp(
            self.w,
            ReadyUpConfig(
                min_players=self._config.min_players,
                max_players=self._config.max_players,
                title=content.ReadyUp.how_to_play,
                how_to_lines=content.Strike.ready_how_to,
                pose_stills=_still_paths(),
                hold_frames=max(1, 10),
                fist_hold_frames=max(1, int(round(30 * 0.5))),
                forget_frames=30,
                debug=self._config.debug,
            ),
        )

    def _in_end_screen(self) -> bool:
        return isinstance(self._screen, FinalScreen)

    @property
    def gesture_hands(self) -> int:
        if self._in_ready_up:
            return self._config.max_players * 2
        if self._in_end_screen():
            return NAV_GESTURE_HANDS
        return NAV_GESTURE_HANDS

    @property
    def wants_gestures(self) -> bool:
        return self._in_ready_up or self._in_end_screen()

    def reset(self) -> None:
        self._stop_drumroll()
        library = load_library(self._config.poses_dir)
        self._logic = StrikeLogic(self._config, library)
        self._logic.subscribe(self._on_logic_event)
        self._confirm = False
        self.gesture_snapshot = None
        self._in_ready_up = True
        self._ready = self._make_ready()
        self._end.reset()
        self._results_preview.reset()
        self._pending_nav = None
        self._screen = LobbyScreen(
            markers=(),
            can_start=False,
            min_players=self._config.min_players,
            max_players=self._config.max_players,
        )

    def handle_key(self, key: int) -> None:
        if key == pygame.K_SPACE:
            if self._in_ready_up:
                if self._config.debug:
                    started = self._ready.force_start()
                    if started is not None:
                        self._begin_from_started(started, timestamp=0.0)
                return
            if isinstance(self._screen, ResultsScreen):
                return
            if isinstance(self._screen, FinalScreen):
                return
            self._confirm = True

    def debug_skip_to_results(self) -> bool:
        """`--debug` + R after ready-up: jump to final RESULTS. False → shell may reset."""
        if not self._config.debug or self._in_ready_up:
            return False
        screen = self._logic.debug_force_final()
        if screen is None:
            return False
        self._stop_drumroll()
        self._screen = screen
        self._end.reset()
        self._results_preview.reset()
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

    def _apply_end_choice(self, choice: EndChoice) -> None:
        if choice is EndChoice.MENU:
            self._pending_nav = StartGame(None)
            return
        self.reset()

    def _begin_from_started(self, started: Started, timestamp: float) -> None:
        people = []
        for entry in started.roster:
            if isinstance(entry, CocoPerson):
                people.append(from_coco_person(entry))
            else:
                # Already a library Person
                people.append(entry)  # type: ignore[arg-type]
        self._in_ready_up = False
        self._end.reset()
        self._screen = self._logic.step(timestamp, confirm=True, people=people)

    def update(self, frame: PoseFrame) -> None:
        self._image = frame.image
        self._frame_ts = frame.timestamp

        if self._in_ready_up:
            snap = self.gesture_snapshot
            hands = snap.hands if snap is not None else ()
            started = self._ready.update(frame.people, hands)
            if started is not None:
                self._begin_from_started(started, frame.timestamp)
            return

        if self._in_end_screen():
            choice = self._end.update(self.gesture_snapshot, frame.timestamp, frame.people)
            if choice is not None:
                self._apply_end_choice(choice)
            return

        confirm = self._confirm
        self._confirm = False
        if isinstance(self._screen, ResultsScreen):
            confirm = False

        now = frame.timestamp
        people = None
        if self._logic.wants_people(now):
            people = [from_coco_person(person) for person in frame.people]
        prev = self._screen
        self._screen = self._logic.step(now, confirm, frame.image, people)
        if isinstance(self._screen, FinalScreen) and not isinstance(prev, FinalScreen):
            self._end.reset()
            self._results_preview.reset()

    def render_camera(self, image):
        source = self._image if self._image is not None else image
        if self._in_ready_up or self._in_end_screen():
            # Ready-up draws over the live feed; the results page paints its own backdrop.
            composed = source
        else:
            composed = compose(self._screen, source)
        if composed.shape[1] != self.w or composed.shape[0] != self.h:
            composed = cv2.resize(composed, (self.w, self.h))
        return composed

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        if self._in_ready_up:
            draw_ready_up(canvas, self._ready, theme=styles.STRIKE, snap=self.gesture_snapshot)
            return
        if self._in_end_screen():
            draw_end_screen(
                canvas,
                self._end,
                snap=self.gesture_snapshot,
                title=content.Results.strike_title,
                body=lambda c, r, f: self._draw_final_body(c, r, f, frame),
                pose=frame,
            )

    def _draw_final_body(
        self, canvas: pygame.Surface, rect: pygame.Rect, frame, pose: PoseFrame
    ) -> None:
        """Winner headline, points table (~75%), live winner PiP on the right."""
        screen = self._screen
        if not isinstance(screen, FinalScreen):
            return
        winners = [s.player for s in screen.standings if s.place == 1]
        bottom = draw_headline(canvas, frame, rect, winners_line(winners), size=58)
        rounds = screen.total_rounds or self._config.rounds
        rows = [
            TableRow(
                place=s.place,
                player=s.player,
                scores=screen.round_scores[s.player - 1]
                if 0 < s.player <= len(screen.round_scores)
                else (),
                total=s.total,
            )
            for s in screen.standings
        ]
        gap = frame.px(40)
        art_w = max(1, int(rect.width * 0.25) - gap)
        table = pygame.Rect(
            rect.x,
            bottom + frame.px(20),
            max(1, rect.width - art_w - gap),
            max(1, rect.bottom - bottom - frame.px(20)),
        )
        draw_points_table(canvas, frame, table, rows, rounds)
        art_box = pygame.Rect(table.right + gap, rect.y, art_w, rect.height)
        self._draw_results_portrait(canvas, frame, art_box, pose, winners)

    def _draw_results_portrait(
        self,
        canvas: pygame.Surface,
        frame,
        art_box: pygame.Rect,
        pose: PoseFrame,
        winners: list[int],
    ) -> None:
        """Final portrait: P# above live crop of first place-1 (full frame if lost)."""
        if art_box.width <= 0 or art_box.height <= 0:
            return
        winner = winners[0] if winners else None
        feed = art_box
        if winner is not None:
            face = paper.hand(frame, 26)
            tag_h = face.get_height() + 2 * max(1, face.get_height() // 12)
            label_gap = frame.px(10)
            feed = pygame.Rect(
                art_box.x,
                art_box.y + tag_h + label_gap,
                art_box.width,
                art_box.height - tag_h - label_gap,
            )
            if feed.height <= 0:
                return
            paper.draw_tag(
                canvas,
                content.Results.player.format(player=winner),
                face,
                paper.player_ink(winner),
                (art_box.centerx, art_box.top),
                "midtop",
            )
        fh, fw = pose.image.shape[:2]
        full = (0.0, 0.0, float(fw), float(fh))
        person = self._winner_person(pose, winner) if winner is not None else None
        self._results_preview.target_aspect = feed.width / max(1, feed.height)
        box = (
            resolve_results_portrait(
                self._results_preview,
                person,
                now=self._frame_ts,
                frame_w=fw,
                frame_h=fh,
            )
            or full
        )
        self._blit_preview_crop(canvas, pose.image, box, feed)
        seed = 80 if winner is None else 80 + winner
        paper.draw_marker_box(canvas, feed, frame, INK, seed=seed)

    def _winner_person(self, pose: PoseFrame, winner: int) -> CocoPerson | None:
        """Rematch the 1-based winner seat to a live detection via roster seeds."""
        seeds = self._logic.roster_seed_x
        if not seeds or winner < 1:
            return None
        slots = match_roster_slots(pose.people, seeds)
        idx = winner - 1
        if idx >= len(slots):
            return None
        return slots[idx]

    def _blit_preview_crop(
        self,
        canvas: pygame.Surface,
        image_bgr: np.ndarray,
        box: tuple[float, float, float, float],
        dest: pygame.Rect,
    ) -> bool:
        """Cover-blit a BGR crop into `dest`. Returns False if empty."""
        x1, y1, x2, y2 = (int(v) for v in box)
        x1, x2 = max(0, min(x1, x2)), min(image_bgr.shape[1], max(x1, x2))
        y1, y2 = max(0, min(y1, y2)), min(image_bgr.shape[0], max(y1, y2))
        if x2 <= x1 or y2 <= y1:
            return False
        crop = np.ascontiguousarray(image_bgr[y1:y2, x1:x2, ::-1])  # BGR -> RGB
        cx, cy, cw, ch = cover_crop(crop.shape[1], crop.shape[0], dest.width, dest.height)
        ix, iy = int(cx), int(cy)
        iw, ih = max(1, int(cw)), max(1, int(ch))
        crop = np.ascontiguousarray(crop[iy : iy + ih, ix : ix + iw])
        surf = pygame.image.frombuffer(crop.tobytes(), (crop.shape[1], crop.shape[0]), "RGB")
        canvas.blit(pygame.transform.smoothscale(surf, dest.size), dest)
        return True

    def debug_lines(self) -> list[str]:
        if self._in_ready_up:
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
        return [type(self._screen).__name__]
