"""User-facing copy. No colors, fonts, or timings."""

from __future__ import annotations


class Shell:
    brand = "moovit"
    menu_title = "moovit"
    splash_prompt = "HOLD THUMBS UP TO START"
    menu_hint = "POINT TO SELECT · HOLD FIST TO START"


class Registry:
    duel = "High Noon"
    dodgeball = "Dodgeball"
    strike = "Strike the Pose"


class Duel:
    window_title = "moovit"
    player_names = ("Player 1", "Player 2")
    waiting_for = "WAITING FOR"
    preview_waiting = "WAITING"
    replay_label = "REPLAY"
    get_ready = "GET READY, PARTNERS"
    lower_gun = "lower your gun"
    lower_guns_again = "lower your guns to play again"
    too_early = "too early"
    phase = {
        "ready": "READY",
        "steady": "STEADY",
        "bang": "BANG!",
    }
    result = {
        "tie": "DEAD EVEN",
        "timeout": "NOBODY FIRED",
        "void": "BOTH TOO EARLY",
    }
    wins_suffix = "WINS"
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
    space_final = "SPACE: final scores"
    space_next = "SPACE: next round"
    space_new_game = "SPACE: new game      Q: quit"
    results_thumbs = "Hold thumbs up to continue"
    results_thumbs_final = "Hold thumbs up for final scores"
    final_scores = "FINAL SCORES"
    col_player = "PLAYER"
    col_round = "ROUND"
    col_total = "TOTAL"
    missing_retry = ("Everyone back in frame,", "then press SPACE", "to try this pose again.")
    capture_close = "SPACE or Q: close"
    lobby_ready = "{count} {label} in frame  -  press SPACE to start"
    lobby_need = "Need {min_players} to {max_players} players in frame"
    round_of = "Round {round_number} of {total_rounds}"
    round_results = "Round {round_number} of {total_rounds}  -  results"
    found_players = "Found {found} of {expected} players"
    saved_pose = "Saved: {name}"
    edit_title = "Edit pose: {name}"
    player_label = "P{player}"
    winner_one = "{name} wins!"
    winner_tie = "It's a tie!"


class Dodgeball:
    window_title = "Dodgeball"
    banner = "DODGEBALL"
    how_to_play = "HOW TO PLAY"
    whos_playing = "WHO'S PLAYING?"
    to_play = "to play"
    to_sit_out = "to sit out"
    lobby_prompt = "Press SPACE to choose who's playing"
    lobby_skip = "or press 1 / 2 / 3 to skip and start with that many"
    confirm_hint = "R clear  |  Backspace rules  |  1 / 2 / 3 skip gestures"
    step_in = "Step in front of the camera"
    everyone_thumbs = "Everyone playing: give a thumbs up!"
    max_players = "Max {max_players} players - someone give a thumbs down first"
    get_ready = "Get ready!"
    restarting = "Game restarting..."
    out_label = "OUT"
    unknown_label = "?"
    rules = (
        "Stand in front of the camera",
        "Dodge the ball bouncing around the live feed",
        "Everyone starts with {lives} lives (hearts, top-right)",
        "Ball touches your body: lose a life and the round pauses",
        "Press R to resume. No lives left and you're out",
        "Leave the screen for {offscreen_seconds} seconds: lose a life",
        "Last player standing wins. Solo: survive as long as you can",
        "NOTE: Red ball = fast, orange = medium, yellow = slow",
    )
