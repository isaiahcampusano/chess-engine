import unittest
from unittest.mock import patch

import chess

import app as web_app
from engine import SearchResult


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()
        self.client.post("/select_bot", json={"bot_id": "professor"})

    def test_home_page_is_served(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Python Chess Engine", response.data)

    def test_home_page_includes_all_promotion_choices(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="promotionDialog"', response.data)
            for piece in (b"q", b"r", b"b", b"n"):
                with self.subTest(piece=piece):
                    self.assertIn(b'data-promotion="' + piece + b'"', response.data)

    def test_home_page_includes_accessible_board_instructions(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="boardInstructions"', response.data)
            self.assertIn(b'aria-describedby="boardInstructions"', response.data)
            self.assertIn(b"Use the arrow keys", response.data)

    def test_home_page_includes_move_planning_controls(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            for element_id in (
                b"planningArrows",
                b"planningCard",
                b"planningSequence",
                b"planMovesButton",
                b"undoPlanButton",
                b"clearPlanButton",
                b"copyPlanButton",
            ):
                with self.subTest(element_id=element_id):
                    self.assertIn(b'id="' + element_id + b'"', response.data)

            self.assertIn(b'aria-pressed="false"', response.data)

    def test_home_page_includes_post_game_analysis_ui(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            for element_id in (
                b"reviewGameButton",
                b"analysisPanel",
                b"analysisGraph",
                b"analysisMoveList",
                b"whiteAccuracy",
                b"blackAccuracy",
                b"analysisBestLine",
                b"previousAnalysisButton",
                b"nextAnalysisButton",
            ):
                with self.subTest(element_id=element_id):
                    self.assertIn(b'id="' + element_id + b'"', response.data)

    def test_home_page_includes_live_evaluation_bar(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            for element_id in (b"evalBar", b"evalBlackFill", b"evalWhiteFill", b"evalBarScore"):
                with self.subTest(element_id=element_id):
                    self.assertIn(b'id="' + element_id + b'"', response.data)

    def test_home_page_includes_explicit_opponent_selection_screen(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="opponentDialog"', response.data)
            self.assertIn(b"Choose your opponent", response.data)
            for bot_id, label in (
                (b"rookie", b"Rookie Randy"),
                (b"hustler", b"Sandbag Sam"),
                (b"professor", b"The Professor"),
                (b"martin", b"Martin"),
            ):
                with self.subTest(bot_id=bot_id):
                    self.assertIn(b'data-bot="' + bot_id + b'"', response.data)
                    self.assertIn(label, response.data)
            for element_id in (b"opponentAvatar", b"botCommentary", b"capturedPieces"):
                self.assertIn(b'id="' + element_id + b'"', response.data)
            self.assertIn(b'id="botSelectionStatus"', response.data)

    def test_home_page_includes_accessible_sound_toggle(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="soundToggle"', response.data)
            self.assertIn(b'aria-pressed="false"', response.data)
            self.assertIn(b'id="soundLabel"', response.data)

    def test_home_page_includes_theme_selector(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="themeSelect"', response.data)
            self.assertIn(b'id="themeStatus"', response.data)
            for theme in (b"dark", b"light", b"sepia", b"ocean", b"forest"):
                with self.subTest(theme=theme):
                    self.assertIn(b'value="' + theme + b'"', response.data)

    def test_bot_selection_is_required_for_a_new_session(self) -> None:
        self.client.post("/new_game")
        response = self.client.get("/select_bot")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "status": "selection_required",
                "selected": None,
                "depth": None,
                "label": None,
                "active_game_bot": None,
                "game_active": False,
                "needs_selection": True,
                "commentary": None,
                "avatar": None,
                "idle_lines": [],
            },
        )

    def test_bot_selection_is_stored_in_session(self) -> None:
        self.client.post("/new_game")
        response = self.client.post("/select_bot", json={"bot_id": "rookie"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["selected"], "rookie")
        self.assertEqual(self.client.get("/select_bot").get_json()["selected"], "rookie")

    def test_all_four_personalities_keep_the_expected_skill_settings(self) -> None:
        expected = {
            "rookie": (1, 0.15),
            "hustler": (2, 0.25),
            "professor": (5, 0.0),
            "martin": (3, 0.08),
        }
        self.assertEqual(set(web_app.BOTS), set(expected))
        for bot_id, (depth, blunder_chance) in expected.items():
            with self.subTest(bot_id=bot_id):
                self.assertEqual(web_app.BOTS[bot_id]["depth"], depth)
                self.assertEqual(web_app.BOTS[bot_id]["blunder_chance"], blunder_chance)

    def test_selection_returns_character_content(self) -> None:
        self.client.post("/new_game")
        response = self.client.post("/select_bot", json={"bot_id": "martin"})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["avatar"], "martin.png")
        self.assertEqual(payload["tier"], "expert")
        self.assertIn(payload["commentary"], web_app.PERSONALITIES["martin"].lines["game_start"])
        self.assertEqual(payload["idle_lines"], web_app.PERSONALITIES["martin"].lines["idle"])

    def test_legacy_bot_ids_are_rejected(self) -> None:
        for bot_id in ("novice", "expert"):
            with self.subTest(bot_id=bot_id):
                self.client.post("/new_game")
                response = self.client.post("/select_bot", json={"bot_id": bot_id})
                self.assertEqual(response.status_code, 400)

    def test_stale_legacy_session_requires_a_new_selection(self) -> None:
        with self.client.session_transaction() as game_session:
            game_session["bot"] = "expert"
            game_session["active_game_bot"] = "expert"
            game_session["opponent_selected"] = True
            game_session["commentary_eval"] = 42

        response = self.client.get("/select_bot")

        self.assertTrue(response.get_json()["needs_selection"])
        with self.client.session_transaction() as game_session:
            self.assertNotIn("active_game_bot", game_session)
            self.assertNotIn("commentary_eval", game_session)

    def test_bot_selection_rejects_invalid_bot(self) -> None:
        response = self.client.post("/select_bot", json={"bot_id": "grandmaster"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid bot ID", response.get_json()["error"])

    def test_new_game_clears_opponent_and_reopens_selection(self) -> None:
        response = self.client.post("/new_game")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["bot"])
        self.assertTrue(response.get_json()["needs_selection"])
        self.assertFalse(response.get_json()["game_active"])
        with self.client.session_transaction() as game_session:
            self.assertNotIn("active_game_bot", game_session)
            self.assertNotIn("opponent_selected", game_session)
            self.assertNotIn("commentary_eval", game_session)
            self.assertNotIn("commentary_tick", game_session)
            self.assertNotIn("last_commentary", game_session)
            self.assertFalse(game_session["game_started"])

    def test_static_assets_are_served(self) -> None:
        for path in ("/static/styles.css", "/static/app.js", "/static/sound.js"):
            with self.subTest(path=path):
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)

        for bot_id in web_app.PERSONALITIES:
            with self.subTest(bot_id=bot_id):
                response = self.client.get(f"/static/avatars/{bot_id}.png")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content_type, "image/png")

    def test_sound_assets_are_served(self) -> None:
        sound_names = (
            "move",
            "capture",
            "check",
            "castle",
            "promote",
            "illegal",
            "game-start",
            "game-win",
            "game-lose",
            "game-draw",
        )
        for sound_name in sound_names:
            with self.subTest(sound_name=sound_name):
                response = self.client.get(f"/static/sounds/{sound_name}.ogg")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content_type, "audio/ogg")

    def test_move_endpoint_returns_engine_result(self) -> None:
        board = chess.Board()
        board.push_uci("e2e4")
        result = SearchResult(
            move=chess.Move.from_uci("e7e5"),
            score=24,
            nodes=1_234,
            depth=3,
        )

        with patch("app.choose_move_with_skill", return_value=result) as search:
            response = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            payload,
            {
                "engine_move": "e7e5",
                "score": 24,
                "nodes": 1_234,
                "depth": 3,
                "timed_out": False,
                "game_over": False,
                "is_capture": False,
                "is_check": False,
                "is_castle": False,
                "is_promotion": False,
                "outcome": None,
                "commentary": None,
                "avatar": "professor.png",
            },
        )
        searched_board = search.call_args.args[0]
        self.assertEqual(searched_board.fen(), board.fen())
        self.assertEqual(search.call_args.kwargs["depth"], 5)
        self.assertEqual(search.call_args.kwargs["time_limit_seconds"], 8.0)

    def test_player_blunder_commentary_uses_static_evaluations(self) -> None:
        board = chess.Board()
        board.push_uci("e2e4")
        result = SearchResult(move=chess.Move.from_uci("e7e5"), score=0, nodes=1, depth=3)
        with self.client.session_transaction() as game_session:
            game_session["commentary_eval"] = 100

        with (
            patch("app.evaluate_board", side_effect=[-100, -100]),
            patch("app.choose_move_with_skill", return_value=result),
            patch("app._pick_commentary", return_value="That loses material.") as speak,
        ):
            response = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(response.get_json()["commentary"], "That loses material.")
        speak.assert_called_once_with("professor", "player_blunder")

    def test_rookie_notices_a_static_evaluation_blunder(self) -> None:
        self.client.post("/new_game")
        self.client.post("/select_bot", json={"bot_id": "rookie"})
        board = chess.Board()
        board.push_uci("e2e4")
        result = SearchResult(move=chess.Move.from_uci("e7e5"), score=0, nodes=1, depth=1)

        with (
            patch("app.evaluate_board", side_effect=[0, 200]),
            patch("app.choose_move_with_skill", return_value=result),
            patch("app._pick_commentary", return_value="I meant to do that.") as speak,
        ):
            response = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(response.get_json()["commentary"], "I meant to do that.")
        speak.assert_called_once_with("rookie", "bot_blunder_aware")

    def test_position_commentary_only_fires_every_second_bot_reply(self) -> None:
        board = chess.Board()
        board.push_uci("e2e4")
        result = SearchResult(move=chess.Move.from_uci("e7e5"), score=200, nodes=1, depth=3)

        with (
            patch("app.evaluate_board", return_value=0),
            patch("app.choose_move_with_skill", return_value=result),
            patch("app._pick_commentary", return_value="The position speaks for itself.") as speak,
        ):
            first = self.client.post("/move", json={"fen": board.fen()})
            second = self.client.post("/move", json={"fen": board.fen()})

        self.assertIsNone(first.get_json()["commentary"])
        self.assertEqual(second.get_json()["commentary"], "The position speaks for itself.")
        speak.assert_called_once_with("professor", "bot_winning")

    def test_checkmate_commentary_has_highest_priority(self) -> None:
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        result = SearchResult(
            move=chess.Move.from_uci("f7g7"),
            score=100_000,
            nodes=1,
            depth=3,
        )
        with self.client.session_transaction() as game_session:
            game_session["commentary_eval"] = 1_000

        with (
            patch("app.choose_move_with_skill", return_value=result),
            patch("app._pick_commentary", return_value="Class dismissed.") as speak,
        ):
            response = self.client.post("/move", json={"fen": board.fen()})

        self.assertTrue(response.get_json()["game_over"])
        speak.assert_called_once_with("professor", "checkmate_win")

    def test_move_endpoint_uses_selected_bot_skill(self) -> None:
        board = chess.Board()
        result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=12,
            nodes=20,
            depth=1,
        )
        self.client.post("/new_game")
        self.client.post("/select_bot", json={"bot_id": "rookie"})

        with patch("app.choose_move_with_skill", return_value=result) as search:
            response = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_args.kwargs["blunder_chance"], 0.15)

    def test_selected_opponent_is_locked_for_the_entire_game(self) -> None:
        board = chess.Board()
        novice_result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=12,
            nodes=20,
            depth=1,
        )
        self.client.post("/new_game")
        self.client.post("/select_bot", json={"bot_id": "rookie"})

        with patch("app.choose_move_with_skill", return_value=novice_result) as search:
            first_move = self.client.post("/move", json={"fen": board.fen()})
            selection = self.client.post("/select_bot", json={"bot_id": "professor"})
            second_move = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(first_move.status_code, 200)
        self.assertEqual(second_move.status_code, 200)
        self.assertEqual(selection.status_code, 409)
        self.assertIn("locked", selection.get_json()["error"])
        self.assertEqual(
            [call.kwargs["blunder_chance"] for call in search.call_args_list],
            [0.15, 0.15],
        )

    def test_new_game_requires_a_fresh_conscious_choice(self) -> None:
        board = chess.Board()
        result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=12,
            nodes=20,
            depth=3,
        )
        self.client.post("/new_game")
        blocked_move = self.client.post("/move", json={"fen": board.fen()})
        selection = self.client.post("/select_bot", json={"bot_id": "professor"})
        with patch("app.choose_move_with_skill", return_value=result) as search:
            move_response = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(blocked_move.status_code, 409)
        self.assertEqual(selection.status_code, 200)
        self.assertEqual(move_response.status_code, 200)
        self.assertEqual(search.call_args.kwargs["depth"], 5)

    def test_end_game_releases_the_locked_opponent(self) -> None:
        response = self.client.post(
            "/end_game",
            json={"fen": "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["needs_selection"])
        self.assertTrue(self.client.get("/select_bot").get_json()["needs_selection"])

    def test_end_game_returns_player_delivered_checkmate_commentary(self) -> None:
        with patch("app._pick_commentary", return_value="Well played. Genuinely.") as speak:
            response = self.client.post(
                "/end_game",
                json={"fen": "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"},
            )

        self.assertEqual(response.get_json()["avatar"], "professor.png")
        self.assertEqual(response.get_json()["commentary"], "Well played. Genuinely.")
        speak.assert_called_once_with("professor", "checkmate_loss")

    def test_end_game_cannot_release_an_unfinished_match(self) -> None:
        response = self.client.post("/end_game", json={"fen": chess.STARTING_FEN})

        self.assertEqual(response.status_code, 409)
        self.assertIn("stays locked", response.get_json()["error"])
        self.assertFalse(self.client.get("/select_bot").get_json()["needs_selection"])

    def test_move_endpoint_rejects_missing_json(self) -> None:
        response = self.client.post("/move")

        self.assertEqual(response.status_code, 400)
        self.assertIn("JSON object", response.get_json()["error"])

    def test_move_endpoint_rejects_missing_fen(self) -> None:
        response = self.client.post("/move", json={})

        self.assertEqual(response.status_code, 400)
        self.assertIn("'fen'", response.get_json()["error"])

    def test_move_endpoint_rejects_invalid_fen(self) -> None:
        response = self.client.post("/move", json={"fen": "not-a-fen"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid", response.get_json()["error"].lower())

    def test_move_endpoint_rejects_invalid_position(self) -> None:
        response = self.client.post(
            "/move",
            json={"fen": "8/8/8/8/8/8/8/8 w - - 0 1"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid chess position", response.get_json()["error"])

    def test_game_over_position_returns_no_move(self) -> None:
        checkmate_fen = "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"

        response = self.client.post("/move", json={"fen": checkmate_fen})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn(payload["commentary"], web_app.PERSONALITIES["professor"].lines["checkmate_loss"])
        self.assertEqual(payload["avatar"], "professor.png")
        payload.pop("commentary")
        payload.pop("avatar")
        self.assertEqual(
            payload,
            {
                "engine_move": None,
                "score": 0,
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "game_over": True,
                "is_capture": False,
                "is_check": False,
                "is_castle": False,
                "is_promotion": False,
                "outcome": {
                    "winner": "white",
                    "termination": "checkmate",
                },
            },
        )

    def test_stalemate_position_returns_draw_outcome(self) -> None:
        stalemate_fen = "7k/5Q2/7K/8/8/8/8/8 b - - 0 1"

        response = self.client.post("/move", json={"fen": stalemate_fen})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["game_over"])
        self.assertEqual(
            response.get_json()["outcome"],
            {"winner": None, "termination": "stalemate"},
        )

    def test_move_endpoint_reports_move_metadata(self) -> None:
        cases = (
            (
                "is_capture",
                "7k/8/8/8/3q4/8/3Q4/7K b - - 0 1",
                "d4d2",
            ),
            (
                "is_check",
                "7k/8/8/8/8/8/8/R6K w - - 0 1",
                "a1a8",
            ),
            (
                "is_castle",
                "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
                "e1g1",
            ),
            (
                "is_promotion",
                "8/P6k/8/8/8/8/7p/7K w - - 0 1",
                "a7a8n",
            ),
        )

        for flag, fen, move_uci in cases:
            with self.subTest(flag=flag):
                board = chess.Board(fen)
                result = SearchResult(
                    move=chess.Move.from_uci(move_uci),
                    score=900,
                    nodes=1,
                    depth=3,
                )

                with patch("app.choose_move_with_skill", return_value=result):
                    response = self.client.post("/move", json={"fen": board.fen()})

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.get_json()[flag])

    def test_engine_checkmate_move_includes_outcome(self) -> None:
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        result = SearchResult(
            move=chess.Move.from_uci("f7g7"),
            score=100_000,
            nodes=1,
            depth=3,
        )

        with patch("app.choose_move_with_skill", return_value=result):
            response = self.client.post("/move", json={"fen": board.fen()})

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["is_check"])
        self.assertTrue(payload["game_over"])
        self.assertEqual(
            payload["outcome"],
            {"winner": "white", "termination": "checkmate"},
        )

    def test_engine_failure_uses_emergency_legal_move(self) -> None:
        board = chess.Board()
        with patch(
            "app.choose_move_with_skill",
            side_effect=RuntimeError("boom"),
        ) as search:
            response = self.client.post("/move", json={"fen": chess.STARTING_FEN})

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn(chess.Move.from_uci(payload["engine_move"]), board.legal_moves)
        self.assertEqual(payload["depth"], 0)
        self.assertTrue(payload["timed_out"])
        self.assertEqual([call.kwargs["depth"] for call in search.call_args_list], [5])
        self.assertTrue(
            all(
                call.kwargs["time_limit_seconds"] == web_app.BOTS["professor"]["time_limit_seconds"]
                for call in search.call_args_list
            )
        )

    def test_illegal_engine_move_uses_emergency_legal_move(self) -> None:
        result = SearchResult(
            move=chess.Move.from_uci("a1a8"),
            score=0,
            nodes=1,
        )
        with patch("app.choose_move_with_skill", return_value=result) as search:
            response = self.client.post("/move", json={"fen": chess.STARTING_FEN})

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            chess.Move.from_uci(payload["engine_move"]),
            chess.Board().legal_moves,
        )
        self.assertEqual(payload["depth"], 0)
        self.assertTrue(payload["timed_out"])
        self.assertEqual([call.kwargs["depth"] for call in search.call_args_list], [5])

    def test_move_endpoint_does_not_restart_search_after_none_result(self) -> None:
        with patch("app.choose_move_with_skill", return_value=None) as search:
            response = self.client.post("/move", json={"fen": chess.STARTING_FEN})
        self.assertEqual(response.status_code, 200)
        self.assertIn(chess.Move.from_uci(response.get_json()["engine_move"]), chess.Board().legal_moves)
        self.assertEqual(response.get_json()["depth"], 0)
        search.assert_called_once()

    def test_rookie_failure_skips_duplicate_depth_one_retry(self) -> None:
        self.client.post("/new_game")
        self.client.post("/select_bot", json={"bot_id": "rookie"})

        with patch(
            "app.choose_move_with_skill",
            side_effect=RuntimeError("boom"),
        ) as search:
            response = self.client.post("/move", json={"fen": chess.STARTING_FEN})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["depth"], 0)
        search.assert_called_once()
        self.assertEqual(search.call_args.kwargs["blunder_chance"], 0.15)

    def test_timed_out_search_returns_best_available_move(self) -> None:
        result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=12,
            nodes=80,
            depth=1,
            timed_out=True,
        )
        with patch("app.choose_move_with_skill", return_value=result):
            response = self.client.post("/move", json={"fen": chess.STARTING_FEN})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["engine_move"], "e2e4")
        self.assertEqual(response.get_json()["depth"], 1)
        self.assertTrue(response.get_json()["timed_out"])

    def test_analysis_endpoint_returns_review_data(self) -> None:
        analysis_result = {
            "engine": "Test engine",
            "moves": [{"san": "e4", "classification": "best"}],
            "evaluations": [{"ply": 0, "evaluation_cp": 0}],
            "summary": {"white_accuracy": 100.0, "black_accuracy": 100.0},
        }
        with patch("app.analyse_game", return_value=analysis_result) as analyze:
            response = self.client.post(
                "/analysis",
                json={"moves": ["e2e4"], "start_fen": chess.STARTING_FEN},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), analysis_result)
        analyze.assert_called_once_with(["e2e4"], start_fen=chess.STARTING_FEN)

    def test_analysis_endpoint_rejects_missing_moves(self) -> None:
        response = self.client.post("/analysis", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("'moves'", response.get_json()["error"])

    def test_analysis_endpoint_rejects_invalid_game(self) -> None:
        with patch("app.analyse_game", side_effect=ValueError("Move 1 is not legal.")):
            response = self.client.post("/analysis", json={"moves": ["e2e5"]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("not legal", response.get_json()["error"])

    def test_evaluation_endpoint_returns_engine_evaluation(self) -> None:
        result = {"eval": 35, "mate": None, "winner": None}
        with patch("app.get_evaluation", return_value=result) as evaluate:
            response = self.client.post("/api/eval", json={"fen": chess.STARTING_FEN})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), result)
        evaluated_board = evaluate.call_args.args[0]
        self.assertEqual(evaluated_board.fen(), chess.STARTING_FEN)
        self.assertEqual(evaluate.call_args.kwargs["depth"], 3)

    def test_evaluation_endpoint_rejects_invalid_fen(self) -> None:
        response = self.client.post("/api/eval", json={"fen": "not-a-fen"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid", response.get_json()["error"].lower())


if __name__ == "__main__":
    unittest.main()
