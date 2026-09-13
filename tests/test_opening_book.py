import io
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch

import chess

import opening_book as books
from opening_book import OpeningBook, position_key
from build_opening_book import aggregate, eligible, finalize, main as build_main, open_pgn
from engine import SearchResult, _score_move_for_side_to_move, choose_best_move, choose_move_with_skill


class BookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "book.json"
        self.board = chess.Board()

    def book(self, entries=None):
        if entries is None:
            entries = [{"move": "e2e4", "weight": 3}, {"move": "d2d4", "weight": 1}]
        self.path.write_text(json.dumps({position_key(self.board): entries}), encoding="utf-8")
        return OpeningBook(self.path)

    def test_weighted_randomness_is_repeatable_and_diverse(self):
        book = self.book()
        def sample():
            rng = random.Random(12)
            return [book.get_move(self.board, rng).uci() for _ in range(1000)]
        first = sample()
        self.assertEqual(first, sample())
        self.assertEqual(set(first), {"e2e4", "d2d4"})
        self.assertGreater(first.count("e2e4"), 650)
        self.assertLess(first.count("e2e4"), 850)

    def test_invalid_entries_are_ignored(self):
        with self.assertLogs("opening_book", level="WARNING"):
            book = self.book([None, {}, {"move": "e2e5", "weight": 10},
                              {"move": "bad", "weight": 3}, {"move": "e2e4", "weight": -1},
                              {"move": "e2e4", "weight": True}, {"move": "e2e4", "weight": 1.5},
                              {"move": "d2d4", "weight": 2}])
        self.assertEqual(book.get_move(self.board).uci(), "d2d4")

    def test_missing_malformed_and_invalid_positions_fail_soft(self):
        for text in (None, "{", "[]", '{"bad": []}', "{}"):
            if text is not None:
                self.path.write_text(text, encoding="utf-8")
            with self.assertLogs("opening_book", level="WARNING"):
                book = OpeningBook(self.path)
            self.assertIsNone(book.get_move(self.board))

    def test_counter_independence_and_castling(self):
        book = self.book()
        self.board.fullmove_number = 40
        self.board.halfmove_clock = 20
        self.assertIsNotNone(book.get_move(self.board))
        self.board.castling_rights = 0
        self.assertIsNone(book.get_move(self.board))

    def test_legal_en_passant_normalization(self):
        self.board.push_uci("e2e4")
        raw = chess.Board(self.board.fen(en_passant="fen"))
        self.assertEqual(position_key(raw).split()[-1], "-")
        for uci in ("a7a6", "e4e5", "d7d5"):
            self.board.push_uci(uci)
        self.assertEqual(position_key(self.board).split()[-1], "d6")
        book = self.book([{"move": "e5d6", "weight": 3}])
        self.assertEqual(book.get_move(self.board).uci(), "e5d6")
        self.board.ep_square = None
        self.assertIsNone(book.get_move(self.board))

    def test_shared_loader_is_thread_safe(self):
        with patch.object(books, "_default_book", None), patch.object(books, "OpeningBook") as loader:
            with ThreadPoolExecutor(max_workers=8) as pool:
                instances = list(pool.map(lambda _: books.get_default_opening_book(), range(16)))
            loader.assert_called_once_with()
            self.assertTrue(all(value is instances[0] for value in instances))

    def test_book_result_and_board_history_for_both_sides(self):
        for black in (False, True):
            if black:
                self.board.push_uci("e2e4")
            uci = "e7e5" if black else "e2e4"
            book = self.book([{"move": uci, "weight": 3}])
            before = (self.board.fen(), list(self.board.move_stack))
            for selector in (choose_best_move, choose_move_with_skill):
                rng = Mock()
                rng.choices.return_value = [chess.Move.from_uci(uci)]
                rng.random.return_value = 0.5
                with patch("engine._search_at_depth", side_effect=AssertionError("book must skip search")):
                    result = selector(self.board, opening_book=book, rng=rng)
                self.assertEqual(result, SearchResult(chess.Move.from_uci(uci), _score_move_for_side_to_move(self.board, chess.Move.from_uci(uci)), 0))
                self.assertEqual((self.board.fen(), self.board.move_stack), before)

    def test_novice_deviation_and_book_miss(self):
        book = self.book()
        rng = Mock()
        rng.choices.return_value = [chess.Move.from_uci("e2e4")]
        rng.random.side_effect = [0.95, 0.9]
        result = choose_move_with_skill(self.board, opening_book=book, rng=rng)
        self.assertEqual(result.depth, 1)
        self.assertGreaterEqual(result.nodes, 20)
        self.board.push_uci("a2a3")
        result = choose_best_move(self.board, depth=1, opening_book=book)
        self.assertEqual(result.depth, 1)
        self.assertIn(result.move, self.board.legal_moves)

    def test_terminal_and_invalid_search_parameters_precede_book(self):
        book = Mock()
        terminal = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        for selector in (choose_best_move, choose_move_with_skill):
            self.assertIsNone(selector(terminal, opening_book=book).move)
        with self.assertRaises(ValueError):
            choose_best_move(self.board, depth=0, opening_book=book)
        book.get_move.assert_not_called()

    def test_deadline_keeps_deepest_completed_iteration(self):
        completed = SearchResult(chess.Move.from_uci("e2e4"), 50, 25, 2)
        interrupted = SearchResult(chess.Move.from_uci("a2a3"), 10, 30, 3, True)
        with patch("engine._search_at_depth", side_effect=[SearchResult(chess.Move.from_uci("d2d4"), 20, 10, 1), completed, interrupted]):
            result = choose_best_move(self.board, depth=4, time_limit_seconds=8)
        self.assertEqual(result.move, completed.move)
        self.assertEqual(result.depth, 2)
        self.assertTrue(result.timed_out)


class BuilderTests(unittest.TestCase):
    PGN = '[Event "Test"]\n[WhiteElo "2100"]\n[BlackElo "2200"]\n[TimeControl "180+2"]\n\n1. e4 e5 2. Nf3 Nc6 *\n\n'

    def test_aggregation_filtering_and_deterministic_pruning(self):
        counts = defaultdict(Counter)
        text = self.PGN * 3 + self.PGN.replace('"2100"', '"1900"') + self.PGN.replace('180+2', '60+0')
        stats = aggregate(io.StringIO(text), counts, max_plies=2)
        self.assertEqual(stats, {"seen": 5, "accepted": 3, "filtered": 2, "malformed": 0})
        book = finalize(counts)
        self.assertEqual(len(book), 2)
        self.assertEqual(book[position_key(chess.Board())], [{"move": "e2e4", "weight": 3}])
        self.assertEqual(finalize(counts, min_count=4), {})
        self.assertEqual(finalize({"x": Counter(a=3, b=4, c=4)}, top_moves=1), {"x": [{"move": "b", "weight": 4}]})

    def test_malformed_game_does_not_contribute_partial_prefix(self):
        counts = defaultdict(Counter)
        stats = aggregate(io.StringIO(self.PGN.replace('2. Nf3 Nc6', '2. e5') + self.PGN), counts)
        self.assertEqual(stats["malformed"], 1)
        self.assertEqual(stats["accepted"], 1)
        self.assertEqual(counts[position_key(chess.Board())]["e2e4"], 1)

    def test_variants_custom_starts_and_missing_ratings_are_filtered(self):
        headers = chess.pgn.Headers(WhiteElo="2100", BlackElo="2100", TimeControl="180+0")
        self.assertTrue(eligible(headers, 2000, 180))
        for key, value in (("Variant", "Chess960"), ("SetUp", "1"), ("WhiteElo", "?"), ("TimeControl", "-"), ("FEN", "bad")):
            changed = headers.copy()
            changed[key] = value
            self.assertFalse(eligible(changed, 2000, 180))

    def test_plain_and_compressed_input_match(self):
        try:
            import zstandard
        except ImportError:
            self.skipTest("optional builder dependency not installed")
        with tempfile.TemporaryDirectory() as folder:
            for suffix in (".pgn", ".pgn.zst"):
                path = Path(folder) / ("games" + suffix)
                raw = self.PGN.encode()
                path.write_bytes(zstandard.ZstdCompressor().compress(raw) if suffix.endswith("zst") else raw)
                with open_pgn(path) as stream:
                    self.assertEqual(stream.read(), self.PGN)

    def test_builder_writes_reproducible_files_and_checksums(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output, metadata = (root / name for name in ("games.pgn", "book.json", "sources.json"))
            source.write_text(self.PGN * 3, encoding="utf-8")
            argv = ["build_opening_book.py", str(source), "--output", str(output), "--metadata", str(metadata)]
            with patch("sys.argv", argv), patch("sys.stdout", new_callable=io.StringIO):
                build_main()
                first = output.read_bytes(), metadata.read_bytes()
                build_main()
                self.assertEqual(first, (output.read_bytes(), metadata.read_bytes()))
            self.assertNotIn(b"\r", first[0])
            report = json.loads(first[1])
            self.assertEqual(report["book_sha256"], hashlib.sha256(first[0]).hexdigest())
            self.assertEqual(report["sources"][0]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_builder_does_not_replace_output_when_no_games_qualify(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "games.pgn", root / "book.json"
            source.write_text(self.PGN, encoding="utf-8")
            output.write_text("existing", encoding="utf-8")
            with patch("sys.argv", ["build_opening_book.py", str(source), "--output", str(output)]), \
                 patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build_main()
            self.assertEqual(output.read_text(), "existing")


class GameplayBookTests(unittest.TestCase):
    def test_browser_bots_follow_their_shared_book_policies(self):
        import app as web_app
        for bot_id in web_app.BOTS:
            with self.subTest(bot_id=bot_id):
                client = web_app.app.test_client()
                page = client.get("/").data.decode()
                self.assertRegex(page, rf'data-bot="{bot_id}"\s+data-depth="{web_app.BOTS[bot_id]["depth"]}"')
                client.post("/select_bot", json={"bot_id": bot_id})
                with patch("engine.random.random", return_value=0.4):
                    response = client.post("/move", json={"fen": chess.STARTING_FEN})
                data = response.get_json()
                self.assertEqual(response.status_code, 200)
                if bot_id == "rookie":
                    self.assertGreater(data["nodes"], 0)
                    self.assertEqual(data["depth"], 1)
                else:
                    self.assertEqual(data["nodes"], 0)
                    self.assertEqual(data["depth"], 0)
                self.assertFalse(data["timed_out"])
                self.assertIn(chess.Move.from_uci(data["engine_move"]), chess.Board().legal_moves)
        self.assertIs(web_app.OPENING_BOOK, books.get_default_opening_book())

    def test_terminal_game_passes_shared_book_and_keeps_requested_depth(self):
        import game
        with patch("game.choose_best_move", wraps=choose_best_move) as select, \
             patch("game._prompt_for_move", side_effect=SystemExit), \
             patch("game._clear_screen"), patch("game._print_status"), patch("game._print_board"):
            with self.assertRaises(SystemExit):
                game.play(depth=2, human_color=chess.BLACK)
        self.assertIs(select.call_args.kwargs["opening_book"], books.get_default_opening_book())
        self.assertEqual(select.call_args.kwargs["depth"], 2)

    def test_analysis_and_live_evaluation_do_not_consult_book(self):
        from analysis import InternalEvaluator
        from engine import get_evaluation
        with patch.object(OpeningBook, "get_move", side_effect=AssertionError("analysis must search")):
            self.assertIsNotNone(InternalEvaluator(depth=1).analyse(chess.Board()).best_move)
            self.assertEqual(get_evaluation(chess.Board(), depth=1)["eval"], 0)

    def test_bundled_data_is_legal_and_covers_common_openings(self):
        data = json.loads(books.DEFAULT_BOOK_PATH.read_text(encoding="utf-8"))
        self.assertGreater(len(data), 100)
        self.assertGreater(len(data[position_key(chess.Board())]), 1)
        for key, entries in data.items():
            board = chess.Board(key + " 0 1")
            self.assertTrue(board.is_valid(), key)
            self.assertEqual(position_key(board), key)
            self.assertLessEqual(len(entries), 5)
            self.assertEqual(len({e["move"] for e in entries}), len(entries))
            for entry in entries:
                self.assertIn(chess.Move.from_uci(entry["move"]), board.legal_moves, key)
                self.assertIs(type(entry["weight"]), int)
                self.assertGreaterEqual(entry["weight"], 3)
        lines = (
            "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7",
            "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O",
            "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6",
        )
        for line in lines:
            board = chess.Board()
            for san in line.split():
                move = board.parse_san(san)
                self.assertIn(move.uci(), [entry["move"] for entry in data.get(position_key(board), [])], (line, san))
                board.push(move)


if __name__ == "__main__":
    unittest.main()
