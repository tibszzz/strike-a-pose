"""User-facing copy. No colors, fonts, or timings."""

from __future__ import annotations


class ReadyUp:
    how_to_play = "HOW TO PLAY"  # ReadyUpConfig.title (no longer drawn)
    join_heading = "Thumbs up to join"
    start_heading = "Fist to start"


class EndScreen:
    replay = "Play again"
    menu = "Menu"
    hint = "POINT TO SELECT · HOLD FIST TO CONFIRM"


class Hints:
    """Gesture hints on the main menu."""

    hover_heading = "Open palm to hover"
    select_heading = "Fist to select"


class HowToPlay:
    play = "Let's go!"
    back = "Back"
    # Per registry id: title, three (heading, sub) steps, one (heading, sub) fact.
    # {lives} {rounds} {min_players} {max_players} come from each game's settings.
    guides = {
        "duel": (
            "High Noon",
            (
                ("Arms down", "Holster up. Stay still."),
                ("Wait...", "Draw on BANG, not before."),
                ("Draw!", "Snap one arm straight out."),
            ),
            ("{lives} lives each", "Lose them all and you're out."),
        ),
        "strike": (
            "Strike a Pose",
            (
                ("Get in frame", "{min_players}-{max_players} players, head to toe."),
                ("Copy it!", "It's a mirror: same side."),
                ("Score!", "Up to 100 a round."),
            ),
            ("{rounds} rounds", "Best total wins."),
        ),
        "dodgeball": (
            "Dodgeball",
            (
                ("Join in", "Thumbs up to play."),
                ("Dodge!", "Lean, duck or step aside."),
                ("Stay in view", "Last one standing wins."),
            ),
            ("Player Lives", "2P: ♥♥♥, 3P: ♥♥, 4P: ♥"),
        ),
    }


class Results:
    duel_title = "High Noon"
    strike_title = "Strike a Pose"
    dodgeball_title = "Dodgeball"
    player = "P{player}"
    wins = "{name} wins!"
    tie = "{names} share the win!"
    nobody = "Nobody wins!"
    solo_over = "Game over!"
    solo_sub = "Nice dodging. Go again?"
    col_player = "Player"
    col_round = "R{n}"
    col_total = "Total"
    no_score = "-"
    out = "OUT"
    lives_left = "lives left"


class Shell:
    brand = "moovit"
    menu_title = "Vai, Vai, Dai!"
    menu_quit = "Quit"
    splash_prompt = "HOLD THUMBS UP TO START"
    menu_hint = "POINT TO SELECT · HOLD FIST TO START"


class Registry:
    duel = "High Noon"
    dodgeball = "Dodgeball"
    strike = "Strike a pose"


class Duel:
    window_title = "moovit"
    player_names = ("Player 1", "Player 2")
    waiting_for = "WAITING FOR"
    preview_waiting = "WAITING"
    ready_how_to = (
        "Two players: thumbs up to ready, fist to start",
        "Wait for READY · STEADY · BANG — then draw sideways",
        "Don't draw early or you're out for that round",
    )
    replay_label = "REPLAY"
    get_ready = "GET READY, PARTNERS"
    lower_gun = "lower your gun"
    lower_guns = "hands down, wait for READY"
    lower_guns_again = "lower your guns to play again"
    too_early = "too early"
    phase = {
        "ready": "READY",
        "steady": "STEADY",
        "bang": "BANG!",
    }
    result = {
        "timeout": "NOBODY FIRED",
        "void": "BOTH TOO EARLY",
    }
    rules = (
        "Two players: stand side by side, left half is Player 1, right half Player 2",
        "Keep your arms down and stand still for a moment to start a round",
        "Wait for READY, then STEADY, then BANG!",
        "On BANG, draw: point either arm straight out sideways at shoulder height",
        "Fastest draw shoots the other player, who loses a heart",
        "Draw before BANG and you're too early: you can't shoot that round",
        "Nobody draws within {draw_timeout} seconds: no one is hit",
        "Everyone has {lives} hearts. Lose them all and your opponent wins",
    )
    early_messages = (
        "too early....",
        "easy there, cowboy....",
        "hold your horses....",
        "not yet, partner....",
        "jumpy, ain't ya....",
        "whoa there....",
        "patience, pardner....",
        "trigger happy....",
    )
    shot_messages = (
        "TOO SLOW HOMBRE",
        "EAT LEAD, PARTNER",
        "YOU'RE PUSHING DAISIES",
        "SHOULDA STAYED IN BED",
        "DRAW? YOU COULDN'T DRAW A BATH",
        "BITE THE DUST",
        "THAT'S ALL SHE WROTE",
        "SADDLE UP FOR BOOT HILL",
    )
    win_messages = (
        "PAY UP YOU SON OF A GUN!",
        "FASTEST GUN IN THE WEST!",
        "THIS TOWN AIN'T BIG ENOUGH FOR THE TWO OF US",
        "DRINKS ARE ON THE LOSER",
        "YEEHAW!",
        "ANOTHER NOTCH ON THE BELT",
        "SHERIFF'S GOT A NEW DEPUTY",
        "RIDE OFF INTO THE SUNSET, PARTNER",
    )


class Strike:
    window_title = "Strike a Pose"
    banner = "STRIKE A POSE"
    esc_menu = "Esc: menu"
    quit_key = "Q: quit"
    final_scores = "FINAL SCORES"
    col_player = "PLAYER"
    col_round = "ROUND"
    col_total = "TOTAL"
    capture_close = "SPACE or Q: close"
    lobby_ready = "{count} {label} in frame  -  press SPACE to start"
    lobby_need = "Need {min_players} to {max_players} players in frame"
    ready_how_to = (
        "2–4 players: thumbs up to ready, fist to start",
        "Copy the target pose before the countdown ends",
        "Closest match scores the round — best total wins",
    )
    round_of = "Round {round_number} of {total_rounds}"
    results_next_round = "Next round in"
    results_final = "Results in"
    saved_pose = "Saved: {name}"
    edit_title = "Edit pose: {name}"
    player_label = "P{player}"
    winner_one = "{name} wins!"
    winner_tie = "It's a tie!"
    rules = (
        "{min_players} to {max_players} players: stand back so your whole body is in frame",
        "Players are numbered left to right as you appear on screen",
        "Each round shows a stick figure: copy its pose before the timer hits zero",
        "You get {countdown_seconds} seconds, then a snapshot is taken",
        "The screen is a mirror: raise the arm on the same side as the figure",
        "Each pose scores 0 to 100 for how closely your body matches",
        "Scores lock, then next round starts on a timer",
        "After {rounds} rounds, the highest total wins",
    )


class Dodgeball:
    window_title = "Dodgeball"
    banner = "DODGEBALL"
    how_to_play = "HOW TO PLAY"
    get_ready = "Get ready!"
    restarting = "Game restarting..."
    out_label = "OUT"
    ready_how_to = (
        "Thumbs up to ready · leave the frame to cancel",
        "Hold a closed fist when enough players are ready to start",
        "Dodge the ball on the live feed — each hit costs a life",
        "2P: ♥♥♥, 3P: ♥♥, 4P: ♥. Last player standing wins",
    )
    rules = (
        "Stand in front of the camera",
        "Dodge the ball bouncing around the live feed",
        "2P: ♥♥♥, 3P: ♥♥, 4P: ♥ (top-right)",
        "Ball touches your body: lose a life and the round pauses",
        "The game restarts by itself after a hit. No lives left and you're out",
        "Leave the screen for {offscreen_seconds} seconds: lose a life",
        "Last player standing wins",
        "NOTE: Red ball = fast, orange = medium, yellow = slow",
    )
