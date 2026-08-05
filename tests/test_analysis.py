import unittest

import chess

from analysis import (
    PositionAnalysis,
    accuracy_score,
    analyse_game,
    centipawn_loss,
    classify_move,
    material_difference,
    principal_variation_to_san,
)


class ScriptedEvaluator:
    name = "Test engine"

    def __init__(self, analyses: list[PositionAnalysis]) -> None:
        self.analyses = iter(analyses)

    def analyse(self, _board: chess.Board) -> PositionAnalysis:
        return next(self.analyses)


class PostGameAnalysisTests(unittest.TestCase):
    def test_classification_thresholds_and_best_move(self) -> None:
        self.assertEqual(classify_move(500, is_best=True), "best")
        self.assertEqual(classify_move(20), "excellent")
        self.assertEqual(classify_move(50), "good")
        self.assertEqual(classify_move(100), "inaccuracy")
        self.assertEqual(classify_move(250), "mistake")
        self.assertEqual(classify_move(251), "blunder")

    def test_centipawn_loss_uses_the_movers_perspective(self) -> None:
        self.assertEqual(centipawn_loss(80, 20, chess.WHITE), 60)
        self.assertEqual(centipawn_loss(-20, 50, chess.BLACK), 70)
        self.assertEqual(centipawn_loss(20, 80, chess.WHITE), 0)

    def test_material_difference_excludes_kings(self) -> None:
        board = chess.Board("3r3k/8/8/8/8/8/8/3Q3K w - - 0 1")
        self.assertEqual(material_difference(board), 4)
        board.push_uci("d1d8")
        self.assertEqual(material_difference(board), 9)

    def test_principal_variation_is_converted_to_san(self) -> None:
        board = chess.Board()
        variation = (
            chess.Move.from_uci("e2e4"),
            chess.Move.from_uci("e7e5"),
            chess.Move.from_uci("g1f3"),
        )
        self.assertEqual(principal_variation_to_san(board, variation), ["e4", "e5", "Nf3"])

    def test_analyse_game_returns_move_reviews_and_summary(self) -> None:
        evaluator = ScriptedEvaluator(
            [
                PositionAnalysis(
                    20,
                    chess.Move.from_uci("e2e4"),
                    (
                        chess.Move.from_uci("e2e4"),
                        chess.Move.from_uci("e7e5"),
                    ),
                    depth=12,
                ),
                PositionAnalysis(10, chess.Move.from_uci("c7c5"), depth=12),
                PositionAnalysis(80, chess.Move.from_uci("g1f3"), depth=12),
            ]
        )

        result = analyse_game(["e2e4", "e7e5"], evaluator=evaluator)

        self.assertEqual(result["engine"], "Test engine")
        self.assertEqual(len(result["evaluations"]), 3)
        first, second = result["moves"]
        self.assertEqual(first["san"], "e4")
        self.assertEqual(first["classification"], "best")
        self.assertEqual(first["best_line_san"], ["e4", "e5"])
        self.assertEqual(second["classification"], "inaccuracy")
        self.assertEqual(second["centipawn_loss"], 70)
        self.assertEqual(result["summary"]["counts"]["black"]["inaccuracy"], 1)
        self.assertEqual(result["final_fen"], second["fen_after"])

    def test_analyse_game_rejects_an_illegal_sequence(self) -> None:
        evaluator = ScriptedEvaluator([PositionAnalysis(0, None)])
        with self.assertRaisesRegex(ValueError, "not legal"):
            analyse_game(["e2e5"], evaluator=evaluator)

    def test_accuracy_drops_as_average_loss_increases(self) -> None:
        self.assertEqual(accuracy_score([]), 100.0)
        self.assertGreater(accuracy_score([20, 30]), accuracy_score([100, 150]))


if __name__ == "__main__":
    unittest.main()
