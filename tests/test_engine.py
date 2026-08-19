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
import time
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

    def test_timeout_does_not_start_an_unrestricted_fallback_search(self) -> None:
        board = chess.Board()

        with patch(
            "engine._search_at_depth",
            side_effect=_SearchDeadlineExceeded,
        ) as search:
            result = choose_best_move(board, depth=3, time_limit_seconds=1)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(result.depth, 0)
        self.assertTrue(result.timed_out)
        search.assert_called_once()

    def test_arbitrary_main_search_crash_uses_safety_net(self) -> None:
        board = chess.Board()

        with patch(
            "engine._search_at_depth",
            side_effect=RuntimeError("main failed"),
        ) as search:
            result = choose_best_move(board, depth=3, time_limit_seconds=1)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(result.depth, 0)
        self.assertTrue(result.timed_out)
        search.assert_called_once()

    def test_safety_net_is_used_when_main_search_fails(self) -> None:
        board = chess.Board()
        original_fen = board.fen()

        with patch(
            "engine._search_at_depth",
            side_effect=_SearchDeadlineExceeded,
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

    def test_issue_20_position_respects_hard_time_limit(self) -> None:
        board = chess.Board(
            "r2qkb1r/ppp1pppp/2n1b3/3n4/2B5/2P2P2/PP1PN1PP/RNBQK2R b KQkq - 3 6"
        )
        started = time.perf_counter()

        result = choose_best_move(board, depth=3, time_limit_seconds=0.1)
        elapsed = time.perf_counter() - started

        self.assertIn(result.move, board.legal_moves)
        self.assertLess(elapsed, 0.25)

    def test_handoff_issue_20_position_returns_a_legal_move(self) -> None:
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2P2P2/PP1P1P1P/RNBQK2R w KQkq - 0 7"
        )
        original_fen = board.fen()

        result = choose_best_move(board, depth=3)

        self.assertIsNotNone(result.move)
        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(board.fen(), original_fen)

    def test_search_crash_returns_legal_move_and_restores_board(self) -> None:
        board = chess.Board()
        original_fen = board.fen()

        with self.assertLogs("engine", level="ERROR") as logs:
            with patch("engine._negamax", side_effect=RuntimeError("boom")):
                result = _search_at_depth(board, depth=3)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(board.fen(), original_fen)
        self.assertEqual(result.depth, 3)
        self.assertTrue(result.timed_out)
        self.assertTrue(any("Search crashed" in entry for entry in logs.output))

    def test_move_ordering_crash_still_returns_a_legal_move(self) -> None:
        board = chess.Board()

        with patch("engine._ordered_moves", side_effect=AttributeError("corrupt")):
            result = _search_at_depth(board, depth=3)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(result.nodes, 0)
        self.assertTrue(result.timed_out)

    def test_search_timeout_returns_legal_move_and_restores_board(self) -> None:
        board = chess.Board()
        original_fen = board.fen()

        with patch(
            "engine._check_deadline",
            side_effect=[None, _SearchDeadlineExceeded],
        ):
            result = _search_at_depth(board, depth=3, deadline=1.0)

        self.assertIn(result.move, board.legal_moves)
        self.assertEqual(board.fen(), original_fen)
        self.assertEqual(result.depth, 3)
        self.assertTrue(result.timed_out)

    def test_iterative_deepening_stops_when_wrapped_search_times_out(self) -> None:
        board = chess.Board()
        timed_out_result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=10,
            nodes=4,
            depth=1,
            timed_out=True,
        )

        with patch("engine._search_at_depth", return_value=timed_out_result) as search:
            result = choose_best_move(board, depth=3, time_limit_seconds=1)

        self.assertEqual(result.move, timed_out_result.move)
        self.assertEqual(result.nodes, timed_out_result.nodes)
        self.assertTrue(result.timed_out)
        search.assert_called_once()

    def test_search_without_legal_moves_returns_a_scored_empty_result(self) -> None:
        board = chess.Board("7k/5Q2/7K/8/8/8/8/8 b - - 0 1")

        result = _search_at_depth(board, depth=1)

        self.assertIsNone(result.move)
        self.assertEqual(result.score, evaluate_board(board))
        self.assertEqual(result.nodes, 0)
        self.assertEqual(result.depth, 1)


if __name__ == "__main__":
    unittest.main()
