import unittest

import chess

from engine import _positional_terms, evaluate_board


class PositionalEvaluationTests(unittest.TestCase):
    def terms(self, board, phase=1.):
        return _positional_terms(board, chess.WHITE, phase)

    def test_starting_position_balanced_and_mobility_counts_legal_moves(self):
        board = chess.Board()
        self.assertEqual(evaluate_board(board), 0)
        self.assertEqual(self.terms(board)["mobility"], 40)
        board = chess.Board("4r1k1/8/8/8/8/8/4N3/4K3 w - - 0 1")
        self.assertTrue(board.is_valid())
        self.assertEqual(self.terms(board)["mobility"], 2 * board.legal_moves.count())
        self.assertFalse(any(m.from_square == chess.E2 for m in board.legal_moves))

    def test_bishop_pair(self):
        board = chess.Board("6k1/8/8/8/8/8/8/2B1KB2 w - - 0 1")
        self.assertEqual(self.terms(board)["bishop_pair"], 30)
        board.remove_piece_at(chess.C1)
        self.assertEqual(self.terms(board)["bishop_pair"], 0)

    def test_doubled_isolated_and_passed_pawns(self):
        board = chess.Board("6k1/8/p7/8/8/P7/P7/6K1 w - - 0 1")
        self.assertEqual(self.terms(board)["pawns"], -30)  # doubled plus two isolated
        board.remove_piece_at(chess.A6)
        self.assertEqual(self.terms(board)["pawns"], 0)  # two passed-pawn bonuses
        board.set_piece_at(chess.B2, chess.Piece(chess.PAWN, chess.WHITE))
        self.assertEqual(self.terms(board)["pawns"], 35)  # no isolated pawns
        board.set_piece_at(chess.B6, chess.Piece(chess.PAWN, chess.BLACK))
        self.assertEqual(self.terms(board)["pawns"], -10)  # adjacent file blocks passers

    def test_rook_open_semi_open_and_closed_files(self):
        board = chess.Board("6k1/8/8/8/8/8/8/R5K1 w - - 0 1")
        self.assertEqual(self.terms(board)["rooks"], 20)
        board.set_piece_at(chess.A7, chess.Piece(chess.PAWN, chess.BLACK))
        self.assertEqual(self.terms(board)["rooks"], 10)
        board.set_piece_at(chess.A2, chess.Piece(chess.PAWN, chess.WHITE))
        self.assertEqual(self.terms(board)["rooks"], 0)

    def test_king_shield_exposure_and_endgame_scaling(self):
        board = chess.Board("6k1/8/8/8/8/8/5PPP/6K1 w - - 0 1")
        self.assertEqual(self.terms(board)["king_safety"], 15)
        board.remove_piece_at(chess.G2)
        self.assertEqual(self.terms(board)["king_safety"], 0)
        board.remove_piece_at(chess.F2)
        self.assertEqual(self.terms(board)["king_safety"], -15)
        self.assertEqual(self.terms(board, phase=0)["king_safety"], 0)
        self.assertLess(abs(self.terms(board, phase=.25)["king_safety"]), 15)

    def test_color_symmetry_and_board_history_including_en_passant(self):
        board = chess.Board()
        for move in ("e2e4", "a7a6", "e4e5", "d7d5"):
            board.push_uci(move)
            before = board.fen(), list(board.move_stack)
            self.assertEqual(evaluate_board(board), -evaluate_board(board.mirror()))
            self.assertEqual((board.fen(), board.move_stack), before)
        self.assertTrue(board.has_legal_en_passant())

    def test_material_still_dominates_and_terminal_scores_are_preserved(self):
        board = chess.Board()
        board.remove_piece_at(chess.D8)
        self.assertGreater(evaluate_board(board), 700)
        self.assertEqual(evaluate_board(chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")), 100000)
        self.assertEqual(evaluate_board(chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")), 0)
        self.assertEqual(evaluate_board(chess.Board("7k/8/6K1/8/8/8/8/8 w - - 0 1")), 0)


if __name__ == "__main__":
    unittest.main()
