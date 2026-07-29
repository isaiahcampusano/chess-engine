import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from engine import _quiescence, choose_best_move, evaluate_board
import math
import unittest
from unittest.mock import patch


class EngineTests(unittest.TestCase):

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
        self.assertEqual(result.depth, 0)
        self.assertTrue(result.timed_out)


if __name__ == "__main__":
    unittest.main()
