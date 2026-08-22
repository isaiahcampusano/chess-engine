import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from engine import _score_move_for_side_to_move, choose_move_with_skill


class SkillLevelTests(unittest.TestCase):
    POSITIONS = (
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 2 3",
        "rnbqk2r/ppp1bppp/3p1n2/4p3/4P3/2NP1N2/PPP1BPPP/R1BQK2R w KQkq - 4 6",
        "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 6 8",
    )

    @staticmethod
    def top_scored_move(board: chess.Board) -> chess.Move:
        return max(
            board.legal_moves,
            key=lambda move: _score_move_for_side_to_move(board, move),
        )

    def test_forced_blunder_can_choose_a_non_best_move(self) -> None:
        rng = random.Random(7)
        sampled_moves = []

        for fen in self.POSITIONS:
            board = chess.Board(fen)
            result = choose_move_with_skill(board, blunder_chance=1.0, rng=rng)
            sampled_moves.append((result.move, self.top_scored_move(board)))

        self.assertTrue(any(move != best for move, best in sampled_moves))

    def test_zero_blunder_chance_always_chooses_the_top_scored_move(self) -> None:
        for fen in self.POSITIONS:
            board = chess.Board(fen)
            result = choose_move_with_skill(
                board,
                blunder_chance=0.0,
                rng=random.Random(7),
            )

            self.assertEqual(result.move, self.top_scored_move(board))


if __name__ == "__main__":
    unittest.main()
