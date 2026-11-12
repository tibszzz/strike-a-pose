"""Results page: torn-paper card with each game's outcome + Play again / Menu notes.

Every game shares the frame (backdrop, title strip, card, buttons, pointer); the card's contents come from a `body` callback so High Noon,
Dodgeball and Strike a Pose can each show their own outcome. Helpers below
(`draw_headline`, `draw_lives_rows`, `draw_points_table`) cover the common
pieces.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import pygame

from main import content
from main.nav import GestureSnapshot
from main.styles import Theme
from main.ui import paper, widgets
from main.ui.paper import INK, INK_SOFT, Frame, PaperStyle

from .logic import EndChoice, EndScreen

copy = content.EndScreen
results = content.Results

# Card in design px; buttons sit top-right (EndScreen.tile_rects).
CARD = (125, 222, 1428, 818)

Body = Callable[[pygame.Surface, pygame.Rect, Frame], None]


def _label(choice: EndChoice) -> str:
    if choice is EndChoice.REPLAY:
        return copy.replay
    return copy.menu


def draw_end_screen(
    canvas: pygame.Surface,
    end: EndScreen,
    *,
    theme: Theme | None = None,  # kept for callers; the page uses the paper palette
    snap: GestureSnapshot | None = None,
    timestamp: float = 0.0,
    dim: bool = True,
    title: str = "",
    body: Body | None = None,
    active: bool = True,
) -> None:
    """Full results page. `active=False` draws it without pointer/selection (before input opens)."""
    del theme, timestamp, dim
    f = Frame(end.w, end.h)
    paper.draw_backdrop(canvas)
    if title:
        widgets.draw_title_strip(canvas, f, title, seed=17)

    card = f.rect(*CARD)
    paper.draw_paper(
        canvas, card, f, PaperStyle(torn="tb", jag=7, holes_top=28, rule_top=True), seed=31
    )
    if body is not None:
        inner = pygame.Rect(
            card.x + f.px(44), card.y + f.px(62), card.width - f.px(88), card.height - f.px(92)
        )
        body(canvas, inner, f)

    for i, (choice, rect) in enumerate(zip(EndScreen.OPTIONS, end.tile_rects())):
        widgets.draw_note_button(
            canvas,
            f,
            rect,
            i + 1,
            _label(choice),
            selected=active and i == end.hard_lock,
            seed=120 + i,
            label_size=42,
            progress=end.hold_progress if active and i == end.hard_lock else 0.0,
        )

    if active:
        widgets.draw_cursor(canvas, f, snap, end.hold_progress)


# --- body helpers -------------------------------------------------------------------


def player_name(player: int) -> str:
    return results.player.format(player=player)


def winners_line(winners: Sequence[int]) -> str:
    """'P2 wins!', 'P1 and P3 share the win!', or 'Nobody wins!'."""
    names = [player_name(p) for p in winners]
    if not names:
        return results.nobody
    if len(names) == 1:
        return results.wins.format(name=names[0])
    return results.tie.format(names=f"{', '.join(names[:-1])} and {names[-1]}")


def draw_headline(
    canvas: pygame.Surface,
    frame: Frame,
    rect: pygame.Rect,
    headline: str,
    sub: str = "",
    *,
    size: float = 64,
    color: paper.Rgb = INK,
) -> int:
    """Marker headline (+ optional hand-lettered sub) at the top of `rect`. Returns bottom y."""
    drawn = paper.text(
        canvas, headline, paper.marker(frame, size), color, (rect.x, rect.y), max_width=rect.width
    )
    bottom = drawn.bottom
    if sub:
        sub_rect = paper.text(
            canvas, sub, paper.hand(frame, 32), INK_SOFT, (rect.x, bottom + frame.px(4)), max_width=rect.width
        )
        bottom = sub_rect.bottom
    return bottom


@dataclass(frozen=True)
class LivesRow:
    player: int
    lives: int
    max_lives: int
    winner: bool = False


def draw_lives_rows(
    canvas: pygame.Surface,
    frame: Frame,
    rect: pygame.Rect,
    rows: Sequence[LivesRow],
    palette: tuple[paper.Rgb, ...] = paper.PLAYER_INK,
) -> None:
    """One line per player: tag, hearts left, OUT / winner star. Rows fill `rect` from the top."""
    if not rows:
        return
    row_h = min(frame.px(64), rect.height // max(1, len(rows)))
    tag_face = paper.hand(frame, 30)
    note_face = paper.hand(frame, 30)
    heart = round(row_h * 0.62)
    for i, row in enumerate(rows):
        cy = rect.y + row_h * i + row_h // 2
        if row.winner:
            paper.draw_highlight(
                canvas, pygame.Rect(rect.x - frame.px(10), cy - row_h // 2 + frame.px(6), rect.width + frame.px(20), row_h - frame.px(12)), seed=row.player
            )
        tag = paper.draw_tag(
            canvas, player_name(row.player), tag_face, paper.player_ink(row.player, palette), (rect.x, cy)
        )
        x = tag.right + frame.px(22)
        for k in range(row.max_lives):
            paper.draw_heart(canvas, (x + heart // 2, cy), heart, filled=k < row.lives)
            x += heart + frame.px(8)
        note = results.out if row.lives <= 0 else f"{row.lives} {results.lives_left}"
        paper.text(canvas, note, note_face, INK_SOFT if row.lives > 0 else paper.HEART, (rect.right, cy), "midright")


@dataclass(frozen=True)
class TableRow:
    place: int
    player: int
    scores: Sequence[int]
    total: int


def draw_points_table(
    canvas: pygame.Surface,
    frame: Frame,
    rect: pygame.Rect,
    rows: Sequence[TableRow],
    rounds: int,
    palette: tuple[paper.Rgb, ...] = paper.PLAYER_INK,
) -> None:
    """Place | player | R1…Rn | Total, best first; first place gets a highlighter stroke."""
    if not rows:
        return
    head_face = paper.hand(frame, 24)
    cell_face = paper.hand(frame, 34)
    total_face = paper.marker(frame, 34)
    tag_face = paper.hand(frame, 30)

    place_w = frame.px(56)
    player_w = frame.px(96)
    total_w = frame.px(110)
    round_area = rect.width - place_w - player_w - total_w
    round_w = round_area / max(1, rounds)
    x_place = rect.x
    x_player = x_place + place_w
    x_round0 = x_player + player_w
    x_total = rect.right

    head_h = frame.px(36)
    head_y = rect.y + head_h // 2
    paper.text(canvas, results.col_player, head_face, INK_SOFT, (x_player, head_y), "midleft")
    for r in range(rounds):
        cx = x_round0 + round_w * (r + 0.5)
        paper.text(canvas, results.col_round.format(n=r + 1), head_face, INK_SOFT, (cx, head_y), "center")
    paper.text(canvas, results.col_total, head_face, INK_SOFT, (x_total, head_y), "midright")
    rule_y = rect.y + head_h
    pygame.draw.line(canvas, paper.INK_FAINT, (rect.x, rule_y), (rect.right, rule_y), max(1, frame.px(2)))

    body_h = rect.bottom - rule_y
    row_h = min(frame.px(70), body_h // max(1, len(rows)))
    for i, row in enumerate(rows):
        top = rule_y + i * row_h
        cy = top + row_h // 2
        if row.place == 1:
            paper.draw_highlight(
                canvas,
                pygame.Rect(rect.x - frame.px(10), top + frame.px(8), rect.width + frame.px(20), row_h - frame.px(14)),
                seed=row.player,
            )
        paper.text(canvas, _ordinal(row.place), cell_face, INK, (x_place, cy), "midleft")
        paper.draw_tag(
            canvas, player_name(row.player), tag_face, paper.player_ink(row.player, palette), (x_player, cy)
        )
        for r in range(rounds):
            value = str(row.scores[r]) if r < len(row.scores) else results.no_score
            cx = x_round0 + round_w * (r + 0.5)
            paper.text(canvas, value, cell_face, INK_SOFT, (cx, cy), "center")
        paper.text(canvas, str(row.total), total_face, INK, (x_total, cy + frame.px(2)), "midright")
        if i < len(rows) - 1:
            y = top + row_h
            pygame.draw.line(canvas, paper.INK_FAINT, (rect.x, y), (rect.right, y), 1)


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def draw_card_art(canvas: pygame.Surface, path: Path, box: pygame.Rect) -> None:
    """Illustration inside the card (re-uses the how-to art)."""
    paper.blit_art(canvas, path, box)
