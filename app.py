"""Flask bridge between the browser UI and the chess engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import chess
from flask import Flask, jsonify, request

from engine import choose_best_move


ENGINE_DEPTH = 3
SEARCH_TIMEOUT_SECONDS = 10
SEARCH_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chess-engine")

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
                "game_over": True,
            }
        )

    future = SEARCH_EXECUTOR.submit(choose_best_move, board, ENGINE_DEPTH)
    try:
        result = future.result(timeout=SEARCH_TIMEOUT_SECONDS)
    except FutureTimeoutError:
        future.cancel()
        return _error(
            f"The engine did not find a move within {SEARCH_TIMEOUT_SECONDS} seconds.",
            504,
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
            "game_over": False,
        }
    )


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


if __name__ == "__main__":
    app.run(debug=True, port=5000)
