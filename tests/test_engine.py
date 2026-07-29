import math
import unittest

import chess

from engine import _quiescence, evaluate_board


class EngineTests(unittest.TestCase):
    def test_evaluate_board_prefers_centralized_pawn(self) -> None:
        # Pawn on e4 (central) vs pawn on e2 (less central)
        central = chess.Board("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1")
        edge = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")

        self.assertGreater(evaluate_board(central), evaluate_board(edge))

    def test_quiescence_search_detects_immediate_captures(self) -> None:
        # Queen trade: white queen on d2, black queen on d4, both can capture
        board = chess.Board("7k/8/8/8/3q4/8/3Q4/7K w - - 0 1")

        score, nodes = _quiescence(board, -math.inf, math.inf)

        # Quiescence should find a capture that improves the score vs static eval
        self.assertGreater(score, evaluate_board(board))
        self.assertGreater(nodes, 1)


if __name__ == "__main__":
    unittest.main()
    
