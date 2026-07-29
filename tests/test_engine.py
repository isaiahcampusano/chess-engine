import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from engine import _quiescence, evaluate_board
import math
import unittest


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


if __name__ == "__main__":
    unittest.main()