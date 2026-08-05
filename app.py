"""Flask bridge between the browser UI and the chess engine."""

from __future__ import annotations

import chess
from flask import Flask, jsonify, request

from analysis import MAX_GAME_PLIES, analyse_game
from engine import choose_best_move


ENGINE_DEPTH = 3
ENGINE_TIME_LIMIT_SECONDS = 8.0

app = Flask(__name__, static_folder="static", static_url_path="/static")


@app.get("/")
def index():
    """Serve the chess interface."""
    return app.send_static_file("index.html")


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

    try:
        result = choose_best_move(
            board,
            depth=ENGINE_DEPTH,
            time_limit_seconds=ENGINE_TIME_LIMIT_SECONDS,
        )
    except Exception:
        app.logger.exception("Chess engine search failed")
        return _error("The engine could not calculate a move.", 500)

    if result.move is None or result.move not in board.legal_moves:
        app.logger.error("Chess engine returned no legal move for FEN: %s", board.fen())
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


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


if __name__ == "__main__":
    app.run(debug=True, port=5000)
