"""Inline ♥ markers expand to paper.draw_heart in hint copy."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from main.ui import paper


def _face() -> pygame.font.Font:
    pygame.font.init()
    return paper.font(paper.HAND_FONT, 28)


def test_plain_text_matches_paper_text_width():
    pygame.display.init()
    canvas = pygame.Surface((400, 80))
    face = _face()
    plain = paper.text(canvas, "2P: 3", face, paper.INK, (10, 40), "midleft")
    with_mark = paper.text_with_hearts(canvas, "2P: 3", face, paper.INK, (10, 40), "midleft")
    assert with_mark.width == plain.width


def test_heart_markers_widen_the_line():
    pygame.display.init()
    canvas = pygame.Surface((800, 80))
    face = _face()
    h = paper.HEART_MARK
    plain = paper.text_with_hearts(canvas, "2P: ", face, paper.INK, (0, 40), "midleft")
    three = paper.text_with_hearts(canvas, f"2P: {h}{h}{h}", face, paper.INK, (0, 40), "midleft")
    one = paper.text_with_hearts(canvas, f"2P: {h}", face, paper.INK, (0, 40), "midleft")
    assert three.width > plain.width
    assert three.width > one.width


def test_dodgeball_how_to_fact_repeats_hearts_per_roster():
    from main.games.how_to_play import guide_for

    guide = guide_for("dodgeball", {})
    sub = guide.fact[1]
    assert "{" not in "".join(guide.fact)
    assert sub == f"2P: {paper.HEART_MARK * 3}, 3P: {paper.HEART_MARK * 2}, 4P: {paper.HEART_MARK}"
    assert "Lives" not in "".join(guide.fact) and "Life" not in "".join(guide.fact)
