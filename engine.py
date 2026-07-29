"""Minimax chess AI built on top of python-chess move generation."""

from __future__ import annotations

import math
from dataclasses import dataclass

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


def choose_best_move(board: chess.Board, depth: int = 3) -> SearchResult:
    """Pick the best legal move for the side to move."""
    if board.is_game_over():
        return SearchResult(move=None, score=evaluate_board(board), nodes=0)

    best_move: chess.Move | None = None
    best_score = -math.inf
    nodes = 0

    for move in _ordered_moves(board):
        board.push(move)
        score, searched = _negamax(board, depth - 1, -math.inf, math.inf)
        score = -score
        nodes += searched + 1
        board.pop()

        if score > best_score:
            best_score = score
            best_move = move

    return SearchResult(move=best_move, score=int(best_score), nodes=nodes)


def _negamax(board: chess.Board, depth: int, alpha: float, beta: float) -> tuple[int, int]:
    if depth == 0 or board.is_game_over():
        return _quiescence(board, alpha, beta)

    best_score = -math.inf
    nodes = 0

    for move in _ordered_moves(board):
        board.push(move)
        score, searched = _negamax(board, depth - 1, -beta, -alpha)
        score = -score
        nodes += searched
        board.pop()

        best_score = max(best_score, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break

    return int(best_score), nodes


def _quiescence(board: chess.Board, alpha: float, beta: float) -> tuple[int, int]:
    """Search only captures to reduce the horizon effect."""
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

        board.push(move)
        score, searched = _quiescence(board, -beta, -alpha)
        score = -score
        nodes += searched
        board.pop()

        best_score = max(best_score, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break

    return int(best_score), nodes


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
