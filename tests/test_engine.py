import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from engine import (
    SearchResult,
    _SearchDeadlineExceeded,
    _quiescence,
    _search_at_depth,
    choose_best_move,
    evaluate_board,
    get_evaluation,
)
import math
import unittest
from unittest.mock import patch


class EngineTests(unittest.TestCase):
    def test_get_evaluation_is_even_at_start(self):
        self.assertEqual(
            get_evaluation(chess.Board(), depth=1),
            {"eval": 0, "mate": None, "winner": None},
        )

    def test_get_evaluation_reports_immediate_white_mate(self):
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        result = get_evaluation(board, depth=1)
        self.assertEqual(result["mate"], 1)
        self.assertEqual(result["winner"], "white")
        self.assertIsNone(result["eval"])

    def test_get_evaluation_reports_immediate_black_mate(self):
        board = chess.Board("7K/5q2/6k1/8/8/8/8/8 b - - 0 1")
        result = get_evaluation(board, depth=1)
        self.assertEqual(result["mate"], -1)
        self.assertEqual(result["winner"], "black")
        self.assertIsNone(result["eval"])


    def test_evaluate_board_prefers_centralized_pawn(self):
        # Pawn on e4 (central) vs pawn on a2 (edge)
        central = chess.Board("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1")
        edge = chess.Board("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")

        self.assertGreater(evaluate_board(central), evaluate_board(edge))
    def test_quiescence_search_detects_immediate_captures(self) -> None:
        # Queen trade: white queen on d2, black queen on d4
        board = chess.Board("7k/8/8/8/3q4/8/3Q4/7K w - - 0 1")

        score, nodes = _quiescence(board, -math.inf, math.inf)

        self.assertGreater(score, evaluate_board(board))
        self.assertGreater(nodes, 1)

    def test_time_limited_search_completes_shallow_depths(self) -> None:
        board = chess.Board()

        result = choose_best_move(board, depth=2, time_limit_seconds=2)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(result.depth, 2)
        self.assertFalse(result.timed_out)

    def test_deadline_returns_legal_fallback_and_restores_board(self) -> None:
        board = chess.Board()
        original_fen = board.fen()

        with patch("engine.perf_counter", side_effect=[0.0, 0.0, 0.0, 2.0]):
            result = choose_best_move(board, depth=3, time_limit_seconds=1)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(board.fen(), original_fen)
        self.assertEqual(result.depth, 1)
        self.assertTrue(result.timed_out)

    def test_depth_one_search_is_primary_emergency_fallback(self) -> None:
        board = chess.Board()
        fallback = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=25,
            nodes=20,
            depth=1,
        )

        with patch(
            "engine._search_at_depth",
            side_effect=[_SearchDeadlineExceeded, fallback],
        ) as search:
            result = choose_best_move(board, depth=3, time_limit_seconds=1)

        self.assertEqual(result.move, fallback.move)
        self.assertEqual(result.score, fallback.score)
        self.assertEqual(result.nodes, fallback.nodes)
        self.assertEqual(result.depth, 1)
        self.assertTrue(result.timed_out)
        self.assertEqual(search.call_count, 2)
        self.assertIsNotNone(search.call_args_list[0].args[2])
        self.assertEqual(len(search.call_args_list[1].args), 2)

    def test_ordered_move_is_only_used_when_depth_one_fallback_fails(self) -> None:
        board = chess.Board()
        original_fen = board.fen()

        with patch(
            "engine._search_at_depth",
            side_effect=[_SearchDeadlineExceeded, RuntimeError("fallback failed")],
        ):
            result = choose_best_move(board, depth=3, time_limit_seconds=1)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(board.fen(), original_fen)
        self.assertEqual(result.depth, 0)
        self.assertEqual(result.nodes, 0)
        self.assertTrue(result.timed_out)

    def test_issue_20_position_returns_a_legal_move_after_immediate_timeout(self) -> None:
        board = chess.Board(
            "r2qkb1r/ppp1pppp/2n1b3/3n4/2B5/2P2P2/PP1PN1PP/RNBQK2R b KQkq - 3 6"
        )
        original_fen = board.fen()

        def expire_only_timed_search(deadline: float | None) -> None:
            if deadline is not None:
                raise _SearchDeadlineExceeded

        with patch("engine._check_deadline", side_effect=expire_only_timed_search):
            result = choose_best_move(board, depth=3, time_limit_seconds=1)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(board.fen(), original_fen)
        self.assertEqual(result.depth, 1)
        self.assertTrue(result.timed_out)

    def test_search_without_legal_moves_returns_a_scored_empty_result(self) -> None:
        board = chess.Board("7k/5Q2/7K/8/8/8/8/8 b - - 0 1")

        result = _search_at_depth(board, depth=1)

        self.assertIsNone(result.move)
        self.assertEqual(result.score, evaluate_board(board))
        self.assertEqual(result.nodes, 0)
        self.assertEqual(result.depth, 1)


if __name__ == "__main__":
    unittest.main()
