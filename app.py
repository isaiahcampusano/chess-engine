"""Flask bridge between the browser UI and the chess engine."""

from __future__ import annotations

import os

import chess
from flask import Flask, jsonify, request, session

from analysis import MAX_GAME_PLIES, analyse_game
from engine import (
    SearchResult,
    choose_move_with_skill,
    evaluate_board,
    get_evaluation,
)
from bot_config import BOT_CONFIGS
from personality import PERSONALITIES, Personality, get_personality
from opening_book import get_default_opening_book


LIVE_EVALUATION_DEPTH = 3
OPENING_BOOK = get_default_opening_book()
PLAYER_BLUNDER_THRESHOLD_CP = 150
PLAYER_GOOD_MOVE_THRESHOLD_CP = 100
POSITION_COMMENTARY_THRESHOLD_CP = 150
POSITION_COMMENTARY_INTERVAL = 2
BOTS = {
    personality_id: {
        **BOT_CONFIGS[personality_id],
        "label": personality.label,
    }
    for personality_id, personality in PERSONALITIES.items()
}

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)


@app.get("/")
def index():
    """Serve the chess interface."""
    return app.send_static_file("index.html")


@app.route("/select_bot", methods=["GET", "POST"])
def select_bot():
    """Return the current opponent or commit a choice for the next game."""
    _reset_stale_opponent()
    opening_commentary = None
    if request.method == "POST":
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("Request body must be a JSON object.", 400)

        bot_id = payload.get("bot_id")
        if bot_id not in BOTS:
            return _error("Invalid bot ID.", 400)

        if session.get("opponent_selected", False):
            active_bot_id = _active_game_bot_id()
            return _error(
                (
                    f"{BOTS[active_bot_id]['label']} is locked for this game. "
                    "Start a new game before choosing another opponent."
                ),
                409,
            )

        session["bot"] = bot_id
        session["active_game_bot"] = bot_id
        session["opponent_selected"] = True
        session["game_started"] = False
        session["commentary_eval"] = evaluate_board(chess.Board())
        session["commentary_tick"] = 0
        session.pop("last_commentary", None)
        opening_commentary = _pick_commentary(bot_id, "game_start")

    if not session.get("opponent_selected", False):
        return jsonify(
            {
                "status": "selection_required",
                "selected": None,
                "depth": None,
                "label": None,
                "active_game_bot": None,
                "game_active": False,
                "needs_selection": True,
                "commentary": None,
                "avatar": None,
                "idle_lines": [],
            }
        )

    bot_id = _active_game_bot_id()
    personality = get_personality(bot_id)
    return jsonify(
        {
            "status": "ok",
            "selected": bot_id,
            "depth": BOTS[bot_id]["depth"],
            "label": BOTS[bot_id]["label"],
            "active_game_bot": _active_game_bot_id(),
            "game_active": session.get("game_started", False),
            "needs_selection": False,
            "tier": personality.tier,
            "commentary": opening_commentary,
            "avatar": personality.avatar,
            "idle_lines": personality.lines.get("idle", []),
        }
    )


@app.post("/new_game")
def new_game():
    """End the current match and require a fresh opponent choice."""
    _clear_opponent_selection()
    return jsonify(
        {
            "status": "ok",
            "selected": None,
            "bot": None,
            "depth": None,
            "label": None,
            "active_game_bot": None,
            "game_active": False,
            "needs_selection": True,
        }
    )


@app.post("/end_game")
def end_game():
    """Release the locked opponent after a completed browser game."""
    payload = request.get_json(silent=True)
    fen = payload.get("fen") if isinstance(payload, dict) else None
    try:
        board = chess.Board(fen) if isinstance(fen, str) else None
    except ValueError:
        board = None
    if board is None or not board.is_game_over():
        return _error("The opponent stays locked until the game is over.", 409)

    bot_id = _valid_session_bot_id()
    outcome = board.outcome()
    trigger = _terminal_commentary_trigger(outcome, chess.BLACK)
    commentary = _pick_commentary(bot_id, trigger) if bot_id and trigger else None
    avatar = get_personality(bot_id).avatar if bot_id else None
    _clear_opponent_selection()
    return jsonify(
        {
            "status": "ok",
            "needs_selection": True,
            "commentary": commentary,
            "avatar": avatar,
        }
    )


@app.post("/move")
def handle_move():
    """Return the engine's best move for a supplied FEN position."""
    _reset_stale_opponent()
    if not session.get("opponent_selected", False):
        return _error("Choose an opponent before starting the game.", 409)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("Request body must be a JSON object.", 400)

    fen = payload.get("fen")
    if not isinstance(fen, str) or not fen.strip():
        return _error("A non-empty 'fen' string is required.", 400)

    try:
        board = chess.Board(fen.strip())
    except ValueError:
        return _error("The supplied FEN is invalid.", 400)

    if not board.is_valid():
        return _error("The supplied FEN does not describe a valid chess position.", 400)

    bot_id = _active_game_bot_id()
    personality = get_personality(bot_id)
    bot_color = board.turn
    if board.is_game_over():
        outcome = board.outcome()
        trigger = _terminal_commentary_trigger(outcome, bot_color)
        commentary = _pick_commentary(bot_id, trigger) if trigger else None
        _clear_opponent_selection()
        return jsonify(
            {
                "engine_move": None,
                "score": 0,
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "game_over": True,
                "is_capture": False,
                "is_check": False,
                "is_castle": False,
                "is_promotion": False,
                "outcome": _outcome_payload(outcome),
                "commentary": commentary,
                "avatar": personality.avatar,
            }
        )

    session["game_started"] = True
    result: SearchResult | None = None
    position_before_bot_eval = evaluate_board(board)
    player_trigger = _player_move_trigger(
        session.get("commentary_eval"),
        position_before_bot_eval,
        not bot_color,
    )

    try:
        candidate = choose_move_with_skill(
            board, **BOT_CONFIGS[bot_id], opening_book=OPENING_BOOK,
        )
        candidate_move = getattr(candidate, "move", None)
        if candidate_move is not None and candidate_move in board.legal_moves:
            result = candidate
        else:
            app.logger.error("Engine returned no legal move for FEN %s.", board.fen())
    except Exception:
        app.logger.exception("Engine failed for FEN %s.", board.fen())

    if result is None:
        legal_moves = list(board.legal_moves)
        if legal_moves:
            emergency_move = legal_moves[0]
            result = SearchResult(
                move=emergency_move,
                score=0,
                nodes=0,
                depth=0,
                timed_out=True,
            )
            app.logger.critical(
                "Emergency fallback selected legal move %s for FEN %s.",
                emergency_move,
                board.fen(),
            )

    if result is None or result.move is None or result.move not in board.legal_moves:
        app.logger.critical("Unable to generate a legal move for FEN: %s", board.fen())
        return _error("The engine did not return a legal move.", 500)

    move = result.move
    move_flags = {
        "is_capture": board.is_capture(move),
        "is_check": board.gives_check(move),
        "is_castle": board.is_castling(move),
        "is_promotion": move.promotion is not None,
    }
    position_after_move = board.copy(stack=False)
    position_after_move.push(move)
    position_after_bot_eval = evaluate_board(position_after_move)
    outcome = position_after_move.outcome()
    game_over = outcome is not None
    commentary_tick = int(session.get("commentary_tick", 0)) + 1
    session["commentary_tick"] = commentary_tick
    session["commentary_eval"] = position_after_bot_eval

    trigger = _terminal_commentary_trigger(outcome, bot_color)
    if trigger is None and player_trigger == "player_blunder":
        trigger = player_trigger
    if trigger is None and _bot_blundered(
        personality,
        position_before_bot_eval,
        position_after_bot_eval,
        bot_color,
    ):
        trigger = "bot_blunder_aware"
    if trigger is None and player_trigger == "player_good_move":
        trigger = player_trigger
    if trigger is None and move_flags["is_capture"]:
        trigger = "bot_capture"
    if trigger is None and commentary_tick % POSITION_COMMENTARY_INTERVAL == 0:
        if result.score > POSITION_COMMENTARY_THRESHOLD_CP:
            trigger = "bot_winning"
        elif result.score < -POSITION_COMMENTARY_THRESHOLD_CP:
            trigger = "bot_losing"

    commentary = _pick_commentary(bot_id, trigger) if trigger else None
    if game_over:
        _clear_opponent_selection()

    return jsonify(
        {
            "engine_move": move.uci(),
            "score": result.score,
            "nodes": result.nodes,
            "depth": result.depth,
            "timed_out": result.timed_out,
            "game_over": game_over,
            **move_flags,
            "outcome": _outcome_payload(outcome),
            "commentary": commentary,
            "avatar": personality.avatar,
        }
    )


@app.post("/analysis")
def handle_analysis():
    """Analyze a legal game move-by-move for the post-game review UI."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("Request body must be a JSON object.", 400)

    moves = payload.get("moves")
    if not isinstance(moves, list):
        return _error("'moves' must be an array of UCI move strings.", 400)
    if len(moves) > MAX_GAME_PLIES:
        return _error(f"Analysis is limited to {MAX_GAME_PLIES} half-moves.", 400)

    start_fen = payload.get("start_fen", chess.STARTING_FEN)
    if not isinstance(start_fen, str) or not start_fen.strip():
        return _error("'start_fen' must be a non-empty FEN string.", 400)

    try:
        result = analyse_game(moves, start_fen=start_fen.strip())
    except ValueError as error:
        return _error(str(error), 400)
    except Exception:
        app.logger.exception("Post-game analysis failed")
        return _error("The game could not be analyzed.", 500)

    return jsonify(result)


@app.post("/api/eval")
def handle_evaluation():
    """Evaluate a supplied position for the live advantage bar."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("Request body must be a JSON object.", 400)

    fen = payload.get("fen")
    if not isinstance(fen, str) or not fen.strip():
        return _error("A non-empty 'fen' string is required.", 400)

    try:
        board = chess.Board(fen.strip())
    except ValueError:
        return _error("The supplied FEN is invalid.", 400)

    if not board.is_valid():
        return _error("The supplied FEN does not describe a valid chess position.", 400)

    try:
        return jsonify(get_evaluation(board, depth=LIVE_EVALUATION_DEPTH))
    except Exception:
        app.logger.exception("Position evaluation failed")
        return _error("The position could not be evaluated.", 500)


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _outcome_payload(outcome: chess.Outcome | None) -> dict[str, str | None] | None:
    if outcome is None:
        return None
    return {
        "winner": (
            "white"
            if outcome.winner is chess.WHITE
            else "black"
            if outcome.winner is chess.BLACK
            else None
        ),
        "termination": outcome.termination.name.lower(),
    }


def _selected_bot_id() -> str:
    bot_id = session.get("bot", "professor")
    return bot_id if bot_id in BOTS else "professor"


def _active_game_bot_id() -> str:
    bot_id = session.get("active_game_bot")
    if bot_id not in BOTS:
        bot_id = _selected_bot_id()
        session["active_game_bot"] = bot_id
    return bot_id


def _clear_opponent_selection() -> None:
    session.pop("bot", None)
    session.pop("active_game_bot", None)
    session.pop("opponent_selected", None)
    session.pop("commentary_eval", None)
    session.pop("commentary_tick", None)
    session.pop("last_commentary", None)
    session["game_started"] = False


def _valid_session_bot_id() -> str | None:
    bot_id = session.get("active_game_bot")
    return bot_id if bot_id in BOTS else None


def _reset_stale_opponent() -> None:
    if session.get("opponent_selected", False) and _valid_session_bot_id() is None:
        _clear_opponent_selection()


def _pick_commentary(bot_id: str, trigger: str) -> str | None:
    line = get_personality(bot_id).say(
        trigger,
        previous=session.get("last_commentary"),
    )
    if line is not None:
        session["last_commentary"] = line
    return line


def _score_for_color(score: int, color: chess.Color) -> int:
    return score if color == chess.WHITE else -score


def _player_move_trigger(
    previous_eval: object,
    current_eval: int,
    player_color: chess.Color,
) -> str | None:
    if not isinstance(previous_eval, (int, float)):
        return None
    delta = _score_for_color(current_eval - int(previous_eval), player_color)
    if delta <= -PLAYER_BLUNDER_THRESHOLD_CP:
        return "player_blunder"
    if delta >= PLAYER_GOOD_MOVE_THRESHOLD_CP:
        return "player_good_move"
    return None


def _bot_blundered(
    personality: Personality,
    before_eval: int,
    after_eval: int,
    bot_color: chess.Color,
) -> bool:
    if "bot_blunder_aware" not in personality.lines:
        return False
    delta = _score_for_color(after_eval - before_eval, bot_color)
    return delta <= -PLAYER_BLUNDER_THRESHOLD_CP


def _terminal_commentary_trigger(
    outcome: chess.Outcome | None,
    bot_color: chess.Color,
) -> str | None:
    if outcome is None or outcome.termination != chess.Termination.CHECKMATE:
        return None
    return "checkmate_win" if outcome.winner == bot_color else "checkmate_loss"


if __name__ == "__main__":
    app.run(debug=True, port=5000)
