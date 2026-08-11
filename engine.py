"""Minimax chess AI built on top of python-chess move generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20_000,
}

CHECKMATE_SCORE = 100_000

def _build_table(rows: list[list[int]]) -> list[int]:
    return [value for row in rows for value in row]


PAWN_TABLE = _build_table([
    [0, 0, 0, 0, 0, 0, 0, 0],
    [20, 20, 20, 25, 25, 20, 20, 20],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [5, 5, 10, 25, 25, 10, 5, 5],
    [0, 0, 0, 20, 20, 0, 0, 0],
    [-5, -5, -10, 0, 0, -10, -5, -5],
    [-10, -10, -10, -20, -20, -10, -10, -10],
    [0, 0, 0, 0, 0, 0, 0, 0],
])

KNIGHT_TABLE = _build_table([
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20, 0, 5, 5, 0, -20, -40],
    [-30, 5, 10, 15, 15, 10, 5, -30],
    [-30, 0, 15, 20, 20, 15, 0, -30],
    [-30, 5, 15, 20, 20, 15, 5, -30],
    [-30, 0, 10, 15, 15, 10, 0, -30],
    [-40, -20, 0, 0, 0, 0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
])

BISHOP_TABLE = _build_table([
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10, 5, 0, 0, 0, 0, 5, -10],
    [-10, 10, 10, 10, 10, 10, 10, -10],
    [-10, 0, 10, 10, 10, 10, 0, -10],
    [-10, 5, 10, 10, 10, 10, 5, -10],
    [-10, 0, 10, 10, 10, 10, 0, -10],
    [-10, 0, 0, 0, 0, 0, 0, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
])

ROOK_TABLE = _build_table([
    [0, 0, 0, 5, 5, 0, 0, 0],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [5, 10, 10, 10, 10, 10, 10, 5],
    [0, 0, 0, 0, 0, 0, 0, 0],
])

QUEEN_TABLE = _build_table([
    [-20, -10, -10, -5, -5, -10, -10, -20],
    [-10, 0, 0, 0, 0, 0, 0, -10],
    [-10, 0, 5, 5, 5, 5, 0, -10],
    [-5, 0, 5, 5, 5, 5, 0, -5],
    [0, 0, 5, 5, 5, 5, 0, -5],
    [-10, 0, 5, 5, 5, 5, 0, -10],
    [-10, 0, 0, 0, 0, 0, 0, -10],
    [-20, -10, -10, -5, -5, -10, -10, -20],
])

KING_TABLE = _build_table([
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [20, 20, 0, 0, 0, 0, 20, 20],
    [20, 30, 10, 0, 0, 10, 30, 20],
])

PIECE_SQUARE_TABLES = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE,
}


@dataclass(frozen=True)
class SearchResult:
    move: chess.Move | None
    score: int
    nodes: int
    depth: int = 0
    timed_out: bool = False


class _SearchDeadlineExceeded(Exception):
    """Stop the current search without leaving moves pushed on the board."""


def _piece_square_score(piece: chess.Piece, square: int) -> int:
    table = PIECE_SQUARE_TABLES[piece.piece_type]
    if piece.color == chess.WHITE:
        return table[square]
    return -table[chess.square_mirror(square)]


def evaluate_board(board: chess.Board) -> int:
    """Return a material + positional score in centipawns. Positive is good for White."""
    if board.is_checkmate():
        return -CHECKMATE_SCORE if board.turn == chess.WHITE else CHECKMATE_SCORE

    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value
        score -= len(board.pieces(piece_type, chess.BLACK)) * value

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            score += _piece_square_score(piece, square)

    return score


def get_evaluation(board: chess.Board, depth: int = 3) -> dict[str, int | str | None]:
    """Return a White-relative static evaluation, with short forced mates detected."""
    if depth < 1:
        raise ValueError("depth must be at least 1")

    position = board.copy(stack=False)
    outcome = position.outcome()
    if outcome is not None:
        if outcome.winner is None:
            return {"eval": 0, "mate": None, "winner": None}
        return {
            "eval": None,
            "mate": 0,
            "winner": "white" if outcome.winner == chess.WHITE else "black",
        }

    search = choose_best_move(position, depth=depth)
    white_score = search.score if position.turn == chess.WHITE else -search.score
    mate_distance = CHECKMATE_SCORE - abs(search.score)
    if 0 < mate_distance <= depth:
        return {
            "eval": None,
            "mate": mate_distance if white_score > 0 else -mate_distance,
            "winner": "white" if white_score > 0 else "black",
        }

    return {"eval": evaluate_board(position), "mate": None, "winner": None}


def choose_best_move(
    board: chess.Board,
    depth: int = 3,
    *,
    time_limit_seconds: float | None = None,
) -> SearchResult:
    """Pick the best legal move, optionally keeping the search within a deadline."""
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if time_limit_seconds is not None and time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive")

    if board.is_game_over():
        return SearchResult(move=None, score=evaluate_board(board), nodes=0, depth=0)

    if time_limit_seconds is None:
        return _search_at_depth(board, depth)

    deadline = perf_counter() + time_limit_seconds
    completed_result: SearchResult | None = None
    completed_nodes = 0
    timed_out = False

    for current_depth in range(1, depth + 1):
        try:
            result = _search_at_depth(board, current_depth, deadline)
        except _SearchDeadlineExceeded:
            timed_out = True
            break

        completed_nodes += result.nodes
        completed_result = SearchResult(
            move=result.move,
            score=result.score,
            nodes=completed_nodes,
            depth=current_depth,
        )

    if completed_result is not None:
        return SearchResult(
            move=completed_result.move,
            score=completed_result.score,
            nodes=completed_result.nodes,
            depth=completed_result.depth,
            timed_out=timed_out,
        )

    fallback_move = _ordered_moves(board)[0]
    board.push(fallback_move)
    try:
        side_multiplier = 1 if board.turn == chess.WHITE else -1
        fallback_score = -evaluate_board(board) * side_multiplier
    finally:
        board.pop()

    return SearchResult(
        move=fallback_move,
        score=fallback_score,
        nodes=0,
        depth=0,
        timed_out=True,
    )


def _search_at_depth(
    board: chess.Board,
    depth: int,
    deadline: float | None = None,
) -> SearchResult:
    _check_deadline(deadline)
    best_move: chess.Move | None = None
    best_score = -math.inf
    nodes = 0

    for move in _ordered_moves(board):
        _check_deadline(deadline)
        board.push(move)
        try:
            score, searched = _negamax(
                board,
                depth - 1,
                -math.inf,
                math.inf,
                deadline,
                ply=1,
            )
        finally:
            board.pop()

        score = -score
        nodes += searched + 1

        if score > best_score:
            best_score = score
            best_move = move

    return SearchResult(
        move=best_move,
        score=int(best_score),
        nodes=nodes,
        depth=depth,
    )


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: float,
    beta: float,
    deadline: float | None = None,
    ply: int = 0,
) -> tuple[int, int]:
    _check_deadline(deadline)
    if depth == 0 or board.is_game_over():
        return _quiescence(board, alpha, beta, deadline, ply)

    best_score = -math.inf
    nodes = 0

    for move in _ordered_moves(board):
        _check_deadline(deadline)
        board.push(move)
        try:
            score, searched = _negamax(
                board,
                depth - 1,
                -beta,
                -alpha,
                deadline,
                ply + 1,
            )
        finally:
            board.pop()

        score = -score
        nodes += searched

        best_score = max(best_score, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break

    return int(best_score), nodes


def _quiescence(
    board: chess.Board,
    alpha: float,
    beta: float,
    deadline: float | None = None,
    ply: int = 0,
) -> tuple[int, int]:
    """Search only captures to reduce the horizon effect."""
    _check_deadline(deadline)
    if board.is_checkmate():
        return -CHECKMATE_SCORE + ply, 1
    if board.is_stalemate() or board.is_insufficient_material():
        return 0, 1

    side_multiplier = 1 if board.turn == chess.WHITE else -1
    stand_pat = evaluate_board(board) * side_multiplier
    if stand_pat >= beta:
        return int(stand_pat), 1

    best_score = stand_pat
    nodes = 1
    alpha = max(alpha, stand_pat)

    for move in _ordered_moves(board):
        if not board.is_capture(move):
            continue

        _check_deadline(deadline)
        board.push(move)
        try:
            score, searched = _quiescence(board, -beta, -alpha, deadline, ply + 1)
        finally:
            board.pop()

        score = -score
        nodes += searched

        best_score = max(best_score, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break

    return int(best_score), nodes


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and perf_counter() >= deadline:
        raise _SearchDeadlineExceeded


def _ordered_moves(board: chess.Board) -> list[chess.Move]:
    """Search forcing moves first so depth 3 stays responsive."""
    def move_priority(move: chess.Move) -> int:
        priority = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            if victim and attacker:
                priority += 10 * PIECE_VALUES[victim.piece_type] - PIECE_VALUES[attacker.piece_type]
            else:
                priority += 1_000
        if move.promotion:
            priority += PIECE_VALUES.get(move.promotion, 0)
        return priority

    return sorted(board.legal_moves, key=move_priority, reverse=True)
