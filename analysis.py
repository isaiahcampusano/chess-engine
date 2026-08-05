"""Move-by-move post-game analysis with an optional Stockfish backend."""

from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import chess
import chess.engine

from engine import choose_best_move


MATE_SCORE = 10_000
MAX_GAME_PLIES = 160
PV_PLIES = 6
INTERNAL_PV_PLIES = 3
INTERNAL_ANALYSIS_DEPTH = 2
INTERNAL_TIME_LIMIT_SECONDS = 0.05
STOCKFISH_TIME_LIMIT_SECONDS = 0.08

MATERIAL_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}

CLASSIFICATIONS = (
    "best",
    "excellent",
    "good",
    "inaccuracy",
    "mistake",
    "blunder",
)

TRUE_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class PositionAnalysis:
    """Engine output for one position, always scored from White's perspective."""

    evaluation_cp: int
    best_move: chess.Move | None
    principal_variation: tuple[chess.Move, ...] = ()
    depth: int = 0
    mate: int | None = None


class StockfishUnavailableError(RuntimeError):
    """Raised when production requires Stockfish but it cannot be used."""


class PositionEvaluator(Protocol):
    name: str

    def analyse(self, board: chess.Board) -> PositionAnalysis:
        """Evaluate a position without mutating ``board``."""


class InternalEvaluator:
    """Fast deploy-safe fallback using the project's minimax engine."""

    name = "Built-in minimax"

    def __init__(
        self,
        depth: int = INTERNAL_ANALYSIS_DEPTH,
        time_limit_seconds: float = INTERNAL_TIME_LIMIT_SECONDS,
    ) -> None:
        self.depth = depth
        self.time_limit_seconds = time_limit_seconds

    def analyse(self, board: chess.Board) -> PositionAnalysis:
        terminal_analysis = _terminal_position_analysis(board)
        if terminal_analysis is not None:
            return terminal_analysis

        result = choose_best_move(
            board.copy(stack=True),
            depth=self.depth,
            time_limit_seconds=self.time_limit_seconds,
        )
        white_score = result.score if board.turn == chess.WHITE else -result.score
        pv = self._principal_variation(board, result.move)
        return PositionAnalysis(
            evaluation_cp=max(-MATE_SCORE, min(MATE_SCORE, white_score)),
            best_move=result.move,
            principal_variation=pv,
            depth=result.depth,
        )

    def _principal_variation(
        self,
        board: chess.Board,
        first_move: chess.Move | None,
    ) -> tuple[chess.Move, ...]:
        variation_board = board.copy(stack=True)
        variation: list[chess.Move] = []
        next_move = first_move

        for ply in range(INTERNAL_PV_PLIES):
            if next_move is None or next_move not in variation_board.legal_moves:
                break
            variation.append(next_move)
            variation_board.push(next_move)
            if variation_board.is_game_over(claim_draw=True):
                break

            result = choose_best_move(
                variation_board.copy(stack=True),
                depth=1,
                time_limit_seconds=min(0.015, self.time_limit_seconds),
            )
            next_move = result.move

        return tuple(variation)


class StockfishEvaluator:
    """UCI evaluator used when ``STOCKFISH_PATH`` or ``stockfish`` is available."""

    name = "Stockfish"

    def __init__(self, executable: str, time_limit_seconds: float) -> None:
        self.executable = executable
        self.time_limit_seconds = time_limit_seconds
        self.engine: chess.engine.SimpleEngine | None = None

    def __enter__(self) -> StockfishEvaluator:
        self.engine = chess.engine.SimpleEngine.popen_uci(self.executable)
        try:
            self.engine.configure({"Threads": 1, "Hash": 32})
        except chess.engine.EngineError:
            pass
        return self

    def __exit__(self, *_args: object) -> None:
        if self.engine is not None:
            self.engine.quit()
            self.engine = None

    def analyse(self, board: chess.Board) -> PositionAnalysis:
        if self.engine is None:
            raise RuntimeError("Stockfish evaluator has not been started.")
        terminal_analysis = _terminal_position_analysis(board)
        if terminal_analysis is not None:
            return terminal_analysis

        info = self.engine.analyse(
            board,
            chess.engine.Limit(time=self.time_limit_seconds),
        )
        score = info["score"].pov(chess.WHITE)
        evaluation_cp = score.score(mate_score=MATE_SCORE)
        pv = tuple(info.get("pv", ())[:PV_PLIES])
        return PositionAnalysis(
            evaluation_cp=int(evaluation_cp if evaluation_cp is not None else 0),
            best_move=pv[0] if pv else None,
            principal_variation=pv,
            depth=int(info.get("depth", 0)),
            mate=score.mate(),
        )


def analyse_game(
    moves: Sequence[str],
    *,
    start_fen: str = chess.STARTING_FEN,
    evaluator: PositionEvaluator | None = None,
) -> dict[str, object]:
    """Return JSON-ready review data for a legal UCI move sequence."""
    if not moves:
        raise ValueError("At least one move is required for analysis.")
    if len(moves) > MAX_GAME_PLIES:
        raise ValueError(f"Analysis is limited to {MAX_GAME_PLIES} half-moves.")

    board = _validated_board(start_fen)
    if evaluator is not None:
        return _analyse_with_evaluator(board, moves, evaluator)

    require_stockfish = stockfish_required()
    stockfish_path = find_stockfish()
    if stockfish_path:
        try:
            with StockfishEvaluator(
                stockfish_path,
                _positive_float_env(
                    "STOCKFISH_ANALYSIS_SECONDS",
                    STOCKFISH_TIME_LIMIT_SECONDS,
                ),
            ) as stockfish:
                return _analyse_with_evaluator(board, moves, stockfish)
        except (OSError, RuntimeError, chess.engine.EngineError) as error:
            if require_stockfish:
                raise StockfishUnavailableError(
                    "Stockfish is required but could not be started."
                ) from error

    if require_stockfish:
        raise StockfishUnavailableError(
            "Stockfish is required but no executable was found."
        )

    return _analyse_with_evaluator(board, moves, InternalEvaluator())


def _analyse_with_evaluator(
    board: chess.Board,
    moves: Sequence[str],
    evaluator: PositionEvaluator,
) -> dict[str, object]:
    initial_fen = board.fen()
    current_analysis = evaluator.analyse(board.copy(stack=True))
    evaluations = [_evaluation_point(0, current_analysis, material_difference(board))]
    move_reviews: list[dict[str, object]] = []
    losses: dict[chess.Color, list[int]] = {chess.WHITE: [], chess.BLACK: []}
    counts = {
        "white": {classification: 0 for classification in CLASSIFICATIONS},
        "black": {classification: 0 for classification in CLASSIFICATIONS},
    }

    for index, uci in enumerate(moves, start=1):
        move = _legal_uci_move(board, uci, index)
        mover = board.turn
        fen_before = board.fen()
        san = board.san(move)
        best_move_san = _move_to_san(board, current_analysis.best_move)
        pv_san = principal_variation_to_san(board, current_analysis.principal_variation)
        pv_uci = [pv_move.uci() for pv_move in current_analysis.principal_variation]
        is_best = move == current_analysis.best_move

        board.push(move)
        next_analysis = evaluator.analyse(board.copy(stack=True))
        loss = centipawn_loss(
            current_analysis.evaluation_cp,
            next_analysis.evaluation_cp,
            mover,
        )
        classification = classify_move(loss, is_best=is_best)
        color_name = "white" if mover == chess.WHITE else "black"
        losses[mover].append(loss)
        counts[color_name][classification] += 1
        material = material_difference(board)

        move_reviews.append(
            {
                "ply": index,
                "move_number": (index + 1) // 2,
                "color": color_name,
                "san": san,
                "uci": move.uci(),
                "classification": classification,
                "centipawn_loss": loss,
                "evaluation_cp": next_analysis.evaluation_cp,
                "evaluation_pawns": round(next_analysis.evaluation_cp / 100, 2),
                "mate": next_analysis.mate,
                "material_difference": material,
                "best_move": current_analysis.best_move.uci()
                if current_analysis.best_move
                else None,
                "best_move_san": best_move_san,
                "best_line": pv_uci,
                "best_line_san": pv_san,
                "depth": current_analysis.depth,
                "fen_before": fen_before,
                "fen_after": board.fen(),
            }
        )
        evaluations.append(_evaluation_point(index, next_analysis, material))
        current_analysis = next_analysis

    return {
        "engine": evaluator.name,
        "start_fen": initial_fen,
        "final_fen": board.fen(),
        "game_over": board.is_game_over(claim_draw=True),
        "result": board.result(claim_draw=True),
        "evaluations": evaluations,
        "moves": move_reviews,
        "summary": {
            "white_accuracy": accuracy_score(losses[chess.WHITE]),
            "black_accuracy": accuracy_score(losses[chess.BLACK]),
            "white_average_loss": average_loss(losses[chess.WHITE]),
            "black_average_loss": average_loss(losses[chess.BLACK]),
            "counts": counts,
        },
    }


def classify_move(loss_cp: int, *, is_best: bool = False) -> str:
    """Classify a move using transparent, non-proprietary CPL thresholds."""
    if is_best:
        return "best"
    if loss_cp <= 20:
        return "excellent"
    if loss_cp <= 50:
        return "good"
    if loss_cp <= 100:
        return "inaccuracy"
    if loss_cp <= 250:
        return "mistake"
    return "blunder"


def centipawn_loss(before_cp: int, after_cp: int, mover: chess.Color) -> int:
    if mover == chess.WHITE:
        return max(0, before_cp - after_cp)
    return max(0, after_cp - before_cp)


def material_difference(board: chess.Board) -> int:
    white = sum(
        len(board.pieces(piece_type, chess.WHITE)) * value
        for piece_type, value in MATERIAL_VALUES.items()
    )
    black = sum(
        len(board.pieces(piece_type, chess.BLACK)) * value
        for piece_type, value in MATERIAL_VALUES.items()
    )
    return white - black


def average_loss(losses: Sequence[int]) -> float:
    return round(sum(losses) / len(losses), 1) if losses else 0.0


def accuracy_score(losses: Sequence[int]) -> float:
    """Return a documented approximation; Chess.com's CAPS formula is proprietary."""
    return round(100 * math.exp(-0.005 * average_loss(losses)), 1)


def principal_variation_to_san(
    board: chess.Board,
    variation: Sequence[chess.Move],
) -> list[str]:
    variation_board = board.copy(stack=False)
    san_moves: list[str] = []
    for move in variation:
        if move not in variation_board.legal_moves:
            break
        san_moves.append(variation_board.san(move))
        variation_board.push(move)
    return san_moves


def find_stockfish() -> str | None:
    configured = os.getenv("STOCKFISH_PATH", "").strip()
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_file():
            return str(configured_path)
        resolved = shutil.which(configured)
        if resolved:
            return resolved
    return shutil.which("stockfish") or shutil.which("stockfish.exe")


def stockfish_required() -> bool:
    return os.getenv("REQUIRE_STOCKFISH", "").strip().lower() in TRUE_ENV_VALUES


def _terminal_position_analysis(board: chess.Board) -> PositionAnalysis | None:
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None
    if outcome.winner is None:
        return PositionAnalysis(evaluation_cp=0, best_move=None)

    evaluation_cp = MATE_SCORE if outcome.winner == chess.WHITE else -MATE_SCORE
    return PositionAnalysis(
        evaluation_cp=evaluation_cp,
        best_move=None,
        mate=0 if board.is_checkmate() else None,
    )


def _validated_board(fen: str) -> chess.Board:
    try:
        board = chess.Board(fen.strip())
    except (AttributeError, ValueError) as error:
        raise ValueError("The supplied starting FEN is invalid.") from error
    if not board.is_valid():
        raise ValueError("The supplied starting FEN is not a valid chess position.")
    return board


def _legal_uci_move(board: chess.Board, uci: str, index: int) -> chess.Move:
    if not isinstance(uci, str):
        raise ValueError(f"Move {index} must be a UCI string.")
    try:
        move = chess.Move.from_uci(uci)
    except ValueError as error:
        raise ValueError(f"Move {index} is not valid UCI notation.") from error
    if move not in board.legal_moves:
        raise ValueError(f"Move {index} ({uci}) is not legal in the supplied game.")
    return move


def _move_to_san(board: chess.Board, move: chess.Move | None) -> str | None:
    return board.san(move) if move is not None and move in board.legal_moves else None


def _evaluation_point(
    ply: int,
    analysis: PositionAnalysis,
    material: int,
) -> dict[str, int | float | None]:
    return {
        "ply": ply,
        "evaluation_cp": analysis.evaluation_cp,
        "evaluation_pawns": round(analysis.evaluation_cp / 100, 2),
        "mate": analysis.mate,
        "material_difference": material,
    }


def _positive_float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default
