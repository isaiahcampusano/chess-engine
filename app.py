"""Flask bridge between the browser UI and the chess engine."""

from __future__ import annotations

import os

import chess
from flask import Flask, jsonify, request, session

from analysis import MAX_GAME_PLIES, analyse_game
from engine import (
    SearchResult,
    choose_best_move,
    choose_move_with_skill,
    get_evaluation,
)


ENGINE_TIME_LIMIT_SECONDS = 8.0
BOTS = {
    "novice": {"depth": 1, "label": "Novice", "blunder_chance": 0.35},
    "expert": {"depth": 3, "label": "Expert", "blunder_chance": 0.0},
}

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)


@app.get("/")
def index():
    """Serve the chess interface."""
    return app.send_static_file("index.html")


@app.route("/select_bot", methods=["GET", "POST"])
def select_bot():
    """Return or update the preferred opponent without changing an active game."""
    if request.method == "POST":
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("Request body must be a JSON object.", 400)

        bot_id = payload.get("bot_id")
        if bot_id not in BOTS:
            return _error("Invalid bot ID.", 400)
        session["bot"] = bot_id

        if session.get("game_started", False):
            active_bot_id = _active_game_bot_id()
            return jsonify(
                {
                    "status": "preference_saved",
                    "selected": bot_id,
                    "depth": BOTS[bot_id]["depth"],
                    "label": BOTS[bot_id]["label"],
                    "message": (
                        f"{BOTS[bot_id]['label']} is saved for the next game."
                    ),
                    "current_game_bot": active_bot_id,
                    "current_game_depth": BOTS[active_bot_id]["depth"],
                    "current_game_label": BOTS[active_bot_id]["label"],
                    "game_active": True,
                }
            )

        session["active_game_bot"] = bot_id

    bot_id = _selected_bot_id()
    return jsonify(
        {
            "status": "ok",
            "selected": bot_id,
            "depth": BOTS[bot_id]["depth"],
            "label": BOTS[bot_id]["label"],
            "active_game_bot": _active_game_bot_id(),
            "game_active": session.get("game_started", False),
        }
    )


@app.post("/new_game")
def new_game():
    """Open a new pre-game window and seed it with the preferred opponent."""
    bot_id = _selected_bot_id()
    session["active_game_bot"] = bot_id
    session["game_started"] = False
    return jsonify(
        {
            "status": "ok",
            "selected": bot_id,
            "bot": bot_id,
            "depth": BOTS[bot_id]["depth"],
            "label": BOTS[bot_id]["label"],
            "active_game_bot": bot_id,
            "game_active": False,
        }
    )


@app.post("/move")
def handle_move():
    """Return the engine's best move for a supplied FEN position."""
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

    if board.is_game_over():
        session["game_started"] = False
        return jsonify(
            {
                "engine_move": None,
                "score": 0,
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "game_over": True,
            }
        )

    bot_id = _active_game_bot_id()
    session["game_started"] = True
    bot_config = BOTS[bot_id]
    max_depth = bot_config["depth"]
    blunder_chance = bot_config.get("blunder_chance", 0.0)
    result: SearchResult | None = None

    search_depths = [max_depth]
    if max_depth != 1:
        search_depths.append(1)

    for index, search_depth in enumerate(search_depths):
        try:
            app.logger.info(
                "Attempting engine search at depth %s for FEN %s.",
                search_depth,
                board.fen(),
            )
            if index == 0 and blunder_chance > 0:
                candidate = choose_move_with_skill(
                    board,
                    blunder_chance=blunder_chance,
                )
            else:
                candidate = choose_best_move(
                    board,
                    depth=search_depth,
                    time_limit_seconds=ENGINE_TIME_LIMIT_SECONDS,
                )
        except Exception:
            app.logger.exception(
                "Engine crashed at depth %s for FEN %s; retrying.",
                search_depth,
                board.fen(),
            )
            continue

        candidate_move = getattr(candidate, "move", None)
        if candidate_move is not None and candidate_move in board.legal_moves:
            result = candidate
            app.logger.info("Engine returned a legal move at depth %s.", search_depth)
            break

        app.logger.warning(
            "Engine returned no legal move at depth %s for FEN %s; retrying.",
            search_depth,
            board.fen(),
        )

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

    return jsonify(
        {
            "engine_move": result.move.uci(),
            "score": result.score,
            "nodes": result.nodes,
            "depth": result.depth,
            "timed_out": result.timed_out,
            "game_over": False,
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
        return jsonify(get_evaluation(board, depth=BOTS["expert"]["depth"]))
    except Exception:
        app.logger.exception("Position evaluation failed")
        return _error("The position could not be evaluated.", 500)


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _selected_bot_id() -> str:
    bot_id = session.get("bot", "expert")
    return bot_id if bot_id in BOTS else "expert"


def _active_game_bot_id() -> str:
    bot_id = session.get("active_game_bot")
    if bot_id not in BOTS:
        bot_id = _selected_bot_id()
        session["active_game_bot"] = bot_id
    return bot_id


if __name__ == "__main__":
    app.run(debug=True, port=5000)
