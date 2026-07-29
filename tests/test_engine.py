import math
import unittest

import chess

from engine import _quiescence, evaluate_board


class EngineTests(unittest.TestCase):
    def test_evaluate_board_prefers_centralized_pawn(self) -> None:
        central = chess.Board("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1")
        edge = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")

        self.assertGreater(evaluate_board(central), evaluate_board(edge))

    def test_quiescence_search_detects_immediate_captures(self) -> None:
        board = chess.Board("7k/8/8/8/3q4/8/3Q4/7K w - - 0 1")

        score, nodes = _quiescence(board, -math.inf, math.inf)

        self.assertGreater(score, evaluate_board(board))
        self.assertGreater(nodes, 1)


if __name__ == "__main__":
    unittest.main()
