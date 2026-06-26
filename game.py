"""Terminal game loop for human vs minimax chess."""

from __future__ import annotations

import os

import chess

from engine import SearchResult, choose_best_move


FILES = "abcdefgh"


def play(depth: int = 3, human_color: chess.Color = chess.WHITE) -> None:
    board = chess.Board()
    last_ai_result: SearchResult | None = None

    while not board.is_game_over():
        _clear_screen()
        _print_status(board, depth, last_ai_result)
        _print_board(board)

        if board.turn == human_color:
            move = _prompt_for_move(board)
        else:
            result = choose_best_move(board, depth=depth)
            move = result.move
            last_ai_result = result

        if move is None:
            break
        board.push(move)

    _clear_screen()
    _print_board(board)
    _print_result(board)


def _prompt_for_move(board: chess.Board) -> chess.Move:
    while True:
        raw = input("Your move (UCI like e2e4, or 'quit'): ").strip().lower()
        if raw in {"q", "quit", "exit"}:
            raise SystemExit("Game ended by player.")

        try:
            move = chess.Move.from_uci(raw)
        except ValueError:
            print("Use UCI notation, for example e2e4 or e7e8q for promotion.")
            continue

        if move in board.legal_moves:
            return move

        print("That move is not legal in this position.")


def _print_board(board: chess.Board) -> None:
    print()
    for rank in range(7, -1, -1):
        row = [board.piece_at(chess.square(file, rank)) for file in range(8)]
        cells = [piece.symbol() if piece else "." for piece in row]
        print(f"{rank + 1}  {' '.join(cells)}")
    print()
    print(f"   {' '.join(FILES)}")
    print()


def _print_status(board: chess.Board, depth: int, last_ai_result: SearchResult | None) -> None:
    side = "White" if board.turn == chess.WHITE else "Black"
    print(f"Python Chess Engine | AI depth: {depth} | Turn: {side}")
    if last_ai_result and last_ai_result.move:
        print(
            f"Last AI move: {last_ai_result.move.uci()} | "
            f"score {last_ai_result.score} | searched {last_ai_result.nodes} nodes"
        )
    if board.is_check():
        print(f"{side} is in check.")


def _print_result(board: chess.Board) -> None:
    outcome = board.outcome()
    if outcome is None:
        print("Game ended.")
        return

    if outcome.winner is None:
        print(f"Draw by {outcome.termination.name.lower().replace('_', ' ')}.")
    else:
        winner = "White" if outcome.winner == chess.WHITE else "Black"
        print(f"{winner} wins by {outcome.termination.name.lower().replace('_', ' ')}.")


def _clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")
