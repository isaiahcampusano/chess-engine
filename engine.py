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

from opening_book import OpeningBook


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

POSITIONAL_WEIGHTS = {
    "mobility": 2,
    "bishop_pair": 30,
    "doubled_pawn": -10,
    "isolated_pawn": -10,
    "passed_pawn": 15,
    "rook_open_file": 20,
    "rook_semi_open_file": 10,
    "pawn_shield": 5,
    "king_exposed_file": -10,
}
INITIAL_NON_PAWN_MATERIAL = 2 * (2 * 320 + 2 * 330 + 2 * 500 + 900)


def _positional_terms(board: chess.Board, color: chess.Color, phase: float) -> dict[str, int]:
    """Small features for one side; never change the caller's board or history."""
    weights = POSITIONAL_WEIGHTS
    pawns = board.pieces_mask(chess.PAWN, color)
    enemy_pawns = board.pieces_mask(chess.PAWN, not color)
    files = [(pawns & mask).bit_count() for mask in chess.BB_FILES]
    pawn_score = sum(max(0, count - 1) for count in files) * weights["doubled_pawn"]
    for square in chess.scan_forward(pawns):
        file = chess.square_file(square)
        neighbors = ((chess.BB_FILES[file - 1] if file else 0) |
                     (chess.BB_FILES[file + 1] if file < 7 else 0))
        if not pawns & neighbors:
            pawn_score += weights["isolated_pawn"]
        rank = chess.square_rank(square)
        ahead = ((chess.BB_ALL << (8 * (rank + 1))) & chess.BB_ALL
                 if color == chess.WHITE else (1 << (8 * rank)) - 1)
        if not enemy_pawns & ahead & (neighbors | chess.BB_FILES[file]):
            pawn_score += weights["passed_pawn"]

    rook_score = 0
    for square in board.pieces(chess.ROOK, color):
        mask = chess.BB_FILES[chess.square_file(square)]
        if not pawns & mask:
            rook_score += weights["rook_semi_open_file"] if enemy_pawns & mask else weights["rook_open_file"]

    king_score = 0
    king = board.king(color)
    if king is not None:
        front_rank = chess.square_rank(king) + (1 if color == chess.WHITE else -1)
        for file in range(max(0, chess.square_file(king) - 1), min(7, chess.square_file(king) + 1) + 1):
            if not files[file]:
                king_score += weights["king_exposed_file"]
            if 0 <= front_rank < 8 and pawns & chess.BB_SQUARES[chess.square(file, front_rank)]:
                king_score += weights["pawn_shield"]

    position = board.copy(stack=False)
    if position.turn != color:
        position.turn = color
        position.ep_square = None  # En passant belongs only to the actual mover.
    # A hypothetical opposite turn must never count a capture of the king.
    targets = chess.BB_ALL & ~board.pieces_mask(chess.KING, not color)
    mobility = sum(1 for _ in position.generate_legal_moves(to_mask=targets))
    return {
        "mobility": weights["mobility"] * mobility,
        "pawns": pawn_score,
        "rooks": rook_score,
        "bishop_pair": weights["bishop_pair"] if len(board.pieces(chess.BISHOP, color)) >= 2 else 0,
        "king_safety": round(king_score * phase),
    }


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

    non_pawn_material = sum(
        PIECE_VALUES[piece_type] * (board.pieces_mask(piece_type, chess.WHITE) |
                                    board.pieces_mask(piece_type, chess.BLACK)).bit_count()
        for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
    )
    phase = min(1.0, non_pawn_material / INITIAL_NON_PAWN_MATERIAL)
    score += sum(_positional_terms(board, chess.WHITE, phase).values())
    score -= sum(_positional_terms(board, chess.BLACK, phase).values())
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
    opening_book: OpeningBook | None = None,
    rng: random.Random | None = None,
) -> SearchResult:
    """Pick the best legal move, optionally keeping the search within a deadline."""
    return _choose_search(
        board, depth, time_limit_seconds=time_limit_seconds, debug=debug,
        opening_book=opening_book, rng=rng,
    )


def _choose_search(
    board: chess.Board,
    depth: int,
    *,
    time_limit_seconds: float | None = None,
    debug: bool = False,
    opening_book: OpeningBook | None = None,
    rng: random.Random | None = None,
    root_scores: list[tuple[chess.Move, int]] | None = None,
    started: float | None = None,
) -> SearchResult:
    search_started = perf_counter() if started is None else started
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if time_limit_seconds is not None and time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive")

    if board.is_game_over():
        return SearchResult(move=None, score=evaluate_board(board), nodes=0, depth=0)

    if opening_book is not None:
        book_move = opening_book.get_move(board, rng=rng)
        if book_move is not None:
            return SearchResult(book_move, _score_move_for_side_to_move(board, book_move), nodes=0)

    safety_move = next(iter(board.legal_moves))
    logger.info("Engine called on FEN: %s", board.fen())

    completed_result: SearchResult | None = None
    interrupted_result: SearchResult | None = None
    completed_nodes = 0
    timed_out = False

    if time_limit_seconds is None:
        state = _SearchState.create(deadline=None)
        try:
            options = {} if root_scores is None else {"root_scores": root_scores}
            result = _search_at_depth(board, depth, state=state, **options)
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
            iteration_scores: list[tuple[chess.Move, int]] = []
            options = {} if root_scores is None else {"root_scores": iteration_scores}
            try:
                result = _search_at_depth(
                    board,
                    current_depth,
                    deadline,
                    state=state,
                    **options,
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

            if root_scores is not None:
                root_scores[:] = iteration_scores
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
            depth=0,
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
    root_scores: list[tuple[chess.Move, int]] | None = None,
) -> SearchResult:
    best_move: chess.Move | None = None
    best_score = -math.inf
    nodes = 0
    state = state or _SearchState.create(deadline)
    root_alpha = -math.inf
    root_beta = math.inf
    scored: list[tuple[chess.Move, int]] = []

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
                    math.inf if root_scores is not None else -root_alpha,
                    deadline,
                    ply=1,
                    state=state,
                )
            finally:
                board.pop()

            score = -score
            nodes += searched + 1
            if root_scores is not None:
                scored.append((move, int(score)))

            if score > best_score:
                best_score = score
                best_move = move
            root_alpha = max(root_alpha, score)

        _check_deadline(deadline)
        if root_scores is not None:
            root_scores[:] = sorted(scored, key=lambda pair: pair[1], reverse=True)
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
    opening_book: OpeningBook | None = None,
    depth: int = 1,
    time_limit_seconds: float | None = None,
    book_policy: Literal["never", "sometimes", "always"] = "sometimes",
    book_chance: float = 0.9,
) -> SearchResult:
    """Search at the requested strength, optionally choosing a weighted error.

    Book decisions precede blunders. The legacy default book probability is
    retained for direct callers; browser bots always supply their own profile.
    A severe blunder samples every legal move, so it may happen to pick the best.
    """
    started = perf_counter()
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if time_limit_seconds is not None and time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive")
    if not 0 <= blunder_chance <= 1 or not 0 <= book_chance <= 1:
        raise ValueError("probabilities must be between 0 and 1")
    if book_policy not in ("never", "sometimes", "always"):
        raise ValueError("unknown book policy")
    if board.is_game_over():
        return SearchResult(move=None, score=evaluate_board(board), nodes=0, depth=0)

    rng = rng or random
    use_book = opening_book is not None and (
        book_policy == "always" or (
            book_policy == "sometimes" and
            (book_chance == 1 or (book_chance > 0 and rng.random() < book_chance))
        )
    )
    if use_book:
        book_move = opening_book.get_move(board, rng=rng)
        if book_move is not None:
            return SearchResult(book_move, _score_move_for_side_to_move(board, book_move), nodes=0)

    # Rank all root moves only on turns that need an error. Other turns retain
    # the faster alpha-beta best-move path, with no random draw at probability 0.
    blunder = blunder_chance > 0 and rng.random() < blunder_chance
    scored: list[tuple[chess.Move, int]] = []
    result = _choose_search(
        board, depth, time_limit_seconds=time_limit_seconds, started=started,
        root_scores=scored if blunder else None,
    )
    if not blunder or not scored:
        return result
    alternatives = [pair for pair in scored if pair[0] != result.move]
    if not alternatives:
        return result
    if rng.random() < 0.70:
        move, score = rng.choice(alternatives[:3])
    else:
        move = rng.choice(list(board.legal_moves))
        score = dict(scored)[move]
    return SearchResult(move, score, result.nodes, result.depth, result.timed_out)


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
