"""Minimax chess AI built on top of python-chess move generation."""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from time import perf_counter
from typing import Literal

import chess
import chess.polyglot


logger = logging.getLogger(__name__)

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


@dataclass(frozen=True)
class _TranspositionEntry:
    depth: int
    score: int
    bound: Literal["exact", "lower", "upper"]
    best_move: chess.Move | None


@dataclass
class _SearchState:
    deadline: float | None
    transposition_table: dict[tuple[int, int], _TranspositionEntry]
    killer_moves: dict[int, list[chess.Move]]
    history: dict[tuple[bool, int, int, int | None], int]

    @classmethod
    def create(cls, deadline: float | None) -> _SearchState:
        return cls(deadline, {}, {}, {})


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
    debug: bool = False,
) -> SearchResult:
    """Pick the best legal move, optionally keeping the search within a deadline."""
    search_started = perf_counter()
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if time_limit_seconds is not None and time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive")

    if board.is_game_over():
        return SearchResult(move=None, score=evaluate_board(board), nodes=0, depth=0)

    safety_move = next(iter(board.legal_moves))
    logger.info("Engine called on FEN: %s", board.fen())

    completed_result: SearchResult | None = None
    interrupted_result: SearchResult | None = None
    completed_nodes = 0
    timed_out = False

    if time_limit_seconds is None:
        state = _SearchState.create(deadline=None)
        try:
            result = _search_at_depth(board, depth, state=state)
        except Exception:
            logger.exception(
                "Unrestricted depth-%s search crashed for FEN %s.",
                depth,
                board.fen(),
            )
            timed_out = True
        else:
            if result.move is not None and result.move in board.legal_moves:
                _log_search_result(board, result, search_started, debug)
                return result
            timed_out = result.timed_out
        logger.warning(
            "Unrestricted depth-%s search returned no legal move for FEN %s; "
            "starting fallback tiers.",
            depth,
            board.fen(),
        )
    else:
        deadline = search_started + time_limit_seconds
        state = _SearchState.create(deadline)
        for current_depth in range(1, depth + 1):
            try:
                result = _search_at_depth(
                    board,
                    current_depth,
                    deadline,
                    state=state,
                )
            except _SearchDeadlineExceeded:
                timed_out = True
                break
            except Exception:
                logger.exception(
                    "Main search crashed at depth %s for FEN %s.",
                    current_depth,
                    board.fen(),
                )
                timed_out = True
                break

            completed_nodes += result.nodes
            if result.timed_out:
                timed_out = True
                interrupted_result = result
                break

            completed_result = SearchResult(
                move=result.move,
                score=result.score,
                nodes=completed_nodes,
                depth=current_depth,
            )
            _log_search_result(board, completed_result, search_started, debug)

    if (
        completed_result is not None
        and completed_result.move is not None
        and completed_result.move in board.legal_moves
    ):
        final_result = SearchResult(
            move=completed_result.move,
            score=completed_result.score,
            nodes=completed_result.nodes,
            depth=completed_result.depth,
            timed_out=timed_out,
        )
        _log_search_result(board, final_result, search_started, debug)
        return final_result

    if (
        interrupted_result is not None
        and interrupted_result.move is not None
        and interrupted_result.move in board.legal_moves
    ):
        final_result = SearchResult(
            move=interrupted_result.move,
            score=interrupted_result.score,
            nodes=completed_nodes,
            depth=interrupted_result.depth,
            timed_out=True,
        )
        _log_search_result(board, final_result, search_started, debug)
        return final_result

    logger.warning(
        "Main search failed or timed out before completing depth 1 of %s; "
        "using the preselected safety-net move.",
        depth,
    )

    fallback_score = _score_move_for_side_to_move(board, safety_move)
    logger.critical(
        "Using absolute last-resort move %s for FEN %s.",
        safety_move,
        board.fen(),
    )

    final_result = SearchResult(
        move=safety_move,
        score=fallback_score,
        nodes=0,
        depth=0,
        timed_out=True,
    )
    _log_search_result(board, final_result, search_started, debug)
    return final_result


def _search_at_depth(
    board: chess.Board,
    depth: int,
    deadline: float | None = None,
    *,
    state: _SearchState | None = None,
) -> SearchResult:
    best_move: chess.Move | None = None
    best_score = -math.inf
    nodes = 0
    state = state or _SearchState.create(deadline)
    root_alpha = -math.inf
    root_beta = math.inf

    try:
        _check_deadline(deadline)
        root_entry = state.transposition_table.get(_position_key(board))
        ordered_moves = _ordered_moves(
            board,
            tt_move=root_entry.best_move if root_entry else None,
            history=state.history,
        )
        if not ordered_moves:
            logger.error("No legal moves available at depth %s; returning no move.", depth)
            return SearchResult(
                move=None,
                score=evaluate_board(board),
                nodes=0,
                depth=depth,
            )

        best_move = ordered_moves[0]
        for move in ordered_moves:
            _check_deadline(deadline)
            board.push(move)
            try:
                score, searched = _negamax(
                    board,
                    depth - 1,
                    -root_beta,
                    -root_alpha,
                    deadline,
                    ply=1,
                    state=state,
                )
            finally:
                board.pop()

            score = -score
            nodes += searched + 1

            if score > best_score:
                best_score = score
                best_move = move
            root_alpha = max(root_alpha, score)

        state.transposition_table[_position_key(board)] = _TranspositionEntry(
            depth=depth,
            score=int(best_score),
            bound="exact",
            best_move=best_move,
        )

        return SearchResult(
            move=best_move,
            score=int(best_score),
            nodes=nodes,
            depth=depth,
        )
    except _SearchDeadlineExceeded:
        fallback_move = _legal_fallback_move(board, best_move)
        logger.warning(
            "Search timed out at depth %s for FEN %s; returning fallback move %s.",
            depth,
            board.fen(),
            fallback_move,
        )
        return SearchResult(
            move=fallback_move,
            score=(
                int(best_score)
                if math.isfinite(best_score)
                else _fallback_score(board, fallback_move)
            ),
            nodes=nodes,
            depth=depth,
            timed_out=True,
        )
    except Exception:
        logger.exception(
            "Search crashed at depth %s for FEN %s; returning a legal fallback.",
            depth,
            board.fen(),
        )
        fallback_move = _legal_fallback_move(board, best_move)
        return SearchResult(
            move=fallback_move,
            score=_fallback_score(board, fallback_move),
            nodes=nodes,
            depth=depth,
            timed_out=True,
        )


def _legal_fallback_move(
    board: chess.Board,
    preferred_move: chess.Move | None = None,
) -> chess.Move | None:
    """Return a known legal move without depending on move ordering."""
    legal_moves = list(board.legal_moves)
    if preferred_move is not None and preferred_move in legal_moves:
        return preferred_move
    return legal_moves[0] if legal_moves else None


def _fallback_score(board: chess.Board, move: chess.Move | None) -> int:
    if move is None:
        return evaluate_board(board)
    return _score_move_for_side_to_move(board, move)


def _score_move_for_side_to_move(board: chess.Board, move: chess.Move) -> int:
    root_turn = board.turn
    board.push(move)
    try:
        white_score = evaluate_board(board)
    finally:
        board.pop()
    return white_score if root_turn == chess.WHITE else -white_score


def choose_move_with_skill(
    board: chess.Board,
    *,
    blunder_chance: float = 0.35,
    rng: random.Random | None = None,
) -> SearchResult:
    """Pick a move with a chance of playing something worse than best.

    Uses a single-ply static evaluation per legal move (no quiescence or deeper
    search), then may sample uniformly from the non-best moves.
    """
    if board.is_game_over():
        return SearchResult(move=None, score=evaluate_board(board), nodes=0, depth=0)

    rng = rng or random
    scored = [
        (move, _score_move_for_side_to_move(board, move))
        for move in board.legal_moves
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    chosen_move, chosen_score = scored[0]
    if len(scored) > 1 and rng.random() < blunder_chance:
        chosen_move, chosen_score = rng.choice(scored[1:])

    return SearchResult(
        move=chosen_move,
        score=chosen_score,
        nodes=len(scored),
        depth=1,
        timed_out=False,
    )


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: float,
    beta: float,
    deadline: float | None = None,
    ply: int = 0,
    state: _SearchState | None = None,
) -> tuple[int, int]:
    _check_deadline(deadline)
    if depth == 0 or board.is_game_over():
        return _quiescence(board, alpha, beta, deadline, ply)

    state = state or _SearchState.create(deadline)
    position_key = _position_key(board)
    entry = state.transposition_table.get(position_key)
    original_alpha = alpha
    original_beta = beta
    if entry is not None and entry.depth >= depth:
        if entry.bound == "exact":
            return entry.score, 1
        if entry.bound == "lower":
            alpha = max(alpha, entry.score)
        else:
            beta = min(beta, entry.score)
        if alpha >= beta:
            return entry.score, 1

    best_score = -math.inf
    best_move: chess.Move | None = None
    nodes = 0

    for move in _ordered_moves(
        board,
        tt_move=entry.best_move if entry else None,
        killer_moves=state.killer_moves.get(ply, ()),
        history=state.history,
    ):
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
                state,
            )
        finally:
            board.pop()

        score = -score
        nodes += searched

        if score > best_score:
            best_score = score
            best_move = move
        alpha = max(alpha, score)
        if alpha >= beta:
            if not board.is_capture(move):
                _record_cutoff(state, board, move, depth, ply)
            break

    score = int(best_score)
    if score <= original_alpha:
        bound: Literal["exact", "lower", "upper"] = "upper"
    elif score >= original_beta:
        bound = "lower"
    else:
        bound = "exact"
    state.transposition_table[position_key] = _TranspositionEntry(
        depth=depth,
        score=score,
        bound=bound,
        best_move=best_move,
    )
    return score, nodes


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


def _position_key(board: chess.Board) -> tuple[int, int]:
    """Hash the position and draw clock for the per-search transposition table."""
    return chess.polyglot.zobrist_hash(board), board.halfmove_clock


def _history_key(board: chess.Board, move: chess.Move) -> tuple[bool, int, int, int | None]:
    return board.turn, move.from_square, move.to_square, move.promotion


def _record_cutoff(
    state: _SearchState,
    board: chess.Board,
    move: chess.Move,
    depth: int,
    ply: int,
) -> None:
    killers = state.killer_moves.setdefault(ply, [])
    if move not in killers:
        killers.insert(0, move)
        del killers[2:]
    key = _history_key(board, move)
    state.history[key] = state.history.get(key, 0) + depth * depth


def _log_search_result(
    board: chess.Board,
    result: SearchResult,
    started: float,
    enabled: bool,
) -> None:
    if enabled:
        logger.info(
            "Search depth=%s nodes=%s elapsed_ms=%.1f move=%s score=%s timed_out=%s fen=%s",
            result.depth,
            result.nodes,
            (perf_counter() - started) * 1000,
            result.move,
            result.score,
            result.timed_out,
            board.fen(),
        )


def _ordered_moves(
    board: chess.Board,
    *,
    tt_move: chess.Move | None = None,
    killer_moves: tuple[chess.Move, ...] | list[chess.Move] = (),
    history: dict[tuple[bool, int, int, int | None], int] | None = None,
) -> list[chess.Move]:
    """Search forcing moves first so depth 3 stays responsive."""
    def move_priority(move: chess.Move) -> int:
        if move == tt_move:
            return 10_000_000

        priority = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            if victim and attacker:
                priority += 10 * PIECE_VALUES[victim.piece_type] - PIECE_VALUES[attacker.piece_type]
            else:
                priority += 1_000
            priority += 1_000_000
        elif move in killer_moves:
            priority += 500_000 - killer_moves.index(move)
        if move.promotion:
            priority += 750_000 + PIECE_VALUES.get(move.promotion, 0)
        if history is not None:
            priority += history.get(_history_key(board, move), 0)
        return priority

    return sorted(board.legal_moves, key=move_priority, reverse=True)
