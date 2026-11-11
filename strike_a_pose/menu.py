"""Game menu and launcher for Strike a Pose mini-games."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

# Game definitions
GAMES = {
    "pose": {
        "title": "Strike a Pose",
        "tagline": "Party Game  •  2-4 Players",
        "desc": "Match the target stick figures before the countdown timer hits zero!",
        "accent": (70, 180, 255),  # Sky blue
        "key": "1",
    },
    "duel": {
        "title": "Wild West Duel",
        "tagline": "Quick-Draw Showdown  •  2 Players",
        "desc": "Stand side by side, wait for BANG, and draw your arm fastest to win!",
        "accent": (255, 180, 60),  # Amber
        "key": "2",
    },
    "dodgeball": {
        "title": "Dodgeball",
        "tagline": "Arcade Agility  •  1-2 Players",
        "desc": "Dodge bouncing balls with your body. Move around to avoid getting hit!",
        "accent": (255, 95, 95),  # Coral / Red
        "key": "3",
    },
}

GAME_KEYS = list(GAMES.keys())


def trigger_game(
    game_key: str,
    camera_index: int = 0,
    imgsz: int = 640,
    device: str | None = None,
    debug: bool = False,
) -> int:
    """Launch the chosen game."""
    if game_key == "pose":
        from strike_a_pose.games.pose.runner import run_pose
        return run_pose(camera_index=camera_index, debug=debug)
    elif game_key == "duel":
        from strike_a_pose.app import run
        from strike_a_pose.games.duel.game import DuelGame
        run(DuelGame, camera_index=camera_index, imgsz=imgsz, device=device)
        return 0
    elif game_key == "dodgeball":
        from strike_a_pose.app import run
        from strike_a_pose.games.dodgeball.dodgeball import DodgeballGame
        run(DodgeballGame, camera_index=camera_index, imgsz=imgsz, device=device)
        return 0
    else:
        raise ValueError(f"Unknown game: {game_key}. Choices are: {GAME_KEYS}")


def show_cli_menu() -> str:
    """Display terminal menu and return selected game key or 'quit'."""
    print("\n" + "=" * 62)
    print("                STRIKE A POSE - GAME MENU")
    print("=" * 62)
    print("Select a game:")
    print("  [1] Strike a Pose  - Pose matching party game (2-4 players)")
    print("  [2] Wild West Duel - Quick-draw reaction game (2 players)")
    print("  [3] Dodgeball      - Dodge bouncing balls with your body (1-2 players)")
    print("  [q] Quit")
    print("=" * 62)
    while True:
        try:
            choice = input("Enter choice (1-3, q): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "quit"
        if choice in ("1", "pose"):
            return "pose"
        elif choice in ("2", "duel"):
            return "duel"
        elif choice in ("3", "dodgeball"):
            return "dodgeball"
        elif choice in ("q", "quit", "exit"):
            return "quit"
        print("Invalid choice. Please enter 1, 2, 3, or q.")


def show_gui_menu() -> str:
    """Display graphical Pygame menu and return selected game key or 'quit'."""
    import pygame

    pygame.init()
    try:
        width, height = 960, 640
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Strike a Pose - Game Launcher")

        # Fonts
        font_title = pygame.font.SysFont("helvetica,arial,sans-serif", 44, bold=True)
        font_sub = pygame.font.SysFont("helvetica,arial,sans-serif", 16, bold=True)
        font_card_title = pygame.font.SysFont("helvetica,arial,sans-serif", 24, bold=True)
        font_card_tag = pygame.font.SysFont("helvetica,arial,sans-serif", 15, bold=True)
        font_card_desc = pygame.font.SysFont("helvetica,arial,sans-serif", 15)
        font_badge = pygame.font.SysFont("menlo,consolas,courier,sans-serif", 20, bold=True)
        font_footer = pygame.font.SysFont("menlo,consolas,courier,sans-serif", 14)

        # Palette
        bg_color = (20, 22, 28)
        card_bg = (30, 33, 42)
        card_bg_hover = (42, 47, 60)
        card_border = (52, 57, 72)
        text_white = (245, 248, 252)
        text_muted = (150, 158, 175)

        card_w, card_h = 760, 105
        card_x = (width - card_w) // 2
        y_start = 145
        gap = 22

        card_rects: list[pygame.Rect] = []
        for i in range(len(GAME_KEYS)):
            card_rects.append(pygame.Rect(card_x, y_start + i * (card_h + gap), card_w, card_h))

        # Quit button
        quit_w, quit_h = 130, 36
        quit_rect = pygame.Rect((width - quit_w) // 2, 535, quit_w, quit_h)

        selected_idx = 0
        clock = pygame.time.Clock()

        while True:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_q, pygame.K_ESCAPE):
                        return "quit"
                    elif event.key == pygame.K_1:
                        return "pose"
                    elif event.key == pygame.K_2:
                        return "duel"
                    elif event.key == pygame.K_3:
                        return "dodgeball"
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        selected_idx = (selected_idx - 1) % len(GAME_KEYS)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        selected_idx = (selected_idx + 1) % len(GAME_KEYS)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return GAME_KEYS[selected_idx]
                elif event.type == pygame.MOUSEMOTION:
                    for idx, rect in enumerate(card_rects):
                        if rect.collidepoint(mouse_pos):
                            selected_idx = idx
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for idx, rect in enumerate(card_rects):
                        if rect.collidepoint(event.pos):
                            return GAME_KEYS[idx]
                    if quit_rect.collidepoint(event.pos):
                        return "quit"

            # Render
            screen.fill(bg_color)

            # Header
            title_surf = font_title.render("STRIKE A POSE", True, text_white)
            screen.blit(title_surf, title_surf.get_rect(center=(width // 2, 55)))

            sub_surf = font_sub.render("BODY-CONTROLLED MINI GAMES", True, (110, 190, 255))
            screen.blit(sub_surf, sub_surf.get_rect(center=(width // 2, 98)))

            # Game Cards
            for idx, key in enumerate(GAME_KEYS):
                info = GAMES[key]
                rect = card_rects[idx]
                is_selected = (idx == selected_idx)
                accent = info["accent"]

                # Card background and border
                c_bg = card_bg_hover if is_selected else card_bg
                pygame.draw.rect(screen, c_bg, rect, border_radius=12)

                border_color = accent if is_selected else card_border
                border_width = 3 if is_selected else 1
                pygame.draw.rect(screen, border_color, rect, width=border_width, border_radius=12)

                # Accent left indicator bar
                if is_selected:
                    bar_rect = pygame.Rect(rect.x, rect.y + 12, 6, rect.height - 24)
                    pygame.draw.rect(screen, accent, bar_rect, border_radius=3)

                # Badge on left
                badge_rect = pygame.Rect(rect.x + 22, rect.y + (card_h - 48) // 2, 48, 48)
                badge_bg = (24, 26, 34) if not is_selected else (28, 36, 52)
                pygame.draw.rect(screen, badge_bg, badge_rect, border_radius=8)
                pygame.draw.rect(screen, accent, badge_rect, width=2, border_radius=8)

                badge_text = font_badge.render(info["key"], True, accent)
                screen.blit(badge_text, badge_text.get_rect(center=badge_rect.center))

                # Game Title & Tagline
                title_x = rect.x + 88
                g_title = font_card_title.render(info["title"], True, text_white)
                screen.blit(g_title, (title_x, rect.y + 16))

                g_tag = font_card_tag.render(info["tagline"], True, accent)
                screen.blit(g_tag, (title_x + g_title.get_width() + 16, rect.y + 23))

                # Description
                g_desc = font_card_desc.render(info["desc"], True, text_muted)
                screen.blit(g_desc, (title_x, rect.y + 54))

                # Arrow indicator on right if selected
                if is_selected:
                    arrow = font_card_title.render("▶", True, accent)
                    screen.blit(arrow, (rect.right - 40, rect.y + (card_h - arrow.get_height()) // 2))

            # Quit Button
            quit_hover = quit_rect.collidepoint(mouse_pos)
            q_bg = (40, 44, 56) if quit_hover else (28, 30, 38)
            q_border = (180, 80, 80) if quit_hover else card_border
            pygame.draw.rect(screen, q_bg, quit_rect, border_radius=8)
            pygame.draw.rect(screen, q_border, quit_rect, width=1, border_radius=8)
            q_surf = font_footer.render("[Q] Quit", True, (240, 120, 120) if quit_hover else text_muted)
            screen.blit(q_surf, q_surf.get_rect(center=quit_rect.center))

            # Footer instructions
            footer_text = "[1-3] Select   •   [↑/↓] Navigate   •   [Enter] Launch   •   [Q / Esc] Quit"
            footer_surf = font_footer.render(footer_text, True, (115, 122, 140))
            screen.blit(footer_surf, footer_surf.get_rect(center=(width // 2, 595)))

            pygame.display.flip()
            clock.tick(60)
    finally:
        pygame.quit()


def show_menu() -> str:
    """Show GUI menu if display available, otherwise fall back to CLI menu."""
    try:
        return show_gui_menu()
    except Exception as exc:
        print(f"GUI menu unavailable ({exc}); using terminal menu.")
        return show_cli_menu()


def run_menu(
    camera_index: int = 0,
    imgsz: int = 640,
    device: str | None = None,
    debug: bool = False,
    cli_mode: bool = False,
) -> int:
    """Run the main menu loop until user quits."""
    while True:
        if cli_mode:
            choice = show_cli_menu()
        else:
            choice = show_menu()

        if choice in ("quit", None):
            print("Exiting Strike a Pose. Thanks for playing!")
            return 0

        game_title = GAMES.get(choice, {}).get("title", choice)
        print(f"\n--- Starting {game_title} ---")
        try:
            trigger_game(
                choice,
                camera_index=camera_index,
                imgsz=imgsz,
                device=device,
                debug=debug,
            )
        except Exception as err:
            print(f"Error running {choice}: {err}", file=sys.stderr)
            print("Returning to menu...")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="strike_a_pose",
        description="Strike a Pose: Body-controlled mini games",
    )
    parser.add_argument(
        "game",
        nargs="?",
        choices=GAME_KEYS,
        default=None,
        help="Game to play (pose, duel, dodgeball). If omitted, opens the selection menu.",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera index (default 0)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="YOLO input size; lower = faster (default 640)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Compute device: mps / cpu / cuda (default: auto)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Use terminal menu instead of graphical GUI",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (allows solo pose game)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.game is not None:
        return trigger_game(
            args.game,
            camera_index=args.camera,
            imgsz=args.imgsz,
            device=args.device,
            debug=args.debug,
        )
    return run_menu(
        camera_index=args.camera,
        imgsz=args.imgsz,
        device=args.device,
        debug=args.debug,
        cli_mode=args.cli,
    )


if __name__ == "__main__":
    sys.exit(main())
