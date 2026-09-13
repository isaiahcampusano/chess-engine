import math
import random
import unittest
from unittest.mock import Mock, patch

import chess

import app as web_app
import engine
from bot_config import BOT_CONFIGS
from personality import PERSONALITIES


class BotProfileTests(unittest.TestCase):
    def test_exact_profiles_and_personality_consistency(self):
        expected = {
            "rookie": (1, .15, "never", 0., 1.),
            "hustler": (2, .25, "sometimes", .5, 2.),
            "professor": (5, 0., "always", 1., 8.),
            "martin": (3, .08, "sometimes", .5, 3.),
        }
        self.assertEqual(set(BOT_CONFIGS), set(expected))
        for bot, values in expected.items():
            config = BOT_CONFIGS[bot]
            self.assertEqual(tuple(config[key] for key in
                ("depth", "blunder_chance", "book_policy", "book_chance", "time_limit_seconds")), values)
            self.assertEqual(PERSONALITIES[bot].depth, values[0])
            self.assertEqual(PERSONALITIES[bot].blunder_chance, values[1])
            for key, value in config.items():
                self.assertEqual(web_app.BOTS[bot][key], value)
        self.assertEqual(len({v[:3] for v in expected.values()}), 4)

    def test_browser_passes_profiles_and_keeps_completed_depth(self):
        for bot, config in BOT_CONFIGS.items():
            client = web_app.app.test_client()
            client.post("/select_bot", json={"bot_id": bot})
            result = engine.SearchResult(chess.Move.from_uci("e2e4"), 12, 40,
                                         max(1, config["depth"] - 1), True)
            target = "app.choose_move_with_skill"
            with patch(target, return_value=result) as select:
                response = client.post("/move", json={"fen": chess.STARTING_FEN})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["depth"], result.depth)
            select.assert_called_once()
            keys = config
            for key in keys:
                self.assertEqual(select.call_args.kwargs[key], config[key])
            self.assertIs(select.call_args.kwargs["opening_book"], web_app.OPENING_BOOK)


class SkillSearchTests(unittest.TestCase):
    def test_zero_blunders_match_search_without_random_draws(self):
        for turn in (chess.WHITE, chess.BLACK):
            board = chess.Board()
            board.turn = turn
            rng = Mock()
            rng.random.side_effect = AssertionError("zero blunders must not draw")
            expected = engine.choose_best_move(board, depth=2)
            result = engine.choose_move_with_skill(board, depth=2, blunder_chance=0, rng=rng)
            self.assertEqual(result, expected)

    def test_weighted_error_candidates_and_boundary(self):
        board = chess.Board()
        moves = list(board.legal_moves)
        scores = [(move, 100 - i) for i, move in enumerate(moves)]
        def ranked_search(*args, root_scores, **kwargs):
            root_scores[:] = scores
            return engine.SearchResult(moves[0], 100, 40, 2)
        for roll in (0., .699999, .7, .999999):
            rng = Mock()
            rng.random.side_effect = [0., roll]
            rng.choice.side_effect = lambda candidates: candidates[-1]
            with patch("engine._choose_search", side_effect=ranked_search):
                result = engine.choose_move_with_skill(board, depth=2, blunder_chance=1, rng=rng)
            candidates = scores[1:4] if roll < .7 else moves
            self.assertEqual(rng.choice.call_args.args[0], candidates)
            self.assertEqual(result.move, moves[3] if roll < .7 else moves[-1])
            self.assertEqual(result.score, dict(scores)[result.move])

    def test_book_policies_and_probability_boundaries(self):
        board = chess.Board()
        for policy, chance, roll, hit in (
            ("never", 1., 0., False), ("always", 0., .99, True),
            ("sometimes", .5, .49999, True), ("sometimes", .5, .5, False),
            ("sometimes", 0., 0., False), ("sometimes", 1., .99, True),
        ):
            book, rng = Mock(), Mock()
            book.get_move.return_value = chess.Move.from_uci("e2e4")
            rng.random.return_value = roll
            result = engine.choose_move_with_skill(board, blunder_chance=0, rng=rng,
                opening_book=book, book_policy=policy, book_chance=chance)
            self.assertEqual(result.depth == 0, hit)
            self.assertEqual(book.get_move.call_count, int(hit))
            if policy != "sometimes" or chance in (0., 1.):
                rng.random.assert_not_called()
        book.get_move.return_value = None
        self.assertEqual(engine.choose_move_with_skill(board, opening_book=book,
            book_policy="always", blunder_chance=0).depth, 1)

    def test_invalid_options_rejected_before_book(self):
        book = Mock()
        for options in ({"depth": 0}, {"time_limit_seconds": 0},
                        {"blunder_chance": -1}, {"book_chance": 1.1}, {"book_policy": "bad"}):
            with self.assertRaises(ValueError):
                engine.choose_move_with_skill(chess.Board(), opening_book=book, **options)
        book.get_move.assert_not_called()

    def test_rankings_use_full_windows_and_restore_board(self):
        board = chess.Board()
        board.push_uci("e2e4")
        before = board.fen(), list(board.move_stack)
        scores = []
        with patch("engine._negamax", wraps=engine._negamax) as search:
            result = engine._search_at_depth(board, 1, root_scores=scores)
        self.assertEqual(len(scores), board.legal_moves.count())
        self.assertEqual(scores[0], (result.move, result.score))
        for call in search.call_args_list:
            self.assertEqual(call.args[2:4], (-math.inf, math.inf))
        self.assertEqual((board.fen(), board.move_stack), before)

    def test_timeout_retains_completed_rankings_for_both_experts_and_colors(self):
        for depth in (3, 5):
            for color in (chess.WHITE, chess.BLACK):
                board = chess.Board()
                board.turn = color
                moves = list(board.legal_moves)
                deadlines = []
                def iteration(board, current, deadline, *, state, root_scores=None):
                    deadlines.append(deadline)
                    if root_scores is not None:
                        # Partial final rankings must not displace the previous iteration.
                        root_scores[:] = [(m, 100 - i) for i, m in enumerate(
                            reversed(moves) if current == depth else moves)]
                    return engine.SearchResult(moves[-1] if current == depth else moves[0],
                                               100, 10, current, current == depth)
                for rate in (0, 1):
                    rng = Mock()
                    rng.random.return_value = 0.
                    rng.choice.side_effect = lambda candidates: candidates[0]
                    with patch("engine._search_at_depth", side_effect=iteration) as search:
                        result = engine.choose_move_with_skill(board, depth=depth,
                            blunder_chance=rate, time_limit_seconds=8, rng=rng)
                    self.assertEqual(result.depth, depth - 1)
                    self.assertEqual(result.move, moves[1] if rate else moves[0])
                    self.assertTrue(result.timed_out)
                    self.assertEqual(search.call_count, depth)
                    self.assertEqual(len(set(deadlines[-depth:])), 1)

    def test_timeout_inside_ranked_search_restores_history(self):
        board = chess.Board()
        board.push_uci("e2e4")
        before = board.fen(), list(board.move_stack)
        with patch("engine._negamax", side_effect=engine._SearchDeadlineExceeded):
            result = engine.choose_move_with_skill(board, depth=3, blunder_chance=1,
                time_limit_seconds=3, rng=random.Random(1))
        self.assertEqual(result.depth, 0)
        self.assertTrue(result.timed_out)
        self.assertIn(result.move, board.legal_moves)
        self.assertEqual((board.fen(), board.move_stack), before)

    def test_terminal_single_move_and_seeded_reproducibility(self):
        terminal = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        self.assertIsNone(engine.choose_move_with_skill(terminal, blunder_chance=1).move)
        forced = chess.Board("7k/5K2/6R1/8/8/8/8/8 b - - 0 1")
        self.assertEqual(forced.legal_moves.count(), 1)
        self.assertEqual(engine.choose_move_with_skill(forced, blunder_chance=1).move,
                         next(iter(forced.legal_moves)))
        for color in (chess.WHITE, chess.BLACK):
            board = chess.Board()
            board.turn = color
            first = engine.choose_move_with_skill(board, depth=2, blunder_chance=1, rng=random.Random(7))
            second = engine.choose_move_with_skill(board, depth=2, blunder_chance=1, rng=random.Random(7))
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
